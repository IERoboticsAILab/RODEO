"""
Chain access for the oracle: tasks, verdicts, and the facts proofs are checked
against (when a task was assigned and submitted, and which service it went to).
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from pathlib import Path

from web3 import Web3


@dataclass
class Task:
    # TaskManager.getTask: 0 id, 1 description, 2 category, 3 taskType, 4 categoryHash,
    # 5 taskTypeHash, 6 creator, 7 reward, 8 status, 9 executor, 10 active,
    # 11 proofURI, 12 oracle, 13 verified
    id: int
    description: str
    category: str
    task_type: str
    creator: str
    reward: int
    status: int
    executor: str
    active: bool
    proof_uri: str
    oracle: str
    verified: bool

    @staticmethod
    def from_tuple(t) -> "Task":
        return Task(int(t[0]), t[1], t[2], t[3], t[6], int(t[7]), int(t[8]), t[9],
                    bool(t[10]), t[11] or "", t[12], bool(t[13]))


def _get_logs(event, from_block: int, to_block: int, argument_filters=None) -> list:
    """event.get_logs over a block range, for web3 6 (fromBlock) and 7 (from_block)."""
    try:
        return event.get_logs(fromBlock=from_block, toBlock=to_block, argument_filters=argument_filters)
    except TypeError:
        return event.get_logs(from_block=from_block, to_block=to_block, argument_filters=argument_filters)


class ChainClient:
    def __init__(self, web3: Web3, settings):
        self.web3 = web3
        self.settings = settings
        c = settings.contracts
        self.tm = self._contract(c["TaskManager"], settings.task_manager_name)
        self.org = self._contract(c["Organization"], "Organization")
        self.sm = self._contract(c["ServiceManager"], "ServiceManager")
        self.oracle_addr = web3.to_checksum_address(settings.oracle_addr)
        self.oracle_key = settings.oracle_key
        self.contract = self.tm                   # used by the event watcher
        # one transaction at a time: the event watcher and the expiry sweeper share the key
        self._tx_lock = threading.RLock()
        self._last_nonce = None

    def _contract(self, address, name):
        path: Path = self.settings.abi_path(name)
        with path.open() as f:
            abi = json.load(f)["abi"]
        return self.web3.eth.contract(address=self.web3.to_checksum_address(address), abi=abi)

    # ------------------------------------------------------------------ transactions
    def send_tx(self, fn):
        with self._tx_lock:              # verdicts and the expiry sweeper share the nonce
            return self._send_tx_locked(fn)

    def _send_tx_locked(self, fn):
        # pending count, never below the last nonce used: the RPC node may lag
        s = self.settings
        nonce = self.web3.eth.get_transaction_count(self.oracle_addr, "pending")
        if self._last_nonce is not None:
            nonce = max(nonce, self._last_nonce + 1)
        gas_price = s.gas_price_override or max(self.web3.eth.gas_price, s.min_gas_price)
        try:
            gas_est = fn.estimate_gas({"from": self.oracle_addr})
        except Exception as e:  # noqa: BLE001
            print(f"Gas estimation failed: {e}; using 500000")
            gas_est = 500000
        tx = fn.build_transaction({"from": self.oracle_addr, "nonce": nonce,
                                   "gas": int(gas_est * s.gas_multiplier), "gasPrice": gas_price})
        signed = self.web3.eth.account.sign_transaction(tx, private_key=self.oracle_key)
        txh = self.web3.eth.send_raw_transaction(signed.raw_transaction)
        self._last_nonce = nonce
        return self.web3.eth.wait_for_transaction_receipt(txh)

    def approve(self, task_id: int):
        self.send_tx(self.tm.functions.oracleFulfill(task_id, True, ""))
        print(f"Approved task {task_id}")

    def reject(self, task_id: int, reason: str):
        reason = (reason or "")[:128]
        self.send_tx(self.tm.functions.oracleFulfill(task_id, False, reason))
        print(f"Rejected task {task_id} with reason, {reason}")

    def expire_overdue(self) -> list:
        """Send TaskManager.expireTask for every assigned task past its execution time
        limit without a proof (the contract unassigns, refunds and frees the service).
        Returns the ids expired. Raises AttributeError on contracts without timeouts."""
        expired = []
        for t in self.tm.functions.getAllTasks().call():
            task = Task.from_tuple(t)
            if task.status != 1 or not task.active:
                continue
            if not self.tm.functions.isExpired(task.id).call():
                continue
            deadline = int(self.tm.functions.deadlineOf(task.id).call())
            self.send_tx(self.tm.functions.expireTask(task.id))
            expired.append((task.id, deadline))
        return expired

    # ------------------------------------------------------------------ reads
    def ensure_is_current_oracle(self):
        try:
            cur = self.web3.to_checksum_address(self.tm.functions.oracle().call())
        except Exception:  # noqa: BLE001
            cur = None
        if cur != self.oracle_addr:
            print(f"Warning, TaskManager oracle is {cur}, but this node uses {self.oracle_addr}")

    def get_total_tasks(self) -> int:
        return int(self.tm.functions.getTotalTasks().call())

    def get_task(self, task_id: int) -> Task:
        return Task.from_tuple(self.tm.functions.getTask(task_id).call())

    def is_inbox_for_this_oracle(self, t: Task) -> bool:
        has_proof = bool(t.proof_uri) and t.proof_uri.lower() != "none"
        return (t.active and t.status == 1 and has_proof and not t.verified
                and self.web3.to_checksum_address(t.oracle) == self.oracle_addr)

    def list_inbox(self):
        print("\nOracle inbox")
        found = False
        for tid in range(1, self.get_total_tasks() + 1):
            t = self.get_task(tid)
            if self.is_inbox_for_this_oracle(t):
                found = True
                print(f"  Task {t.id}, Desc {t.description[:60]}, Cat {t.category}, Type {t.task_type}, "
                      f"Reward {self.web3.from_wei(t.reward, 'ether')} IEC, Executor {t.executor}, "
                      f"ProofURI {t.proof_uri}")
        if not found:
            print("  None")

    def _last_event_time(self, event, task_id: int, before_block=None):
        """
        Block time and number of the task's last ``event`` at or before
        ``before_block``. Searches backwards from there in chunks of LOG_CHUNK
        blocks, down to START_BLOCK: on a public chain (OP Sepolia) the RPC refuses
        one query over the whole chain, and the event is usually recent.
        """
        start = int(getattr(self.settings, "start_block", 0))
        chunk = max(1, int(getattr(self.settings, "log_chunk", 10000)))
        hi = self.web3.eth.block_number if before_block is None else int(before_block)
        while hi >= start:
            lo = max(start, hi - chunk + 1)
            logs = _get_logs(event, lo, hi, {"taskId": task_id})
            if logs:
                last = max(logs, key=lambda lg: (lg["blockNumber"], lg["logIndex"]))
                return int(self.web3.eth.get_block(last["blockNumber"])["timestamp"]), last["blockNumber"]
            hi = lo - 1
        return None, None

    def task_window(self, task_id: int):
        """(assigned_ts, submitted_ts) in Unix seconds, from block times; None if unknown."""
        submitted, sub_block = self._last_event_time(self.tm.events.TaskProofSubmitted, task_id)
        assigned, _ = self._last_event_time(self.tm.events.TaskAssigned, task_id, sub_block)
        return assigned, submitted

    def service_description_for_task(self, task_id: int):
        """The on-chain description of the service the task is assigned to, or None."""
        sid = int(self.org.functions.taskToService(task_id).call())
        if sid == 0:
            return None
        return self.sm.functions.getService(sid).call()[2]

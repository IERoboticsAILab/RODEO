"""
Execution time limits kept by org-web, for a TaskManager that has none on chain
(e.g. the IE Coin contracts on OP Sepolia, which predate categoryTimeout).

Every task gets its own deadline: the block time of its last TaskAssigned event
plus the limit of its category (ORG_TASK_TIMEOUTS, default Logistics=900). When
the chain's latest block time is past it and no proof was submitted, the task is
unassigned with Organization.unassignTask (the organization's key): the creator
is refunded, the robot's service freed, the task deactivated, and the robot's
agent cancels the run on TaskUnassigned. Activate posts it again; a new
assignment starts a new clock.

Only chain time is used, so no host clock matters. A TaskManager that has
on-chain limits (categoryTimeout) enforces them itself, with the oracle's expiry
sweeper; then this timer does not run.

Limitation: the contract can't refuse a late proof. A proof submitted after the
deadline but before the next check (ORG_TIMER_EVERY_S) is accepted.
"""

import json
import os
import threading
from typing import Callable, Dict, List, Optional, Tuple


def parse_limits(text: str) -> Dict[str, int]:
    """'Logistics=900, Cleaning=600' -> {'Logistics': 900, 'Cleaning': 600}; 0 or empty = none."""
    out = {}
    for part in (text or "").split(","):
        if not part.strip():
            continue
        cat, _, sec = part.partition("=")
        sec = int(float(sec.strip())) if sec.strip() else 0
        if cat.strip() and sec > 0:
            out[cat.strip()] = sec
    return out


def has_proof(task: dict) -> bool:
    """The contract keeps proofURI "none" until a proof is submitted."""
    uri = (task.get("proofURI") or "").strip()
    return bool(uri) and uri.lower() != "none"


class Web3Chain:
    """What the timer reads from the chain (a fake one in the tests)."""

    def __init__(self, web3, get_task_manager, list_tasks):
        self.web3 = web3
        self._tm = get_task_manager
        self._list = list_tasks

    def ident(self) -> str:
        return f"{self.web3.eth.chain_id}:{self._tm().address}"

    def latest(self) -> Tuple[int, int]:
        b = self.web3.eth.get_block("latest")
        return int(b["number"]), int(b["timestamp"])

    def block_time(self, number: int) -> int:
        return int(self.web3.eth.get_block(number)["timestamp"])

    def assigned_logs(self, from_block: int, to_block: int) -> List[Tuple[int, int, int]]:
        """[(blockNumber, logIndex, taskId)] of TaskAssigned in the range."""
        logs = self._tm().events.TaskAssigned.get_logs(from_block=from_block, to_block=to_block)
        return [(int(lg["blockNumber"]), int(lg["logIndex"]), int(lg["args"]["taskId"])) for lg in logs]

    def tasks(self) -> list:
        return self._list()


class TaskTimer:
    def __init__(self, chain, limits: Dict[str, int], unassign: Callable[[int], object],
                 start_block: int = 0, chunk: int = 2000, state_path: Optional[str] = None,
                 log: Callable[[str], None] = print):
        self.chain = chain
        self.limits = dict(limits)
        self.unassign = unassign
        self.start_block = max(0, int(start_block))
        self.chunk = max(1, int(chunk))
        self.state_path = state_path
        self.log = log
        self._lock = threading.Lock()
        self.assigned: Dict[int, int] = {}       # taskId -> block time of its last assignment
        self.next_block = self.start_block
        self._ident = None
        self._load()

    # ---------------------------------------------------------------- state
    def _load(self) -> None:
        if not self.state_path or not os.path.exists(self.state_path):
            return
        try:
            with open(self.state_path) as f:
                s = json.load(f)
            ident = self.chain.ident()
            if s.get("chain") != ident or int(s.get("start_block", -1)) != self.start_block:
                self.log("task timer: saved state is for another chain or start block, rescanning")
                return
            self.assigned = {int(k): int(v) for k, v in s.get("assigned", {}).items()}
            self.next_block = max(self.start_block, int(s.get("next_block", self.start_block)))
            self._ident = ident
        except Exception as e:                    # a broken file only costs a rescan
            self.log(f"task timer: ignoring saved state ({e})")

    def _save(self) -> None:
        if not self.state_path:
            return
        try:
            if self._ident is None:
                self._ident = self.chain.ident()
            os.makedirs(os.path.dirname(self.state_path) or ".", exist_ok=True)
            tmp = self.state_path + ".tmp"
            with open(tmp, "w") as f:
                json.dump({"chain": self._ident, "start_block": self.start_block,
                           "next_block": self.next_block,
                           "assigned": {str(k): v for k, v in self.assigned.items()}}, f)
            os.replace(tmp, self.state_path)
        except Exception as e:
            self.log(f"task timer: could not save state ({e})")

    # ---------------------------------------------------------------- reading the chain
    def scan(self, latest_block: int) -> None:
        """Record the block time of every TaskAssigned up to latest_block."""
        changed = False
        while self.next_block <= latest_block:
            to = min(latest_block, self.next_block + self.chunk - 1)
            logs = sorted(self.chain.assigned_logs(self.next_block, to))
            times: Dict[int, int] = {}
            with self._lock:
                for block, _, tid in logs:
                    if block not in times:
                        times[block] = self.chain.block_time(block)
                    self.assigned[tid] = times[block]     # the last assignment wins
                self.next_block = to + 1
            changed = True
        if changed:
            self._save()

    def deadline(self, task: dict) -> Optional[int]:
        limit = self.limits.get(task.get("taskCategory"))
        if not limit or task.get("status") != 1:
            return None
        with self._lock:
            at = self.assigned.get(int(task["id"]))
        return None if at is None else at + limit

    # ---------------------------------------------------------------- acting
    def tick(self) -> List[int]:
        """Unassign every overdue task without a proof; returns their ids."""
        latest_block, now = self.chain.latest()
        self.scan(latest_block)
        done = []
        for t in self.chain.tasks():
            d = self.deadline(t)
            if d is None or not t.get("active") or has_proof(t) or now <= d:
                continue
            limit = self.limits[t["taskCategory"]]
            try:
                self.unassign(int(t["id"]))
                self.log(f"task {t['id']}: {t['taskCategory']} time limit ({limit} s) passed "
                         f"{now - d} s ago without a proof, unassigned (creator refunded)")
                done.append(int(t["id"]))
            except Exception as e:            # proof landed meanwhile, or already unassigned
                self.log(f"task {t['id']}: overdue, but unassigning failed: {e}")
        return done

    def annotate(self, tasks: list) -> list:
        """The page's fields (as org_code._with_timeouts gives for on-chain limits)."""
        if not tasks:
            return tasks
        try:
            now = self.chain.latest()[1]
        except Exception:
            now = None
        for t in tasks:
            limit = self.limits.get(t.get("taskCategory"))
            if not limit:
                continue
            t["timeoutS"] = limit
            d = self.deadline(t)
            if d is not None:
                t["deadline"] = d
                if now is not None:
                    t["secondsLeft"] = d - now
                t["proofInTime"] = has_proof(t)
        return tasks

    def run(self, every_s: float, stop: Optional[threading.Event] = None) -> None:
        stop = stop or threading.Event()
        self.log(f"task timer: limits {self.limits}, checking every {every_s:g} s "
                 f"(events from block {self.next_block})")
        while not stop.is_set():
            try:
                self.tick()
            except Exception as e:
                self.log(f"task timer: check failed: {e}")
            stop.wait(every_s)


def start_from_env(web3, get_task_manager, list_tasks, unassign, timeouts_on_chain: bool,
                   log: Callable[[str], None] = print) -> Optional[TaskTimer]:
    """Starts the timer thread unless the contract has its own limits or none are set."""
    if timeouts_on_chain:
        log("task timer: off (the TaskManager enforces time limits on chain)")
        return None
    limits = parse_limits(os.environ.get("ORG_TASK_TIMEOUTS", "Logistics=900"))
    if not limits:
        log("task timer: off (ORG_TASK_TIMEOUTS is empty)")
        return None
    timer = TaskTimer(Web3Chain(web3, get_task_manager, list_tasks), limits, unassign,
                      start_block=int(os.environ.get("ORG_START_BLOCK", "0") or 0),
                      chunk=int(os.environ.get("ORG_LOG_CHUNK", "2000")),
                      state_path=os.environ.get("ORG_TIMER_STATE", "/app/state/task_timer.json"),
                      log=log)
    every = float(os.environ.get("ORG_TIMER_EVERY_S", "10"))
    threading.Thread(target=timer.run, args=(every,), daemon=True, name="task-timer").start()
    return timer

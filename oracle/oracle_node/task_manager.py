from pathlib import Path
from web3 import Web3
import json

class TaskManagerClient:
    def __init__(self, web3: Web3, settings, tm_address_hex: str):
        self.web3 = web3
        self.settings = settings
        self.tm_address = web3.to_checksum_address(tm_address_hex)
        self.contract = self._load_contract(self.tm_address, settings.task_manager_name)
        self.oracle_addr = web3.to_checksum_address(settings.oracle_addr)
        self.oracle_key = settings.oracle_key

    def _load_contract(self, address, name):
        path: Path = self.settings.abi_path(name)
        with path.open() as f:
            abi = json.load(f)["abi"]
        return self.web3.eth.contract(address=address, abi=abi)

    def send_tx(self, fn):
        nonce = self.web3.eth.get_transaction_count(self.oracle_addr)
        
        # Determine gas price with override support
        if self.settings.gas_price_override:
            gas_price = self.settings.gas_price_override
        else:
            gas_price = self.web3.eth.gas_price
            # Apply minimum gas price
            if gas_price < self.settings.min_gas_price:
                gas_price = self.settings.min_gas_price
        
        # Estimate gas with error handling
        try:
            gas_est = fn.estimate_gas({"from": self.oracle_addr})
        except Exception as e:
            print(f"Gas estimation failed: {e}")
            print("Using default gas limit of 500000")
            gas_est = 500000
        
        # Apply gas multiplier for safety buffer
        gas_limit = int(gas_est * self.settings.gas_multiplier)
        
        tx = fn.build_transaction({
            "from": self.oracle_addr,
            "nonce": nonce,
            "gas": gas_limit,
            "gasPrice": gas_price
        })
        signed = self.web3.eth.account.sign_transaction(tx, private_key=self.oracle_key)
        h = self.web3.eth.send_raw_transaction(signed.raw_transaction)
        rcpt = self.web3.eth.wait_for_transaction_receipt(h)
        return rcpt

    def contract_oracle_addr(self):
        try:
            return self.web3.to_checksum_address(self.contract.functions.oracle().call())
        except Exception:
            return None

    def ensure_is_current_oracle(self):
        cur = self.contract_oracle_addr()
        if cur != self.oracle_addr:
            print(f"Warning, TaskManager oracle is {cur}, but this node uses {self.oracle_addr}")

    def get_total_tasks(self) -> int:
        return int(self.contract.functions.getTotalTasks().call())

    def get_task(self, task_id):
        return self.contract.functions.getTask(task_id).call()

    def approve(self, task_id: int):
        self.send_tx(self.contract.functions.oracleFulfill(task_id, True, ""))
        print(f"Approved task {task_id}")

    def reject(self, task_id: int, reason: str):
        reason = reason or ""
        if len(reason) > 128:
            reason = reason[:128]
        self.send_tx(self.contract.functions.oracleFulfill(task_id, False, reason))
        print(f"Rejected task {task_id} with reason, {reason}")

    def is_inbox_for_this_oracle(self, task_tuple) -> bool:
        # 0 id, 1 description, 2 taskCategory, 3 taskType,
        # 4 categoryHash, 5 taskTypeHash, 6 creator, 7 reward,
        # 8 status, 9 executor, 10 active, 11 proofURI, 12 oracle, 13 verified
        active = bool(task_tuple[10])
        assigned = int(task_tuple[8]) == 1
        proof_uri = task_tuple[11]
        has_proof = isinstance(proof_uri, str) and len(proof_uri) > 0 and proof_uri.lower() != "none"
        not_verified = not bool(task_tuple[13])
        oracle_match = self.web3.to_checksum_address(task_tuple[12]) == self.oracle_addr
        return active and assigned and has_proof and not_verified and oracle_match

    def list_inbox(self):
        total = self.get_total_tasks()
        print("\nOracle inbox")
        any_found = False
        for tid in range(1, total + 1):
            t = self.get_task(tid)
            if self.is_inbox_for_this_oracle(t):
                any_found = True
                print(
                    f"  Task {t[0]}, Desc {t[1]}, Cat {t[2]}, Type {t[3]}, "
                    f"Reward {self.web3.from_wei(t[7], 'ether')} IEC, "
                    f"Executor {t[9]}, ProofURI {t[11]}"
                )
        if not any_found:
            print("  None")

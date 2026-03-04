import os
import time
from web3 import Web3
from .utils import sanitize_bag_path, reason_from_output
from .validator.run_subprocess import run_rosbag_validator
from .power_csv import compute_energy_and_coins

class OracleController:
    def __init__(self, web3: Web3, settings, tm_client):
        self.web3 = web3
        self.settings = settings
        self.tm = tm_client

    def handle_request(self, tid: int):
        t = self.tm.get_task(tid)
        if not self.tm.is_inbox_for_this_oracle(t):
            return

        proof_uri = t[11] or ""
        path = sanitize_bag_path(proof_uri)
        lower = path.lower()

        if lower.endswith(".bag"):
            if not os.path.exists(path):
                self.tm.reject(tid, "ProofURI path not found on oracle")
                return

            print(f"\nStarting validation for task {tid}, bag {path}")
            code, out_text = run_rosbag_validator(path)
            print("\n----- validator output begin -----")
            print(out_text)
            print("----- validator output end -----\n")

            if code == 0:
                self.tm.approve(tid)
            elif code in (2, 3, 99):
                reason = reason_from_output(out_text)
                self.tm.reject(tid, reason)
            else:
                self.tm.reject(tid, f"Validator exited with code {code}")

        elif lower.endswith(".csv"):
            print(f"\nCSV proof received for task {tid}, validatining proof")
            local_path = sanitize_bag_path(proof_uri)
            if not os.path.exists(local_path):
                self.tm.reject(tid, f"CSV not found at {local_path}")
                return
            try:
                time.sleep(10)
                res = compute_energy_and_coins(
                        local_path,
                        self.settings.iec_per_kwh,
                        self.settings.iec_decimals
                    )
            except Exception as e:
                self.tm.reject(tid, f"CSV parse failed, {e}")
                return

            # Log summary for the operator
            print(f"\nTask {tid} CSV summary")
            print(f"\nTask 69 summary")
            print(f"Rows, {res.rows}")
            print(f"Energy Wh, {res.energy_Wh:.6f}")
            print(f"Energy kWh, {res.energy_kWh:.9f}")
            print(f"IEC to award, {res.coins_IEC_float:.9f} IEC, {res.coins_IEC} wei")
 


            # Approve task after successful analysis
            self.tm.approve(tid)
        else:
            self.tm.reject(tid, "Unsupported proof type, expected .bag or .csv")

    def on_verified(self, tid: int):
        print(f"\nTask {tid} verified")

    def on_rejected(self, tid: int, reason: str):
        print(f"\nTask {tid} rejected, reason, {reason}")

    def run_menu(self):
        self.tm.ensure_is_current_oracle()
        while True:
            choice = input("\n[li] list inbox, [ok] approve, [no] reject, [va] validate, [q] quit: ").lower().strip()
            if choice == "li":
                self.tm.list_inbox()
            elif choice == "ok":
                try:
                    tid = int(input("Task id, one based: ").strip())
                except ValueError:
                    print("Bad task id")
                    continue
                self.tm.approve(tid)
            elif choice == "no":
                try:
                    tid = int(input("Task id, one based: ").strip())
                except ValueError:
                    print("Bad task id")
                    continue
                reason = input("Reason, max 128 chars: ").strip()
                self.tm.reject(tid, reason)
            elif choice == "va":
                try:
                    tid = int(input("Task id to validate, one based: ").strip())
                except ValueError:
                    print("Bad task id")
                    continue
                self.handle_request(tid)
            elif choice == "q":
                print("Exiting oracle node")
                break
            else:
                print("Invalid option")
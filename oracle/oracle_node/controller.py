"""
Routes each proof to its checks.

    RODEO proof (ROS 2 bag with a manifest)
        -> shared checks (manifest, parameters, time window, hash, reuse)
        -> the validator registered for the task's category/task type
    legacy ROS 1 .bag   -> waste-sorting validator (original demo)
    legacy .csv         -> energy validator (original charging log)
"""
from __future__ import annotations

import os
import traceback
from dataclasses import dataclass

from rodeo_common.proof import parse_proof_uri, sha256_path

from .checks import UsedProofs, check_rodeo_proof
from .proofs import KIND_CSV, KIND_RODEO, KIND_ROS1_BAG, detect_kind, path_size, read_rodeo_proof
from .validators import Verdict, registered, validator_for
from .validators.energy_csv import validate_csv
from .validators.waste_ros1 import validate_bag


@dataclass
class Context:
    """What a validator gets."""
    task: object
    proof: object
    service_desc: str
    settings: object


class OracleController:
    def __init__(self, web3, settings, chain):
        self.web3 = web3
        self.settings = settings
        self.tm = chain
        self.used = UsedProofs(os.path.join(settings.state_dir, "used_proofs.json"))
        print(f"Validators: {', '.join(registered())}")
        if settings.legacy_proofs:
            print("Legacy proofs (ROS 1 .bag, .csv) are ACCEPTED. They carry no manifest, so a "
                  "legacy proof passes for any task; set LEGACY_PROOFS=0 to refuse them.")
        else:
            print("Legacy proofs (ROS 1 .bag, .csv) are refused (LEGACY_PROOFS=0)")

    # ------------------------------------------------------------------ one request
    def handle_request(self, tid: int):
        t = self.tm.get_task(tid)
        if not self.tm.is_inbox_for_this_oracle(t):
            return
        print(f"\nStarting validation for task {tid} ({t.category}/{t.task_type}), proof {t.proof_uri}")
        try:
            verdict = self._validate(t)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            verdict = Verdict(ok=False, reason=f"Validator error, {e}")
        print("Validation summary")
        print("\n".join(verdict.lines))
        print("APPROVED" if verdict.ok else f"REJECTED: {verdict.reason}")
        print("\n----- validator output end -----\n")
        if verdict.ok:
            self.tm.approve(tid)
        else:
            self.tm.reject(tid, verdict.reason)

    def _validate(self, t) -> Verdict:
        try:
            path, sha = parse_proof_uri(t.proof_uri)
        except ValueError as e:
            return Verdict(ok=False, reason=f"Unsupported proof URI, {e}"[:128])
        if not os.path.exists(path):
            return Verdict(ok=False, reason="ProofURI path not found on oracle")
        sha_ok = sha is None or sha == sha256_path(path)
        kind = detect_kind(path)
        print(f"  proof kind {kind}, {path_size(path)} bytes, hash {'given' if sha else 'not given'}")

        if kind == KIND_RODEO:
            if not sha:
                return Verdict(ok=False, reason="RODEO proof without #sha256 in the URI")
            reused = self.tm_reused(sha, t.id)
            proof = read_rodeo_proof(path)
            service_desc = self.tm.service_description_for_task(t.id)
            verdict = check_rodeo_proof(t, proof, self.tm.task_window(t.id), service_desc,
                                        sha_ok, reused, self.settings.clock_tolerance_s)
            if verdict.ok:
                fn = validator_for(t.category, t.task_type)
                if fn is None:
                    verdict.check(False, f"no validator for {t.category}/{t.task_type}",
                                  f"No validator for {t.category}/{t.task_type}")
                else:
                    sub = fn(Context(t, proof, service_desc, self.settings))
                    verdict.lines += sub.lines
                    if not sub.ok:
                        verdict.ok, verdict.reason = False, sub.reason
            self.used.record(sha, t.id)
            return verdict

        if kind in (KIND_ROS1_BAG, KIND_CSV) and not self.settings.legacy_proofs:
            return Verdict(ok=False, reason="Legacy proof refused, task needs a RODEO proof")
        legacy = Verdict(ok=True)
        legacy.check(sha_ok, "proof hash matches the URI" if sha else "no hash given (legacy)",
                     "proof changed after submission (hash mismatch)")
        if not legacy.ok:
            return legacy
        if kind == KIND_ROS1_BAG:
            sub = validate_bag(path)
        elif kind == KIND_CSV:
            sub = validate_csv(path, self.settings.iec_per_kwh, self.settings.iec_decimals)
        else:
            return Verdict(ok=False, reason="Unsupported proof type, expected a RODEO bag, .bag or .csv")
        sub.lines = legacy.lines + sub.lines
        return sub

    def tm_reused(self, sha: str, tid: int):
        prev = self.used.task_for(sha)
        return prev if prev is not None and prev != tid else None

    # ------------------------------------------------------------------ outcomes
    def on_verified(self, tid: int):
        print(f"\nTask {tid} verified")

    def on_rejected(self, tid: int, reason: str):
        print(f"\nTask {tid} rejected, reason, {reason}")

    # ------------------------------------------------------------------ console
    def run_menu(self):
        self.tm.ensure_is_current_oracle()
        if not self.settings.interactive:
            print("Running unattended (ORACLE_INTERACTIVE=0)")
            import threading
            threading.Event().wait()
        while True:
            try:
                choice = input("\n[li] list inbox, [ok] approve, [no] reject, [va] validate, [q] quit: ").lower().strip()
            except EOFError:                      # no terminal attached: keep serving
                print("No console attached; running unattended")
                import threading
                threading.Event().wait()
            if choice == "li":
                self.tm.list_inbox()
            elif choice in ("ok", "no", "va"):
                try:
                    tid = int(input("Task id, one based: ").strip())
                except ValueError:
                    print("Bad task id")
                    continue
                if choice == "ok":
                    self.tm.approve(tid)
                elif choice == "no":
                    self.tm.reject(tid, input("Reason, max 128 chars: ").strip())
                else:
                    self.handle_request(tid)
            elif choice == "q":
                print("Exiting oracle node")
                break
            else:
                print("Invalid option")

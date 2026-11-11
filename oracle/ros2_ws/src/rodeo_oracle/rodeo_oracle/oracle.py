#!/usr/bin/env python3
"""
oracle - the RODEO oracle as a ROS 2 node.

    chain     watches TaskOracleRequested / TaskVerified / TaskRejected and sends
              oracleFulfill, with the oracle wallet from the environment
              (same variables as the pure-Python oracle)
    shared    hash, reuse, manifest, parameters and time-window checks on every
              RODEO proof (read with rosbag2)
    validate  calls the validator node registered for the task's
              (category, task type) through rodeo_interfaces/srv/ValidateProof
    legacy    ROS 1 .bag and .csv proofs (rosbag2 cannot read ROS 1 bags) are
              checked in-process with the ported legacy validators while the
              legacy_proofs parameter is true
    report    each verdict is also published as JSON on oracle/verdicts

Parameters
    validators            ["Category/TaskType=service", ...], service names
                          relative to this node's namespace
    validator_timeout_sec time a validator may take (default 300)
    legacy_proofs         accept legacy proofs (default: LEGACY_PROOFS env, else true)
"""
from __future__ import annotations

import json
import os
import threading
import traceback

import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String
from web3 import Web3

from oracle_node.chain import ChainClient
from oracle_node.checks import UsedProofs, check_rodeo_proof
from oracle_node.events import EventWatcher
from oracle_node.proofs import KIND_CSV, KIND_RODEO, KIND_ROS1_BAG, detect_kind
from oracle_node.settings import Settings
from oracle_node.validators import Verdict
from oracle_node.validators.energy_csv import validate_csv
from oracle_node.validators.waste_ros1 import validate_bag
from rodeo_common.proof import parse_proof_uri, sha256_path
from rodeo_interfaces.srv import ValidateProof

from rodeo_oracle.bag_reader import read_proof


class RodeoOracle(Node):
    def __init__(self):
        super().__init__("oracle")
        self.declare_parameter("validators", ["Logistics/ItemTransport=validate/delivery"])
        self.declare_parameter("validator_timeout_sec", 300.0)
        env_legacy = os.environ.get("LEGACY_PROOFS", "1") not in ("0", "false", "no")
        self.declare_parameter("legacy_proofs", env_legacy)
        self.log = self.get_logger()

        self.settings = Settings()
        self.chain = ChainClient(Web3(Web3.HTTPProvider(self.settings.rpc_url)), self.settings)
        self.chain.ensure_is_current_oracle()
        self.used = UsedProofs(os.path.join(self.settings.state_dir, "used_proofs.json"))
        self.timeout = float(self.get_parameter("validator_timeout_sec").value)
        self.legacy = bool(self.get_parameter("legacy_proofs").value)

        cb = ReentrantCallbackGroup()
        self.validators = {}                       # (category, task_type) -> client
        for entry in self.get_parameter("validators").value:
            kind, _, service = entry.partition("=")
            category, _, task_type = kind.partition("/")
            if not (category and task_type and service):
                raise ValueError(f"bad validators entry '{entry}', expected Category/TaskType=service")
            self.validators[(category, task_type)] = self.create_client(
                ValidateProof, service.strip(), callback_group=cb)
        self.pub = self.create_publisher(String, "verdicts", 20)

        for (c, t), cli in self.validators.items():
            self.log.info(f"validator {c}/{t} -> {cli.srv_name}")
        self.log.info("legacy proofs (ROS 1 .bag, .csv): " + (
            "ACCEPTED - they carry no manifest, so a legacy proof passes for any task"
            if self.legacy else "refused"))

        self.watcher = EventWatcher(self.chain)
        threading.Thread(target=self.watcher.start, daemon=True, kwargs={
            "on_request": self.handle_request,
            "on_verified": lambda tid: self.log.info(f"task {tid} verified"),
            "on_rejected": lambda tid, r: self.log.info(f"task {tid} rejected: {r}"),
        }).start()

    # ------------------------------------------------------------------ one request
    def handle_request(self, tid: int):
        t = self.chain.get_task(tid)
        if not self.chain.is_inbox_for_this_oracle(t):
            return
        self.log.info(f"validating task {tid} ({t.category}/{t.task_type}), proof {t.proof_uri}")
        try:
            verdict = self._validate(t)
        except Exception as e:  # noqa: BLE001
            self.log.error(traceback.format_exc())
            verdict = Verdict(ok=False, reason=f"Validator error, {e}"[:128])
        summary = "\n".join(verdict.lines)
        self.log.info(f"task {tid} validation summary\n{summary}\n"
                      + ("APPROVED" if verdict.ok else f"REJECTED: {verdict.reason}"))
        if verdict.ok:
            self.chain.approve(tid)
        else:
            self.chain.reject(tid, verdict.reason)
        self.pub.publish(String(data=json.dumps({
            "task_id": tid, "category": t.category, "task_type": t.task_type,
            "ok": verdict.ok, "reason": verdict.reason, "lines": verdict.lines})))

    def _validate(self, t) -> Verdict:
        try:
            path, sha = parse_proof_uri(t.proof_uri)
        except ValueError as e:
            return Verdict(ok=False, reason=f"Unsupported proof URI, {e}"[:128])
        if not os.path.exists(path):
            return Verdict(ok=False, reason="ProofURI path not found on oracle")
        sha_ok = sha is None or sha == sha256_path(path)
        kind = detect_kind(path)

        if kind == KIND_RODEO:
            if not sha:
                return Verdict(ok=False, reason="RODEO proof without #sha256 in the URI")
            prev = self.used.task_for(sha)
            reused = prev if prev is not None and prev != t.id else None
            proof = read_proof(path)
            service_desc = self.chain.service_description_for_task(t.id)
            verdict = check_rodeo_proof(t, proof, self.chain.task_window(t.id), service_desc,
                                        sha_ok, reused, self.settings.clock_tolerance_s)
            if verdict.ok:
                self._call_validator(t, proof, service_desc, path, verdict)
            self.used.record(sha, t.id)
            return verdict

        if kind in (KIND_ROS1_BAG, KIND_CSV):
            if not self.legacy:
                return Verdict(ok=False, reason="Legacy proof refused, task needs a RODEO proof")
            if not sha_ok:
                return Verdict(ok=False, reason="proof changed after submission (hash mismatch)")
            if kind == KIND_ROS1_BAG:
                return validate_bag(path)
            return validate_csv(path, self.settings.iec_per_kwh, self.settings.iec_decimals)
        return Verdict(ok=False, reason="Unsupported proof type, expected a RODEO bag, .bag or .csv")

    def _call_validator(self, t, proof, service_desc, path, verdict: Verdict) -> None:
        cli = self.validators.get((t.category, t.task_type))
        if cli is None:
            verdict.check(False, f"no validator for {t.category}/{t.task_type}",
                          f"No validator for {t.category}/{t.task_type}")
            return
        if not cli.wait_for_service(timeout_sec=10.0):
            verdict.check(False, f"validator {cli.srv_name} not running",
                          f"Validator for {t.category}/{t.task_type} not available")
            return
        req = ValidateProof.Request(task_id=t.id, category=t.category, task_type=t.task_type,
                                    executor=t.executor, params_json=json.dumps(proof.params),
                                    service_description=service_desc or "", proof_path=path)
        done, box = threading.Event(), {}
        cli.call_async(req).add_done_callback(lambda f: (box.setdefault("r", f.result()), done.set()))
        if not done.wait(self.timeout):
            verdict.check(False, f"validator {cli.srv_name} timed out", "Validator timed out")
            return
        res = box["r"]
        verdict.lines += list(res.lines)
        if not res.ok:
            verdict.ok, verdict.reason = False, res.reason or "rejected by validator"


def main(args=None):
    rclpy.init(args=args)
    node = RodeoOracle()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.watcher.stop()
        ex.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

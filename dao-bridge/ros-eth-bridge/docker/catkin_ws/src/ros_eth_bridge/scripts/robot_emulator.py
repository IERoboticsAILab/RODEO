#!/usr/bin/env python3
"""
robot_emulator.py — Simulates an autonomous robot agent on the DAO bridge.

Lifecycle
---------
1. Start-up: register two services the robot can offer:
     • Cleaning  / LabCleaning    @ 200 IEC
     • Logistics / ItemTransport  @ 300 IEC

2. Idle loop: subscribe to /dao/task_assigned.
   When the executor address matches our wallet, accept the task:
     • query task details (category / reward)
     • log "starting work"
     • sleep (simulated execution time)
     • submit proof  ipfs://proof.csv  via the bridge action

3. Verdict: subscribe to /dao/task_verified and /dao/task_rejected.
   When a verdict arrives for one of our tasks, print result + IEC balance.

Prerequisites
-------------
  1. Ganache running:  npx ganache --deterministic --chainId 1337
  2. Contracts deployed (addresses in config/dao.yaml)
  3. Both bridge nodes running:
       roslaunch ros_eth_bridge ros_eth_gateway.launch

Usage
-----
  rosrun ros_eth_bridge robot_emulator.py
  # or:
  python3 scripts/robot_emulator.py

The robot uses the wallet address configured in dao.yaml
(PRIVATE_KEY_ROBOT = 0x47e179...  →  0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65)
"""
from __future__ import annotations

import os
import sys
import threading
import time
from typing import Dict, Set

import actionlib
import rospy
import rospkg
import yaml
from web3 import Web3

# ── action types ─────────────────────────────────────────────────────────────
from ros_eth_msgs.msg import (
    RegisterServiceAction, RegisterServiceGoal,
    SubmitProofAction, SubmitProofGoal,
)

# ── service types ─────────────────────────────────────────────────────────────
from ros_eth_msgs.srv import (
    GetAllServices, GetAllServicesRequest,
    GetBalance,    GetBalanceRequest,
    GetTask,       GetTaskRequest,
)

# ── event message types ───────────────────────────────────────────────────────
from ros_eth_msgs.msg import TaskAssignment, TaskId, TaskRejection

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Simulated execution durations (seconds)
EXEC_TIME: Dict[str, float] = {
    "Cleaning":  5.0,
    "Logistics": 8.0,
}
DEFAULT_EXEC_TIME = 4.0

PROOF_URI = "ipfs://proof.csv"

# Terminal colours
_CYAN   = "\033[96m"
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_BOLD   = "\033[1m"
_RESET  = "\033[0m"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _banner(text: str, colour: str = _CYAN) -> None:
    bar = "═" * 58
    rospy.loginfo("\n%s%s\n  %s\n%s%s", colour + _BOLD, bar, text, bar, _RESET)


def _log(text: str, colour: str = "") -> None:
    rospy.loginfo("%s%s%s", colour, text, _RESET if colour else "")


def _load_wallet_address() -> str:
    """Read the wallet address from dao.yaml (same source the bridge nodes use)."""
    try:
        pkg_path = rospkg.RosPack().get_path("ros_eth_bridge")
        yaml_path = os.path.join(pkg_path, "config", "dao.yaml")
    except Exception:
        yaml_path = os.environ.get("ROS_ETH_DAO_YAML", "")
        if not yaml_path:
            raise RuntimeError("Cannot locate dao.yaml")

    with open(yaml_path) as f:
        cfg = yaml.safe_load(f)
    addr = cfg["wallet"]["address"]
    if not addr.startswith("0x"):
        addr = "0x" + addr
    return Web3.to_checksum_address(addr)


# ─────────────────────────────────────────────────────────────────────────────
# Robot Emulator
# ─────────────────────────────────────────────────────────────────────────────

class RobotEmulator:

    # ── services the robot can offer ─────────────────────────────────────────
    _SERVICE_DEFS = [
        dict(
            name="LabCleaningRobot",
            description="Autonomous lab cleaning service",
            category="Cleaning",
            service_type="LabCleaning",
            price=200,
            provider_type=0,
        ),
        dict(
            name="ItemTransportRobot",
            description="Autonomous item transport service",
            category="Logistics",
            service_type="ItemTransport",
            price=300,
            provider_type=0,
        ),
    ]

    def __init__(self) -> None:
        rospy.init_node("robot_emulator", anonymous=False)

        self.wallet_addr: str = _load_wallet_address()
        _log(f"Robot wallet: {self.wallet_addr}", _CYAN)

        # tasks currently being executed (task_id → category string)
        self._active: Dict[int, str] = {}
        self._active_lock = threading.Lock()

        # ── action clients ────────────────────────────────────────────────────
        rospy.loginfo("Connecting to bridge action servers …")
        self._ac_register = actionlib.SimpleActionClient(
            "/dao/register_service_action", RegisterServiceAction)
        self._ac_register.wait_for_server(rospy.Duration(30.0))

        self._ac_proof = actionlib.SimpleActionClient(
            "/dao/submit_proof_action", SubmitProofAction)
        self._ac_proof.wait_for_server(rospy.Duration(30.0))

        # ── ROS service proxies ───────────────────────────────────────────────
        rospy.loginfo("Waiting for bridge query services …")
        rospy.wait_for_service("/dao/get_task_by_id",   timeout=30.0)
        rospy.wait_for_service("/dao/get_all_services", timeout=30.0)
        rospy.wait_for_service("/dao/get_balance",      timeout=30.0)

        self._srv_task      = rospy.ServiceProxy("/dao/get_task_by_id",   GetTask)
        self._srv_services  = rospy.ServiceProxy("/dao/get_all_services", GetAllServices)
        self._srv_balance   = rospy.ServiceProxy("/dao/get_balance",      GetBalance)

    # ─────────────────────────────────────────────────────────────────────────
    # Start-up: register services
    # ─────────────────────────────────────────────────────────────────────────

    def _already_registered(self, category: str, service_type: str) -> bool:
        """True if a live service with these traits is already on-chain."""
        try:
            resp = self._srv_services(GetAllServicesRequest())
            if not resp.ok:
                return False
            return any(
                s.category == category and s.service_type == service_type
                and s.creator == self.wallet_addr and s.active
                for s in resp.services
            )
        except Exception:
            return False

    def register_services(self) -> None:
        _banner("Registering robot services …")
        for svc in self._SERVICE_DEFS:
            if self._already_registered(svc["category"], svc["service_type"]):
                _log(f"  [SKIP]   {svc['name']} already registered and active",
                     _YELLOW)
                continue

            goal = RegisterServiceGoal(
                name=svc["name"],
                description=svc["description"],
                category=svc["category"],
                service_type=svc["service_type"],
                price=str(svc["price"]),
                provider_type=svc["provider_type"],
            )
            _log(f"  [REG]    {svc['name']}  "
                 f"({svc['category']} / {svc['service_type']})  "
                 f"{svc['price']} IEC …", _CYAN)

            self._ac_register.send_goal(goal)
            done = self._ac_register.wait_for_result(rospy.Duration(60.0))
            result = self._ac_register.get_result() if done else None
            if result and result.ok:
                _log(f"  [OK]     registered  tx={result.tx_hash[:14]}…", _GREEN)
            else:
                rospy.logwarn("  [FAIL]   %s registration failed", svc["name"])

    # ─────────────────────────────────────────────────────────────────────────
    # Subscription callbacks
    # ─────────────────────────────────────────────────────────────────────────

    def _on_task_assigned(self, msg: TaskAssignment) -> None:
        """Called when the poller sees a TaskAssigned event on-chain."""
        executor = Web3.to_checksum_address(msg.executor) \
            if msg.executor.startswith("0x") else msg.executor

        if executor.lower() != self.wallet_addr.lower():
            # Task assigned to a different executor — ignore
            return

        task_id = int(msg.task_id)
        with self._active_lock:
            if task_id in self._active:
                return   # already handling this task
            self._active[task_id] = "?"  # placeholder until we query

        # Spawn a worker thread so the subscriber callback returns immediately
        t = threading.Thread(target=self._execute_task,
                             args=(task_id, msg.reward_wei),
                             daemon=True)
        t.start()

    def _on_task_verified(self, msg: TaskId) -> None:
        task_id = int(msg.task_id)
        with self._active_lock:
            if task_id not in self._active:
                return

        _banner(f"✓ TASK {task_id} VERIFIED — reward paid!", _GREEN)
        self._print_balance()
        with self._active_lock:
            self._active.pop(task_id, None)

    def _on_task_rejected(self, msg: TaskRejection) -> None:
        task_id = int(msg.task_id)
        with self._active_lock:
            if task_id not in self._active:
                return

        reason = msg.reason or "(no reason given)"
        _banner(f"✗ TASK {task_id} REJECTED — reason: {reason}", _RED)
        self._print_balance()
        with self._active_lock:
            self._active.pop(task_id, None)

    # ─────────────────────────────────────────────────────────────────────────
    # Task execution (runs in its own thread)
    # ─────────────────────────────────────────────────────────────────────────

    def _execute_task(self, task_id: int, reward_wei: str) -> None:
        # ── 1. Query task details ─────────────────────────────────────────────
        try:
            resp = self._srv_task(GetTaskRequest(task_id=task_id))
        except Exception as exc:
            rospy.logwarn("Could not query task %d: %s", task_id, exc)
            return

        if not resp.ok:
            rospy.logwarn("get_task_by_id %d returned ok=False", task_id)
            return

        task = resp.task
        category    = task.category
        reward_iec  = int(reward_wei) / 1e18 if reward_wei else "?"

        with self._active_lock:
            self._active[task_id] = category

        # ── 2. Log acceptance ─────────────────────────────────────────────────
        _banner(f"TASK {task_id} ASSIGNED  →  starting execution", _CYAN)
        _log(f"  Category  : {category}", _CYAN)
        _log(f"  Type      : {task.task_type}", _CYAN)
        _log(f"  Reward    : {reward_iec:.0f} IEC", _CYAN)
        _log(f"  Desc      : {task.description}", _CYAN)

        exec_time = EXEC_TIME.get(category, DEFAULT_EXEC_TIME)
        _log(f"\n  Simulating {exec_time:.0f} s of work …", _YELLOW)

        # ── 3. Simulate work ──────────────────────────────────────────────────
        for remaining in range(int(exec_time), 0, -1):
            if rospy.is_shutdown():
                return
            _log(f"  … {remaining} s remaining", _YELLOW)
            time.sleep(1.0)

        _log("  Work complete. Submitting proof …", _GREEN)

        # ── 4. Submit proof via bridge action ─────────────────────────────────
        goal = SubmitProofGoal(task_id=task_id, proof_uri=PROOF_URI)
        self._ac_proof.send_goal(goal)
        done   = self._ac_proof.wait_for_result(rospy.Duration(60.0))
        result = self._ac_proof.get_result() if done else None

        if result and result.ok:
            _log(f"  [PROOF SUBMITTED]  tx={result.tx_hash[:14]}…  "
                 f"— waiting for oracle verdict …", _GREEN)
        else:
            rospy.logerr("submit_proof action failed for task %d", task_id)
            with self._active_lock:
                self._active.pop(task_id, None)

    # ─────────────────────────────────────────────────────────────────────────
    # Balance query helper
    # ─────────────────────────────────────────────────────────────────────────

    def _print_balance(self) -> None:
        try:
            resp = self._srv_balance(GetBalanceRequest(owner=self.wallet_addr))
            if resp.ok:
                iec = int(resp.balance_wei) / 1e18
                _log(f"  IEC Balance: {iec:.2f} IEC  ({resp.balance_wei} wei)",
                     _BOLD + _GREEN)
            else:
                rospy.logwarn("get_balance returned ok=False")
        except Exception as exc:
            rospy.logwarn("Balance query failed: %s", exc)

    # ─────────────────────────────────────────────────────────────────────────
    # Main
    # ─────────────────────────────────────────────────────────────────────────

    def run(self) -> None:
        # Register services first
        self.register_services()

        # Print initial balance
        _banner("Robot ready — waiting for task assignments", _GREEN)
        _log(f"  Offering services:", _CYAN)
        for svc in self._SERVICE_DEFS:
            _log(f"    • {svc['category']} / {svc['service_type']}"
                 f"  @  {svc['price']} IEC", _CYAN)
        _log("")
        self._print_balance()

        # Subscribe to event topics
        rospy.Subscriber("/dao/task_assigned",  TaskAssignment, self._on_task_assigned,  queue_size=100)
        rospy.Subscriber("/dao/task_verified",  TaskId,         self._on_task_verified,  queue_size=100)
        rospy.Subscriber("/dao/task_rejected",  TaskRejection,  self._on_task_rejected,  queue_size=100)

        _log("\n  Subscribed to /dao/task_assigned, /dao/task_verified, /dao/task_rejected", _CYAN)
        _log("  Ctrl-C to quit\n")

        rospy.spin()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    # Ensure we can import from the package src/ folder whether running via
    # rosrun or directly with python3.
    try:
        pkg_path = rospkg.RosPack().get_path("ros_eth_bridge")
        sys.path.insert(0, os.path.join(pkg_path, "src"))
    except Exception:
        pass

    robot = RobotEmulator()
    robot.run()


if __name__ == "__main__":
    main()

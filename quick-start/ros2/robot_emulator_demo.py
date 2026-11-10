#!/usr/bin/env python3
"""
Robot emulator for the RODEO integration demo - ROS 2 version.

Same behaviour as quick-start/robot_emulator_demo.py (ROS 1), used as the
acceptance test for the ROS 2 bridge:
    1. register a delivery service           (dao/register_service_action)
    2. wait for an assignment                 (dao/task_assigned)
    3. "execute" it (10 s countdown)
    4. submit the pre-recorded proof bag      (dao/submit_proof_action)
    5. report the oracle's verdict            (dao/task_verified / dao/task_rejected)

Names are relative, so run it in the bridge's namespace:
    ros2 run ... --ros-args -r __ns:=/panther
"""
from __future__ import annotations

import os
import sys
import threading
import time

import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node

from ros_eth_msgs.action import RegisterService, SubmitProof
from ros_eth_msgs.msg import TaskAssignment, TaskId, TaskRejection

DEFAULT_PROOF = "/root/oracle/proofs/task_tid10_20250910_145742.bag"


class RobotEmulator(Node):
    def __init__(self, skip_registration: bool = False):
        super().__init__("robot_emulator_demo")
        log = self.get_logger()
        log.info("=" * 60)
        log.info("RODEO Robot Emulator - Full Integration Demo (ROS 2)")
        log.info("=" * 60)

        self.skip_registration = skip_registration
        self.proof_file = os.environ.get("PROOF_FILE", DEFAULT_PROOF)
        self.assigned_tasks: set[int] = set()
        self.proof_submitted_tasks: set[int] = set()
        self._lock = threading.Lock()

        cb = ReentrantCallbackGroup()
        self.register_service_client = ActionClient(
            self, RegisterService, "dao/register_service_action", callback_group=cb)
        self.submit_proof_client = ActionClient(
            self, SubmitProof, "dao/submit_proof_action", callback_group=cb)

        self.create_subscription(TaskAssignment, "dao/task_assigned",
                                 self.on_task_assigned, 50, callback_group=cb)
        self.create_subscription(TaskId, "dao/task_verified",
                                 self.on_task_verified, 50, callback_group=cb)
        self.create_subscription(TaskRejection, "dao/task_rejected",
                                 self.on_task_rejected, 50, callback_group=cb)

    # ------------------------------------------------------------------ helpers
    def _call_action(self, client: ActionClient, goal, timeout: float):
        """Send a goal and block (outside the executor thread) until its result."""
        done = threading.Event()
        box = {}

        def on_result(fut):
            box["result"] = fut.result().result
            done.set()

        def on_goal(fut):
            gh = fut.result()
            if not gh.accepted:
                box["result"] = None
                done.set()
                return
            gh.get_result_async().add_done_callback(on_result)

        client.send_goal_async(goal).add_done_callback(on_goal)
        if not done.wait(timeout):
            return None, True
        return box.get("result"), False

    def wait_for_servers(self) -> None:
        self.get_logger().info("⏳ Waiting for action servers...")
        if not self.register_service_client.wait_for_server(timeout_sec=30.0):
            raise RuntimeError("❌ Register service action server not available")
        if not self.submit_proof_client.wait_for_server(timeout_sec=30.0):
            raise RuntimeError("❌ Submit proof action server not available")
        self.get_logger().info("✅ Action servers connected!")

    # ------------------------------------------------------------------ steps
    def register_service(self) -> None:
        log = self.get_logger()
        log.info("")
        log.info("📝 Step 1: Registering delivery service...")
        log.info("-" * 60)
        goal = RegisterService.Goal()
        goal.name = "Delivery Service"
        goal.description = "Autonomous package delivery robot"
        goal.category = "Logistics"
        goal.service_type = "ItemTransport"
        goal.price = "100"
        goal.provider_type = 0  # Robot
        goal.min_confirmations = 1
        log.info(f"   Name: {goal.name}  |  Category: {goal.category}  |  Price: {goal.price} IEC")
        log.info("⏳ Waiting for blockchain transaction...")

        result, timed_out = self._call_action(self.register_service_client, goal, 60.0)
        if timed_out:
            log.error("❌ Service registration timed out")
        elif result is not None and result.ok:
            log.info(f"✅ Service registered! TX: {result.tx_hash}  Block: {result.block_number}")
        else:
            log.error("❌ Service registration failed")

    def on_task_assigned(self, msg: TaskAssignment) -> None:
        with self._lock:
            if msg.task_id in self.assigned_tasks:
                return
            self.assigned_tasks.add(msg.task_id)
        # Work happens in its own thread so the executor keeps spinning.
        threading.Thread(target=self._execute, args=(msg,), daemon=True).start()

    def _execute(self, msg: TaskAssignment) -> None:
        log = self.get_logger()
        reward_iec = int(msg.reward_wei) / 10**18
        log.info("")
        log.info("=" * 60)
        log.info(f"🎯 Task assigned! ID: {msg.task_id}  Reward: {reward_iec} IEC")
        log.info("=" * 60)
        log.info("🤖 Step 3: Executing task (10 seconds simulation)...")
        for i in range(10, 0, -1):
            log.info(f"   ⏱  {i}s remaining...")
            time.sleep(1)
        log.info("✅ Task execution completed!")
        self.submit_proof(msg.task_id)

    def submit_proof(self, task_id: int) -> None:
        log = self.get_logger()
        log.info("")
        log.info("📤 Step 4: Submitting proof of completion...")
        log.info("-" * 60)
        if not os.path.exists(self.proof_file):
            log.error(f"❌ Proof file not found: {self.proof_file}")
            return
        log.info(f"   Proof: {self.proof_file} ({os.path.getsize(self.proof_file)} bytes)")

        goal = SubmitProof.Goal()
        goal.task_id = int(task_id)
        goal.proof_uri = f"file://{self.proof_file}"
        goal.min_confirmations = 1
        log.info("⏳ Submitting to blockchain...")

        result, timed_out = self._call_action(self.submit_proof_client, goal, 60.0)
        if timed_out:
            log.error("❌ Proof submission timed out")
        elif result is not None and result.ok:
            log.info(f"✅ Proof submitted! TX: {result.tx_hash}  Block: {result.block_number}")
            log.info("🔍 Step 5: Waiting for oracle validation...")
            with self._lock:
                self.proof_submitted_tasks.add(task_id)
        else:
            log.error("❌ Proof submission failed")

    def on_task_verified(self, msg: TaskId) -> None:
        with self._lock:
            if msg.task_id not in self.proof_submitted_tasks:
                return
        log = self.get_logger()
        log.info("")
        log.info("=" * 60)
        log.info(f"🏆 Task {msg.task_id} verified — reward received!")
        log.info("   Oracle validated the proof successfully.")
        log.info("   Demo complete! ✅")
        log.info("=" * 60)
        log.info("")

    def on_task_rejected(self, msg: TaskRejection) -> None:
        with self._lock:
            if msg.task_id not in self.proof_submitted_tasks:
                return
        self.get_logger().error(f"❌ Task {msg.task_id} rejected by the oracle: {msg.reason}")

    def run_setup(self) -> None:
        log = self.get_logger()
        log.info("")
        log.info("🚀 Starting robot emulator...")
        self.wait_for_servers()
        if self.skip_registration:
            log.info("⏭️  Skipping service registration")
        else:
            self.register_service()
        log.info("")
        log.info("=" * 60)
        log.info("✅ Robot ready - listening for task assignments")
        log.info("=" * 60)
        log.info("")
        log.info("📋 Next steps:")
        log.info("   1. Open web console: http://localhost:8080")
        log.info("   2. Navigate to 'Tasks' page")
        log.info("   3. Click 'Register New Task'")
        log.info("   4. Fill in task details:")
        log.info("      - Description: Package delivery")
        log.info("      - Category: Logistics")
        log.info("      - Task Type: ItemTransport")
        log.info("      - Reward: 100 IEC")
        log.info("   5. Submit and watch this robot automatically:")
        log.info("      → Receive assignment")
        log.info("      → Execute task")
        log.info("      → Submit proof")
        log.info("      → Get paid!")
        log.info("")


def main(args=None):
    skip_registration = "--skip-registration" in sys.argv
    rclpy.init(args=args)
    node = RobotEmulator(skip_registration=skip_registration)
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    def setup():
        try:
            node.run_setup()
        except Exception as e:  # noqa: BLE001
            node.get_logger().error(f"Fatal error: {e}")
            rclpy.try_shutdown()

    threading.Thread(target=setup, daemon=True).start()
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        node.get_logger().info("Shutting down robot emulator...")
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

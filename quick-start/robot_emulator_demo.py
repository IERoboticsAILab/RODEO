#!/usr/bin/env python3
"""
Robot emulator for RODEO full integration demo.

This script simulates a robot that:
1. Registers a delivery service on the blockchain
2. Monitors for task assignments
3. Executes tasks (simulated with sleep)
4. Submits proof of completion
"""

import rospy
import time
import os
import actionlib
from ros_eth_msgs.msg import (
    RegisterServiceAction, RegisterServiceGoal,
    SubmitProofAction, SubmitProofGoal,
    TaskAssignment, TaskId
)

class RobotEmulator:
    def __init__(self, skip_registration=False):
        rospy.init_node('robot_emulator_demo', anonymous=True)

        rospy.loginfo("=" * 60)
        rospy.loginfo("RODEO Robot Emulator - Full Integration Demo")
        rospy.loginfo("=" * 60)

        self.skip_registration = skip_registration
        self.assigned_tasks = []
        self.proof_submitted_tasks = []
        self.service_registered = False

        # Action clients
        self.register_service_client = actionlib.SimpleActionClient(
            '/dao/register_service_action', RegisterServiceAction
        )
        self.submit_proof_client = actionlib.SimpleActionClient(
            '/dao/submit_proof_action', SubmitProofAction
        )

        rospy.loginfo("⏳ Waiting for action servers...")
        if not self.register_service_client.wait_for_server(timeout=rospy.Duration(30)):
            raise Exception("❌ Register service action server not available")
        if not self.submit_proof_client.wait_for_server(timeout=rospy.Duration(30)):
            raise Exception("❌ Submit proof action server not available")
        rospy.loginfo("✅ Action servers connected!")

        rospy.Subscriber('/dao/task_assigned', TaskAssignment, self.on_task_assigned)
        rospy.Subscriber('/dao/task_verified', TaskId, self.on_task_verified)

    def register_service(self):
        """Register delivery service on blockchain"""
        rospy.loginfo("")
        rospy.loginfo("📝 Step 1: Registering delivery service...")
        rospy.loginfo("-" * 60)

        goal = RegisterServiceGoal()
        goal.name = "Delivery Service"
        goal.description = "Autonomous package delivery robot"
        goal.category = "Logistics"
        goal.service_type = "ItemTransport"
        goal.price = "100"
        goal.provider_type = 0  # Robot
        goal.min_confirmations = 1

        rospy.loginfo(f"   Name: {goal.name}  |  Category: {goal.category}  |  Price: {goal.price} IEC")

        self.register_service_client.send_goal(goal)
        rospy.loginfo("⏳ Waiting for blockchain transaction...")

        if not self.register_service_client.wait_for_result(timeout=rospy.Duration(60)):
            rospy.logerr("❌ Service registration timed out")
            return

        result = self.register_service_client.get_result()
        if result and result.ok:
            rospy.loginfo(f"✅ Service registered! TX: {result.tx_hash}  Block: {result.block_number}")
            self.service_registered = True
        else:
            rospy.logerr("❌ Service registration failed")

    def on_task_assigned(self, msg):
        """Callback for task assignment events"""
        if msg.task_id in self.assigned_tasks:
            return
        self.assigned_tasks.append(msg.task_id)

        reward_iec = int(msg.reward_wei) / 10**18
        rospy.loginfo("")
        rospy.loginfo("=" * 60)
        rospy.loginfo(f"🎯 Task assigned! ID: {msg.task_id}  Reward: {reward_iec} IEC")
        rospy.loginfo("=" * 60)

        rospy.loginfo("🤖 Step 3: Executing task (10 seconds simulation)...")
        for i in range(10, 0, -1):
            rospy.loginfo(f"   ⏱  {i}s remaining...")
            time.sleep(1)
        rospy.loginfo("✅ Task execution completed!")

        self.submit_proof(msg.task_id)

    def submit_proof(self, task_id):
        """Submit task completion proof as .bag file"""
        rospy.loginfo("")
        rospy.loginfo("📤 Step 4: Submitting proof of completion...")
        rospy.loginfo("-" * 60)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        proof_file = os.path.join(project_root, "oracle", "proofs", "task_tid10_20250910_145742.bag")

        if not os.path.exists(proof_file):
            rospy.logerr(f"❌ Proof file not found: {proof_file}")
            return

        rospy.loginfo(f"   Proof: {proof_file} ({os.path.getsize(proof_file)} bytes)")

        goal = SubmitProofGoal()
        goal.task_id = task_id
        goal.proof_uri = f"file://{proof_file}"
        goal.min_confirmations = 1

        self.submit_proof_client.send_goal(goal)
        rospy.loginfo("⏳ Submitting to blockchain...")

        if not self.submit_proof_client.wait_for_result(timeout=rospy.Duration(60)):
            rospy.logerr("❌ Proof submission timed out")
            return

        result = self.submit_proof_client.get_result()
        if result and result.ok:
            rospy.loginfo(f"✅ Proof submitted! TX: {result.tx_hash}  Block: {result.block_number}")
            rospy.loginfo("🔍 Step 5: Waiting for oracle validation...")
            self.proof_submitted_tasks.append(task_id)
        else:
            rospy.logerr("❌ Proof submission failed")

    def on_task_verified(self, msg):
        """Callback for task verification events from the oracle"""
        if msg.task_id not in self.proof_submitted_tasks:
            return
        rospy.loginfo("")
        rospy.loginfo("=" * 60)
        rospy.loginfo(f"🏆 Task {msg.task_id} verified — reward received!")
        rospy.loginfo("   Oracle validated the proof successfully.")
        rospy.loginfo("   Demo complete! ✅")
        rospy.loginfo("=" * 60)
        rospy.loginfo("")

    def run(self):
        """Main execution loop"""
        rospy.loginfo("")
        rospy.loginfo("🚀 Starting robot emulator...")

        if self.skip_registration:
            rospy.loginfo("⏭️  Skipping service registration")
        else:
            self.register_service()

        rospy.loginfo("")
        rospy.loginfo("=" * 60)
        rospy.loginfo("✅ Robot ready - listening for task assignments")
        rospy.loginfo("=" * 60)
        rospy.loginfo("")
        rospy.loginfo("📋 Next steps:")
        rospy.loginfo("   1. Open web console: http://localhost:8080")
        rospy.loginfo("   2. Navigate to 'Tasks' page")
        rospy.loginfo("   3. Click 'Register New Task'")
        rospy.loginfo("   4. Fill in task details:")
        rospy.loginfo("      - Description: Package delivery")
        rospy.loginfo("      - Category: Logistics")
        rospy.loginfo("      - Task Type: ItemTransport")
        rospy.loginfo("      - Reward: 100 IEC")
        rospy.loginfo("   5. Submit and watch this robot automatically:")
        rospy.loginfo("      → Receive assignment")
        rospy.loginfo("      → Execute task")
        rospy.loginfo("      → Submit proof")
        rospy.loginfo("      → Get paid!")
        rospy.loginfo("")
        rospy.spin()


def main():
    import sys
    skip_registration = '--skip-registration' in sys.argv
    try:
        robot = RobotEmulator(skip_registration=skip_registration)
        robot.run()
    except (rospy.ROSInterruptException, KeyboardInterrupt):
        rospy.loginfo("Shutting down robot emulator...")
    except Exception as e:
        rospy.logerr(f"Fatal error: {e}")

if __name__ == '__main__':
    main()

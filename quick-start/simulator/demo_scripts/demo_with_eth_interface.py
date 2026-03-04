#!/usr/bin/env python3

import rospy
from navigation_move_base import NavigationEngine

# import your interface (adjust the import path/module name to where EthInterface lives)
from eth_interface import EthInterface  # <-- change if your file/module name differs


class DemoMissionNode:
    """
    Demo node:
      1) Registers services
      2) Waits for a task assigned to this robot
      3) Executes the task
      4) Submits proof after completion
    """

    def __init__(self):
        # --- Navigation locations ---
        self.locations = {
            "bottom_right": {"x": -18.698, "y": -11.069, "z": -0.680, "w": 0.733},
            "start_room":   {"x": -13.045, "y": 4.102,  "z": 0.567, "w": 0.823},
            "front_start":  {"x": 2.303,   "y": 8.280,  "z": 0.022, "w": 0.999},
            "top_left":     {"x": 19.112,  "y": 18.273, "z": 0.663, "w": 0.748},
            "top_right":    {"x": 19.155,  "y": -16.322,"z": -0.978, "w": 0.205},
            "big_room":     {"x": 12.638,  "y": -6.038, "z": -0.999, "w": 0.003},
            "hallway":      {"x": -11.009, "y": -10.938,"z": -0.842, "w": 0.539}
        }

        # --- Navigation Engine ---
        self.nav = None
        try:
            self.nav = NavigationEngine(action_name='/move_base')
        except RuntimeError as e:
            rospy.logerr(f"Shutdown: {e}")
            raise

        # --- DAO / ETH interface ---
        self.eth = EthInterface()

        # Optional: define a simple mapping from on-chain "task/service type"
        # to your local handlers. You can change these keys to match your contract conventions.
        #
        # Supported keys are compared in a tolerant way (strings/ints).
        self.task_handlers = {
            "delivery": self.run_task_delivery,
            "battery_charging": self.run_task_battery_charging,
            "charging": self.run_task_battery_charging,
            "cleaning": self.run_task_cleaning,
            1: self.run_task_delivery,
            2: self.run_task_battery_charging,
            3: self.run_task_cleaning,
        }

    # -------------------------
    # Demo task implementations
    # -------------------------
    def run_task_delivery(self):
        """Delivery Task: Start Room -> bottom right Room -> Start Room"""
        rospy.loginfo("Starting task delivery...")
        ok1 = self.execute_move("bottom_right")
        rospy.sleep(5)  # Simulate pickup time
        ok2 = self.execute_move("start_room")
        return bool(ok1 and ok2)

    def run_task_battery_charging(self):
        """Battery Charging: go to top left room (your demo uses top_left)"""
        rospy.loginfo("Starting task battery charging...")
        ok = self.execute_move("top_left")
        rospy.loginfo("Charging battery for 15 seconds...")
        rospy.sleep(15)
        return bool(ok)

    def run_task_cleaning(self):
        """Cleaning: clean all rooms..."""
        rospy.loginfo("Starting Cleaning task...")
        seq = ["front_start", "top_left", "top_right", "big_room", "hallway", "bottom_right"]
        ok_all = True
        for name in seq:
            ok_all = bool(self.execute_move(name)) and ok_all
        return ok_all

    def execute_move(self, name):
        if self.nav is None:
            rospy.logerr("Cannot move: Navigation Engine not initialized.")
            return False

        if name not in self.locations:
            rospy.logerr(f"Location {name} not found in database.")
            return False

        coords = self.locations[name]
        rospy.loginfo(f"Moving to: {name.upper()}")
        return self.nav.move_to_pose(coords['x'], coords['y'], coords['z'], coords['w'])

    # -------------------------
    # DAO / Task helpers
    # -------------------------
    def register_demo_services(self):
        """
        Register the services this robot can provide.
        Adjust category/service_type/price to match your on-chain schema.
        """
        rospy.loginfo("Registering demo services on DAO...")

        services = [
            {
                "name": "Robot Delivery",
                "description": "Autonomous delivery: start_room <-> bottom_right",
                "category": "logistics",
                "service_type": "delivery",   # could be int/string depending on your contract
                "price_tokens": 1
            },
            {
                "name": "Robot Charging",
                "description": "Navigate to charging station and wait",
                "category": "maintenance",
                "service_type": "battery_charging",
                "price_tokens": 1
            },
            {
                "name": "Robot Cleaning",
                "description": "Patrol and clean all rooms",
                "category": "maintenance",
                "service_type": "cleaning",
                "price_tokens": 2
            },
        ]

        for s in services:
            try:
                res = self.eth.register_service(
                    name=s["name"],
                    description=s["description"],
                    category=s["category"],
                    service_type=s["service_type"],
                    price_tokens=s["price_tokens"]
                )
                rospy.loginfo(
                    f"Registered service '{s['name']}' "
                    f"(tx={res.get('tx_hash','')}, block={res.get('block_number',0)})"
                )
            except Exception as e:
                rospy.logerr(f"Failed registering service '{s['name']}': {e}")

    def wait_for_next_assignment(self, timeout=0.0):
        """
        Wait until EthInterface sees a /dao/task_assigned event for THIS robot.

        timeout=0.0 means wait forever.
        Returns the TaskAssignment message or None on timeout/shutdown.
        """
        # clear any previous signal
        self.eth._assign_evt.clear()

        if timeout and timeout > 0.0:
            ok = self.eth._assign_evt.wait(timeout)
            if not ok:
                return None
        else:
            # wait forever, but remain responsive to shutdown
            while not rospy.is_shutdown():
                if self.eth._assign_evt.wait(0.5):
                    break
            if rospy.is_shutdown():
                return None

        return self.eth._last_assignment

    def _get_assignment_fields(self, assignment_msg):
        """
        Try to extract task_id + a type discriminator (task_type/service_type/category)
        in a robust way (different message versions).
        """
        task_id = int(getattr(assignment_msg, "task_id", -1))

        # Try several likely field names for "what kind of task is this?"
        type_candidates = [
            getattr(assignment_msg, "task_type", None),
            getattr(assignment_msg, "service_type", None),
            getattr(assignment_msg, "category", None),
            getattr(assignment_msg, "task_category", None),
        ]
        task_kind = next((v for v in type_candidates if v not in (None, "", 0)), None)

        # Normalize string if it is bytes-like / etc.
        if isinstance(task_kind, bytes):
            task_kind = task_kind.decode("utf-8", errors="ignore")

        return task_id, task_kind

    def execute_assigned_task_and_submit_proof(self, assignment_msg):
        task_id, task_kind = self._get_assignment_fields(assignment_msg)

        rospy.loginfo(f"Received assignment: task_id={task_id}, kind={task_kind}")

        # Choose handler
        handler = None
        if task_kind in self.task_handlers:
            handler = self.task_handlers[task_kind]
        else:
            # Also try string-lower match (e.g. "CLEANING" -> "cleaning")
            if isinstance(task_kind, str):
                key = task_kind.strip().lower()
                handler = self.task_handlers.get(key)

        if handler is None:
            rospy.logerr(f"No handler for assigned task kind='{task_kind}'. Rejecting locally (no proof).")
            return

        # Execute
        rospy.loginfo(f"Executing task_id={task_id} using handler='{handler.__name__}'...")
        success = False
        try:
            success = bool(handler())
        except Exception as e:
            rospy.logerr(f"Exception while executing task {task_id}: {e}")
            success = False

        # Build proof URI (replace with your real proof artifact: IPFS CID, S3 URL, etc.)
        proof_uri = f"ros://demo_mission/proof/task_{task_id}?result={'ok' if success else 'fail'}"

        # Submit proof
        rospy.loginfo(f"Submitting proof for task_id={task_id}: {proof_uri}")
        try:
            res = self.eth.submit_proof(task_id=task_id, proof_uri=proof_uri)
            rospy.loginfo(f"Proof submitted: ok={res.get('ok')} tx={res.get('tx_hash','')}")
        except Exception as e:
            rospy.logerr(f"Failed to submit proof for task {task_id}: {e}")
            return

        # Optional: wait for verification/rejection event
        try:
            verdict = self.eth.wait_for_proof_verification(task_id=task_id, timeout=300.0)
            if verdict.get("verified"):
                rospy.loginfo(f"Task {task_id} verified ✅")
            else:
                rospy.logwarn(f"Task {task_id} NOT verified ❌ reason={verdict.get('reason')}")
        except Exception as e:
            rospy.logwarn(f"Could not wait for verification for task {task_id}: {e}")

    def run(self):
        # 1) Register services
        self.register_demo_services()

        # 2) Main loop: wait for assignments, execute, submit proof
        rospy.loginfo("Waiting for tasks to be assigned to this robot...")
        while not rospy.is_shutdown():
            assignment = self.wait_for_next_assignment(timeout=0.0)  # wait forever
            if assignment is None:
                continue

            # IMPORTANT: clear event so we can wait for the next one later
            self.eth._assign_evt.clear()

            # Execute + proof
            self.execute_assigned_task_and_submit_proof(assignment)

            rospy.loginfo("Done handling assignment. Waiting for the next task...")


def main():
    rospy.init_node('demo_mission_node', anonymous=False)
    app = DemoMissionNode()
    app.run()


if __name__ == '__main__':
    try:
        main()
    except rospy.ROSInterruptException:
        pass

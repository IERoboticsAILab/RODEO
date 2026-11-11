#!/usr/bin/env python3
"""
fake_executor - stands in for a robot's executor: serves rodeo/execute_task,
"does" the task in a few seconds and writes a standard RODEO proof bag.

For a task with pickup/dropoff places it records a delivery: drive to the
pick-up place, announce, load (weight rises), drive to the drop-off place,
announce, unload (weight falls), recipient confirms. Poses use the places'
coordinates from services.yaml. Any other task gets a short generic proof.

Parameters
    services_file   the robot's services.yaml (for place coordinates)
    proof_mode      "rodeo"  - return the RODEO proof bag (default)
                    "legacy" - write the RODEO proof, but return legacy_proof
                               instead, for the oracle that still validates
                               the ROS 1 waste-demo bag
    legacy_proof    path of that ROS 1 bag
    leg_sec         seconds per drive leg (default 4)
    battery_drain_pct  battery used per task (default 40); the simulated battery is
                    published on battery/battery_status (as the Panther's driver does)
                    and refilled when the agent reports a verified charge on
                    rodeo/charged. It also serves rodeo/dock (a 3 s "drive to the dock").
"""
from __future__ import annotations

import json
import math
import os
import time

import rclpy
from rclpy.action import ActionServer, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node
from sensor_msgs.msg import BatteryState
from std_msgs.msg import String
from std_srvs.srv import Trigger

from rodeo_common.services_config import load_robot_config
from rodeo_interfaces.action import ExecuteTask
from rodeo_interfaces.msg import TaskEvent

from rodeo_agent.proof_writer import ProofWriter


class FakeExecutor(Node):
    def __init__(self):
        super().__init__("fake_executor")
        self.declare_parameter("services_file", "")
        self.declare_parameter("proof_mode", "rodeo")
        self.declare_parameter("legacy_proof", "/root/oracle/proofs/task_tid10_20250910_145742.bag")
        self.declare_parameter("leg_sec", 4.0)
        self.declare_parameter("battery_drain_pct", 40.0)
        path = self.get_parameter("services_file").value or os.environ.get("RODEO_SERVICES_FILE", "")
        self.places = load_robot_config(path).places if path else {}
        self.mode = self.get_parameter("proof_mode").value
        self.leg = float(self.get_parameter("leg_sec").value)
        self.busy = False
        cb = ReentrantCallbackGroup()
        ActionServer(self, ExecuteTask, "rodeo/execute_task", execute_callback=self.execute,
                     goal_callback=self.on_goal, callback_group=cb)
        # simulated battery, dock and charge
        self.battery = 1.0
        self.drain = float(self.get_parameter("battery_drain_pct").value) / 100.0
        self.battery_pub = self.create_publisher(BatteryState, "battery/battery_status", 10)
        self.create_timer(1.0, self._publish_battery, callback_group=cb)
        self.create_service(Trigger, "rodeo/dock", self._on_dock, callback_group=cb)
        self.create_subscription(String, "rodeo/charged", self._on_charged, 10, callback_group=cb)
        self.get_logger().info(f"fake executor ready on {self.resolve_action_name()} "
                               f"(proof_mode={self.mode}, {len(self.places)} places)")

    def _publish_battery(self):
        self.battery_pub.publish(BatteryState(percentage=float(self.battery), voltage=float("nan"),
                                              present=True))

    def _on_dock(self, _req, res):
        self.get_logger().info(f"docking (battery {self.battery * 100:.0f} %)")
        time.sleep(3.0)
        res.success, res.message = True, "docked (simulated)"
        return res

    def _on_charged(self, msg: String):
        try:
            ok = bool(json.loads(msg.data).get("ok"))
        except ValueError:
            return
        if ok:
            self.battery = 1.0
            self.get_logger().info("charge verified: battery back to 100 %")

    def resolve_action_name(self):
        ns = self.get_namespace().rstrip("/")
        return f"{ns}/rodeo/execute_task"

    def on_goal(self, goal):
        if self.busy:
            self.get_logger().warning(f"task {goal.task_id}: rejected, already executing one")
            return GoalResponse.REJECT
        self.busy = True
        return GoalResponse.ACCEPT

    # ------------------------------------------------------------------ execution
    def execute(self, gh):
        g = gh.request
        log = self.get_logger()
        try:
            params = json.loads(g.params_json or "{}")
            log.info(f"task {g.task_id}: {g.category}/{g.task_type} {params}")
            with ProofWriter(g.proof_dir, g) as proof:
                if "pickup" in params and "dropoff" in params:
                    self._delivery(gh, proof, params)
                else:
                    self._generic(gh, proof)
            log.info(f"task {g.task_id}: proof written to {proof.path}")
            result = ExecuteTask.Result(success=True, proof_path=proof.path, message="done")
            if self.mode == "legacy":
                result.proof_path = self.get_parameter("legacy_proof").value
                result.message = f"done; returning the legacy proof (RODEO proof at {proof.path})"
                log.info(f"task {g.task_id}: legacy mode - returning {result.proof_path}")
            self.battery = max(0.0, self.battery - self.drain)
            log.info(f"task {g.task_id}: battery now {self.battery * 100:.0f} %")
            gh.succeed()
            return result
        except Exception as e:  # noqa: BLE001
            log.error(f"task {g.task_id}: {e}")
            gh.abort()
            return ExecuteTask.Result(success=False, proof_path="", message=str(e))
        finally:
            self.busy = False

    def _stage(self, gh, stage, detail=""):
        gh.publish_feedback(ExecuteTask.Feedback(stage=stage, detail=detail))
        self.get_logger().info(f"task {gh.request.task_id}: {stage}" + (f" - {detail}" if detail else ""))

    def _xy(self, place_id):
        p = self.places.get(place_id)
        if p is None or p.xy is None:
            raise RuntimeError(f"place '{place_id}' has no coordinates in services.yaml")
        return p.xy[0], p.xy[1]

    def _drive(self, proof, start, end, steps_per_sec=2.0):
        (x0, y0), (x1, y1) = start, end
        yaw = math.atan2(y1 - y0, x1 - x0)
        n = max(2, int(self.leg * steps_per_sec))
        for i in range(n + 1):
            a = i / n
            proof.pose(x0 + a * (x1 - x0), y0 + a * (y1 - y0), yaw)
            time.sleep(self.leg / n)

    def _hold(self, proof, xy, kg, seconds=1.5):
        for _ in range(3):
            proof.pose(xy[0], xy[1])
            proof.weight(kg, stable=True)
            time.sleep(seconds / 3)

    def _delivery(self, gh, proof, p):
        pick, drop = self._xy(p["pickup"]), self._xy(p["dropoff"])
        sender, recipient = p.get("sender") or "RODEO", p.get("recipient") or "the recipient"
        kg = float(p.get("declared_weight_kg") or 1.2)
        start = (pick[0] - 1.0, pick[1] - 1.0)

        self._stage(gh, "to_pickup", p["pickup"])
        proof.weight(0.0, stable=True)
        self._drive(proof, start, pick)
        proof.event(TaskEvent.ARRIVE, place=p["pickup"])
        proof.event(TaskEvent.SAY, place=p["pickup"], text="I am here to pick a package")
        self._stage(gh, "waiting_pickup", "package placed on the deck")
        self._hold(proof, pick, 0.0)
        self._hold(proof, pick, kg)
        proof.event(TaskEvent.DEPART, place=p["pickup"])

        self._stage(gh, "to_dropoff", p["dropoff"])
        self._drive(proof, pick, drop)
        proof.event(TaskEvent.ARRIVE, place=p["dropoff"])
        proof.event(TaskEvent.SAY, place=p["dropoff"], text=f"Package for {recipient} from {sender}")
        self._stage(gh, "waiting_confirm", f"{recipient} takes the package and confirms")
        self._hold(proof, drop, kg)
        self._hold(proof, drop, 0.0)
        proof.event(TaskEvent.CONFIRM, place=p["dropoff"], actor=recipient)
        proof.event(TaskEvent.DEPART, place=p["dropoff"])

    def _generic(self, gh, proof):
        self._stage(gh, "working", "generic task")
        proof.event(TaskEvent.NOTE, text="fake executor: generic task started")
        for i in range(int(self.leg * 2)):
            proof.pose(0.1 * i, 0.0)
            time.sleep(0.5)
        proof.event(TaskEvent.NOTE, text="fake executor: generic task finished")


def main(args=None):
    rclpy.init(args=args)
    node = FakeExecutor()
    ex = MultiThreadedExecutor(num_threads=4)
    ex.add_node(node)
    try:
        ex.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        ex.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

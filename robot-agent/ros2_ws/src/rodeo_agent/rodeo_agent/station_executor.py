#!/usr/bin/env python3
"""
station_executor - the charging station's executor.

The station takes part in RODEO like a robot: the institution's wallet runs a
bridge and the generic agent with the station's services.yaml (an
Energy/Charging service), and this node serves rodeo/execute_task for it. For
each charging task it runs one session and records the station's own
measurements as the proof:

    TaskEvent note "session start" / "session end", actor = the paying robot's wallet
    /rodeo/charge  ChargeSample (voltage, current, charge state) at 2 Hz

Parameters
    services_file  the station's services.yaml; the Charging service's settings
                   give the session: stub_seconds, stub_voltage_v, stub_current_a
    source         "stub" (simulated charge, default). A WiBotic source, reading
                   the transmitter's VMonBatt / IBattery / ChargeState, replaces it
                   once the station is commissioned.
"""
from __future__ import annotations

import json
import os
import time

import rclpy
from rclpy.action import ActionServer, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node

from rodeo_common.services_config import load_robot_config
from rodeo_interfaces.action import ExecuteTask
from rodeo_interfaces.msg import TaskEvent

from rodeo_agent.proof_writer import ProofWriter

SESSION_START, SESSION_END = "session start", "session end"


class StationExecutor(Node):
    def __init__(self):
        super().__init__("station_executor")
        self.declare_parameter("services_file", "")
        self.declare_parameter("source", "stub")
        path = self.get_parameter("services_file").value or os.environ.get("RODEO_SERVICES_FILE", "")
        cfg = load_robot_config(path)
        spec = cfg.service_for("Energy", "Charging")
        if spec is None:
            raise RuntimeError(f"{path} has no Energy/Charging service")
        self.settings = spec.settings
        self.source = self.get_parameter("source").value
        if self.source != "stub":
            raise RuntimeError(f"charging source '{self.source}' is not implemented yet (use stub)")
        self.busy = False
        ActionServer(self, ExecuteTask, "rodeo/execute_task", execute_callback=self.execute,
                     goal_callback=self.on_goal, callback_group=ReentrantCallbackGroup())
        self.get_logger().info(f"charging station executor ready (source={self.source}, "
                               f"{self.settings.get('stub_seconds', 10)} s sessions)")

    def on_goal(self, goal):
        if self.busy or (goal.category, goal.task_type) != ("Energy", "Charging"):
            return GoalResponse.REJECT
        self.busy = True
        return GoalResponse.ACCEPT

    def execute(self, gh):
        g, log = gh.request, self.get_logger()
        try:
            params = json.loads(g.params_json or "{}")
            payer = params.get("wallet", "")
            robot = params.get("robot", "robot")
            seconds = float(self.settings.get("stub_seconds", 10))
            v0 = float(self.settings.get("stub_voltage_v", 38.0))
            amps = float(self.settings.get("stub_current_a", 4.0))
            log.info(f"task {g.task_id}: charging {robot} ({payer}) for {seconds:g} s")
            gh.publish_feedback(ExecuteTask.Feedback(stage="charging", detail=robot))
            with ProofWriter(g.proof_dir, g) as proof:
                proof.event(TaskEvent.NOTE, text=SESSION_START, actor=payer)
                n = max(2, int(seconds * 2))
                for k in range(n + 1):
                    state = "ramp_up" if k < 2 else "cc"
                    current = amps * min(1.0, k / 2.0)
                    proof.charge(v0 + 2.0 * k / n, current, state)          # voltage rises while charging
                    time.sleep(seconds / n)
                proof.charge(v0 + 2.0, 0.0, "idle")
                proof.event(TaskEvent.NOTE, text=SESSION_END, actor=payer)
            log.info(f"task {g.task_id}: session done, proof {proof.path}")
            gh.succeed()
            return ExecuteTask.Result(success=True, proof_path=proof.path, message="charged")
        except Exception as e:  # noqa: BLE001
            log.error(f"task {g.task_id}: {e}")
            gh.abort()
            return ExecuteTask.Result(success=False, proof_path="", message=str(e))
        finally:
            self.busy = False


def main(args=None):
    rclpy.init(args=args)
    node = StationExecutor()
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

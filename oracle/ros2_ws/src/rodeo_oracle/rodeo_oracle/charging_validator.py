#!/usr/bin/env python3
"""
charging_validator - validator node for Energy/Charging.

Serves rodeo_interfaces/srv/ValidateProof at validate/charging (in the
oracle's namespace: /oracle/validate/charging). It reads the proof bag with
rosbag2 and applies the charging rules (session, energy, payer); see
oracle/oracle_node/validators/charging.py for the rules and their settings.

This node is also the template for other validators: any node, in any
language, that serves ValidateProof can be registered with the oracle.
"""
from __future__ import annotations

import traceback
from types import SimpleNamespace

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from oracle_node.validators.charging import validate
from rodeo_interfaces.srv import ValidateProof

from rodeo_oracle.bag_reader import read_proof


class ChargingValidator(Node):
    def __init__(self):
        super().__init__("charging_validator")
        self.create_service(ValidateProof, "validate/charging", self.on_validate)
        self.get_logger().info("charging validator ready (Energy/Charging)")

    def on_validate(self, req, res):
        try:
            proof = read_proof(req.proof_path)
            task = SimpleNamespace(id=req.task_id, category=req.category, task_type=req.task_type,
                                   executor=req.executor, creator=req.creator)
            v = validate(SimpleNamespace(task=task, proof=proof,
                                         service_desc=req.service_description, settings=None))
            res.ok, res.reason, res.lines = bool(v.ok), v.reason[:128], list(v.lines)
        except Exception as e:  # noqa: BLE001
            self.get_logger().error(traceback.format_exc())
            res.ok, res.reason, res.lines = False, f"Validator error, {e}"[:128], [f"  FAIL  {e}"]
        self.get_logger().info(f"task {req.task_id}: {'OK' if res.ok else 'FAIL ' + res.reason}")
        return res


def main(args=None):
    rclpy.init(args=args)
    node = ChargingValidator()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

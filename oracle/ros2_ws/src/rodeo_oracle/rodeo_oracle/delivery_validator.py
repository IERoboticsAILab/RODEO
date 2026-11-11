#!/usr/bin/env python3
"""
delivery_validator - validator node for Logistics/ItemTransport.

Serves rodeo_interfaces/srv/ValidateProof at validate/delivery (in the
oracle's namespace: /oracle/validate/delivery). It reads the proof bag with
rosbag2 and applies the delivery rules (route, load, receipt); see
oracle/oracle_node/validators/delivery.py for the rules and their settings.

This node is also the template for other validators: any node, in any
language, that serves ValidateProof can be registered with the oracle.
"""
from __future__ import annotations

import traceback
from types import SimpleNamespace

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node

from oracle_node.validators.delivery import validate
from rodeo_interfaces.srv import ValidateProof

from rodeo_oracle.bag_reader import read_proof


class DeliveryValidator(Node):
    def __init__(self):
        super().__init__("delivery_validator")
        self.create_service(ValidateProof, "validate/delivery", self.on_validate)
        self.get_logger().info("delivery validator ready (Logistics/ItemTransport)")

    def on_validate(self, req, res):
        try:
            proof = read_proof(req.proof_path)
            task = SimpleNamespace(id=req.task_id, category=req.category, task_type=req.task_type,
                                   executor=req.executor)
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
    node = DeliveryValidator()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

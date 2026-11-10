#!/usr/bin/env python3
"""
dao_listener - read-only DAO interface (ROS 2 port of dao_listener_node.py).

* 6 query services (get_task_by_id, get_all_tasks, ...).
* EthPoller in a daemon thread publishing 7 event topics.

All names are relative ("dao/..."), so the node's namespace decides where they
appear: no namespace gives the same /dao/... names as the ROS 1 bridge, and
namespace "panther" gives /panther/dao/...

Difference from ROS 1: with ``own_assignments_only`` (default true) the node
publishes ``dao/task_assigned`` only for tasks whose executor is this bridge's
wallet, so each robot's agent sees only its own assignments.
"""
from __future__ import annotations

import logging
import os

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from web3 import Web3

from eth.contracts import ContractRegistry
from eth.dao.query import (
    get_all_services, get_all_tasks, get_service, get_services_by_creator,
    get_task, get_tasks_by_creator,
)
from eth.events.checkpoint import CHECKPOINT_FILE, Checkpoint
from eth.events.decoder import (
    ServiceBusyUpdatedEvent, ServiceRegisteredEvent, TaskAssignedEvent,
    TaskRegisteredEvent, TaskRejectedEvent, TaskUnassignedEvent, TaskVerifiedEvent,
)
from eth.events.poller import EthPoller
from ros_eth_msgs.msg import (
    ServiceBusy, ServiceInfo, ServiceMeta, TaskAssignment, TaskId, TaskInfo,
    TaskRegistered, TaskRejection,
)
from ros_eth_msgs.srv import (
    GetAllServices, GetAllTasks, GetService, GetServicesByCreator, GetTask,
    GetTasksByCreator,
)

from ros_eth_bridge.config_loader import load_config, make_web3, resolve_config_path
from ros_eth_bridge.converters import service_data_to_msg, task_data_to_msg


def _checkpoint_path(node: Node, param: str) -> str:
    if param:
        return os.path.expanduser(param)
    ns = node.get_namespace().strip("/").replace("/", "_")
    if not ns:
        return CHECKPOINT_FILE
    return os.path.join(os.path.dirname(CHECKPOINT_FILE), f"event_checkpoint_{ns}.json")


def _hash32(b) -> list:
    raw = bytes(b or b"")
    return list(raw[:32].ljust(32, b"\x00"))


class DaoListener(Node):
    def __init__(self):
        super().__init__("dao_listener")
        self.declare_parameter("config_file", "")
        self.declare_parameter("poll_interval_sec", 1.0)
        self.declare_parameter("block_chunk", 1000)
        self.declare_parameter("checkpoint_file", "")
        self.declare_parameter("own_assignments_only", True)

        cfg_path = resolve_config_path(self.get_parameter("config_file").value)
        self.cfg = load_config(cfg_path)
        # HTTP provider: no websocket recv contention with the writer node.
        self.w3 = make_web3(self.cfg, prefer_http=True)
        self.reg = ContractRegistry(self.w3, self.cfg.contracts, self.cfg.abi_paths)

        self.own_address = None
        try:
            self.own_address = Web3.to_checksum_address(self.cfg.wallet.address)
        except Exception:
            pass
        self.own_only = bool(self.get_parameter("own_assignments_only").value)
        if self.own_only and not self.own_address:
            self.get_logger().warning(
                "own_assignments_only is set but wallet.address is missing: "
                "publishing every assignment")
            self.own_only = False

        # Query services
        self.create_service(GetService, "dao/get_service_by_id", self.srv_get_service)
        self.create_service(GetAllServices, "dao/get_all_services", self.srv_get_all_services)
        self.create_service(GetServicesByCreator, "dao/get_services_by_creator",
                            self.srv_get_services_by_creator)
        self.create_service(GetTask, "dao/get_task_by_id", self.srv_get_task)
        self.create_service(GetAllTasks, "dao/get_all_tasks", self.srv_get_all_tasks)
        self.create_service(GetTasksByCreator, "dao/get_tasks_by_creator",
                            self.srv_get_tasks_by_creator)

        # Event publishers
        self._pub = {
            "task_registered": self.create_publisher(TaskRegistered, "dao/task_registered", 50),
            "task_assigned": self.create_publisher(TaskAssignment, "dao/task_assigned", 50),
            "task_unassigned": self.create_publisher(TaskId, "dao/task_unassigned", 50),
            "task_verified": self.create_publisher(TaskId, "dao/task_verified", 50),
            "task_rejected": self.create_publisher(TaskRejection, "dao/task_rejected", 50),
            "service_registered": self.create_publisher(ServiceMeta, "dao/service_registered", 50),
            "service_busy": self.create_publisher(ServiceBusy, "dao/service_busy", 50),
        }

        ckpt_path = _checkpoint_path(self, self.get_parameter("checkpoint_file").value)
        self.poller = EthPoller(
            w3=self.w3,
            reg=self.reg,
            checkpoint=Checkpoint(ckpt_path),
            on_event=self._on_event,
            poll_interval=float(self.get_parameter("poll_interval_sec").value),
            block_chunk=int(self.get_parameter("block_chunk").value),
        )
        self.poller.start()

        self.get_logger().info(
            f"dao_listener ready - chain {self.w3.eth.chain_id}  config {cfg_path}  "
            f"checkpoint {ckpt_path}  "
            + (f"assignments for {self.own_address} only" if self.own_only
               else "all assignments"))

    # ------------------------------------------------------------------ queries
    def _creator(self, req_creator: str) -> str:
        creator = (req_creator or "").strip() or self.own_address
        if not creator:
            raise RuntimeError("creator not provided and wallet.address missing")
        return creator

    def srv_get_service(self, req, res):
        try:
            res.service = service_data_to_msg(get_service(self.reg, int(req.service_id)))
            res.ok = True
        except Exception as e:
            self.get_logger().warning(f"get_service {req.service_id} failed: {e}")
            res.ok, res.service = False, ServiceInfo()
        return res

    def srv_get_all_services(self, _req, res):
        try:
            res.services = [service_data_to_msg(s) for s in get_all_services(self.reg)]
            res.ok = True
        except Exception as e:
            self.get_logger().warning(f"get_all_services failed: {e}")
            res.ok, res.services = False, []
        return res

    def srv_get_services_by_creator(self, req, res):
        try:
            res.services = [service_data_to_msg(s) for s in
                            get_services_by_creator(self.reg, self._creator(req.creator))]
            res.ok = True
        except Exception as e:
            self.get_logger().warning(f"get_services_by_creator failed: {e}")
            res.ok, res.services = False, []
        return res

    def srv_get_task(self, req, res):
        try:
            res.task = task_data_to_msg(get_task(self.reg, int(req.task_id)))
            res.ok = True
        except Exception as e:
            self.get_logger().warning(f"get_task {req.task_id} failed: {e}")
            res.ok, res.task = False, TaskInfo()
        return res

    def srv_get_all_tasks(self, _req, res):
        try:
            res.tasks = [task_data_to_msg(t) for t in get_all_tasks(self.reg)]
            res.ok = True
        except Exception as e:
            self.get_logger().warning(f"get_all_tasks failed: {e}")
            res.ok, res.tasks = False, []
        return res

    def srv_get_tasks_by_creator(self, req, res):
        try:
            res.tasks = [task_data_to_msg(t) for t in
                         get_tasks_by_creator(self.reg, self._creator(req.creator))]
            res.ok = True
        except Exception as e:
            self.get_logger().warning(f"get_tasks_by_creator failed: {e}")
            res.ok, res.tasks = False, []
        return res

    # ------------------------------------------------------------------ events
    def _is_own(self, executor: str) -> bool:
        try:
            return Web3.to_checksum_address(executor) == self.own_address
        except Exception:
            return False

    def _on_event(self, event) -> None:
        try:
            if isinstance(event, TaskRegisteredEvent):
                self._pub["task_registered"].publish(TaskRegistered(
                    task_id=int(event.task_id), creator=str(event.creator),
                    block_number=int(event.block_number)))

            elif isinstance(event, TaskAssignedEvent):
                if self.own_only and not self._is_own(event.executor):
                    self.get_logger().debug(
                        f"task {event.task_id} assigned to {event.executor}: not ours")
                    return
                self._pub["task_assigned"].publish(TaskAssignment(
                    task_id=int(event.task_id), executor=str(event.executor),
                    reward_wei=str(event.reward_wei)))

            elif isinstance(event, TaskUnassignedEvent):
                self._pub["task_unassigned"].publish(TaskId(task_id=int(event.task_id)))

            elif isinstance(event, TaskVerifiedEvent):
                self._pub["task_verified"].publish(TaskId(task_id=int(event.task_id)))

            elif isinstance(event, TaskRejectedEvent):
                self._pub["task_rejected"].publish(TaskRejection(
                    task_id=int(event.task_id), reason=str(event.reason or "")))

            elif isinstance(event, ServiceRegisteredEvent):
                self._pub["service_registered"].publish(ServiceMeta(
                    id=int(event.service_id),
                    category_hash=_hash32(event.category_hash),
                    service_type_hash=_hash32(event.service_type_hash),
                    price_wei=str(event.price_wei),
                    creator=str(event.creator),
                    active=bool(event.active),
                    busy=bool(event.busy)))

            elif isinstance(event, ServiceBusyUpdatedEvent):
                self._pub["service_busy"].publish(ServiceBusy(
                    service_id=int(event.service_id), busy=bool(event.busy)))

        except Exception as exc:
            self.get_logger().error(
                f"failed to publish {type(event).__name__}: {exc}")


def main(args=None):
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] [%(name)s]: %(message)s")
    rclpy.init(args=args)
    node = DaoListener()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.poller.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

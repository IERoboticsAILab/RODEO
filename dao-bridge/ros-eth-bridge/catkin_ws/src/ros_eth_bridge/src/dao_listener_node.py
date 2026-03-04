#!/usr/bin/env python3
"""
dao_listener_node — read-only DAO interface (consolidates gateway + event listener).

Responsibilities
----------------
* Exposes 6 ROS services for querying tasks and services from the blockchain.
* Runs EthPoller in a daemon thread and publishes 7 ROS topics when DAO events
  are detected on-chain.

One HTTP Web3 connection is shared by both the query services and the poller,
avoiding websocket recv contention with the writer node.
"""
import os
import sys

import rospy
import rospkg
from web3 import Web3

pkg_path = rospkg.RosPack().get_path("ros_eth_bridge")
sys.path.insert(0, os.path.join(pkg_path, "src"))

from abi_loader import load_config, make_web3
from eth.contracts import ContractRegistry
from eth.dao.query import (
    get_task, get_all_tasks, get_tasks_by_creator,
    get_service, get_all_services, get_services_by_creator,
)
from eth.events.checkpoint import Checkpoint, CHECKPOINT_FILE
from eth.events.poller import EthPoller
from eth.events.decoder import (
    TaskRegisteredEvent, TaskAssignedEvent, TaskUnassignedEvent,
    TaskVerifiedEvent, TaskRejectedEvent,
    ServiceRegisteredEvent, ServiceBusyUpdatedEvent,
)
from bridge.converters import task_data_to_msg, service_data_to_msg

from ros_eth_msgs.msg import (
    ServiceInfo, TaskInfo,
    TaskId, TaskAssignment, TaskRejection,
    ServiceMeta, ServiceBusy, TaskRegistered,
)
from ros_eth_msgs.srv import (
    GetService, GetServiceResponse,
    GetAllServices, GetAllServicesResponse,
    GetServicesByCreator, GetServicesByCreatorResponse,
    GetTask, GetTaskResponse,
    GetAllTasks, GetAllTasksResponse,
    GetTasksByCreator, GetTasksByCreatorResponse,
)


class DaoListener:
    def __init__(self):
        rospy.init_node("dao_listener")

        self.cfg = load_config()
        # HTTP provider: avoids websocket recv contention with the writer node;
        # suitable for both synchronous service calls and event polling.
        self.w3 = make_web3(self.cfg, prefer_http=True)

        self.reg = ContractRegistry(self.w3, self.cfg.contracts, self.cfg.abi_paths)

        self.default_creator = None
        try:
            self.default_creator = Web3.to_checksum_address(self.cfg.wallet.address)
        except Exception:
            pass

        # ------------------------------------------------------------------ #
        # Query services
        # ------------------------------------------------------------------ #
        rospy.Service("/dao/get_service_by_id",       GetService,          self.srv_get_service)
        rospy.Service("/dao/get_all_services",         GetAllServices,      self.srv_get_all_services)
        rospy.Service("/dao/get_services_by_creator",  GetServicesByCreator, self.srv_get_services_by_creator)
        rospy.Service("/dao/get_task_by_id",           GetTask,             self.srv_get_task)
        rospy.Service("/dao/get_all_tasks",            GetAllTasks,         self.srv_get_all_tasks)
        rospy.Service("/dao/get_tasks_by_creator",     GetTasksByCreator,   self.srv_get_tasks_by_creator)

        # ------------------------------------------------------------------ #
        # Event publishers
        # ------------------------------------------------------------------ #
        self._pub = {
            "task_registered":    rospy.Publisher("/dao/task_registered",    TaskRegistered, queue_size=50),
            "task_assigned":      rospy.Publisher("/dao/task_assigned",      TaskAssignment, queue_size=50),
            "task_unassigned":    rospy.Publisher("/dao/task_unassigned",    TaskId,         queue_size=50),
            "task_verified":      rospy.Publisher("/dao/task_verified",      TaskId,         queue_size=50),
            "task_rejected":      rospy.Publisher("/dao/task_rejected",      TaskRejection,  queue_size=50),
            "service_registered": rospy.Publisher("/dao/service_registered", ServiceMeta,    queue_size=50),
            "service_busy":       rospy.Publisher("/dao/service_busy",       ServiceBusy,    queue_size=50),
        }

        self.poller = EthPoller(
            w3=self.w3,
            reg=self.reg,
            checkpoint=Checkpoint(CHECKPOINT_FILE),
            on_event=self._on_event,
            poll_interval=rospy.get_param("~poll_interval_sec", 1.0),
            block_chunk=rospy.get_param("~block_chunk", 1000),
        )
        self.poller.start()

        rospy.loginfo("dao_listener ready — chain %s", self.w3.eth.chain_id)

    # ------------------------------------------------------------------
    # Query service handlers
    # ------------------------------------------------------------------

    def srv_get_service(self, req):
        try:
            return GetServiceResponse(ok=True,
                service=service_data_to_msg(get_service(self.reg, int(req.service_id))))
        except Exception as e:
            rospy.logwarn("get_service %s failed: %s", req.service_id, e)
            return GetServiceResponse(ok=False, service=ServiceInfo())

    def srv_get_all_services(self, _req):
        try:
            return GetAllServicesResponse(ok=True,
                services=[service_data_to_msg(s) for s in get_all_services(self.reg)])
        except Exception as e:
            rospy.logwarn("get_all_services failed: %s", e)
            return GetAllServicesResponse(ok=False, services=[])

    def srv_get_services_by_creator(self, req):
        try:
            creator = req.creator.strip() or self.default_creator
            if not creator:
                raise RuntimeError("creator not provided and wallet.address missing")
            return GetServicesByCreatorResponse(ok=True,
                services=[service_data_to_msg(s) for s in get_services_by_creator(self.reg, creator)])
        except Exception as e:
            rospy.logwarn("get_services_by_creator failed: %s", e)
            return GetServicesByCreatorResponse(ok=False, services=[])

    def srv_get_task(self, req):
        try:
            return GetTaskResponse(ok=True,
                task=task_data_to_msg(get_task(self.reg, int(req.task_id))))
        except Exception as e:
            rospy.logwarn("get_task %s failed: %s", req.task_id, e)
            return GetTaskResponse(ok=False, task=TaskInfo())

    def srv_get_all_tasks(self, _req):
        try:
            return GetAllTasksResponse(ok=True,
                tasks=[task_data_to_msg(t) for t in get_all_tasks(self.reg)])
        except Exception as e:
            rospy.logwarn("get_all_tasks failed: %s", e)
            return GetAllTasksResponse(ok=False, tasks=[])

    def srv_get_tasks_by_creator(self, req):
        try:
            creator = req.creator.strip() or self.default_creator
            if not creator:
                raise RuntimeError("creator not provided and wallet.address missing")
            return GetTasksByCreatorResponse(ok=True,
                tasks=[task_data_to_msg(t) for t in get_tasks_by_creator(self.reg, creator)])
        except Exception as e:
            rospy.logwarn("get_tasks_by_creator failed: %s", e)
            return GetTasksByCreatorResponse(ok=False, tasks=[])

    # ------------------------------------------------------------------
    # Event → ROS message routing
    # ------------------------------------------------------------------

    def _on_event(self, event) -> None:
        try:
            if isinstance(event, TaskRegisteredEvent):
                self._pub["task_registered"].publish(TaskRegistered(
                    task_id=event.task_id, creator=event.creator,
                    block_number=event.block_number))

            elif isinstance(event, TaskAssignedEvent):
                self._pub["task_assigned"].publish(TaskAssignment(
                    task_id=event.task_id, executor=event.executor,
                    reward_wei=str(event.reward_wei)))

            elif isinstance(event, TaskUnassignedEvent):
                self._pub["task_unassigned"].publish(TaskId(task_id=event.task_id))

            elif isinstance(event, TaskVerifiedEvent):
                self._pub["task_verified"].publish(TaskId(task_id=event.task_id))

            elif isinstance(event, TaskRejectedEvent):
                self._pub["task_rejected"].publish(
                    TaskRejection(task_id=event.task_id, reason=event.reason))

            elif isinstance(event, ServiceRegisteredEvent):
                self._pub["service_registered"].publish(ServiceMeta(
                    id=event.service_id,
                    category_hash=list(bytearray(event.category_hash)),
                    service_type_hash=list(bytearray(event.service_type_hash)),
                    price_wei=str(event.price_wei),
                    creator=event.creator,
                    active=event.active,
                    busy=event.busy))

            elif isinstance(event, ServiceBusyUpdatedEvent):
                self._pub["service_busy"].publish(
                    ServiceBusy(service_id=event.service_id, busy=event.busy))

        except Exception as exc:
            rospy.logerr("dao_listener: failed to publish %s: %s",
                         type(event).__name__, exc)


def main():
    node = DaoListener()
    rospy.spin()
    node.poller.stop()


if __name__ == "__main__":
    main()

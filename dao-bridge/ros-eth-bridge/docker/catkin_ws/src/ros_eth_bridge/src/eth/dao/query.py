"""
eth/dao/query.py — Read-only queries against TaskManager and ServiceManager.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.
  - Returns plain Python dataclasses.  The bridge/converters.py layer is
    responsible for mapping these into ROS message types.
  - Every query has a fallback path (count-loop) to stay compatible with
    contract deployments that may not expose getAllTasks / getAllServices.

Usage
-----
    from eth.dao.query import get_all_tasks, get_service, TaskData, ServiceData

    tasks = get_all_tasks(reg)
    for t in tasks:
        print(t.id, t.description, t.reward_wei)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from web3 import Web3

from eth.contracts import ContractRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plain-Python result dataclasses (no ROS types)
# ---------------------------------------------------------------------------

@dataclass
class TaskData:
    """Mirrors the Task struct returned by TaskManager.getTask()."""
    id: int
    description: str
    category: str
    task_type: str
    creator: str
    reward_wei: int         # raw wei value
    status: int             # 0=Pending, 1=Assigned, 2=Completed, 3=Verified, 4=Rejected
    executor: str
    active: bool
    proof_uri: str
    verified: bool


@dataclass
class ServiceData:
    """Mirrors the Service struct returned by ServiceManager.getService()."""
    id: int
    name: str
    description: str
    category: str
    service_type: str
    price_wei: int          # raw wei value
    creator: str
    active: bool
    provider_type: int
    busy: bool


# ---------------------------------------------------------------------------
# Internal unpack helpers
# ---------------------------------------------------------------------------

def _unpack_task(t) -> TaskData:
    # Task struct layout (index → field):
    # 0=id  1=description  2=taskCategory  3=taskType
    # 4=categoryHash(bytes32)  5=taskTypeHash(bytes32)
    # 6=creator  7=reward  8=status  9=executor
    # 10=active  11=proofURI  12=oracle  13=verified
    return TaskData(
        id=int(t[0]),
        description=str(t[1]),
        category=str(t[2]),
        task_type=str(t[3]),
        creator=str(t[6]),
        reward_wei=int(t[7]),
        status=int(t[8]),
        executor=str(t[9]),
        active=bool(t[10]),
        proof_uri=str(t[11]),
        verified=bool(t[13]),
    )


def _unpack_service(s) -> ServiceData:
    # Service struct layout (index → field):
    # 0=id  1=name  2=description  3=serviceCategory  4=serviceType
    # 5=categoryHash(bytes32)  6=serviceTypeHash(bytes32)
    # 7=price  8=creator  9=active  10=providerType  11=busy
    return ServiceData(
        id=int(s[0]),
        name=str(s[1]),
        description=str(s[2]),
        category=str(s[3]),
        service_type=str(s[4]),
        price_wei=int(s[7]),
        creator=str(s[8]),
        active=bool(s[9]),
        provider_type=int(s[10]),
        busy=bool(s[11]),
    )


# ---------------------------------------------------------------------------
# Task queries
# ---------------------------------------------------------------------------

def get_task(reg: ContractRegistry, task_id: int) -> TaskData:
    t = reg.task_manager.functions.getTask(task_id).call()
    return _unpack_task(t)


def get_all_tasks(reg: ContractRegistry) -> List[TaskData]:
    """Fetch all tasks; falls back to a count-loop if getAllTasks() is absent."""
    try:
        items = reg.task_manager.functions.getAllTasks().call()
        return [_unpack_task(t) for t in items]
    except Exception as exc:
        logger.debug("getAllTasks() failed (%s), falling back to count loop", exc)

    n = int(reg.task_manager.functions.getTotalTasks().call())
    return [_unpack_task(reg.task_manager.functions.getTask(i).call()) for i in range(1, n + 1)]


def get_tasks_by_creator(reg: ContractRegistry, creator: str) -> List[TaskData]:
    creator = Web3.to_checksum_address(creator)
    ids = reg.task_manager.functions.getTasksByCreator(creator).call()
    return [_unpack_task(reg.task_manager.functions.getTask(int(tid)).call()) for tid in ids]


# ---------------------------------------------------------------------------
# Service queries
# ---------------------------------------------------------------------------

def get_service(reg: ContractRegistry, service_id: int) -> ServiceData:
    s = reg.service_manager.functions.getService(service_id).call()
    return _unpack_service(s)


def get_all_services(reg: ContractRegistry) -> List[ServiceData]:
    """Fetch all services; falls back to a count-loop if getAllServices() is absent."""
    try:
        items = reg.service_manager.functions.getAllServices().call()
        return [_unpack_service(s) for s in items]
    except Exception as exc:
        logger.debug("getAllServices() failed (%s), falling back to count loop", exc)

    n = int(reg.service_manager.functions.getServiceCount().call())
    return [_unpack_service(reg.service_manager.functions.getService(i).call()) for i in range(1, n + 1)]


def get_services_by_creator(reg: ContractRegistry, creator: str) -> List[ServiceData]:
    creator = Web3.to_checksum_address(creator)
    ids = reg.service_manager.functions.getServicesByCreator(creator).call()
    return [_unpack_service(reg.service_manager.functions.getService(int(sid)).call()) for sid in ids]

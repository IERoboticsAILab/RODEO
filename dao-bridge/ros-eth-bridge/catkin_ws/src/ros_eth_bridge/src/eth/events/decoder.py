"""
eth/events/decoder.py — Typed Python dataclasses for every DAO contract event.

Each ``decode_*`` function receives the raw ``args`` AttributeDict from a
web3 log entry and returns a typed dataclass.  The ``ServiceRegistered``
event additionally requires a live contract call to fetch off-chain metadata —
the contract object is passed explicitly to keep this module side-effect free
at import time.

No rospy / ros_eth_msgs imports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from web3 import Web3

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _to_bytes32(x) -> bytes:
    """Coerce any web3 bytes32 representation to exactly 32 raw bytes."""
    if isinstance(x, (bytes, bytearray)) and len(x) == 32:
        return bytes(x)
    try:
        b = bytes(x)
        if len(b) == 32:
            return b
    except Exception:
        pass
    return Web3.to_bytes(hexstr=Web3.to_hex(x)).rjust(32, b"\x00")


# ---------------------------------------------------------------------------
# TaskManager events
# ---------------------------------------------------------------------------

@dataclass
class TaskRegisteredEvent:
    task_id: int
    creator: str
    block_number: int


@dataclass
class TaskAssignedEvent:
    task_id: int
    executor: str       # fetched from contract (not in log args)
    reward_wei: int     # fetched from contract


@dataclass
class TaskUnassignedEvent:
    task_id: int


@dataclass
class TaskVerifiedEvent:
    task_id: int


@dataclass
class TaskRejectedEvent:
    task_id: int
    reason: str


# ---------------------------------------------------------------------------
# ServiceManager events
# ---------------------------------------------------------------------------

@dataclass
class ServiceRegisteredEvent:
    service_id: int
    category_hash: bytes    # 32 bytes
    service_type_hash: bytes  # 32 bytes
    price_wei: int
    creator: str
    active: bool
    busy: bool


@dataclass
class ServiceBusyUpdatedEvent:
    service_id: int
    busy: bool


# ---------------------------------------------------------------------------
# Decode functions
# ---------------------------------------------------------------------------

def decode_task_registered(args, block_number: int) -> TaskRegisteredEvent:
    return TaskRegisteredEvent(
        task_id=int(args["taskId"]),
        creator=str(args["creator"]),
        block_number=block_number,
    )


def decode_task_assigned(args, task_manager_contract) -> TaskAssignedEvent:
    """
    The TaskAssigned event only carries the taskId; the executor and reward
    are read from the contract so the consumer always gets consistent data.
    """
    tid = int(args["taskId"])
    try:
        t = task_manager_contract.functions.getTask(tid).call()
        executor = str(t[9])   # address executor  (struct index 9)
        reward   = int(t[7])   # uint256 reward     (struct index 7)
    except Exception as exc:
        logger.warning("decode_task_assigned: getTask(%d) failed: %s", tid, exc)
        executor = ""
        reward = 0
    return TaskAssignedEvent(task_id=tid, executor=executor, reward_wei=reward)


def decode_task_unassigned(args) -> TaskUnassignedEvent:
    return TaskUnassignedEvent(task_id=int(args["taskId"]))


def decode_task_verified(args) -> TaskVerifiedEvent:
    return TaskVerifiedEvent(task_id=int(args["taskId"]))


def decode_task_rejected(args) -> TaskRejectedEvent:
    return TaskRejectedEvent(
        task_id=int(args["taskId"]),
        reason=str(args.get("reason", "")),
    )


def decode_service_registered(args, service_manager_contract) -> ServiceRegisteredEvent:
    """
    Fetch the full service metadata via ``getServiceMeta`` so that all fields
    are available even when the log only carries the service ID.
    """
    sid = int(args["serviceId"])
    try:
        meta = service_manager_contract.functions.getServiceMeta(sid).call()
        # struct layout: sid, categoryHash, serviceTypeHash, price, creator, active, busy
        return ServiceRegisteredEvent(
            service_id=int(meta[0]),
            category_hash=_to_bytes32(meta[1]),
            service_type_hash=_to_bytes32(meta[2]),
            price_wei=int(meta[3]),
            creator=str(meta[4]),
            active=bool(meta[5]),
            busy=bool(meta[6]),
        )
    except Exception as exc:
        logger.warning("decode_service_registered: getServiceMeta(%d) failed: %s", sid, exc)
        return ServiceRegisteredEvent(
            service_id=sid,
            category_hash=b"\x00" * 32,
            service_type_hash=b"\x00" * 32,
            price_wei=0,
            creator="",
            active=False,
            busy=False,
        )


def decode_service_busy_updated(args) -> ServiceBusyUpdatedEvent:
    return ServiceBusyUpdatedEvent(
        service_id=int(args["serviceId"]),
        busy=bool(args["busy"]),
    )

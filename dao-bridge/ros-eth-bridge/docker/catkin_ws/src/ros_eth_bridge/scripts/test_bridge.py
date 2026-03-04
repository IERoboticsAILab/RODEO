#!/usr/bin/env python3
"""
test_bridge.py — Functional end-to-end test of the ROS-ETH bridge.

Validates every action and service exposed by dao_writer_node and
dao_listener_node against a live local ganache chain.

Prerequisites
-------------
  1. Ganache running:  npx ganache --deterministic --chainId 1337
  2. Contracts deployed and addresses matching config/dao.yaml
  3. Both bridge nodes launched:
       roslaunch ros_eth_bridge ros_eth_gateway.launch

Usage
-----
  rosrun ros_eth_bridge test_bridge.py
  # or directly (after sourcing the workspace):
  python3 scripts/test_bridge.py

Optional env vars
-----------------
  SECONDARY_ADDR  Ethereum address used as transfer target.
                  Defaults to Ganache deterministic account[5].
  REWARD_IEC      Integer IEC amount to use for task reward / service price.
                  Defaults to 5.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import traceback
from typing import Callable, List, Optional, Tuple

import actionlib
import rospy

# ── action types ────────────────────────────────────────────────────────────
from ros_eth_msgs.msg import (
    ActivateServiceAction, ActivateServiceGoal,
    ActivateTaskAction, ActivateTaskGoal,
    ApproveSpenderAction, ApproveSpenderGoal,
    RegisterServiceAction, RegisterServiceGoal,
    RegisterTaskAction, RegisterTaskGoal,
    RemoveServiceAction, RemoveServiceGoal,
    RemoveTaskAction, RemoveTaskGoal,
    SetServiceBusyAction, SetServiceBusyGoal,
    TransferTokenAction, TransferTokenGoal,
    # event message types (used by topic subscription tests)
    ServiceBusy, ServiceMeta,
    TaskAssignment, TaskRegistered,
)

# ── service types ────────────────────────────────────────────────────────────
from ros_eth_msgs.srv import (
    GetAllServices, GetAllServicesRequest,
    GetAllTasks, GetAllTasksRequest,
    GetAllowance, GetAllowanceRequest,
    GetBalance, GetBalanceRequest,
    GetService, GetServiceRequest,
    GetServicesByCreator, GetServicesByCreatorRequest,
    GetTask, GetTaskRequest,
    GetTasksByCreator, GetTasksByCreatorRequest,
)

# ────────────────────────────────────────────────────────────────────────────
# Config
# ────────────────────────────────────────────────────────────────────────────

# Ganache deterministic account[5] — a safe recipient distinct from the wallet
_DEFAULT_SECONDARY = "0xBcd4042DE499D14e55001CcbB24a551F3b954096"

SECONDARY_ADDR: str = os.environ.get("SECONDARY_ADDR", _DEFAULT_SECONDARY)
REWARD_IEC: int = int(os.environ.get("REWARD_IEC", "5"))

# Shared category/type so task ↔ service auto-assignment fires
TEST_CATEGORY = "bridge_test_cat"
TEST_TYPE     = "bridge_test_type"

# Action call timeout (seconds) — ganache mines instantly, so 30 s is generous
ACTION_TIMEOUT = 30.0
# Service call timeout
SRV_TIMEOUT = 10.0
# Event topic timeout — must cover at least one full poll cycle (default 1 s)
# plus action execution time.  15 s is conservative.
EVENT_TIMEOUT = 15.0

# Category/type used for event subscription tests so they don't overlap with
# the action-layer tests that use TEST_CATEGORY / TEST_TYPE.
EV_SVC_CAT  = "ev_svc_cat_001"
EV_SVC_TYPE = "ev_svc_type_001"

# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"

Results: List[Tuple[str, bool, str]] = []


def _record(name: str, ok: bool, note: str = "") -> None:
    Results.append((name, ok, note))
    tag = f"{_GREEN}PASS{_RESET}" if ok else f"{_RED}FAIL{_RESET}"
    suffix = f"  ({note})" if note else ""
    rospy.loginfo("[%s] %-45s %s%s", tag, name, "" , suffix)


def _make_client(action_ns: str, ActionSpec) -> actionlib.SimpleActionClient:
    client = actionlib.SimpleActionClient(action_ns, ActionSpec)
    rospy.logdebug("Waiting for action server %s …", action_ns)
    client.wait_for_server(rospy.Duration(20.0))
    return client


def _call_action(client: actionlib.SimpleActionClient, goal, timeout=ACTION_TIMEOUT):
    """Returns (succeeded: bool, result)."""
    client.send_goal(goal)
    finished = client.wait_for_result(rospy.Duration(timeout))
    if not finished:
        return False, None
    result = client.get_result()
    return (result is not None and result.ok), result


def _call_srv(proxy, request):
    """Returns the response or raises."""
    return proxy(request)


def _wei_to_iec(wei_str: str) -> float:
    try:
        return int(wei_str) / 1e18
    except Exception:
        return 0.0


def _wait_for_event(topic: str, MsgType, trigger_fn: Optional[Callable] = None,
                    predicate: Optional[Callable] = None,
                    timeout: float = EVENT_TIMEOUT):
    """
    Subscribe to a ROS topic, call trigger_fn(), then block until a message
    arrives that satisfies predicate (or any message if predicate is None).

    Returns (received: bool, msg).  The subscriber is always unregistered on
    return.

    Implementation notes
    --------------------
    * We set a sentinel *after* creating the subscriber so that any messages
      already buffered in the topic queue (from previous tests) are silently
      dropped.
    * The 100 ms pause before setting the sentinel gives the ROS subscriber
      thread time to flush any in-flight messages before we start timing.
    """
    ready   = threading.Event()
    matched: list = [None]
    armed   = threading.Event()   # set once trigger_fn has been called

    def _cb(msg):
        if not armed.is_set():
            return   # ignore pre-trigger buffered messages
        if predicate is None or predicate(msg):
            matched[0] = msg
            ready.set()

    sub = rospy.Subscriber(topic, MsgType, _cb, queue_size=50)
    time.sleep(0.15)   # let subscriber thread drain any pre-existing queue
    armed.set()        # from now on callbacks are live
    try:
        if trigger_fn is not None:
            trigger_fn()
        ok = ready.wait(timeout)
        return ok, matched[0]
    finally:
        sub.unregister()


# ────────────────────────────────────────────────────────────────────────────
# Test cases
# ────────────────────────────────────────────────────────────────────────────

class BridgeTestSuite:
    """
    Each test_* method is a single functional check.
    Shared state (service_id, task_id, …) is stored on self so later tests
    can reference what earlier ones created.
    """

    def __init__(self):
        # ── action clients ──────────────────────────────────────────────────
        rospy.loginfo("Connecting to action servers …")
        self.ac_register_task    = _make_client("/dao/register_task_action",      RegisterTaskAction)
        self.ac_remove_task      = _make_client("/dao/remove_task_action",        RemoveTaskAction)
        self.ac_activate_task    = _make_client("/dao/activate_task_action",      ActivateTaskAction)
        self.ac_register_service = _make_client("/dao/register_service_action",   RegisterServiceAction)
        self.ac_remove_service   = _make_client("/dao/remove_service_action",     RemoveServiceAction)
        self.ac_activate_service = _make_client("/dao/activate_service_action",   ActivateServiceAction)
        self.ac_set_busy         = _make_client("/dao/set_service_busy_action",   SetServiceBusyAction)
        self.ac_transfer         = _make_client("/dao/transfer_token_action",     TransferTokenAction)
        self.ac_approve          = _make_client("/dao/approve_spender_action",    ApproveSpenderAction)

        # ── service proxies ─────────────────────────────────────────────────
        rospy.loginfo("Connecting to ROS services …")
        _w = lambda ns, T: rospy.ServiceProxy(ns, T)  # noqa: E731
        self.srv_balance         = _w("/dao/get_balance",           GetBalance)
        self.srv_allowance       = _w("/dao/get_allowance",         GetAllowance)
        self.srv_all_tasks       = _w("/dao/get_all_tasks",         GetAllTasks)
        self.srv_task_by_id      = _w("/dao/get_task_by_id",        GetTask)
        self.srv_tasks_creator   = _w("/dao/get_tasks_by_creator",  GetTasksByCreator)
        self.srv_all_services    = _w("/dao/get_all_services",      GetAllServices)
        self.srv_service_by_id   = _w("/dao/get_service_by_id",     GetService)
        self.srv_svcs_creator    = _w("/dao/get_services_by_creator", GetServicesByCreator)

        # state shared between tests
        self.service_id: Optional[int] = None           # set by T06 (used through T11)
        self.task_id_assigned: Optional[int] = None     # set by T12 (auto-assigned)
        self.task_id_free: Optional[int] = None          # set by T16 (no match, removed T17)
        self.service_id_rm: Optional[int] = None         # set by T18 (dedicated remove test)
        self.task_id_rm: Optional[int] = None            # set by T20 (dedicated remove/activate)
        self.service_id_ev: Optional[int] = None         # set by T21 (event topic tests)

    # ──────────────────────────────────────────────────────────────────
    # T01 — get_balance (smoke test + discover wallet addr)
    # ──────────────────────────────────────────────────────────────────
    def test_01_get_balance(self):
        resp = self.srv_balance(GetBalanceRequest(owner=""))  # empty → uses wallet
        ok = resp.ok and int(resp.balance_wei) >= 0
        _record("T01 get_balance (self)", ok,
                f"{_wei_to_iec(resp.balance_wei):.1f} IEC" if ok else resp.balance_wei)

    # ──────────────────────────────────────────────────────────────────
    # T02 — transfer_token to secondary address
    # ──────────────────────────────────────────────────────────────────
    def test_02_transfer_token(self):
        bal_before_resp = self.srv_balance(GetBalanceRequest(owner=SECONDARY_ADDR))
        bal_before = int(bal_before_resp.balance_wei) if bal_before_resp.ok else 0

        goal = TransferTokenGoal(to=SECONDARY_ADDR, amount="1")
        ok, result = _call_action(self.ac_transfer, goal)
        if not ok:
            _record("T02 transfer_token", False,
                    getattr(result, "tx_hash", "timeout/no result"))
            return

        # verify balance increased on secondary
        time.sleep(1)
        bal_after_resp = self.srv_balance(GetBalanceRequest(owner=SECONDARY_ADDR))
        bal_after = int(bal_after_resp.balance_wei) if bal_after_resp.ok else 0
        increased = bal_after > bal_before
        _record("T02 transfer_token", ok and increased,
                f"secondary balance {_wei_to_iec(str(bal_after)):.1f} IEC"
                f" (was {_wei_to_iec(str(bal_before)):.1f})")

    # ──────────────────────────────────────────────────────────────────
    # T03 — get_balance for secondary address
    # ──────────────────────────────────────────────────────────────────
    def test_03_get_balance_secondary(self):
        resp = self.srv_balance(GetBalanceRequest(owner=SECONDARY_ADDR))
        ok = resp.ok and int(resp.balance_wei) > 0
        _record("T03 get_balance (secondary)", ok,
                f"{_wei_to_iec(resp.balance_wei):.1f} IEC" if ok
                else "zero or error")

    # ──────────────────────────────────────────────────────────────────
    # T04 — approve_spender (let TaskManager spend on behalf of wallet)
    # ──────────────────────────────────────────────────────────────────
    def test_04_approve_spender(self):
        # We approve a non-zero amount to a fixed target address (the
        # service_manager contract address is fine as a spender placeholder)
        spender = SECONDARY_ADDR  # any valid checksummed address
        goal = ApproveSpenderGoal(spender=spender, amount="10")
        ok, result = _call_action(self.ac_approve, goal)
        _record("T04 approve_spender", ok,
                getattr(result, "tx_hash", "")[:12] + "…" if ok else "failed")

    # ──────────────────────────────────────────────────────────────────
    # T05 — get_allowance
    # ──────────────────────────────────────────────────────────────────
    def test_05_get_allowance(self):
        resp = self.srv_allowance(
            GetAllowanceRequest(owner="", spender=SECONDARY_ADDR))
        ok = resp.ok and int(resp.allowance_wei) > 0
        _record("T05 get_allowance", ok,
                f"{_wei_to_iec(resp.allowance_wei):.1f} IEC" if ok else "0 or error")

    # ──────────────────────────────────────────────────────────────────
    # T06 — register_service (matching category/type for auto-assignment)
    # ──────────────────────────────────────────────────────────────────
    def test_06_register_service(self):
        goal = RegisterServiceGoal(
            name="TestServiceBot",
            description="Automated test service",
            category=TEST_CATEGORY,
            service_type=TEST_TYPE,
            price=str(REWARD_IEC),   # price == task reward → triggers assignment
            provider_type=0,
        )
        ok, result = _call_action(self.ac_register_service, goal)
        _record("T06 register_service", ok,
                getattr(result, "tx_hash", "")[:12] + "…" if ok else "failed")
        if not ok:
            return

        # discover the new service_id via get_all_services
        time.sleep(1)
        resp = self.srv_all_services(GetAllServicesRequest())
        if resp.ok and resp.services:
            matching = [s for s in resp.services
                        if s.category == TEST_CATEGORY and s.service_type == TEST_TYPE]
            if matching:
                self.service_id = matching[-1].id

    # ──────────────────────────────────────────────────────────────────
    # T07 — get_all_services (verify service appears)
    # ──────────────────────────────────────────────────────────────────
    def test_07_get_all_services(self):
        resp = self.srv_all_services(GetAllServicesRequest())
        found = resp.ok and any(
            s.category == TEST_CATEGORY for s in resp.services)
        _record("T07 get_all_services", found,
                f"{len(resp.services)} service(s)" if resp.ok else "error")

    # ──────────────────────────────────────────────────────────────────
    # T08 — get_services_by_creator
    # ──────────────────────────────────────────────────────────────────
    def test_08_get_services_by_creator(self):
        resp = self.srv_svcs_creator(GetServicesByCreatorRequest(creator=""))
        found = resp.ok and any(
            s.category == TEST_CATEGORY for s in resp.services)
        _record("T08 get_services_by_creator", found,
                f"{len(resp.services)} service(s)" if resp.ok else "error")

    # ──────────────────────────────────────────────────────────────────
    # T09 — get_service_by_id
    # ──────────────────────────────────────────────────────────────────
    def test_09_get_service_by_id(self):
        if self.service_id is None:
            _record("T09 get_service_by_id", False, "no service_id (T06 failed?)")
            return
        resp = self.srv_service_by_id(GetServiceRequest(service_id=self.service_id))
        ok = (resp.ok
              and resp.service.category == TEST_CATEGORY
              and resp.service.service_type == TEST_TYPE
              and int(resp.service.price_wei) == REWARD_IEC * (10 ** 18))
        _record("T09 get_service_by_id", ok,
                f"id={self.service_id} price_wei={resp.service.price_wei}" if resp.ok
                else "error")

    # ──────────────────────────────────────────────────────────────────
    # T10 — set_service_busy True
    # ──────────────────────────────────────────────────────────────────
    def test_10_set_service_busy_true(self):
        if self.service_id is None:
            _record("T10 set_service_busy=True", False, "no service_id")
            return
        goal = SetServiceBusyGoal(service_id=self.service_id, is_busy=True)
        ok, result = _call_action(self.ac_set_busy, goal)
        if ok:
            time.sleep(1)
            resp = self.srv_service_by_id(GetServiceRequest(service_id=self.service_id))
            ok = ok and resp.ok and resp.service.busy
        _record("T10 set_service_busy=True", ok)

    # ──────────────────────────────────────────────────────────────────
    # T11 — set_service_busy False
    # ──────────────────────────────────────────────────────────────────
    def test_11_set_service_busy_false(self):
        if self.service_id is None:
            _record("T11 set_service_busy=False", False, "no service_id")
            return
        goal = SetServiceBusyGoal(service_id=self.service_id, is_busy=False)
        ok, result = _call_action(self.ac_set_busy, goal)
        if ok:
            time.sleep(1)
            resp = self.srv_service_by_id(GetServiceRequest(service_id=self.service_id))
            ok = ok and resp.ok and not resp.service.busy
        _record("T11 set_service_busy=False", ok)

    # ──────────────────────────────────────────────────────────────────
    # T12 — register_task (same category/type/reward → auto-assignment)
    # ──────────────────────────────────────────────────────────────────
    def test_12_register_task_auto_assign(self):
        goal = RegisterTaskGoal(
            description="Automated test task (auto-assign)",
            category=TEST_CATEGORY,
            task_type=TEST_TYPE,
            reward=str(REWARD_IEC),
        )
        ok, result = _call_action(self.ac_register_task, goal)
        _record("T12 register_task (auto-assign)", ok,
                getattr(result, "tx_hash", "")[:12] + "…" if ok else "failed")
        if not ok:
            return

        time.sleep(1)
        resp = self.srv_all_tasks(GetAllTasksRequest())
        if resp.ok:
            matching = [t for t in resp.tasks
                        if t.category == TEST_CATEGORY and t.task_type == TEST_TYPE]
            if matching:
                self.task_id_assigned = matching[-1].id

    # ──────────────────────────────────────────────────────────────────
    # T13 — verify task was auto-assigned (executor != "")
    # ──────────────────────────────────────────────────────────────────
    def test_13_verify_auto_assignment(self):
        if self.task_id_assigned is None:
            _record("T13 verify auto-assignment", False, "no task_id (T12 failed?)")
            return
        resp = self.srv_task_by_id(GetTaskRequest(task_id=self.task_id_assigned))
        assigned = (resp.ok
                    and resp.task.executor.strip() not in ("", "0x0000000000000000000000000000000000000000"))
        _record("T13 verify auto-assignment", assigned,
                f"executor={resp.task.executor[:10]}…" if resp.ok and assigned
                else "executor is zero or error")

    # ──────────────────────────────────────────────────────────────────
    # T14 — get_all_tasks
    # ──────────────────────────────────────────────────────────────────
    def test_14_get_all_tasks(self):
        resp = self.srv_all_tasks(GetAllTasksRequest())
        found = resp.ok and any(t.category == TEST_CATEGORY for t in resp.tasks)
        _record("T14 get_all_tasks", found,
                f"{len(resp.tasks)} task(s)" if resp.ok else "error")

    # ──────────────────────────────────────────────────────────────────
    # T15 — get_tasks_by_creator
    # ──────────────────────────────────────────────────────────────────
    def test_15_get_tasks_by_creator(self):
        resp = self.srv_tasks_creator(GetTasksByCreatorRequest(creator=""))
        found = resp.ok and any(t.category == TEST_CATEGORY for t in resp.tasks)
        _record("T15 get_tasks_by_creator", found,
                f"{len(resp.tasks)} task(s)" if resp.ok else "error")

    # ──────────────────────────────────────────────────────────────────
    # T16 — register_task with NO matching service → registers, no executor
    # ──────────────────────────────────────────────────────────────────
    def test_16_register_task_no_match(self):
        goal = RegisterTaskGoal(
            description="Unmatched test task",
            category="non_existent_cat_xyz",
            task_type="non_existent_type_xyz",
            reward=str(REWARD_IEC),
        )
        ok, result = _call_action(self.ac_register_task, goal)
        _record("T16 register_task (no match, no executor)", ok,
                getattr(result, "tx_hash", "")[:12] + "…" if ok else "failed")
        if not ok:
            return

        time.sleep(1)
        resp = self.srv_all_tasks(GetAllTasksRequest())
        if resp.ok:
            matching = [t for t in resp.tasks
                        if t.category == "non_existent_cat_xyz"]
            if matching:
                t = matching[-1]
                self.task_id_free = t.id
                executor_zero = t.executor.strip() in (
                    "", "0x0000000000000000000000000000000000000000")
                _record("T16b task has no executor", executor_zero,
                        f"executor={t.executor[:10]}…")

    # ──────────────────────────────────────────────────────────────────
    # T17 — remove_task (the unassigned one)
    # ──────────────────────────────────────────────────────────────────
    def test_17_remove_task_unassigned(self):
        if self.task_id_free is None:
            _record("T17 remove_task (unassigned)", False, "no task_id (T16 failed?)")
            return
        goal = RemoveTaskGoal(task_id=self.task_id_free)
        ok, result = _call_action(self.ac_remove_task, goal)
        if ok:
            time.sleep(1)
            resp = self.srv_task_by_id(GetTaskRequest(task_id=self.task_id_free))
            # after removal the task should be inactive
            ok = ok and resp.ok and not resp.task.active
        _record("T17 remove_task (unassigned)", ok)

    # ──────────────────────────────────────────────────────────────────
    # T18 — register a fresh service, then remove it
    #
    # We cannot remove self.service_id (from T06) because it has the
    # auto-assigned task from T12 still attached — the contract refuses
    # removal of a service that owns an active task.  Use a separate,
    # unmatched service so the test is fully isolated.
    # ──────────────────────────────────────────────────────────────────
    def test_18_remove_service(self):
        # Register a dedicated service with a unique category so it never
        # gets a task auto-assigned to it.
        reg_goal = RegisterServiceGoal(
            name="RemoveTestService",
            description="Dedicated service for remove/activate test",
            category="rm_test_cat_xyz",
            service_type="rm_test_type_xyz",
            price=str(REWARD_IEC),
            provider_type=0,
        )
        reg_ok, _ = _call_action(self.ac_register_service, reg_goal)
        if not reg_ok:
            _record("T18 remove_service", False, "could not register test service")
            return
        time.sleep(1)

        # discover its id
        resp = self.srv_all_services(GetAllServicesRequest())
        if not resp.ok:
            _record("T18 remove_service", False, "get_all_services failed")
            return
        matching = [s for s in resp.services if s.category == "rm_test_cat_xyz"]
        if not matching:
            _record("T18 remove_service", False, "registered service not found")
            return
        self.service_id_rm = matching[-1].id

        # now remove it
        goal = RemoveServiceGoal(service_id=self.service_id_rm)
        ok, result = _call_action(self.ac_remove_service, goal)
        if ok:
            time.sleep(1)
            resp2 = self.srv_service_by_id(GetServiceRequest(service_id=self.service_id_rm))
            ok = ok and resp2.ok and not resp2.service.active
        _record("T18 remove_service", ok,
                f"id={self.service_id_rm}" if self.service_id_rm else "")

    # ──────────────────────────────────────────────────────────────────
    # T19 — activate_service (re-activate the one removed in T18)
    # ──────────────────────────────────────────────────────────────────
    def test_19_activate_service(self):
        if self.service_id_rm is None:
            _record("T19 activate_service", False, "no service_id (T18 failed?)")
            return
        goal = ActivateServiceGoal(service_id=self.service_id_rm)
        ok, result = _call_action(self.ac_activate_service, goal)
        if ok:
            time.sleep(1)
            resp = self.srv_service_by_id(GetServiceRequest(service_id=self.service_id_rm))
            ok = ok and resp.ok and resp.service.active
        _record("T19 activate_service", ok,
                f"id={self.service_id_rm}" if self.service_id_rm else "")

    # ──────────────────────────────────────────────────────────────────
    # T20 — register a fresh unassigned task, remove it, then re-activate
    #
    # We cannot remove task_id_assigned (T12) because the contract
    # disallows removing a task that already has an executor assigned.
    # Use a brand-new task with a unique category for a clean cycle.
    # ──────────────────────────────────────────────────────────────────
    def test_20_activate_task(self):
        # Register a fresh task (unique category → no auto-assignment)
        reg_goal = RegisterTaskGoal(
            description="Dedicated task for remove/activate test",
            category="rm_task_cat_xyz",
            task_type="rm_task_type_xyz",
            reward=str(REWARD_IEC),
        )
        reg_ok, _ = _call_action(self.ac_register_task, reg_goal)
        if not reg_ok:
            _record("T20 activate_task", False, "could not register test task")
            return
        time.sleep(1)

        # discover its id
        resp = self.srv_all_tasks(GetAllTasksRequest())
        if not resp.ok:
            _record("T20 activate_task", False, "get_all_tasks failed")
            return
        matching = [t for t in resp.tasks if t.category == "rm_task_cat_xyz"]
        if not matching:
            _record("T20 activate_task", False, "registered task not found")
            return
        self.task_id_rm = matching[-1].id

        # remove it
        rem_ok, _ = _call_action(self.ac_remove_task,
                                 RemoveTaskGoal(task_id=self.task_id_rm))
        if not rem_ok:
            _record("T20 activate_task", False, "remove step failed")
            return
        time.sleep(1)

        # re-activate it
        goal = ActivateTaskGoal(task_id=self.task_id_rm)
        ok, result = _call_action(self.ac_activate_task, goal)
        if ok:
            time.sleep(1)
            resp2 = self.srv_task_by_id(GetTaskRequest(task_id=self.task_id_rm))
            ok = ok and resp2.ok and resp2.task.active
        _record("T20 activate_task", ok,
                f"id={self.task_id_rm}" if self.task_id_rm else "")

    # ══════════════════════════════════════════════════════════════════
    # EVENT TOPIC TESTS  (T21 – T24)
    # Each test subscribes to a /dao/* topic BEFORE triggering the
    # on-chain action, then waits for the expected message to arrive.
    # The poller runs every ~1 s, so EVENT_TIMEOUT = 15 s is generous.
    # ══════════════════════════════════════════════════════════════════

    # ──────────────────────────────────────────────────────────────────
    # T21 — /dao/service_registered fires when register_service is called
    # ──────────────────────────────────────────────────────────────────
    def test_21_event_service_registered(self):
        def _trigger():
            goal = RegisterServiceGoal(
                name="EventTestService",
                description="Service for event topic test",
                category=EV_SVC_CAT,
                service_type=EV_SVC_TYPE,
                price=str(REWARD_IEC),
                provider_type=0,
            )
            _call_action(self.ac_register_service, goal)

        ok, msg = _wait_for_event(
            "/dao/service_registered", ServiceMeta,
            trigger_fn=_trigger,
            predicate=lambda m: m.creator.strip() not in ("", "0x" + "0" * 40),
        )
        if ok and msg is not None:
            self.service_id_ev = int(msg.id)
        _record("T21 event /dao/service_registered", ok,
                f"id={self.service_id_ev}" if ok else "timeout – no message received")

    # ──────────────────────────────────────────────────────────────────
    # T22 — /dao/task_registered fires when register_task is called
    # ──────────────────────────────────────────────────────────────────
    def test_22_event_task_registered(self):
        def _trigger():
            goal = RegisterTaskGoal(
                description="Task for event topic test",
                category="ev_task_cat_001",
                task_type="ev_task_type_001",
                reward=str(REWARD_IEC),
            )
            _call_action(self.ac_register_task, goal)

        ok, msg = _wait_for_event(
            "/dao/task_registered", TaskRegistered,
            trigger_fn=_trigger,
            predicate=lambda m: m.task_id > 0,
        )
        _record("T22 event /dao/task_registered", ok,
                f"task_id={msg.task_id} block={msg.block_number}" if ok and msg
                else "timeout – no message received")

    # ──────────────────────────────────────────────────────────────────
    # T23 — /dao/task_assigned fires when task auto-assigns to a service
    #
    # Registers a task whose category/type/reward matches the service
    # created in T21.  The Organisation contract auto-assigns the task
    # and emits TaskAssigned, which the poller turns into this topic.
    # ──────────────────────────────────────────────────────────────────
    def test_23_event_task_assigned(self):
        if self.service_id_ev is None:
            _record("T23 event /dao/task_assigned", False,
                    "no event service (T21 failed?)")
            return

        def _trigger():
            goal = RegisterTaskGoal(
                description="Task for auto-assign event test",
                category=EV_SVC_CAT,
                task_type=EV_SVC_TYPE,
                reward=str(REWARD_IEC),
            )
            _call_action(self.ac_register_task, goal)

        ok, msg = _wait_for_event(
            "/dao/task_assigned", TaskAssignment,
            trigger_fn=_trigger,
            predicate=lambda m: (
                m.executor.strip() not in ("", "0x" + "0" * 40)
            ),
        )
        _record("T23 event /dao/task_assigned", ok,
                f"task_id={msg.task_id} executor={msg.executor[:12]}…" if ok and msg
                else "timeout – no message received")

    # ──────────────────────────────────────────────────────────────────
    # T24 — /dao/service_busy fires when set_service_busy is called
    # ──────────────────────────────────────────────────────────────────
    def test_24_event_service_busy(self):
        if self.service_id_ev is None:
            _record("T24 event /dao/service_busy", False,
                    "no event service (T21 failed?)")
            return

        svc_id = self.service_id_ev

        def _trigger():
            goal = SetServiceBusyGoal(service_id=svc_id, is_busy=True)
            _call_action(self.ac_set_busy, goal)

        ok, msg = _wait_for_event(
            "/dao/service_busy", ServiceBusy,
            trigger_fn=_trigger,
            predicate=lambda m: int(m.service_id) == svc_id and m.busy,
        )
        _record("T24 event /dao/service_busy", ok,
                f"service_id={svc_id} busy=True" if ok
                else "timeout – no message received")

    # ──────────────────────────────────────────────────────────────────
    # Run everything
    # ──────────────────────────────────────────────────────────────────
    def run(self) -> int:
        tests: List[Callable] = [
            self.test_01_get_balance,
            self.test_02_transfer_token,
            self.test_03_get_balance_secondary,
            self.test_04_approve_spender,
            self.test_05_get_allowance,
            self.test_06_register_service,
            self.test_07_get_all_services,
            self.test_08_get_services_by_creator,
            self.test_09_get_service_by_id,
            self.test_10_set_service_busy_true,
            self.test_11_set_service_busy_false,
            self.test_12_register_task_auto_assign,
            self.test_13_verify_auto_assignment,
            self.test_14_get_all_tasks,
            self.test_15_get_tasks_by_creator,
            self.test_16_register_task_no_match,
            self.test_17_remove_task_unassigned,
            self.test_18_remove_service,
            self.test_19_activate_service,
            self.test_20_activate_task,
            # ── event topic tests ──
            self.test_21_event_service_registered,
            self.test_22_event_task_registered,
            self.test_23_event_task_assigned,
            self.test_24_event_service_busy,
        ]

        print(f"\n{_BOLD}{'=' * 58}")
        print("  ROS-ETH Bridge  —  Functional Test Suite")
        print(f"{'=' * 58}{_RESET}\n")

        for fn in tests:
            if rospy.is_shutdown():
                break
            try:
                fn()
            except Exception as exc:
                name = fn.__name__.replace("test_", "T").replace("_", " ", 1)
                _record(name, False, f"exception: {exc}")
                rospy.logerr("%s raised:\n%s", fn.__name__, traceback.format_exc())
            time.sleep(0.3)  # small gap between tests

        return _print_summary()


# ────────────────────────────────────────────────────────────────────────────
# Summary
# ────────────────────────────────────────────────────────────────────────────

def _print_summary() -> int:
    passed  = sum(1 for _, ok, _ in Results if ok)
    failed  = sum(1 for _, ok, _ in Results if not ok)
    total   = len(Results)

    print(f"\n{_BOLD}{'=' * 58}")
    print("  Summary")
    print(f"{'=' * 58}{_RESET}")
    for name, ok, note in Results:
        tag = f"{_GREEN}PASS{_RESET}" if ok else f"{_RED}FAIL{_RESET}"
        suffix = f"  — {note}" if note else ""
        print(f"  [{tag}] {name}{suffix}")

    colour = _GREEN if failed == 0 else _RED
    print(f"\n{_BOLD}{colour}  {passed}/{total} tests passed{_RESET}")
    if failed:
        print(f"{_BOLD}{_RED}  {failed} test(s) FAILED{_RESET}")
    print(f"{_BOLD}{'=' * 58}{_RESET}\n")
    return failed  # 0 = all passed


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────

def main():
    rospy.init_node("bridge_test", anonymous=True)

    rospy.loginfo("Waiting for bridge nodes to become available …")
    # Wait until at least one dao service is up before connecting clients
    try:
        rospy.wait_for_service("/dao/get_all_tasks", timeout=30.0)
        rospy.wait_for_service("/dao/get_balance",   timeout=30.0)
    except rospy.ROSException as exc:
        rospy.logerr("Bridge services not available: %s", exc)
        sys.exit(1)

    suite = BridgeTestSuite()
    n_failed = suite.run()
    sys.exit(0 if n_failed == 0 else 1)


if __name__ == "__main__":
    main()

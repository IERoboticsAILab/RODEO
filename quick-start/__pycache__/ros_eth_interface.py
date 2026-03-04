#!/usr/bin/env python

import rospy
import actionlib
import threading
from decimal import Decimal, getcontext
from actionlib_msgs.msg import GoalStatus

# DAO ROS-ETH bridge messages and services
from ros_eth_msgs.msg import (
    RegisterServiceAction, RegisterServiceGoal,
    RegisterTaskAction, RegisterTaskGoal,
    SubmitProofAction, SubmitProofGoal,
    TaskAssignment, TaskId, TaskRejection, TaskRegistered
)

from ros_eth_msgs.srv import (
    GetBalance, GetBalanceRequest,
    GetTask, GetTaskRequest
)

class EthInterface:
    def __init__(self):
        # 1. Action Clients
        self.register_service_ac = actionlib.SimpleActionClient('/dao/register_service_action', RegisterServiceAction)
        self.register_task_ac    = actionlib.SimpleActionClient('/dao/register_task_action', RegisterTaskAction)
        self.submit_proof_ac     = actionlib.SimpleActionClient('/dao/submit_proof_action', SubmitProofAction)

        rospy.loginfo("Waiting for DAO action servers...")
        self.register_service_ac.wait_for_server()
        self.register_task_ac.wait_for_server()
        self.submit_proof_ac.wait_for_server()

        # 2. Service Proxies
        rospy.wait_for_service('/dao/get_balance')
        self.get_balance_srv = rospy.ServiceProxy('/dao/get_balance', GetBalance)
        
        rospy.wait_for_service('/dao/get_task_by_id')
        self.get_task_srv = rospy.ServiceProxy('/dao/get_task_by_id', GetTask)

        # 3. Parameters & State
        self.dao_account_robot = rospy.get_param('~dao_account_robot', '0x9DF377e211294E4826b8C4e9589548dd51E6637e')
        
        self._last_assignment = None
        self._assign_evt = threading.Event()
        self._waiting_task_id = None
        self._verified_evt = threading.Event()
        self._rejected_evt = threading.Event()
        self._rejected_reason = ""
        self._taskreg_evt = threading.Event()
        self._taskreg_task_id = None
        self._taskreg_wait_creator = None
        self._taskreg_wait_after_block = 0
        self._await_task_id = None
        self._await_assignment_evt = threading.Event()

        # 4. Subscribers
        self._assignment_sub = rospy.Subscriber('/dao/task_assigned', TaskAssignment, self._task_assigned_cb)
        self._verified_sub = rospy.Subscriber('/dao/task_verified', TaskId, self._task_verified_cb)
        self._rejected_sub = rospy.Subscriber('/dao/task_rejected', TaskRejection, self._task_rejected_cb)
        self._task_registered_sub = rospy.Subscriber("/dao/task_registered", TaskRegistered, self._task_registered_cb)

    # --- Internal Callbacks ---
    def _norm_account(self, addr):
        if not addr: return ""
        a = addr.strip().lower()
        return a if a.startswith("0x") else "0x" + a

    def _extract_executor(self, msg):
        for f in ['executor', 'executor_account', 'provider', 'assignee']:
            if hasattr(msg, f): return getattr(msg, f)
        return ""

    def _task_registered_cb(self, msg):
        creator = self._norm_account(getattr(msg, "creator", ""))
        tid = int(getattr(msg, "task_id", 0))
        blk = int(getattr(msg, "block_number", 0))

        if self._taskreg_wait_creator == creator and blk >= self._taskreg_wait_after_block:
            if not self._taskreg_evt.is_set():
                self._taskreg_task_id = tid
                self._taskreg_evt.set()

    def _task_assigned_cb(self, msg):
        exec_addr = self._norm_account(self._extract_executor(msg))
        if exec_addr == self._norm_account(self.dao_account_robot):
            self._last_assignment = msg
            self._assign_evt.set()
        
        tid = int(getattr(msg, "task_id", -1))
        if self._await_task_id is not None and tid == self._await_task_id:
            self._await_assignment_evt.set()

    def _task_verified_cb(self, msg):
        if self._waiting_task_id == int(getattr(msg, "task_id", -1)):
            self._verified_evt.set()

    def _task_rejected_cb(self, msg):
        if self._waiting_task_id == int(getattr(msg, "task_id", -1)):
            self._rejected_reason = str(getattr(msg, "reason", ""))
            self._rejected_evt.set()

    # --- Public API Functions ---
    def get_balance(self, owner):
        req = GetBalanceRequest(owner=str(owner))
        resp = self.get_balance_srv(req)
        wei = int(str(resp.balance_wei), 0)
        decimals = int(getattr(resp, "decimals", 18))
        getcontext().prec = 60
        return Decimal(wei) / (Decimal(10) ** decimals)

    def register_service(self, name, description, category, service_type, price_tokens):
        goal = RegisterServiceGoal(name=name, description=description, category=category, 
                                   service_type=service_type, price=str(price_tokens), min_confirmations=1)
        self.register_service_ac.send_goal(goal)
        self.register_service_ac.wait_for_result()
        res = self.register_service_ac.get_result()
        return {"tx_hash": getattr(res, "tx_hash", ""), "block_number": int(getattr(res, "block_number", 0))}

    def register_task(self, description, category, task_type, reward_tokens):
        goal = RegisterTaskGoal(description=description, category=category, 
                                task_type=task_type, reward=str(reward_tokens), min_confirmations=1)
        self.register_task_ac.send_goal(goal)
        self.register_task_ac.wait_for_result()
        res = self.register_task_ac.get_result()
        return {"tx_hash": getattr(res, "tx_hash", ""), "block_number": int(getattr(res, "block_number", 0))}

    def submit_proof(self, task_id, proof_uri):
        goal = SubmitProofGoal(task_id=int(task_id), proof_uri=str(proof_uri), min_confirmations=1)
        self.submit_proof_ac.send_goal(goal)
        self.submit_proof_ac.wait_for_result()
        res = self.submit_proof_ac.get_result()
        return {"ok": bool(getattr(res, "ok", False)), "tx_hash": getattr(res, "tx_hash", "")}

    def wait_for_task_assigned(self, task_id, timeout=180.0):
        deadline = rospy.Time.now() + rospy.Duration(timeout)
        req = GetTaskRequest(task_id=int(task_id))
        while not rospy.is_shutdown() and rospy.Time.now() < deadline:
            try:
                resp = self.get_task_srv(req)
                if resp.task.status == 1: return resp
            except Exception: pass
            rospy.sleep(2.0)
        return None

    def wait_for_proof_verification(self, task_id, timeout=300.0):
        self._waiting_task_id = int(task_id)
        self._verified_evt.clear()
        self._rejected_evt.clear()
        if self._verified_evt.wait(timeout): return {"verified": True, "reason": ""}
        if self._rejected_evt.is_set(): return {"verified": False, "reason": self._rejected_reason}
        return {"verified": False, "reason": "timeout"}
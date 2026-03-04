#!/usr/bin/env python3
"""
dao_writer_node — all DAO write operations (consolidates eth_tx_manager + token_operations).

Responsibilities
----------------
* 8 action servers for task/service mutations (register, remove, activate, etc.)
* 2 action servers for token transfers (transfer, approve)
* 2 ROS services for token balance / allowance queries

One Web3 connection and one Wallet are shared across all action servers.
The nonce lock in eth/tx.py ensures concurrent goal callbacks are serialised
per wallet address.
"""
import os
import sys

import rospy
import rospkg
import actionlib
from web3 import Web3

pkg_path = rospkg.RosPack().get_path("ros_eth_bridge")
sys.path.insert(0, os.path.join(pkg_path, "src"))

from abi_loader import load_config, make_web3
from eth.contracts import ContractRegistry
from eth.wallet import Wallet
from bridge.passphrase import resolve_passphrase
from eth.dao import task_ops, service_ops, token_ops
from bridge.converters import run_action

# ── actions ──────────────────────────────────────────────────────────────────
from ros_eth_msgs.msg import (
    RegisterServiceAction, RegisterServiceFeedback, RegisterServiceResult,
    RegisterTaskAction,    RegisterTaskFeedback,    RegisterTaskResult,
    SubmitProofAction,     SubmitProofFeedback,     SubmitProofResult,
    RemoveTaskAction,      RemoveTaskFeedback,      RemoveTaskResult,
    RemoveServiceAction,   RemoveServiceFeedback,   RemoveServiceResult,
    ActivateServiceAction, ActivateServiceFeedback, ActivateServiceResult,
    ActivateTaskAction,    ActivateTaskFeedback,    ActivateTaskResult,
    SetServiceBusyAction,  SetServiceBusyFeedback,  SetServiceBusyResult,
    TransferTokenAction,   TransferTokenFeedback,   TransferTokenResult,
    ApproveSpenderAction,  ApproveSpenderFeedback,  ApproveSpenderResult,
)
# ── services ─────────────────────────────────────────────────────────────────
from ros_eth_msgs.srv import (
    GetBalance,   GetBalanceResponse,
    GetAllowance, GetAllowanceResponse,
)


class DaoWriter:
    def __init__(self):
        rospy.init_node("dao_writer")

        self.cfg    = load_config()
        self.w3     = make_web3(self.cfg)
        self.wallet = Wallet(self.cfg.wallet, passphrase_fn=resolve_passphrase)
        self.reg    = ContractRegistry(self.w3, self.cfg.contracts, self.cfg.abi_paths)

        self._register_services()
        self._register_actions()

        rospy.loginfo("dao_writer ready — chain %s  sender %s",
                      self.w3.eth.chain_id, self.wallet.addr)

    # ------------------------------------------------------------------
    # ROS service registrations
    # ------------------------------------------------------------------

    def _register_services(self):
        rospy.Service("/dao/get_balance",   GetBalance,   self.srv_get_balance)
        rospy.Service("/dao/get_allowance", GetAllowance, self.srv_get_allowance)

    def _register_actions(self):
        def _as(topic, ActionCls, cb):
            s = actionlib.SimpleActionServer(topic, ActionCls,
                                             execute_cb=cb, auto_start=False)
            s.start()
            return s

        self.as_register_service  = _as("/dao/register_service_action",  RegisterServiceAction,  self.handle_register_service)
        self.as_register_task     = _as("/dao/register_task_action",      RegisterTaskAction,     self.handle_register_task)
        self.as_submit_proof      = _as("/dao/submit_proof_action",       SubmitProofAction,      self.handle_submit_proof)
        self.as_remove_task       = _as("/dao/remove_task_action",        RemoveTaskAction,       self.handle_remove_task)
        self.as_remove_service    = _as("/dao/remove_service_action",     RemoveServiceAction,    self.handle_remove_service)
        self.as_activate_service  = _as("/dao/activate_service_action",   ActivateServiceAction,  self.handle_activate_service)
        self.as_activate_task     = _as("/dao/activate_task_action",      ActivateTaskAction,     self.handle_activate_task)
        self.as_set_service_busy  = _as("/dao/set_service_busy_action",   SetServiceBusyAction,   self.handle_set_service_busy)
        self.as_transfer          = _as("/dao/transfer_token_action",     TransferTokenAction,    self.handle_transfer)
        self.as_approve           = _as("/dao/approve_spender_action",    ApproveSpenderAction,   self.handle_approve)

    # ------------------------------------------------------------------
    # Convenience: minimal wrapper that injects shared objects
    # ------------------------------------------------------------------

    def _run(self, action_server, ResultCls, FeedbackCls, dao_fn, **kwargs):
        run_action(
            action_server, ResultCls, FeedbackCls, dao_fn,
            self.w3, self.reg, self.wallet, self.cfg.transaction,
            wallet=self.wallet,
            min_conf=self.cfg.transaction.confirmations,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Token query services
    # ------------------------------------------------------------------

    def srv_get_balance(self, req):
        try:
            owner = req.owner.strip() or self.wallet.addr
            balance_wei, decimals = token_ops.get_balance(self.reg, owner)
            return GetBalanceResponse(ok=True, balance_wei=str(balance_wei), decimals=decimals)
        except Exception as e:
            rospy.logwarn("get_balance failed: %s", e)
            return GetBalanceResponse(ok=False, balance_wei="0", decimals=0)

    def srv_get_allowance(self, req):
        try:
            owner = req.owner.strip() or self.wallet.addr
            allowance = token_ops.get_allowance(self.reg, owner, req.spender)
            return GetAllowanceResponse(ok=True, allowance_wei=str(allowance))
        except Exception as e:
            rospy.logwarn("get_allowance failed: %s", e)
            return GetAllowanceResponse(ok=False, allowance_wei="0")

    # ------------------------------------------------------------------
    # Task action handlers
    # ------------------------------------------------------------------

    def handle_register_task(self, goal):
        self._run(self.as_register_task, RegisterTaskResult, RegisterTaskFeedback,
                  task_ops.register_task,
                  description=goal.description, category=goal.category,
                  task_type=goal.task_type, reward_iec=int(goal.reward))

    def handle_submit_proof(self, goal):
        self._run(self.as_submit_proof, SubmitProofResult, SubmitProofFeedback,
                  task_ops.submit_proof,
                  task_id=int(goal.task_id), proof_uri=goal.proof_uri)

    def handle_activate_task(self, goal):
        self._run(self.as_activate_task, ActivateTaskResult, ActivateTaskFeedback,
                  task_ops.activate_task,
                  task_id=int(goal.task_id))

    def handle_remove_task(self, goal):
        self._run(self.as_remove_task, RemoveTaskResult, RemoveTaskFeedback,
                  task_ops.remove_task,
                  task_id=int(goal.task_id))

    # ------------------------------------------------------------------
    # Service action handlers
    # ------------------------------------------------------------------

    def handle_register_service(self, goal):
        self._run(self.as_register_service, RegisterServiceResult, RegisterServiceFeedback,
                  service_ops.register_service,
                  name=goal.name, description=goal.description,
                  category=goal.category, service_type=goal.service_type,
                  price_iec=int(goal.price), provider_type=int(goal.provider_type))

    def handle_remove_service(self, goal):
        self._run(self.as_remove_service, RemoveServiceResult, RemoveServiceFeedback,
                  service_ops.remove_service,
                  service_id=int(goal.service_id))

    def handle_activate_service(self, goal):
        self._run(self.as_activate_service, ActivateServiceResult, ActivateServiceFeedback,
                  service_ops.activate_service,
                  service_id=int(goal.service_id))

    def handle_set_service_busy(self, goal):
        self._run(self.as_set_service_busy, SetServiceBusyResult, SetServiceBusyFeedback,
                  service_ops.set_service_busy,
                  service_id=int(goal.service_id), is_busy=bool(goal.is_busy))

    # ------------------------------------------------------------------
    # Token action handlers
    # ------------------------------------------------------------------

    def handle_transfer(self, goal):
        self._run(self.as_transfer, TransferTokenResult, TransferTokenFeedback,
                  token_ops.transfer,
                  to_addr=goal.to, amount_iec=int(goal.amount))

    def handle_approve(self, goal):
        self._run(self.as_approve, ApproveSpenderResult, ApproveSpenderFeedback,
                  token_ops.approve,
                  spender=goal.spender, amount_iec=int(goal.amount))


def main():
    DaoWriter()
    rospy.loginfo("dao_writer running")
    rospy.spin()


if __name__ == "__main__":
    main()

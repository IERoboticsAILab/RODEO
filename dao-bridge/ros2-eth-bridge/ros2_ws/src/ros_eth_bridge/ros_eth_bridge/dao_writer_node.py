#!/usr/bin/env python3
"""
dao_writer - all DAO write operations (ROS 2 port of dao_writer_node.py).

* 10 action servers (register/remove/activate task and service, busy flag,
  submit proof, transfer and approve tokens).
* 2 services (get_balance, get_allowance).

One Web3 connection and one Wallet are shared. Goals run concurrently on a
MultiThreadedExecutor; the per-wallet nonce lock in eth/tx.py serialises the
transactions themselves, as in ROS 1.

Differences from ROS 1:
* the wallet is unlocked at start-up, so a wrong passphrase or missing
  keystore stops the node immediately instead of failing the first goal;
* the ROS 1 SimpleActionServer replaced a running goal when a new one arrived;
  here goals on the same action run side by side.
"""
from __future__ import annotations

import logging

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import ExternalShutdownException, MultiThreadedExecutor
from rclpy.node import Node

from eth.contracts import ContractRegistry
from eth.dao import service_ops, task_ops, token_ops
from eth.wallet import Wallet
from ros_eth_msgs.action import (
    ActivateService, ActivateTask, ApproveSpender, RegisterService, RegisterTask,
    RemoveService, RemoveTask, SetServiceBusy, SubmitProof, TransferToken,
)
from ros_eth_msgs.srv import GetAllowance, GetBalance

from ros_eth_bridge.config_loader import load_config, make_web3, resolve_config_path
from ros_eth_bridge.converters import run_action
from ros_eth_bridge.passphrase import make_passphrase_fn


class DaoWriter(Node):
    def __init__(self):
        super().__init__("dao_writer")
        self.declare_parameter("config_file", "")
        self.declare_parameter("wallet_passphrase", "")

        cfg_path = resolve_config_path(self.get_parameter("config_file").value)
        self.cfg = load_config(cfg_path)
        self.w3 = make_web3(self.cfg)
        self.wallet = Wallet(self.cfg.wallet, passphrase_fn=make_passphrase_fn(self))
        self.reg = ContractRegistry(self.w3, self.cfg.contracts, self.cfg.abi_paths)
        self.wallet.unlock()

        self._cb = ReentrantCallbackGroup()
        self.create_service(GetBalance, "dao/get_balance", self.srv_get_balance,
                            callback_group=self._cb)
        self.create_service(GetAllowance, "dao/get_allowance", self.srv_get_allowance,
                            callback_group=self._cb)

        def server(action_type, name, cb):
            return ActionServer(
                self, action_type, name, execute_callback=cb,
                goal_callback=lambda _g: GoalResponse.ACCEPT,
                cancel_callback=lambda _h: CancelResponse.ACCEPT,
                callback_group=self._cb)

        self._servers = [
            server(RegisterService, "dao/register_service_action", self.handle_register_service),
            server(RegisterTask, "dao/register_task_action", self.handle_register_task),
            server(SubmitProof, "dao/submit_proof_action", self.handle_submit_proof),
            server(RemoveTask, "dao/remove_task_action", self.handle_remove_task),
            server(RemoveService, "dao/remove_service_action", self.handle_remove_service),
            server(ActivateService, "dao/activate_service_action", self.handle_activate_service),
            server(ActivateTask, "dao/activate_task_action", self.handle_activate_task),
            server(SetServiceBusy, "dao/set_service_busy_action", self.handle_set_service_busy),
            server(TransferToken, "dao/transfer_token_action", self.handle_transfer),
            server(ApproveSpender, "dao/approve_spender_action", self.handle_approve),
        ]

        self.get_logger().info(
            f"dao_writer ready - chain {self.w3.eth.chain_id}  sender {self.wallet.addr}  "
            f"config {cfg_path}")

    # ------------------------------------------------------------------ helper
    def _run(self, goal_handle, action_type, dao_fn, **kwargs):
        return run_action(
            goal_handle, action_type, dao_fn,
            self.w3, self.reg, self.wallet, self.cfg.transaction,
            wallet=self.wallet, logger=self.get_logger(),
            min_conf=self.cfg.transaction.confirmations,
            **kwargs)

    # ------------------------------------------------------------------ token queries
    def srv_get_balance(self, req, res):
        try:
            owner = req.owner.strip() or self.wallet.addr
            balance_wei, decimals = token_ops.get_balance(self.reg, owner)
            res.ok, res.balance_wei, res.decimals = True, str(balance_wei), int(decimals)
        except Exception as e:
            self.get_logger().warning(f"get_balance failed: {e}")
            res.ok, res.balance_wei, res.decimals = False, "0", 0
        return res

    def srv_get_allowance(self, req, res):
        try:
            owner = req.owner.strip() or self.wallet.addr
            allowance = token_ops.get_allowance(self.reg, owner, req.spender)
            res.ok, res.allowance_wei = True, str(allowance)
        except Exception as e:
            self.get_logger().warning(f"get_allowance failed: {e}")
            res.ok, res.allowance_wei = False, "0"
        return res

    # ------------------------------------------------------------------ tasks
    def handle_register_task(self, gh):
        g = gh.request
        return self._run(gh, RegisterTask, task_ops.register_task,
                         description=g.description, category=g.category,
                         task_type=g.task_type, reward_iec=int(g.reward))

    def handle_submit_proof(self, gh):
        g = gh.request
        return self._run(gh, SubmitProof, task_ops.submit_proof,
                         task_id=int(g.task_id), proof_uri=g.proof_uri)

    def handle_activate_task(self, gh):
        return self._run(gh, ActivateTask, task_ops.activate_task,
                         task_id=int(gh.request.task_id))

    def handle_remove_task(self, gh):
        return self._run(gh, RemoveTask, task_ops.remove_task,
                         task_id=int(gh.request.task_id))

    # ------------------------------------------------------------------ services
    def handle_register_service(self, gh):
        g = gh.request
        return self._run(gh, RegisterService, service_ops.register_service,
                         name=g.name, description=g.description,
                         category=g.category, service_type=g.service_type,
                         price_iec=int(g.price), provider_type=int(g.provider_type))

    def handle_remove_service(self, gh):
        return self._run(gh, RemoveService, service_ops.remove_service,
                         service_id=int(gh.request.service_id))

    def handle_activate_service(self, gh):
        return self._run(gh, ActivateService, service_ops.activate_service,
                         service_id=int(gh.request.service_id))

    def handle_set_service_busy(self, gh):
        g = gh.request
        return self._run(gh, SetServiceBusy, service_ops.set_service_busy,
                         service_id=int(g.service_id), is_busy=bool(g.is_busy))

    # ------------------------------------------------------------------ tokens
    def handle_transfer(self, gh):
        g = gh.request
        return self._run(gh, TransferToken, token_ops.transfer,
                         to_addr=g.to, amount_iec=int(g.amount))

    def handle_approve(self, gh):
        g = gh.request
        return self._run(gh, ApproveSpender, token_ops.approve,
                         spender=g.spender, amount_iec=int(g.amount))


def main(args=None):
    logging.basicConfig(level=logging.INFO,
                        format="[%(levelname)s] [%(name)s]: %(message)s")
    rclpy.init(args=args)
    node = DaoWriter()
    executor = MultiThreadedExecutor(num_threads=8)
    executor.add_node(node)
    try:
        executor.spin()
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()

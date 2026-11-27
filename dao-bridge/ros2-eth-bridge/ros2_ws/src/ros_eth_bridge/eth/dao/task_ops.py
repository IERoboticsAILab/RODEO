"""
eth/dao/task_ops.py — Write operations on the TaskManager contract.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.
  - The allowance pre-check lives here, not in the ROS layer.
    register_task() automatically issues an ERC-20 approve() if the
    current allowance is insufficient, before calling registerTask().

Usage
-----
    from eth.dao.task_ops import register_task, submit_proof
    from eth.tx import TxProgress

    def on_prog(p: TxProgress):
        ros_pubfb(RegisterTaskFeedback(state=p.state, tx_hash=p.tx_hash,
                                       confirmations=p.confirmations, error=p.error))

    outcome = register_task(w3, reg, wallet, tx_cfg,
                            description="Inspect area A",
                            category="inspection",
                            task_type="visual",
                            reward_iec=10,
                            min_conf=2,
                            on_progress=on_prog)
"""

from __future__ import annotations

import logging
from typing import Callable

from web3 import Web3

from eth.config import TransactionCfg
from eth.contracts import ContractRegistry
from eth.tx import TxOutcome, TxProgress, sign_and_send
from eth.wallet import Wallet

logger = logging.getLogger(__name__)

_NOOP: Callable[[TxProgress], None] = lambda _: None

# IEC uses 18 decimals (same as ETH)
_WEI_PER_IEC = 10 ** 18


def _iec_to_wei(amount_iec: int) -> int:
    return amount_iec * _WEI_PER_IEC


# ---------------------------------------------------------------------------
# register_task (with automatic allowance guard)
# ---------------------------------------------------------------------------

def register_task(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    description: str,
    category: str,
    task_type: str,
    reward_iec: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """
    Register a task on-chain.

    Automatically issues an ERC-20 ``approve(TaskManager, reward)`` transaction
    first if the current allowance is insufficient.  Both the approve and the
    registerTask steps deliver progress via *on_progress*.
    """
    wallet.unlock()
    reward_wei = _iec_to_wei(reward_iec)
    spender = Web3.to_checksum_address(reg.task_manager.address)

    # --- allowance guard ---
    current_allowance = reg.iecoin.functions.allowance(wallet.addr, spender).call()
    if current_allowance < reward_wei:
        logger.info(
            "Allowance %s < reward %s; auto-approving TaskManager …",
            current_allowance, reward_wei,
        )
        # Use min_conf=1 for the approve prerequisite: we only need it mined,
        # not deeply confirmed.  On ganache, blocks only mine when a tx arrives,
        # so waiting for >1 confirmation here would block the registerTask call.
        approve_outcome = sign_and_send(
            w3,
            reg.iecoin.functions.approve(spender, reward_wei),
            wallet, tx_cfg, min_conf=1, on_progress=on_progress,
        )
        if not approve_outcome.ok:
            logger.error("approve() reverted: %s", approve_outcome.error)
            return TxOutcome(ok=False, tx_hash=approve_outcome.tx_hash,
                             block_number=approve_outcome.block_number,
                             error="approve reverted: " + approve_outcome.error)
        logger.info("Approve included, tx %s", approve_outcome.tx_hash)

    # --- registerTask ---
    return sign_and_send(
        w3,
        reg.task_manager.functions.registerTask(
            description, category, task_type, reward_wei,
        ),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )


# ---------------------------------------------------------------------------
# submit_proof
# ---------------------------------------------------------------------------

def submit_proof(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    task_id: int,
    proof_uri: str,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """Submit a proof URI for a completed task."""
    wallet.unlock()
    return sign_and_send(
        w3,
        reg.task_manager.functions.submitProof(task_id, proof_uri),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )


# ---------------------------------------------------------------------------
# activate_task
# ---------------------------------------------------------------------------

def activate_task(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    task_id: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """Re-activate a previously removed task.

    The contract re-escrows the reward via transferFrom on activation,
    so we apply the same allowance guard as register_task.
    """
    wallet.unlock()
    spender = reg.task_manager.address

    # Read the task's stored reward so we know how much allowance is needed.
    task = reg.task_manager.functions.getTask(task_id).call()
    # getTask tuple: id, description, taskCategory, taskType, categoryHash,
    #                taskTypeHash, creator, reward, status, executor, active
    reward_wei = task[7]

    current_allowance = reg.iecoin.functions.allowance(wallet.addr, spender).call()
    if current_allowance < reward_wei:
        logger.info(
            "activateTask: allowance %s < reward %s; auto-approving TaskManager …",
            current_allowance, reward_wei,
        )
        approve_outcome = sign_and_send(
            w3,
            reg.iecoin.functions.approve(spender, reward_wei),
            wallet, tx_cfg, min_conf=1, on_progress=on_progress,
        )
        if not approve_outcome.ok:
            return TxOutcome(ok=False, tx_hash=approve_outcome.tx_hash,
                             block_number=approve_outcome.block_number,
                             error="approve reverted: " + approve_outcome.error)

    return sign_and_send(
        w3,
        reg.task_manager.functions.activateTask(task_id),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )


# ---------------------------------------------------------------------------
# remove_task
# ---------------------------------------------------------------------------

def remove_task(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    task_id: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """Remove a task from the registry (creator only)."""
    wallet.unlock()
    return sign_and_send(
        w3,
        reg.task_manager.functions.removeTask(task_id),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )

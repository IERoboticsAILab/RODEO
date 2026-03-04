"""
eth/tx.py — Low-level transaction building, signing, and confirmation waiting.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.
  - Nonce collisions between concurrent action servers are prevented with a
    per-wallet threading.Lock.
  - Progress is reported through a plain Python callable receiving a
    TxProgress dataclass — the caller (bridge layer) converts it to
    whichever ROS feedback type it needs.

Usage
-----
    from eth.tx import sign_and_send, TxProgress, TxOutcome

    def on_progress(p: TxProgress) -> None:
        pubfb(MyActionFeedback(state=p.state, tx_hash=p.tx_hash,
                               confirmations=p.confirmations, error=p.error))

    outcome = sign_and_send(w3, contract.functions.doSomething(arg),
                            wallet, tx_cfg, min_conf=2,
                            on_progress=on_progress)
    if outcome.ok:
        ...
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from web3 import Web3

from eth.config import TransactionCfg
from eth.wallet import Wallet

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-wallet nonce locks — prevents collisions when concurrent action servers
# call sign_and_send() for the same sender address simultaneously.
# ---------------------------------------------------------------------------
_nonce_locks: dict[str, threading.Lock] = {}
_nonce_locks_meta: threading.Lock = threading.Lock()


def _nonce_lock_for(addr: str) -> threading.Lock:
    addr = addr.lower()
    with _nonce_locks_meta:
        if addr not in _nonce_locks:
            _nonce_locks[addr] = threading.Lock()
        return _nonce_locks[addr]


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class TxProgress:
    """
    Snapshot of an in-flight transaction reported to the caller's callback.

    Mapped 1-to-1 onto every ROS action feedback message by bridge/converters.py.
    """
    state: str          # "pending" | "included" | "confirmed" | "failed"
    tx_hash: str
    confirmations: int
    error: str = ""


@dataclass
class TxOutcome:
    """
    Final result of a submitted transaction, returned by sign_and_send().

    Mapped 1-to-1 onto every ROS action result message by bridge/converters.py.
    """
    ok: bool
    tx_hash: str
    block_number: int
    error: str = ""


# ---------------------------------------------------------------------------
# Transaction builder
# ---------------------------------------------------------------------------

def _build_base_tx(w3: Web3, sender: str, tx_cfg: TransactionCfg) -> dict:
    """
    Build the common transaction dict (from, nonce, chainId, optional EIP-1559 gas).

    Must be called while holding the nonce lock for *sender*.
    """
    nonce = w3.eth.get_transaction_count(sender)
    tx: dict = {"from": sender, "nonce": nonce, "chainId": w3.eth.chain_id}
    if tx_cfg.max_fee_per_gas_wei and tx_cfg.max_priority_fee_per_gas_wei:
        tx["maxFeePerGas"] = tx_cfg.max_fee_per_gas_wei
        tx["maxPriorityFeePerGas"] = tx_cfg.max_priority_fee_per_gas_wei
        tx["type"] = 2
    return tx


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sign_and_send(
    w3: Web3,
    contract_fn,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = lambda _: None,
) -> TxOutcome:
    """
    Build, sign, broadcast, and wait for *contract_fn* to be confirmed.

    Parameters
    ----------
    w3:
        Connected Web3 instance.
    contract_fn:
        A bound contract function object, e.g.
        ``contract.functions.registerTask(description, category, ...)``.
    wallet:
        Unlocked :class:`~eth.wallet.Wallet` instance.
    tx_cfg:
        :class:`~eth.config.TransactionCfg` (gas caps, confirmation count).
    min_conf:
        Minimum number of block confirmations to wait for.
    on_progress:
        Called with a :class:`TxProgress` on each state transition:
        ``"pending"`` → ``"included"`` (repeated until confirmed) → final.
        Used by the bridge layer to publish ROS action feedback.

    Returns
    -------
    TxOutcome
        ``ok=True`` when the receipt status is 1 and ``min_conf`` is reached.
    """
    nonce_lock = _nonce_lock_for(wallet.addr)
    with nonce_lock:
        tx = _build_base_tx(w3, wallet.addr, tx_cfg)
        # Estimate gas using the full tx context so Ganache's simulator
        # sees the correct nonce and chain state.
        _GAS_FLOOR = 50_000  # never go below intrinsic + small buffer
        try:
            gas_est = contract_fn.estimate_gas({"from": wallet.addr, "nonce": tx["nonce"]})
            gas = max(int(gas_est * tx_cfg.gas_multiplier), _GAS_FLOOR)
        except Exception as est_exc:
            logger.warning("estimate_gas failed (%s); falling back to gas_limit=%d",
                           est_exc, tx_cfg.gas_limit)
            if tx_cfg.gas_limit <= 0:
                raise RuntimeError(
                    f"estimate_gas failed and no gas_limit fallback configured: {est_exc}"
                ) from est_exc
            gas = tx_cfg.gas_limit
        tx["gas"] = gas
        tx = contract_fn.build_transaction(tx)

    # Sign and broadcast outside the nonce lock to minimise contention
    signed = w3.eth.account.sign_transaction(tx, wallet.key)
    txh = w3.eth.send_raw_transaction(signed.raw_transaction)
    hexh = txh.hex()
    logger.info("tx %s sent, waiting for %d confirmation(s)", hexh, max(1, min_conf))
    on_progress(TxProgress(state="pending", tx_hash=hexh, confirmations=0))

    try:
        rcpt = w3.eth.wait_for_transaction_receipt(txh, timeout=600)
    except Exception as exc:
        msg = str(exc)
        logger.error("tx %s receipt wait failed: %s", hexh, msg)
        on_progress(TxProgress(state="failed", tx_hash=hexh, confirmations=0, error=msg))
        return TxOutcome(ok=False, tx_hash=hexh, block_number=0, error=msg)

    block = int(rcpt.blockNumber)
    ok = (rcpt.status == 1)
    if ok:
        logger.info("tx %s mined in block %d", hexh, block)
    else:
        logger.warning("tx %s reverted in block %d", hexh, block)

    conf = 1
    while conf < max(1, min_conf):
        latest = w3.eth.block_number
        conf = max(1, int(latest) - block + 1)
        on_progress(TxProgress(state="included", tx_hash=hexh, confirmations=conf))
        if conf >= min_conf:
            break
        time.sleep(1.0)

    on_progress(TxProgress(state="confirmed" if ok else "failed", tx_hash=hexh, confirmations=conf))
    return TxOutcome(ok=ok, tx_hash=hexh, block_number=block,
                     error="" if ok else "tx reverted")

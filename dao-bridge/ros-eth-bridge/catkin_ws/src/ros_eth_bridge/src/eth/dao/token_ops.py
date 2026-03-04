"""
eth/dao/token_ops.py — IECoin token read and write operations.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.
  - get_balance / get_allowance are pure read calls (no signing).
  - transfer / approve use sign_and_send from eth.tx.

Usage
-----
    from eth.dao.token_ops import get_balance, transfer

    wei, decimals = get_balance(reg, "0xABC...")
    outcome = transfer(w3, reg, wallet, tx_cfg,
                       to_addr="0xDEF...", amount_iec=5,
                       min_conf=1, on_progress=on_prog)
"""

from __future__ import annotations

import logging
from typing import Callable, Tuple

from web3 import Web3

from eth.config import TransactionCfg
from eth.contracts import ContractRegistry
from eth.tx import TxOutcome, TxProgress, sign_and_send
from eth.wallet import Wallet

logger = logging.getLogger(__name__)

_NOOP: Callable[[TxProgress], None] = lambda _: None

_WEI_PER_IEC = 10 ** 18


def _iec_to_wei(amount_iec: int) -> int:
    return amount_iec * _WEI_PER_IEC


# ---------------------------------------------------------------------------
# Read-only queries
# ---------------------------------------------------------------------------

def get_balance(reg: ContractRegistry, owner: str) -> Tuple[int, int]:
    """
    Return ``(balance_wei, decimals)`` for *owner*.

    Parameters
    ----------
    reg:
        :class:`~eth.contracts.ContractRegistry`.
    owner:
        Ethereum address string (checksummed or bare hex).

    Returns
    -------
    tuple[int, int]
        ``(balance_wei, decimals)`` where ``balance_iec = balance_wei / 10**decimals``.
    """
    owner = Web3.to_checksum_address(owner)
    balance_wei = int(reg.iecoin.functions.balanceOf(owner).call())
    decimals     = int(reg.iecoin.functions.decimals().call())
    return balance_wei, decimals


def get_allowance(reg: ContractRegistry, owner: str, spender: str) -> int:
    """
    Return the current ERC-20 allowance in wei that *spender* may use on behalf of *owner*.
    """
    owner   = Web3.to_checksum_address(owner)
    spender = Web3.to_checksum_address(spender)
    return int(reg.iecoin.functions.allowance(owner, spender).call())


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def transfer(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    to_addr: str,
    amount_iec: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """
    Transfer *amount_iec* IEC tokens from the wallet to *to_addr*.

    Parameters
    ----------
    amount_iec:
        Integer number of IEC tokens (internally converted to wei).
    """
    if amount_iec <= 0:
        raise ValueError("amount_iec must be positive")
    wallet.unlock()
    to = Web3.to_checksum_address(to_addr.strip())
    return sign_and_send(
        w3,
        reg.iecoin.functions.transfer(to, _iec_to_wei(amount_iec)),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )


def approve(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    spender: str,
    amount_iec: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """
    Grant *spender* an ERC-20 allowance of *amount_iec* tokens.

    Pass ``amount_iec=0`` to revoke a previously granted allowance.
    """
    if amount_iec < 0:
        raise ValueError("amount_iec must be >= 0")
    wallet.unlock()
    sp = Web3.to_checksum_address(spender.strip())
    return sign_and_send(
        w3,
        reg.iecoin.functions.approve(sp, _iec_to_wei(amount_iec)),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )

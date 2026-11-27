"""
eth/dao/service_ops.py — Write operations on the ServiceManager contract.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.

Usage
-----
    from eth.dao.service_ops import register_service, set_service_busy

    outcome = register_service(w3, reg, wallet, tx_cfg,
                               name="robot-arm-1",
                               description="Pick and place",
                               category="manipulation",
                               service_type="pick_place",
                               price_iec=5,
                               provider_type=0,
                               min_conf=2,
                               on_progress=on_prog)
"""

from __future__ import annotations

import logging
from typing import Callable

from eth.config import TransactionCfg
from eth.contracts import ContractRegistry
from eth.tx import TxOutcome, TxProgress, sign_and_send
from eth.wallet import Wallet
from web3 import Web3

logger = logging.getLogger(__name__)

_NOOP: Callable[[TxProgress], None] = lambda _: None

_WEI_PER_IEC = 10 ** 18


def _iec_to_wei(amount_iec: int) -> int:
    return amount_iec * _WEI_PER_IEC


# ---------------------------------------------------------------------------
# register_service
# ---------------------------------------------------------------------------

def register_service(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    name: str,
    description: str,
    category: str,
    service_type: str,
    price_iec: int,
    provider_type: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """Register a new robot service in the DAO."""
    wallet.unlock()
    price_wei = _iec_to_wei(price_iec)
    return sign_and_send(
        w3,
        reg.service_manager.functions.registerService(
            name, description, category, service_type, price_wei, provider_type,
        ),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )


# ---------------------------------------------------------------------------
# remove_service
# ---------------------------------------------------------------------------

def remove_service(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    service_id: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """Remove a service registration (creator only)."""
    wallet.unlock()
    return sign_and_send(
        w3,
        reg.service_manager.functions.removeService(service_id),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )


# ---------------------------------------------------------------------------
# activate_service
# ---------------------------------------------------------------------------

def activate_service(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    service_id: int,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """Activate a registered service so it becomes visible in the marketplace."""
    wallet.unlock()
    return sign_and_send(
        w3,
        reg.service_manager.functions.activateService(service_id),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )


# ---------------------------------------------------------------------------
# set_service_busy
# ---------------------------------------------------------------------------

def set_service_busy(
    w3: Web3,
    reg: ContractRegistry,
    wallet: Wallet,
    tx_cfg: TransactionCfg,
    *,
    service_id: int,
    is_busy: bool,
    min_conf: int = 1,
    on_progress: Callable[[TxProgress], None] = _NOOP,
) -> TxOutcome:
    """
    Mark a service as busy or available.

    Only the service creator or the Organization contract can call setBusy.
    The service must already be active.
    """
    wallet.unlock()
    return sign_and_send(
        w3,
        reg.service_manager.functions.setBusy(service_id, is_busy),
        wallet, tx_cfg, min_conf=min_conf, on_progress=on_progress,
    )

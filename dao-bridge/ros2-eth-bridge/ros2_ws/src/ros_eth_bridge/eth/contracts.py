"""
eth/contracts.py — Contract registry: load every contract ABI once.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.
  - ABI files are read and parsed exactly once at construction time.
  - All format variants understood by the original abi_loader.load_contract()
    are supported (plain list, Hardhat artifact, solc combined JSON).

Usage
-----
    from eth.contracts import ContractRegistry

    reg = ContractRegistry(w3, cfg.contracts, cfg.abi_paths)
    reg.task_manager.functions.getTask(1).call()
    reg.iecoin.functions.balanceOf(addr).call()
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from web3 import Web3
from web3.contract import Contract

from eth.config import AbiPathsCfg, ContractsCfg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal ABI extraction
# ---------------------------------------------------------------------------

def _extract_abi(raw, abi_path: str) -> list:
    """
    Pull the ABI list out of the various JSON formats produced by different
    Solidity toolchains.

    Supported formats
    -----------------
    * Plain list  ``[...]``
    * Hardhat / Truffle artifact  ``{"abi": [...], ...}``
    * solc combined JSON  ``{"output": {"abi": [...]}, ...}``
    * ABI embedded as a JSON string  ``"[...]"``
    """
    if isinstance(raw, list):
        return raw

    if isinstance(raw, dict):
        if "abi" in raw and isinstance(raw["abi"], list):
            return raw["abi"]
        if (
            "output" in raw
            and isinstance(raw.get("output"), dict)
            and isinstance(raw["output"].get("abi"), list)
        ):
            return raw["output"]["abi"]
        raise ValueError(f"ABI list not found in {abi_path}")

    if isinstance(raw, str):
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            return parsed
        raise ValueError(f"ABI in {abi_path} is a JSON string but not a list")

    raise ValueError(f"Unsupported ABI format in {abi_path} (type={type(raw).__name__})")


def _load_one(w3: Web3, address: str, abi_path: str) -> Optional[Contract]:
    """
    Load a single contract.  Returns ``None`` if either *address* or
    *abi_path* is empty (optional contracts such as ``organization`` may not
    be configured in every deployment).
    """
    if not address or not abi_path:
        return None
    with open(abi_path, "r") as f:
        raw = json.load(f)
    abi = _extract_abi(raw, abi_path)
    return w3.eth.contract(address=Web3.to_checksum_address(address), abi=abi)


# ---------------------------------------------------------------------------
# ContractRegistry
# ---------------------------------------------------------------------------

class ContractRegistry:
    """
    Loads and holds all DAO contract instances.

    Contracts are loaded **once** at construction time, so every part of
    the bridge that shares a ``ContractRegistry`` instance uses the same
    cached ABI and checksum-validated address.

    Parameters
    ----------
    w3:
        A connected ``Web3`` instance.
    contracts_cfg:
        A :class:`~eth.config.ContractsCfg` with on-chain addresses.
    abi_paths_cfg:
        A :class:`~eth.config.AbiPathsCfg` with paths to artifact files.
    """

    def __init__(
        self,
        w3: Web3,
        contracts_cfg: ContractsCfg,
        abi_paths_cfg: AbiPathsCfg,
    ) -> None:
        self._iecoin          = _load_one(w3, contracts_cfg.iecoin,          abi_paths_cfg.iecoin)
        self._task_manager    = _load_one(w3, contracts_cfg.task_manager,    abi_paths_cfg.task_manager)
        self._service_manager = _load_one(w3, contracts_cfg.service_manager, abi_paths_cfg.service_manager)
        self._organization    = _load_one(w3, contracts_cfg.organization,    abi_paths_cfg.organization)

        loaded = [
            name for name, obj in [
                ("iecoin", self._iecoin),
                ("task_manager", self._task_manager),
                ("service_manager", self._service_manager),
                ("organization", self._organization),
            ] if obj is not None
        ]
        logger.info("ContractRegistry loaded: %s", ", ".join(loaded))

    # ------------------------------------------------------------------
    # Contract accessors — raise a descriptive error if not configured
    # ------------------------------------------------------------------

    @property
    def iecoin(self) -> Contract:
        if self._iecoin is None:
            raise RuntimeError("IECoin contract not configured (check dao.yaml iecoin address/abi_path)")
        return self._iecoin

    @property
    def task_manager(self) -> Contract:
        if self._task_manager is None:
            raise RuntimeError("TaskManager contract not configured (check dao.yaml task_manager address/abi_path)")
        return self._task_manager

    @property
    def service_manager(self) -> Contract:
        if self._service_manager is None:
            raise RuntimeError("ServiceManager contract not configured (check dao.yaml service_manager address/abi_path)")
        return self._service_manager

    @property
    def organization(self) -> Optional[Contract]:
        """Organization contract — may be ``None`` if not configured."""
        return self._organization

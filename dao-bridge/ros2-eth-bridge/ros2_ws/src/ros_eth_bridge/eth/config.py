"""
eth/config.py — Pure-Python configuration dataclasses for the ROS-ETH bridge.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.
  - Zero file I/O or network calls.
  - Zero Web3 imports.

This module is importable without a running ROS master and can be unit-tested
standalone. The decision of WHERE to load config from (ROS param, YAML file,
env variable) belongs to bridge/config_loader.py, not here.

Usage
-----
    raw: dict = yaml.safe_load(open("dao.yaml"))
    cfg: BridgeCfg = BridgeCfg.from_dict(raw)
    print(cfg.chain.rpc_url)
    print(cfg.contracts.task_manager)
"""

from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Sub-config dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ChainCfg:
    """Ethereum network connection parameters."""
    rpc_url: str
    http_fallback_url: str = ""
    chain_id: int = 1337


@dataclass
class ContractsCfg:
    """On-chain contract addresses (checksummed or bare hex)."""
    iecoin: str = ""
    organization: str = ""
    task_manager: str = ""
    service_manager: str = ""


@dataclass
class AbiPathsCfg:
    """Filesystem paths to compiled contract JSON artifact files."""
    iecoin: str = ""
    organization: str = ""
    task_manager: str = ""
    service_manager: str = ""


@dataclass
class WalletCfg:
    """Local keystore / signing wallet configuration."""
    keystore_path: str = ""
    unlock_method: str = "prompt"   # "prompt" | "env" | "param" | ""
    address: str = ""               # checksummed or bare address; used as default sender


@dataclass
class TransactionCfg:
    """Transaction submission policy."""
    confirmations: int = 2
    max_retries: int = 5
    # EIP-1559 gas caps; 0 means "let web3 estimate"
    max_fee_per_gas_wei: int = 0
    max_priority_fee_per_gas_wei: int = 0
    # Gas limit used as fallback when estimate_gas fails, and as a safety cap.
    # 0 means "estimate only, no cap".  Defaults to 500 000 which covers
    # all DAO contract calls while staying well below Ganache's block limit.
    gas_limit: int = 500_000
    # Multiplier applied on top of estimate_gas(); increase if you hit
    # out-of-gas errors on complex calls.
    gas_multiplier: float = 1.3


@dataclass
class StorageCfg:
    """Off-chain storage for proof artefacts."""
    proof_backend: str = "ipfs"
    ipfs_api: str = "http://127.0.0.1:5001"


# ---------------------------------------------------------------------------
# Top-level config dataclass
# ---------------------------------------------------------------------------

@dataclass
class BridgeCfg:
    """
    Complete configuration for the ROS-ETH bridge, built from dao.yaml.

    All child dataclasses are plain Python objects — no dict access needed
    anywhere in node code.
    """
    chain: ChainCfg
    contracts: ContractsCfg = field(default_factory=ContractsCfg)
    abi_paths: AbiPathsCfg = field(default_factory=AbiPathsCfg)
    wallet: WalletCfg = field(default_factory=WalletCfg)
    transaction: TransactionCfg = field(default_factory=TransactionCfg)
    storage: StorageCfg = field(default_factory=StorageCfg)

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def from_dict(d: dict) -> "BridgeCfg":
        """
        Build a BridgeCfg from the raw dictionary produced by yaml.safe_load.

        All missing keys fall back to sensible defaults so that partial YAML
        files and unit-test fixtures still produce a valid config object.
        """
        chain_d = d.get("chain", {}) or {}
        chain = ChainCfg(
            rpc_url=chain_d.get("rpc_url", "ws://127.0.0.1:8545"),
            http_fallback_url=chain_d.get("http_fallback_url", ""),
            chain_id=int(chain_d.get("chain_id", 1337)),
        )

        c = d.get("contracts", {}) or {}
        contracts = ContractsCfg(
            iecoin=c.get("iecoin", ""),
            organization=c.get("organization", ""),
            task_manager=c.get("task_manager", ""),
            service_manager=c.get("service_manager", ""),
        )

        a = d.get("abi_paths", {}) or {}
        abi_paths = AbiPathsCfg(
            iecoin=a.get("iecoin", ""),
            organization=a.get("organization", ""),
            task_manager=a.get("task_manager", ""),
            service_manager=a.get("service_manager", ""),
        )

        w = d.get("wallet", {}) or {}
        wallet = WalletCfg(
            keystore_path=w.get("keystore_path", ""),
            unlock_method=w.get("unlock_method", "prompt"),
            address=w.get("address", ""),
        )

        t = d.get("transaction", {}) or {}
        transaction = TransactionCfg(
            confirmations=int(t.get("confirmations", 2)),
            max_retries=int(t.get("max_retries", 5)),
            max_fee_per_gas_wei=int(t.get("max_fee_per_gas_wei", 0)),
            max_priority_fee_per_gas_wei=int(t.get("max_priority_fee_per_gas_wei", 0)),
            gas_limit=int(t.get("gas_limit", 500_000)),
            gas_multiplier=float(t.get("gas_multiplier", 1.3)),
        )

        s = d.get("storage", {}) or {}
        storage = StorageCfg(
            proof_backend=s.get("proof_backend", "ipfs"),
            ipfs_api=s.get("ipfs_api", "http://127.0.0.1:5001"),
        )

        return BridgeCfg(
            chain=chain,
            contracts=contracts,
            abi_paths=abi_paths,
            wallet=wallet,
            transaction=transaction,
            storage=storage,
        )

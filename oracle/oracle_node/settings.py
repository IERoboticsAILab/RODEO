import json
import os
from pathlib import Path


class Settings:
    def __init__(self):
        self.rpc_url = os.environ.get("RPC_URL", "http://localhost:8545")
        self.addresses_path = Path(os.environ.get("ADDRESSES_JSON", "addresses.json"))
        # ABIs: the ROS 2 bridge's copies (mounted at /workspace/abi in Docker)
        project_root = Path(__file__).parent.parent.parent
        default_abi_path = project_root / "dao-bridge" / "ros2-eth-bridge" / "ros2_ws" / "src" / "ros_eth_bridge" / "abi"
        self.base_abi = Path(os.environ.get("BASE_ABI", str(default_abi_path)))
        self.task_manager_name = os.environ.get("TASK_MANAGER_NAME", "TaskManager")

        # Contract addresses and the oracle wallet: environment first, else addresses.json
        if self._load_from_env():
            print("✅ Oracle configuration loaded from environment variables")
        else:
            print("📄 Oracle configuration loaded from addresses.json")
            self._load_from_json()
        self.oracle_addr = self.wallets["oracle"]["public"]
        self.oracle_key = self.wallets["oracle"]["private"]

        # Validation
        self.clock_tolerance_s = float(os.environ.get("CLOCK_TOLERANCE_SEC", "5"))
        self.state_dir = os.environ.get("STATE_DIR", str(Path(__file__).parent.parent / "state"))
        # ORACLE_WATCH=0: console only, no chain watcher (e.g. next to the ROS 2 oracle)
        self.watch = os.environ.get("ORACLE_WATCH", "1") not in ("0", "false", "no")
        self.legacy_proofs = os.environ.get("LEGACY_PROOFS", "1") not in ("0", "false", "no")
        self.interactive = os.environ.get("ORACLE_INTERACTIVE", "1") not in ("0", "false", "no")
        self.iec_per_kwh = float(os.environ.get("IEC_PER_KWH", "1.0"))
        self.iec_decimals = int(os.environ.get("IEC_DECIMALS", "18"))

        # Gas
        self.min_gas_price = int(os.environ.get("MIN_GAS_PRICE", "1000000000"))   # 1 gwei
        self.gas_multiplier = float(os.environ.get("GAS_MULTIPLIER", "1.2"))
        override = os.environ.get("GAS_PRICE_OVERRIDE")
        self.gas_price_override = int(override) if override else None

    def _load_from_env(self) -> bool:
        contracts = ["ORGANIZATION_ADDRESS", "TASK_MANAGER_ADDRESS", "SERVICE_MANAGER_ADDRESS", "IECOIN_ADDRESS"]
        wallet = ["ORACLE_ADDRESS", "ORACLE_PRIVATE_KEY"]
        if not all(os.environ.get(v) for v in contracts + wallet):
            return False
        self.contracts = {
            "Organization": os.environ["ORGANIZATION_ADDRESS"],
            "TaskManager": os.environ["TASK_MANAGER_ADDRESS"],
            "ServiceManager": os.environ["SERVICE_MANAGER_ADDRESS"],
            "IECoin": os.environ["IECOIN_ADDRESS"],
        }
        self.wallets = {"oracle": {"public": os.environ["ORACLE_ADDRESS"],
                                   "private": os.environ["ORACLE_PRIVATE_KEY"]}}
        return True

    def _load_from_json(self):
        with self.addresses_path.open() as f:
            cfg = json.load(f)
        self.contracts = cfg["contracts"]
        self.wallets = cfg["wallets"]

    def abi_path(self, name: str) -> Path:
        return self.base_abi / f"{name}.json"

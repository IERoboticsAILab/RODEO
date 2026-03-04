import os
import json
from pathlib import Path

class Settings:
    def __init__(self):
        self.rpc_url = os.environ.get("RPC_URL", "http://localhost:8545")
        self.addresses_path = Path(os.environ.get("ADDRESSES_JSON", "addresses.json"))
        # Use path relative to the project root
        project_root = Path(__file__).parent.parent.parent
        default_abi_path = project_root / "dao-bridge" / "ros-eth-bridge" / "catkin_ws" / "src" / "ros_eth_bridge" / "abi"
        self.base_abi = Path(os.environ.get("BASE_ABI", str(default_abi_path)))
        self.task_manager_name = os.environ.get("TASK_MANAGER_NAME", "TaskManager")
        self.play_rate = float(os.environ.get("PLAY_RATE", "3.0"))

        # Try loading from environment variables first, fallback to addresses.json
        if self._load_from_env():
            print("✅ Oracle configuration loaded from environment variables")
        else:
            print("📄 Oracle configuration loaded from addresses.json")
            self._load_from_json()
        
        self.iec_per_kwh = float(os.environ.get("IEC_PER_KWH", "1.0"))
        self.iec_decimals = int(os.environ.get("IEC_DECIMALS", "18"))

        self.oracle_addr = self.wallets["oracle"]["public"]
        self.oracle_key = self.wallets["oracle"]["private"]

        # Gas configuration
        self.min_gas_price = int(os.environ.get("MIN_GAS_PRICE", "1000000000"))  # 1 gwei default
        self.gas_multiplier = float(os.environ.get("GAS_MULTIPLIER", "1.2"))  # 20% buffer
        self.gas_price_override = os.environ.get("GAS_PRICE_OVERRIDE")  # Optional override for testing
        if self.gas_price_override:
            self.gas_price_override = int(self.gas_price_override)

    def _load_from_env(self) -> bool:
        """Load contract addresses and wallets from environment variables.
        Returns True if all required variables are present, False otherwise."""
        required_contracts = ["ORGANIZATION_ADDRESS", "TASK_MANAGER_ADDRESS", "SERVICE_MANAGER_ADDRESS", "IECOIN_ADDRESS"]
        required_wallet = ["ORACLE_ADDRESS", "ORACLE_PRIVATE_KEY"]
        
        # Check if all required environment variables are present
        if not all(os.environ.get(var) for var in required_contracts + required_wallet):
            return False
        
        # Load contract addresses from environment
        self.contracts = {
            "Organization": os.environ["ORGANIZATION_ADDRESS"],
            "TaskManager": os.environ["TASK_MANAGER_ADDRESS"],
            "ServiceManager": os.environ["SERVICE_MANAGER_ADDRESS"],
            "IECoin": os.environ["IECOIN_ADDRESS"]
        }
        
        # Load wallet info from environment
        self.wallets = {
            "oracle": {
                "public": os.environ["ORACLE_ADDRESS"],
                "private": os.environ["ORACLE_PRIVATE_KEY"]
            }
        }
        
        return True
    
    def _load_from_json(self):
        """Load contract addresses and wallets from addresses.json file."""
        with self.addresses_path.open() as f:
            cfg = json.load(f)
        self.contracts = cfg["contracts"]
        self.wallets = cfg["wallets"]

    def abi_path(self, name: str) -> Path:
        return self.base_abi / f"{name}.json"

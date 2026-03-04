#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from web3 import Web3
from web3.contract import Contract


REPO_ROOT = Path(__file__).resolve().parents[2]
DEPLOYMENT_FILE = REPO_ROOT / "deployments" / "1337.json"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "contracts"

provider_type_map = ["Robot", "Human", "Organization"]
task_status_map = ["Unassigned", "Assigned", "Executed"]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text())


def load_abi(contract_name: str) -> Any:
    artifact_path = ARTIFACTS_DIR / f"{contract_name}.sol" / f"{contract_name}.json"
    data = load_json(artifact_path)
    return data["abi"]


def load_deployments() -> Dict[str, str]:
    dep = load_json(DEPLOYMENT_FILE)
    contracts = dep["contracts"]
    return {
        "TaskManager": contracts["TaskManager"]["address"],
        "ServiceManager": contracts["ServiceManager"]["address"],
    }


def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def safe_map(arr, idx):
    try:
        i = int(idx)
        return arr[i] if 0 <= i < len(arr) else str(idx)
    except Exception:
        return str(idx)


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")
    rpc_url = require_env("GANACHE_URL")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to RPC: {rpc_url}")

    dep = load_deployments()
    tm_addr = w3.to_checksum_address(dep["TaskManager"])
    sm_addr = w3.to_checksum_address(dep["ServiceManager"])

    task_mgr: Contract = w3.eth.contract(address=tm_addr, abi=load_abi("TaskManager"))
    service_mgr: Contract = w3.eth.contract(address=sm_addr, abi=load_abi("ServiceManager"))

    print(f"Connected: {rpc_url} (chainId={w3.eth.chain_id})")
    print("TaskManager:   ", tm_addr)
    print("ServiceManager:", sm_addr)

    # --- Tasks ---
    print("\n====================")
    print("All Tasks")
    print("====================")
    total_tasks = task_mgr.functions.getTotalTasks().call()
    print(f"Total tasks: {total_tasks}")

    for i in range(1, int(total_tasks) + 1):
        t = task_mgr.functions.getTask(i).call()

        # Task struct layout in your TaskManager.sol:
        # 0 id
        # 1 description
        # 2 taskCategory
        # 3 taskType
        # 4 categoryHash
        # 5 taskTypeHash
        # 6 creator
        # 7 reward
        # 8 status
        # 9 executor
        # 10 active
        # 11 proofURI
        # 12 oracle
        # 13 verified

        status = safe_map(task_status_map, t[8])
        reward_iec = w3.from_wei(int(t[7]), "ether")  # 18 decimals

        print(
            f"\nTask #{t[0]}\n"
            f"  description : {t[1]}\n"
            f"  category    : {t[2]}\n"
            f"  type        : {t[3]}\n"
            f"  creator     : {t[6]}\n"
            f"  reward      : {reward_iec} IEC\n"
            f"  status      : {status}\n"
            f"  executor    : {t[9]}\n"
            f"  active      : {t[10]}\n"
            f"  proofURI    : {t[11]}\n"
            f"  oracle      : {t[12]}\n"
            f"  verified    : {t[13]}"
        )

    # --- Services ---
    print("\n====================")
    print("All Services")
    print("====================")
    total_services = service_mgr.functions.getServiceCount().call()
    print(f"Total services: {total_services}")

    for i in range(1, int(total_services) + 1):
        s = service_mgr.functions.getService(i).call()

        # Service struct layout (as you documented):
        # 0 id
        # 1 name
        # 2 description
        # 3 serviceCategory
        # 4 serviceType
        # 5 categoryHash
        # 6 serviceTypeHash
        # 7 price
        # 8 creator
        # 9 active
        # 10 providerType
        # 11 busy

        ptype = safe_map(provider_type_map, s[10])
        price_iec = w3.from_wei(int(s[7]), "ether")

        print(
            f"\nService #{s[0]}\n"
            f"  name        : {s[1]}\n"
            f"  description : {s[2]}\n"
            f"  category    : {s[3]}\n"
            f"  type        : {s[4]}\n"
            f"  price       : {price_iec} IEC\n"
            f"  creator     : {s[8]}\n"
            f"  active      : {s[9]}\n"
            f"  provider    : {ptype}\n"
            f"  busy        : {s[11]}"
        )


if __name__ == "__main__":
    main()

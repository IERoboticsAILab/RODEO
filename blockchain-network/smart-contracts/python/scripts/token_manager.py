#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from web3 import Web3
from web3.contract import Contract


REPO_ROOT = Path(__file__).resolve().parents[2]  # python/scripts/ -> repo root
DEPLOYMENT_FILE = REPO_ROOT / "deployments" / "1337.json"
ARTIFACTS_DIR = REPO_ROOT / "artifacts" / "contracts"

def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing file: {path}")
    return json.loads(path.read_text())

def load_abi(contract_name: str) -> Any:
    """
    Loads ABI from artifacts/contracts/<Contract>.sol/<Contract>.json
    """
    artifact_path = ARTIFACTS_DIR / f"{contract_name}.sol" / f"{contract_name}.json"
    data = load_json(artifact_path)
    return data["abi"]

def load_deployments() -> Dict[str, str]:
    dep = load_json(DEPLOYMENT_FILE)
    contracts = dep["contracts"]
    return {
        "IECoin": contracts["IECoin"]["address"],
        "Organization": contracts["Organization"]["address"],
        "ServiceManager": contracts["ServiceManager"]["address"],
        "TaskManager": contracts["TaskManager"]["address"],
    }

def require_env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def checksum(w3: Web3, addr: str) -> str:
    return w3.to_checksum_address(addr)


def wei_iec(w3: Web3, amount_iec: float | int | str) -> int:
    # IEC uses 18 decimals (same as ether)
    return w3.to_wei(str(amount_iec), "ether")


def tx_build_common(w3: Web3, from_addr: str) -> Dict[str, Any]:
    """
    EIP-1559 friendly if the node supports it, otherwise falls back to gasPrice.
    Ganache supports gasPrice fine; we keep it simple.
    """
    return {
        "from": from_addr,
        "nonce": w3.eth.get_transaction_count(from_addr),
        "gasPrice": w3.to_wei("2", "gwei"),
    }


def sign_send_wait(w3: Web3, tx: Dict[str, Any], private_key: str) -> str:
    signed = w3.eth.account.sign_transaction(tx, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    if receipt.status != 1:
        raise RuntimeError(f"Transaction failed: {tx_hash.hex()}")
    return tx_hash.hex()


def estimate_gas_with_buffer(fn_call, tx_params: Dict[str, Any], buffer: float = 1.25) -> int:
    est = fn_call.estimate_gas(tx_params)
    return int(est * buffer)


def print_balances(w3: Web3, iec: Contract, addrs: Dict[str, str]) -> None:
    print("\n=== Balances (IEC) ===")
    for name, addr in addrs.items():
        bal = iec.functions.balanceOf(addr).call()
        print(f"{name:14s} {addr}  ->  {w3.from_wei(bal, 'ether')} IEC")


def main() -> None:
    load_dotenv(REPO_ROOT / ".env")

    rpc_url = require_env("GANACHE_URL")
    pk_deployer = require_env("PRIVATE_KEY_DEPLOYER")
    pk_robot = require_env("PRIVATE_KEY_ROBOT")
    pk_human = require_env("PRIVATE_KEY_HUMAN")
    pk_org = require_env("PRIVATE_KEY_ORGANIZATION")
    pk_oracle = require_env("PRIVATE_KEY_ORACLE")

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError(f"Cannot connect to RPC: {rpc_url}")

    chain_id = w3.eth.chain_id
    print(f"Connected to RPC {rpc_url} (chainId={chain_id})")

    # Accounts
    acct_deployer = w3.eth.account.from_key(pk_deployer)
    acct_robot = w3.eth.account.from_key(pk_robot)
    acct_human = w3.eth.account.from_key(pk_human)
    acct_org = w3.eth.account.from_key(pk_org)
    acct_oracle = w3.eth.account.from_key(pk_oracle)

    print("deployer:", acct_deployer.address)
    print("robot:   ", acct_robot.address)
    print("human:   ", acct_human.address)
    print("org:     ", acct_org.address)
    print("oracle:  ", acct_oracle.address)

    # Deployed contract addresses
    deployed = load_deployments()
    iecoin_addr = checksum(w3, deployed["IECoin"])
    org_addr = checksum(w3, deployed["Organization"])
    tm_addr = checksum(w3, deployed["TaskManager"])

    # Contracts
    iec = w3.eth.contract(address=iecoin_addr, abi=load_abi("IECoin"))
    org = w3.eth.contract(address=org_addr, abi=load_abi("Organization"))

    # Helper addresses map for prints
    addr_map = {
        "deployer": acct_deployer.address,
        "robot": acct_robot.address,
        "human": acct_human.address,
        "org_wallet": acct_org.address,
        "org_contract": org_addr,
        "task_mgr": tm_addr,
    }

    # --- Example actions ---
    # 1) Send IEC to robot/human
    def send_token(to_addr: str, amount_iec: float | int | str) -> None:
        to_addr = checksum(w3, to_addr)
        amt = wei_iec(w3, amount_iec)

        fn = iec.functions.transfer(to_addr, amt)
        txp = tx_build_common(w3, acct_deployer.address)
        gas = estimate_gas_with_buffer(fn, {"from": acct_deployer.address})
        tx = fn.build_transaction({**txp, "gas": gas, "chainId": chain_id})

        tx_hash = sign_send_wait(w3, tx, pk_deployer)
        print(f"✅ transfer {amount_iec} IEC -> {to_addr}  ({tx_hash})")

    # 2) Approve + deposit into Organization (from deployer)
    def approve_and_deposit_to_organization(amount_iec: float | int | str) -> None:
        amt = wei_iec(w3, amount_iec)

        # Approve IECoin -> Organization contract (so org.deposit can transferFrom deployer)
        fn_approve = iec.functions.approve(org_addr, amt)
        txp = tx_build_common(w3, acct_deployer.address)
        gas = estimate_gas_with_buffer(fn_approve, {"from": acct_deployer.address})
        tx = fn_approve.build_transaction({**txp, "gas": gas, "chainId": chain_id})
        tx_hash = sign_send_wait(w3, tx, pk_deployer)
        print(f"✅ approve {amount_iec} IEC for Organization  ({tx_hash})")

        # Deposit
        fn_deposit = org.functions.deposit(amt)
        txp2 = tx_build_common(w3, acct_deployer.address)
        gas2 = estimate_gas_with_buffer(fn_deposit, {"from": acct_deployer.address})
        tx2 = fn_deposit.build_transaction({**txp2, "gas": gas2, "chainId": chain_id})
        tx_hash2 = sign_send_wait(w3, tx2, pk_deployer)
        print(f"🏦 deposit {amount_iec} IEC into Organization  ({tx_hash2})")

    # ---- Run whatever you want here ----
    # Uncomment as needed:
    send_token(acct_robot.address, 2000)
    send_token(acct_human.address, 2000)
    approve_and_deposit_to_organization(10000)

    # Allowances (robot -> TaskManager / Organization) just as diagnostics
    allowance_robot_tm = iec.functions.allowance(acct_robot.address, tm_addr).call()
    allowance_robot_org = iec.functions.allowance(acct_robot.address, org_addr).call()
    print("\nallowance(robot -> task_mgr):", w3.from_wei(allowance_robot_tm, "ether"), "IEC")
    print("allowance(robot -> org):     ", w3.from_wei(allowance_robot_org, "ether"), "IEC")

    print_balances(w3, iec, addr_map)

    # Total supply (if your IECoin exposes it)
    if hasattr(iec.functions, "totalSupply"):
        total = iec.functions.totalSupply().call()
        print("\nTotal supply:", w3.from_wei(total, "ether"), "IEC")


if __name__ == "__main__":
    main()

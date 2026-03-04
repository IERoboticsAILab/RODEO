from web3 import Web3
import json
import os
import sys
from typing import Any, Dict, List, Tuple, Optional
from decimal import Decimal, getcontext
from hexbytes import HexBytes

# Load configuration from environment variables or addresses.json
def load_config():
    """Load configuration from environment or addresses.json file"""
    # Try environment first
    rpc_url = os.environ.get("RPC_URL")
    org_addr = os.environ.get("ORGANIZATION_ADDRESS")
    iec_addr = os.environ.get("IECOIN_ADDRESS")
    org_public = os.environ.get("ORGANIZATION_WALLET_PUBLIC")
    org_private = os.environ.get("ORGANIZATION_WALLET_PRIVATE")
    abi_root = os.environ.get("ABI_ROOT", "contracts")
    
    # Fall back to addresses.json if environment variables not set
    if not all([rpc_url, org_addr, iec_addr, org_public, org_private]):
        config_file = os.environ.get("ADDRESSES_JSON", "addresses.json")
        with open(config_file) as f:
            cfg = json.load(f)
        
        rpc_url = rpc_url or cfg.get("rpc_url", "http://localhost:8545")
        contracts_cfg = cfg["contracts"]
        org_addr = org_addr or contracts_cfg["Organization"]
        iec_addr = iec_addr or contracts_cfg["IECoin"]
        abi_root = abi_root or cfg.get("abi_root", "contracts")
        
        wallets = cfg.get("wallets", {})
        if "organization" in wallets:
            org_public = org_public or wallets["organization"]["public"]
            org_private = org_private or wallets["organization"]["private"]
        else:
            print("ERROR: Organization wallet not configured")
            sys.exit(1)
    
    return {
        "rpc_url": rpc_url,
        "org_address": org_addr,
        "iec_address": iec_addr,
        "org_public": org_public,
        "org_private": org_private,
        "abi_root": abi_root
    }

config = load_config()

# Initialize Web3
RPC_URL = config["rpc_url"]
web3 = Web3(Web3.HTTPProvider(RPC_URL))

if not web3.is_connected():
    print(f"ERROR: Cannot connect to blockchain at {RPC_URL}")
    sys.exit(1)

ORG_CONTRACT_ADDR = web3.to_checksum_address(config["org_address"])
ORG_WALLET_ADDR = web3.to_checksum_address(config["org_public"])
ORG_WALLET_KEY = config["org_private"]
BASE_ABI = config["abi_root"]

def load_contract(address: str, name: str):
    path = f"{BASE_ABI}/{name}.sol/{name}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"ABI not found at {path}")
    with open(path) as f:
        abi = json.load(f)["abi"]
    return web3.eth.contract(address=web3.to_checksum_address(address), abi=abi)

# IECoin contract
IECOIN_ADDR = web3.to_checksum_address(config["iec_address"])
iecoin = load_contract(IECOIN_ADDR, "IECoin")

organization = load_contract(ORG_CONTRACT_ADDR, "Organization")

# token metadata
try:
    TOKEN_SYMBOL = iecoin.functions.symbol().call()
except Exception:
    TOKEN_SYMBOL = "IEC"

try:
    TOKEN_DECIMALS = iecoin.functions.decimals().call()
except Exception:
    TOKEN_DECIMALS = 18

getcontext().prec = 78  # safe precision

def _to_units(raw: int) -> str:
    # return a human string without losing precision
    scale = Decimal(10) ** int(TOKEN_DECIMALS)
    return str(Decimal(int(raw)) / scale)

# log scan helpers
ZERO = "0x0000000000000000000000000000000000000000"
TRANSFER_TOPIC = Web3.keccak(text="Transfer(address,address,uint256)")

def _parse_uint256(data) -> int:
    if isinstance(data, (bytes, bytearray, HexBytes)):
        return int.from_bytes(data, byteorder="big")
    if isinstance(data, str):
        s = data[2:] if data.startswith("0x") else data
        return int(s, 16)
    raise TypeError(f"Unexpected log data type: {type(data)}")

def _topic_to_address(topic) -> str:
    if isinstance(topic, (bytes, bytearray, HexBytes)):
        hx = topic.hex()
    else:
        hx = topic[2:] if isinstance(topic, str) and topic.startswith("0x") else str(topic)
    return web3.to_checksum_address("0x" + hx[-40:])

def list_iecoin_holders(start_block: Optional[int] = None,
                        end_block: Optional[int] = None,
                        chunk: int = 5_000,
                        verify_with_balance_of: bool = True) -> List[Dict[str, Any]]:
    """
    Scan Transfer logs of IECoin, build nonzero balances, return sorted list.
    """
    # allow an optional deploy block in config, fall back to zero
    cfg_start = int(os.environ.get("IECOIN_DEPLOY_BLOCK", "0"))
    start = cfg_start if start_block is None else int(start_block)
    end = web3.eth.block_number if end_block is None else int(end_block)

    balances: dict[str, int] = {}
    cur = start
    while cur <= end:
        to_block = min(cur + chunk - 1, end)
        logs = web3.eth.get_logs({
            "fromBlock": cur,
            "toBlock": to_block,
            "address": IECOIN_ADDR,
            "topics": [TRANSFER_TOPIC],
        })
        for lg in logs:
            frm = _topic_to_address(lg["topics"][1])
            to  = _topic_to_address(lg["topics"][2])
            value = _parse_uint256(lg["data"])

            if frm != ZERO:
                balances[frm] = balances.get(frm, 0) - value
            if to != ZERO:
                balances[to]  = balances.get(to, 0) + value
        cur = to_block + 1

    # optional safety pass against on chain balanceOf
    if verify_with_balance_of:
        final: dict[str, int] = {}
        for addr, raw in balances.items():
            onchain = iecoin.functions.balanceOf(addr).call()
            if onchain > 0:
                final[addr] = onchain
        balances = final

    # keep only positive and sort desc
    rows = [(addr, raw) for addr, raw in balances.items() if raw > 0]
    rows.sort(key=lambda kv: kv[1], reverse=True)

    # build response items
    out = []
    for addr, raw in rows:
        out.append({
            "address": addr,
            "balanceWei": str(int(raw)),
            "balanceIec": _to_units(raw),
        })
    return out

def _mgr_addresses() -> Tuple[str, str]:
    task_mgr = organization.functions.taskManager().call()
    svc_mgr = organization.functions.serviceManager().call()
    return web3.to_checksum_address(task_mgr), web3.to_checksum_address(svc_mgr)

def get_task_manager():
    tm, _ = _mgr_addresses()
    return load_contract(tm, "TaskManager")

def get_service_manager():
    _, sm = _mgr_addresses()
    return load_contract(sm, "ServiceManager")

def send_tx(fn):
    nonce = web3.eth.get_transaction_count(ORG_WALLET_ADDR)
    gas_price = web3.eth.gas_price
    gas_est = fn.estimate_gas({"from": ORG_WALLET_ADDR})
    tx = fn.build_transaction({
        "from": ORG_WALLET_ADDR,
        "nonce": nonce,
        "gas": int(gas_est * 12 // 10),
        "gasPrice": gas_price,
    })
    signed = web3.eth.account.sign_transaction(tx, private_key=ORG_WALLET_KEY)
    tx_hash = web3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = web3.eth.wait_for_transaction_receipt(tx_hash)
    return receipt

# ---------- Writes via Organization ----------

def register_task(desc: str, category: str, task_type: str, reward_iec: float) -> str:
    r_wei = web3.to_wei(reward_iec, "ether")
    rcpt = send_tx(organization.functions.registerTask(desc, category, task_type, r_wei))
    return rcpt.transactionHash.hex()

def remove_task(task_id: int) -> str:
    rcpt = send_tx(organization.functions.removeTask(task_id))
    return rcpt.transactionHash.hex()

def activate_task(task_id: int) -> str:
    rcpt = send_tx(organization.functions.activateTask(task_id))
    return rcpt.transactionHash.hex()

def unassign_task(task_id: int) -> str:
    rcpt = send_tx(organization.functions.unassignTask(task_id))
    return rcpt.transactionHash.hex()

def submit_proof_as_executor(task_id: int, proof_uri: str) -> str:
    rcpt = send_tx(organization.functions.submitProofAsExecutor(task_id, proof_uri))
    return rcpt.transactionHash.hex()

def register_service(name: str, desc: str, category: str, service_type: str, price_iec: float) -> str:
    p_wei = web3.to_wei(price_iec, "ether")
    # ProviderType.Organization is 2
    rcpt = send_tx(organization.functions.registerService(name, desc, category, service_type, p_wei, 2))
    return rcpt.transactionHash.hex()

def activate_service(service_id: int) -> str:
    rcpt = send_tx(organization.functions.activateService(service_id))
    return rcpt.transactionHash.hex()

def remove_service(service_id: int) -> str:
    rcpt = send_tx(organization.functions.removeService(service_id))
    return rcpt.transactionHash.hex()

def set_service_busy(index: int, is_busy: bool) -> str:
    rcpt = send_tx(organization.functions.setServiceBusy(index, is_busy))
    return rcpt.transactionHash.hex()

# ---------- Reads ----------

def list_all_tasks() -> list:
    tm = get_task_manager()
    rows = tm.functions.getAllTasks().call()
    return [_normalize_task(t) for t in rows]

def get_tasks_by_creator(creator: str) -> list:
    tm = get_task_manager()
    ids = tm.functions.getTasksByCreator(web3.to_checksum_address(creator)).call()
    tasks = []
    for tid in ids:
        t = tm.functions.getTask(tid).call()
        tasks.append(_normalize_task(t))
    return tasks

def list_all_services() -> list:
    sm = get_service_manager()
    rows = sm.functions.getAllServices().call()
    return [_normalize_service(s) for s in rows]

def get_services_by_creator(creator: str) -> list:
    sm = get_service_manager()
    ids = sm.functions.getServicesByCreator(web3.to_checksum_address(creator)).call()
    out = []
    for sid in ids:
        s = sm.functions.getService(sid).call()
        out.append(_normalize_service(s))
    return out

def _normalize_task(t) -> Dict[str, Any]:
    # matches TaskManager.Task tuple
    return {
        "id": int(t[0]),
        "description": t[1],
        "taskCategory": t[2],
        "taskType": t[3],
        "categoryHash": Web3.to_hex(t[4]),
        "taskTypeHash": Web3.to_hex(t[5]),
        "creator": Web3.to_checksum_address(t[6]),
        "rewardWei": str(int(t[7])),
        "status": int(t[8]),           # 0 Unassigned, 1 Assigned, 2 Executed
        "executor": Web3.to_checksum_address(t[9]) if int(t[9], 16) != 0 else "0x0000000000000000000000000000000000000000",
        "active": bool(t[10]),
        "proofURI": t[11],
        "oracle": Web3.to_checksum_address(t[12]) if int(t[12], 16) != 0 else "0x0000000000000000000000000000000000000000",
        "verified": bool(t[13]),
    }

def _normalize_service(s) -> Dict[str, Any]:
    # matches ServiceManager.Service tuple
    return {
        "id": int(s[0]),
        "name": s[1],
        "description": s[2],
        "serviceCategory": s[3],
        "serviceType": s[4],
        "categoryHash": Web3.to_hex(s[5]),
        "serviceTypeHash": Web3.to_hex(s[6]),
        "priceWei": str(int(s[7])),
        "creator": Web3.to_checksum_address(s[8]),
        "active": bool(s[9]),
        "providerType": int(s[10]),
        "busy": bool(s[11]),
    }

def manager_addresses() -> Dict[str, str]:
    tm, sm = _mgr_addresses()
    return {
        "organization": ORG_CONTRACT_ADDR,
        "taskManager": tm,
        "serviceManager": sm,
    }

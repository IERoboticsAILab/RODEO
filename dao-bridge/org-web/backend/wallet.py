"""
Support for people posting tasks from their own wallet (MetaMask).

The browser signs and pays; the backend only helps:

    GET  /wallet/config   chain id, the RPC URL the *wallet* should use (the
                          backend's own RPC_URL may only work inside Docker),
                          contract addresses, and whether the dev faucet is on
    POST /tasks/prepare   the same checks as /tasks/register (service online,
                          reward >= lowest price, parameters valid), but instead
                          of posting it returns the description to sign and the
                          reward in wei. The browser then approves the
                          TaskManager for the reward and calls
                          TaskManager.registerTask itself, so the connected
                          wallet is the task's creator and payer.
    POST /faucet          local chain only: sends test ETH (for gas) and IEC
                          from the organization's wallet to a new wallet, once
                          per address per FAUCET_COOLDOWN_SEC

Settings (environment):
    WALLET_RPC_URL        RPC URL as seen from the user's browser
                          (default http://localhost:8545)
    WALLET_CHAIN_NAME     network name shown in MetaMask (default "RODEO local")
    DEV_FAUCET            1 / 0; empty or unset: on for chain 1337 (Ganache) only
    FAUCET_ETH, FAUCET_IEC, FAUCET_COOLDOWN_SEC   amounts and rate limit
"""
from __future__ import annotations

import os
import threading
import time

from web3 import Web3

import org_code as oc

_faucet_lock = threading.Lock()
_faucet_last: dict = {}


def chain_id() -> int:
    return int(oc.web3.eth.chain_id)


def faucet_enabled() -> bool:
    env = (os.environ.get("DEV_FAUCET") or "").strip().lower()
    if env:                                   # set explicitly
        return env in ("1", "true", "yes", "on")
    return chain_id() == 1337                 # empty or unset: local chain only


def config() -> dict:
    tm, sm = oc._mgr_addresses()
    return {
        "chainId": chain_id(),
        "chainName": os.environ.get("WALLET_CHAIN_NAME", "RODEO local"),
        "rpcUrl": os.environ.get("WALLET_RPC_URL", "http://localhost:8545"),
        "currencySymbol": "ETH",
        "taskManager": tm,
        "iecoin": oc.IECOIN_ADDR,
        "organization": oc.ORG_CONTRACT_ADDR,
        "tokenSymbol": oc.TOKEN_SYMBOL if hasattr(oc, "TOKEN_SYMBOL") else "IEC",
        "faucet": faucet_enabled(),
        "faucetEth": float(os.environ.get("FAUCET_ETH", "1")),
        "faucetIec": float(os.environ.get("FAUCET_IEC", "200")),
    }


def _send_eth(to: str, amount_wei: int) -> str:
    tx = {
        "from": oc.ORG_WALLET_ADDR,
        "to": to,
        "value": amount_wei,
        "nonce": oc.web3.eth.get_transaction_count(oc.ORG_WALLET_ADDR),
        "gas": 21000,
        "gasPrice": oc.web3.eth.gas_price,
        "chainId": chain_id(),
    }
    signed = oc.web3.eth.account.sign_transaction(tx, private_key=oc.ORG_WALLET_KEY)
    h = oc.web3.eth.send_raw_transaction(signed.raw_transaction)
    oc.web3.eth.wait_for_transaction_receipt(h)
    return h.hex()


def faucet(address: str) -> dict:
    if not faucet_enabled():
        raise ValueError("the faucet is only available on the local development chain")
    if not Web3.is_address(address):
        raise ValueError(f"not an address: {address}")
    to = Web3.to_checksum_address(address)
    cooldown = float(os.environ.get("FAUCET_COOLDOWN_SEC", "600"))
    with _faucet_lock:
        last = _faucet_last.get(to, 0.0)
        if time.time() - last < cooldown:
            raise ValueError(f"this address was funded {time.time() - last:.0f} s ago; "
                             f"try again in {cooldown - (time.time() - last):.0f} s")
        eth_wei = Web3.to_wei(float(os.environ.get("FAUCET_ETH", "1")), "ether")
        iec_wei = Web3.to_wei(float(os.environ.get("FAUCET_IEC", "200")), "ether")
        if oc.iecoin.functions.balanceOf(oc.ORG_WALLET_ADDR).call() < iec_wei:
            raise ValueError("the organization's wallet has too little IEC left for the faucet")
        eth_tx = _send_eth(to, eth_wei)
        iec_tx = oc.send_tx(oc.iecoin.functions.transfer(to, iec_wei)).transactionHash.hex()
        _faucet_last[to] = time.time()
    return {"address": to, "ethTx": eth_tx, "iecTx": iec_tx,
            "eth": float(Web3.from_wei(eth_wei, "ether")), "iec": float(Web3.from_wei(iec_wei, "ether"))}

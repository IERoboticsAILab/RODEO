#!/usr/bin/env python3
import os, sys
import rospkg
from web3 import Web3

# Ensure we import helper modules from the package src folder
pkg_path = rospkg.RosPack().get_path("ros_eth_bridge")
sys.path.insert(0, os.path.join(pkg_path, "src"))

from abi_loader import load_config, make_web3, load_contract
import abi_loader as abi_mod

def main():
    print("abi_loader from:", abi_mod.__file__)
    cfg = load_config()
    w3 = make_web3(cfg)

    iec_addr = cfg.contracts.iecoin
    tman_addr = cfg.contracts.task_manager
    wallet = cfg.wallet.address
    abi_path = cfg.abi_paths.iecoin

    token = load_contract(w3, iec_addr, abi_path)
    bal = token.functions.balanceOf(wallet).call()
    allow = token.functions.allowance(wallet, Web3.to_checksum_address(tman_addr)).call()

    print("RPC connected:", True)
    print("Wallet:", wallet)
    print("IECoin:", iec_addr)
    print("TaskManager:", tman_addr)
    print("Balance wei:", bal)
    print("Allowance to TaskManager wei:", allow)

if __name__ == "__main__":
    main()

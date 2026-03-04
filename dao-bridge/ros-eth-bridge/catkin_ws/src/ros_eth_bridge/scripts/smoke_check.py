#!/usr/bin/env python3
import os, sys
import rospkg
# Ensure we import helper modules from the package src folder
pkg_path = rospkg.RosPack().get_path("ros_eth_bridge")
sys.path.insert(0, os.path.join(pkg_path, "src"))

from abi_loader import load_config, make_web3, load_contract
import abi_loader as abi_mod

def main():
    cfg = load_config()
    w3 = make_web3(cfg)

    tman = load_contract(w3, cfg.contracts.task_manager, cfg.abi_paths.task_manager)
    sman = load_contract(w3, cfg.contracts.service_manager, cfg.abi_paths.service_manager)

    total_tasks = tman.functions.getTotalTasks().call()
    service_count = sman.functions.getServiceCount().call()

    print("Connected, chain id:", w3.eth.chain_id)
    print("Total tasks:", total_tasks)
    print("Service count:", service_count)

if __name__ == "__main__":
    main()

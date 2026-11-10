"""
config_loader.py - locate and parse dao.yaml for the ROS 2 bridge nodes.

Replaces the ROS 1 ``abi_loader.py``. Resolution order for the config file:
    1. the node parameter ``config_file`` (if non-empty)
    2. the environment variable ``ROS_ETH_DAO_YAML`` (if non-empty)
    3. ``<share>/ros_eth_bridge/config/dao.yaml`` from the installed package

Relative ``abi_paths`` entries are resolved against the installed package's
share directory, so a dao.yaml can say ``abi/TaskManager.json`` instead of a
container-specific absolute path.
"""
from __future__ import annotations

import os

import yaml
from ament_index_python.packages import get_package_share_directory

from eth.config import BridgeCfg
from eth.provider import make_web3 as _eth_make_web3

PACKAGE = "ros_eth_bridge"


def share_dir() -> str:
    return get_package_share_directory(PACKAGE)


def resolve_config_path(param_value: str = "") -> str:
    if param_value:
        return os.path.expanduser(param_value)
    env = os.environ.get("ROS_ETH_DAO_YAML", "")
    if env:
        return os.path.expanduser(env)
    return os.path.join(share_dir(), "config", "dao.yaml")


def load_config(path: str) -> BridgeCfg:
    with open(path, "r") as f:
        cfg = BridgeCfg.from_dict(yaml.safe_load(f) or {})
    base = share_dir()
    for name in ("iecoin", "organization", "task_manager", "service_manager"):
        p = getattr(cfg.abi_paths, name)
        if p and not os.path.isabs(p):
            setattr(cfg.abi_paths, name, os.path.join(base, p))
    return cfg


def make_web3(cfg: BridgeCfg, prefer_http: bool = False):
    return _eth_make_web3(cfg.chain, prefer_http)

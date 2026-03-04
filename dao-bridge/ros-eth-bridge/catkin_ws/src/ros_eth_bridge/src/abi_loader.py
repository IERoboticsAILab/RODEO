#!/usr/bin/env python3
import os
import yaml
from eth.config import BridgeCfg
from eth.provider import make_web3 as _eth_make_web3
from eth.contracts import ContractRegistry, _load_one

# ContractRegistry is re-exported here so nodes can import it from either
# abi_loader or eth.contracts — both work.
__all__ = ["load_config", "make_web3", "load_contract", "ContractRegistry"]

def load_config():
    """
    Try to read the dao.yaml ROS param first,
    otherwise load the default file from the package.
    """
    try:
        import rospy
        cfg = rospy.get_param("dao_config", None)
        if isinstance(cfg, dict):
            return BridgeCfg.from_dict(cfg)
    except Exception:
        pass

    # fallback to file on disk
    try:
        import rospkg
        rp = rospkg.RosPack()
        path = os.path.join(rp.get_path("ros_eth_bridge"), "config", "dao.yaml")
    except Exception:
        # last chance, environment variable
        path = os.environ.get("ROS_ETH_DAO_YAML", "")
        if not path:
            raise RuntimeError("dao.yaml not found, set ROS param dao_config or env ROS_ETH_DAO_YAML")

    with open(path, "r") as f:
        return BridgeCfg.from_dict(yaml.safe_load(f))

def make_web3(cfg, prefer_http: bool = False):
    """
    Backward-compatible wrapper — delegates to eth.provider.make_web3().

    Parameters
    ----------
    cfg:
        A BridgeCfg instance.
    prefer_http:
        When True, prefer HTTP over WebSocket (useful for event listeners).
    """
    return _eth_make_web3(cfg.chain, prefer_http)

def load_contract(w3, address, abi_path):
    """
    Backward-compatible helper used by utility scripts.
    Delegates to eth.contracts._load_one; raises ValueError for empty inputs.
    """
    contract = _load_one(w3, address, abi_path)
    if contract is None:
        raise ValueError(
            f"load_contract: address or abi_path is empty "
            f"(address={address!r}, abi_path={abi_path!r})"
        )
    return contract

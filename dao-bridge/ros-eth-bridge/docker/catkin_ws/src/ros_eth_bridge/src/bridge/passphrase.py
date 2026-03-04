"""
bridge/passphrase.py — Passphrase resolution for the signing wallet.

This is the SINGLE place that knows the priority order:
    1. ROS private parameter ``~wallet_passphrase``
    2. Environment variable ``ETH_WALLET_PASSPHRASE``
    3. Interactive terminal prompt (``getpass``)

All three sources are tried in order.  The interactive prompt is used only
when neither of the silent sources is available, making it safe to run the
bridge both in headless robot deployments (via env / ROS param) and in
interactive development sessions.

Usage
-----
    from bridge.passphrase import resolve_passphrase
    wallet = Wallet(cfg.wallet, passphrase_fn=resolve_passphrase)
"""

from __future__ import annotations

import getpass as _getpass
import os

import rospy


def resolve_passphrase() -> str:
    """
    Return the wallet decryption passphrase.

    Resolution order
    ----------------
    1. ROS private param ``~wallet_passphrase``  (set in launch file or
       via ``rosparam set /dao_writer/wallet_passphrase "..."``).
    2. Environment variable ``ETH_WALLET_PASSPHRASE``.
    3. Interactive ``getpass`` prompt on the controlling terminal.

    Returns
    -------
    str
        The passphrase.  May be an empty string for unprotected keystores.
    """
    # 1 — ROS param (silent, works in headless deployments)
    try:
        if rospy.has_param("~wallet_passphrase"):
            pw = rospy.get_param("~wallet_passphrase")
            if pw is not None:
                return str(pw)
    except Exception:
        pass

    # 2 — Environment variable (CI / Docker secrets)
    pw = os.environ.get("ETH_WALLET_PASSPHRASE")
    if pw is not None:
        return pw

    # 3 — Interactive prompt (developer workstation)
    return _getpass.getpass("Wallet passphrase (leave empty if none): ")

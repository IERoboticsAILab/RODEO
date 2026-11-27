"""
passphrase.py - keystore passphrase resolution for the dao_writer node.

Order:
    1. environment variable ETH_WALLET_PASSPHRASE (used if set, even if empty)
    2. node parameter ``wallet_passphrase`` (used if non-empty)
    3. interactive prompt, only when stdin is a terminal
    4. empty string (unprotected development keystore)

Unlike the ROS 1 launch file, nothing here hard-codes an empty passphrase:
an encrypted keystore works as soon as ETH_WALLET_PASSPHRASE is set.
"""
from __future__ import annotations

import getpass
import os
import sys


def make_passphrase_fn(node):
    def resolve() -> str:
        env = os.environ.get("ETH_WALLET_PASSPHRASE")
        if env is not None:
            return env
        try:
            pw = node.get_parameter("wallet_passphrase").get_parameter_value().string_value
        except Exception:
            pw = ""
        if pw:
            return pw
        if sys.stdin is not None and sys.stdin.isatty():
            return getpass.getpass("Wallet passphrase (leave empty if none): ")
        return ""
    return resolve

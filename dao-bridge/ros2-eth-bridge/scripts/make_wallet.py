#!/usr/bin/env python3
"""
Create the encrypted keystore a bridge signs with.

    python3 make_wallet.py                              # robot dev key -> ~/.ros_eth/wallet.json
    python3 make_wallet.py --key 0x... --out ~/.ros_eth/panther_wallet.json

The default key is Ganache account #4, the robot in the standard deployment.
It is a public test key: never use it on a real network. Press Enter at the
prompt for an empty passphrase, or set the same passphrase as
ETH_WALLET_PASSPHRASE for the bridge. Needs `pip install eth-account`.
"""
import argparse
import getpass
import json
import os
import pathlib
import sys

from eth_account import Account

ROBOT_DEV_KEY = "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--key", default=os.environ.get("ROBOT_PRIVATE_KEY", ROBOT_DEV_KEY),
                    help="private key (hex); default: $ROBOT_PRIVATE_KEY or the Ganache robot key")
    ap.add_argument("--out", default="~/.ros_eth/wallet.json", help="keystore path")
    ap.add_argument("--force", action="store_true", help="overwrite an existing keystore")
    a = ap.parse_args()

    acct = Account.from_key(a.key)
    path = pathlib.Path(a.out).expanduser()
    if path.exists() and not a.force:
        sys.exit(f"{path} exists; use --force to overwrite")
    print("Address:", acct.address)
    pw = getpass.getpass("Passphrase (Enter for none): ")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(Account.encrypt(acct.key, pw), indent=2))
    print("Saved to", path)


if __name__ == "__main__":
    main()

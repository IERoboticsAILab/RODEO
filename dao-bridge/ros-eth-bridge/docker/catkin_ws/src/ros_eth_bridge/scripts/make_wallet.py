#!/usr/bin/env python3
import json, os, getpass, pathlib
from eth_account import Account

HEX_PRIV = "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"

def main():
    acct = Account.from_key(HEX_PRIV)
    print("Address:", acct.address)
    pw = getpass.getpass("Passphrase: ")
    keystore = Account.encrypt(acct.key, pw)
    path = pathlib.Path("~/.ros_eth/wallet.json").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keystore, indent=2))
    print("Saved to", str(path))

if __name__ == "__main__":
    main()
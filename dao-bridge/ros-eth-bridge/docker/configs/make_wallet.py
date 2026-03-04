#!/usr/bin/env python3
import json, os, getpass, pathlib
from eth_account import Account

HEX_PRIV = "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926a"

def main():
    acct = Account.from_key(HEX_PRIV)
    print("Address:", acct.address)
    pw = getpass.getpass("Passphrase: ")
    keystore = Account.encrypt(acct.key, pw)
    path = pathlib.Path("wallet.json").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(keystore, indent=2))
    print("Saved to", str(path))

if __name__ == "__main__":
    main()

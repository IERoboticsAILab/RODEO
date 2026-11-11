"""wallet.faucet_enabled without a chain (org_code is stubbed: importing it would connect)."""
import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.modules.setdefault("org_code", types.SimpleNamespace())
import wallet  # noqa: E402


def test_faucet_switch(monkeypatch):
    for chain, env, expect in [(1337, None, True), (1337, "", True), (1337, "0", False),
                               (1, None, False), (1, "", False), (1, "1", True)]:
        monkeypatch.setattr(wallet, "chain_id", lambda c=chain: c)
        if env is None:
            monkeypatch.delenv("DEV_FAUCET", raising=False)
        else:
            monkeypatch.setenv("DEV_FAUCET", env)
        assert wallet.faucet_enabled() is expect, (chain, env)

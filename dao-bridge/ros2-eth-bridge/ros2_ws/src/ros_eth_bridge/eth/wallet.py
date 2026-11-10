"""
eth/wallet.py — Thread-safe Ethereum keystore wallet.

Rules enforced here:
  - Zero rospy imports.
  - Zero ROS message imports.
  - Passphrase SOURCE is not this class's responsibility; it is injected
    by the caller via passphrase_fn.  This keeps the eth/ layer pure and
    unit-testable without a ROS master.

Usage (in a ROS node)
---------------------
    from eth.wallet import Wallet
    from bridge.passphrase import resolve_passphrase

    wallet = Wallet(cfg.wallet, passphrase_fn=resolve_passphrase)
    # unlock happens lazily on first .key access, or explicitly:
    wallet.unlock()
    signed = w3.eth.account.sign_transaction(tx, wallet.key)
"""

from __future__ import annotations

import os
import threading
from typing import Callable, Optional

from eth_account import Account
from web3 import Web3


class Wallet:
    """
    Wraps an encrypted JSON keystore file.

    Parameters
    ----------
    wallet_cfg:
        A ``WalletCfg`` dataclass (from ``eth.config``).
    passphrase_fn:
        Zero-argument callable that returns the decryption passphrase.
        Called at most once (result is cached).  Defaults to returning an
        empty string, which works for unprotected development keystores.
    """

    def __init__(
        self,
        wallet_cfg,  # WalletCfg — avoid circular import by not type-hinting
        passphrase_fn: Callable[[], str] = lambda: "",
    ) -> None:
        self.addr: str = Web3.to_checksum_address(wallet_cfg.address)
        self._path: str = os.path.expanduser(wallet_cfg.keystore_path)
        self._passphrase_fn: Callable[[], str] = passphrase_fn
        self._key: Optional[bytes] = None
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def unlock(self) -> None:
        """
        Decrypt the keystore and cache the private key.

        Idempotent — safe to call multiple times or from multiple threads.
        ``passphrase_fn`` is invoked exactly once.
        """
        with self._lock:
            if self._key is not None:
                return
            with open(self._path, "r") as f:
                ks_text = f.read()
            pw = self._passphrase_fn()
            self._key = Account.decrypt(ks_text, pw)

    @property
    def key(self) -> bytes:
        """
        Private key bytes.  Triggers ``unlock()`` on first access so
        nodes that never call unlock() explicitly still work.
        """
        if self._key is None:
            self.unlock()
        return self._key

    @property
    def is_unlocked(self) -> bool:
        """True once the keystore has been decrypted."""
        return self._key is not None

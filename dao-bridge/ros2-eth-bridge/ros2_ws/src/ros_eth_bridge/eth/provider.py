"""
eth/provider.py — Web3 connection factory.

Rules enforced here:
  - Zero rospy / ros_eth_msgs imports.
  - No side effects beyond establishing a network connection.
  - Logging via Python's standard ``logging`` module so the function is
    usable in tests and CLI scripts without a ROS master.

Usage
-----
    from eth.config import BridgeCfg
    from eth.provider import make_web3

    cfg = BridgeCfg.from_dict(raw)
    w3_read  = make_web3(cfg.chain, prefer_http=True)   # polling / events
    w3_write = make_web3(cfg.chain)                     # signing / sending
"""

from __future__ import annotations

import logging
from typing import Optional

from web3 import Web3

from eth.config import ChainCfg

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_connected(w3: Web3) -> bool:
    """Compatibility shim for web3 v5 (isConnected) vs v6 (is_connected)."""
    try:
        return w3.is_connected()
    except AttributeError:
        return w3.isConnected()  # type: ignore[attr-defined]


def _try_ws(url: str) -> Optional[Web3]:
    """Attempt a WebSocket connection; return None on failure."""
    if not url.startswith("ws"):
        return None
    try:
        w3 = Web3(Web3.WebsocketProvider(url, websocket_timeout=30))
        logger.debug("Trying WebSocket provider at %s …", url)
        if _is_connected(w3):
            logger.info("Connected via WebSocket: %s", url)
            return w3
        logger.debug("WebSocket provider at %s not connected.", url)
    except Exception as exc:
        logger.debug("WebSocket provider at %s failed: %s", url, exc)
    return None


def _try_http(url: str) -> Optional[Web3]:
    """Attempt an HTTP connection; return None on failure."""
    if not url:
        return None
    try:
        w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 30}))
        logger.debug("Trying HTTP provider at %s …", url)
        if _is_connected(w3):
            logger.info("Connected via HTTP: %s", url)
            return w3
        logger.debug("HTTP provider at %s not connected.", url)
    except Exception as exc:
        logger.debug("HTTP provider at %s failed: %s", url, exc)
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def make_web3(chain_cfg: ChainCfg, prefer_http: bool = False) -> Web3:
    """
    Build and return a connected ``Web3`` instance.

    Parameters
    ----------
    chain_cfg:
        A :class:`~eth.config.ChainCfg` dataclass with ``rpc_url`` and
        optional ``http_fallback_url``.
    prefer_http:
        When ``True``, try the HTTP fallback URL before the WebSocket URL.
        Useful for polling-only workloads (e.g. event listeners) that do
        not need a persistent socket.

    Returns
    -------
    Web3
        A connected Web3 instance.

    Raises
    ------
    RuntimeError
        If neither transport can connect.
    """
    ws   = chain_cfg.rpc_url
    http = chain_cfg.http_fallback_url

    if prefer_http:
        w3 = _try_http(http) or _try_ws(ws)
    else:
        w3 = _try_ws(ws) or _try_http(http)

    if w3 is None:
        raise RuntimeError(
            "Web3 cannot connect. Tried: "
            f"ws={ws!r}, http={http!r}. "
            "Check rpc_url / http_fallback_url in dao.yaml."
        )
    return w3

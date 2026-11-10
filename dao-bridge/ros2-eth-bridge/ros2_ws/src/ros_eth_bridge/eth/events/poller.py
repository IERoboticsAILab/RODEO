"""
eth/events/poller.py — Block-range event poller for DAO contracts.

``EthPoller`` wraps the polling loop, chunked range iteration, and
deduplication against the checkpoint.  It is completely decoupled from ROS:
every event is delivered to a caller-supplied ``on_event`` callback as a
typed Python dataclass (from ``eth.events.decoder``).

No rospy / ros_eth_msgs imports.

Usage
-----
    from eth.events.checkpoint import Checkpoint
    from eth.events.poller import EthPoller

    ckpt   = Checkpoint()
    poller = EthPoller(w3, reg, ckpt, on_event=my_callback,
                       poll_interval=1.0, block_chunk=1000)
    poller.start()          # daemon thread; call poller.stop() to finish

    def my_callback(event):
        # event is one of the dataclasses in eth.events.decoder
        print(event)
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from eth.contracts import ContractRegistry
from eth.events.checkpoint import Checkpoint
from eth.events import decoder as dec

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# web3 v5/v6 compat shim
# ---------------------------------------------------------------------------

def _get_logs(event_obj, from_block: int, to_block: int) -> list:
    """Call ``get_logs`` with whichever kwarg style the installed web3 uses."""
    try:
        return event_obj.get_logs(from_block=from_block, to_block=to_block)
    except TypeError:
        return event_obj.get_logs(fromBlock=from_block, toBlock=to_block)


# ---------------------------------------------------------------------------
# Event descriptor table
# ---------------------------------------------------------------------------
# Each entry: (contract_attr, event_name, decode_fn)
# decode_fn receives (args_dict, block_number, reg) and returns a dataclass.

def _decode_task_registered(args, block, reg):
    return dec.decode_task_registered(args, block)

def _decode_task_assigned(args, block, reg):
    return dec.decode_task_assigned(args, reg.task_manager)

def _decode_task_unassigned(args, block, reg):
    return dec.decode_task_unassigned(args)

def _decode_task_verified(args, block, reg):
    return dec.decode_task_verified(args)

def _decode_task_rejected(args, block, reg):
    return dec.decode_task_rejected(args)

def _decode_service_registered(args, block, reg):
    return dec.decode_service_registered(args, reg.service_manager)

def _decode_service_busy_updated(args, block, reg):
    return dec.decode_service_busy_updated(args)


# (contract attribute on ContractRegistry, event name on ABI, decode wrapper)
_EVENT_TABLE = [
    ("task_manager",    "TaskRegistered",    _decode_task_registered),
    ("task_manager",    "TaskAssigned",      _decode_task_assigned),
    ("task_manager",    "TaskUnassigned",    _decode_task_unassigned),
    ("task_manager",    "TaskVerified",      _decode_task_verified),
    ("task_manager",    "TaskRejected",      _decode_task_rejected),
    ("service_manager", "ServiceRegistered", _decode_service_registered),
    ("service_manager", "ServiceBusyUpdated",_decode_service_busy_updated),
]


# ---------------------------------------------------------------------------
# EthPoller
# ---------------------------------------------------------------------------

class EthPoller:
    """
    Polls DAO contract events and delivers them as typed dataclasses.

    Parameters
    ----------
    w3:
        Connected Web3 instance.  Prefer an HTTP provider to avoid websocket
        recv contention with the tx-sending nodes.
    reg:
        :class:`~eth.contracts.ContractRegistry` holding all contract objects.
    checkpoint:
        :class:`~eth.events.checkpoint.Checkpoint` that persists the last
        processed block/log-index so restarts don't replay old events.
    on_event:
        Callable invoked for every new event.  Receives a single argument: a
        typed dataclass from :mod:`eth.events.decoder`.
    poll_interval:
        Seconds between poll cycles.
    block_chunk:
        Maximum number of blocks queried per ``eth_getLogs`` call.  Keep this
        below 2 000 for ganache and public nodes.
    """

    def __init__(
        self,
        w3,
        reg: ContractRegistry,
        checkpoint: Checkpoint,
        on_event: Callable,
        poll_interval: float = 1.0,
        block_chunk: int = 1000,
    ) -> None:
        self.w3 = w3
        self.reg = reg
        self.ckpt = checkpoint
        self.on_event = on_event
        self.poll_interval = poll_interval
        self.block_chunk = block_chunk

        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="EthPoller")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread."""
        self._thread.start()
        logger.info("EthPoller started (interval=%.1fs, chunk=%d)",
                    self.poll_interval, self.block_chunk)

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the polling thread to stop and wait for it to finish."""
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        logger.info("EthPoller stopped")

    @property
    def is_running(self) -> bool:
        return self._thread.is_alive()

    # ------------------------------------------------------------------
    # Internal loop
    # ------------------------------------------------------------------

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_once()
            except Exception as exc:
                logger.warning("EthPoller error: %s", repr(exc))
            self._stop_event.wait(timeout=self.poll_interval)

    def _poll_once(self) -> None:
        latest = int(self.w3.eth.block_number)
        start  = self.ckpt.next_from_block(latest)

        # Chain-reset detection: if the stored cursor is ahead of the current
        # chain tip, a local chain (ganache / hardhat) was restarted.  Reset
        # the checkpoint to 0 so all events from the new deployment are seen.
        if start > latest:
            logger.warning(
                "EthPoller: checkpoint block %d > chain tip %d — "
                "chain restart detected, resetting cursor to 0",
                start, latest,
            )
            self.ckpt.reset()
            start = 0

        cursor = start
        while cursor <= latest and not self._stop_event.is_set():
            upper = min(cursor + self.block_chunk, latest)
            self._process_range(cursor, upper)
            cursor = upper + 1
            self.ckpt.save()

    def _process_range(self, from_block: int, to_block: int) -> None:
        last_block, last_index = self.ckpt.last_cursor()

        for contract_attr, event_name, decode_fn in _EVENT_TABLE:
            contract = getattr(self.reg, contract_attr, None)
            if contract is None:
                continue
            try:
                event_obj = getattr(contract.events, event_name)()
            except AttributeError:
                logger.debug("contract %s has no event %s", contract_attr, event_name)
                continue

            try:
                logs = _get_logs(event_obj, from_block, to_block)
            except Exception as exc:
                logger.warning("get_logs %s.%s [%d-%d] failed: %s",
                               contract_attr, event_name, from_block, to_block, exc)
                continue

            logs = sorted(logs, key=lambda e: (int(e["blockNumber"]), int(e["logIndex"])))
            for log in logs:
                blk = int(log["blockNumber"])
                idx = int(log["logIndex"])
                # skip already-processed entries
                if blk < last_block or (blk == last_block and idx <= last_index):
                    continue
                try:
                    event_obj_decoded = decode_fn(log["args"], blk, self.reg)
                    self.on_event(event_obj_decoded)
                except Exception as exc:
                    logger.error("decode %s.%s failed: %s", contract_attr, event_name, exc)
                finally:
                    self.ckpt.update_cursor(blk, idx)

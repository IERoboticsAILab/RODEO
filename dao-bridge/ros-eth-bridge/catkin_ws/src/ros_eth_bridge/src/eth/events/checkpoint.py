"""
eth/events/checkpoint.py — Disk-backed block cursor for the event poller.

Persists the last-seen (block, log_index) pair to a JSON file so the poller
resumes without replaying old events after a restart.

No rospy / ros_eth_msgs imports.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# Default location; override by passing a different path to Checkpoint().
CHECKPOINT_FILE = os.path.expanduser("~/.ros_eth/event_checkpoint.json")


class Checkpoint:
    """
    Persistent cursor that tracks the last event processed by the poller.

    Thread-safety: ``save()`` is atomic (write-to-tmp then rename).  The rest
    of the methods are intentionally not locked — the caller (EthPoller) owns
    the single polling thread, so concurrent mutation never happens.

    Parameters
    ----------
    path:
        File path for the JSON checkpoint.  Parent directories are created
        on first ``save()``.
    """

    def __init__(self, path: str = CHECKPOINT_FILE) -> None:
        self.path = path
        self.data: dict = {
            "from_block": None,
            "last_log": {"block": 0, "index": -1},
        }
        self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> None:
        try:
            with open(self.path) as f:
                self.data = json.load(f)
            logger.debug("checkpoint loaded from %s: %s", self.path, self.data)
        except FileNotFoundError:
            logger.debug("no checkpoint file at %s, starting fresh", self.path)
        except Exception as exc:
            logger.warning("could not load checkpoint (%s); starting fresh", exc)

    def save(self) -> None:
        """Atomically persist the current cursor to disk."""
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f)
        os.replace(tmp, self.path)

    # ------------------------------------------------------------------
    # Cursor helpers
    # ------------------------------------------------------------------

    def next_from_block(self, latest: int) -> int:
        """
        Return the block number the poller should start from.

        On the very first run (no checkpoint) returns *latest* so that only
        future events are delivered (no historical replay).
        """
        fb = self.data.get("from_block")
        if fb is None:
            return max(0, int(latest))
        return max(0, int(fb))

    def update_cursor(self, block: int, log_index: int) -> None:
        """Advance the cursor if *block/log_index* is newer than the stored one."""
        cur = self.data["last_log"]
        if block > cur["block"] or (block == cur["block"] and log_index > cur["index"]):
            cur["block"] = block
            cur["index"] = log_index
            self.data["from_block"] = block

    def reset(self) -> None:
        """Reset cursor to block 0 and persist.

        Called when the poller detects that the chain tip is behind the stored
        checkpoint (e.g. a local ganache restart).  Replaying from block 0
        ensures no events are missed after the chain is redeployed.
        """
        self.data = {"from_block": 0, "last_log": {"block": 0, "index": -1}}
        self.save()
        logger.info("checkpoint reset to block 0")

    def last_cursor(self) -> tuple[int, int]:
        """Return ``(block, log_index)`` of the last processed event."""
        cur = self.data.get("last_log", {"block": 0, "index": -1})
        return int(cur.get("block", 0)), int(cur.get("index", -1))

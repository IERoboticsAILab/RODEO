import threading
import time
import traceback

from .chain import _get_logs


class EventWatcher:
    """
    Polls TaskManager for oracle requests and verdicts with plain eth_getLogs over
    block ranges (no eth_newFilter: public, load-balanced RPCs such as OP Sepolia's
    lose filters between requests). Ranges are at most LOG_CHUNK blocks.
    """

    def __init__(self, chain):
        self.chain = chain
        self.web3 = chain.web3
        self.stop_event = threading.Event()
        self._processing = set()
        self._lock = threading.Lock()
        s = chain.settings
        self.start_block = int(getattr(s, "start_block", 0))
        self.chunk = max(1, int(getattr(s, "log_chunk", 10000)))

    def _handle_request(self, e, on_request):
        tid = int(e["args"]["taskId"])
        if self.web3.to_checksum_address(e["args"]["oracle"]) != self.chain.oracle_addr:
            return
        with self._lock:
            if tid in self._processing:
                return
            self._processing.add(tid)
        try:
            on_request(tid)
        finally:
            with self._lock:
                self._processing.discard(tid)

    def poll(self, from_block, to_block, on_request, on_verified=None, on_rejected=None):
        ev = self.chain.contract.events
        for e in _get_logs(ev.TaskOracleRequested, from_block, to_block):
            self._handle_request(e, on_request)
        if on_verified:
            for e in _get_logs(ev.TaskVerified, from_block, to_block):
                on_verified(int(e["args"]["taskId"]))
        if on_rejected:
            for e in _get_logs(ev.TaskRejected, from_block, to_block):
                on_rejected(int(e["args"]["taskId"]), e["args"]["reason"])

    def start(self, on_request, on_verified=None, on_rejected=None):
        # look back up to 1000 blocks to catch requests made while the oracle was down
        current_block = self.web3.eth.block_number
        cursor = max(self.start_block, current_block - 1000)
        print(f"Starting event watcher from block {cursor} (current: {current_block})")
        print("Watching oracle requests and outcomes")
        while not self.stop_event.is_set():
            try:
                latest = self.web3.eth.block_number
                while cursor <= latest and not self.stop_event.is_set():
                    hi = min(latest, cursor + self.chunk - 1)
                    self.poll(cursor, hi, on_request, on_verified, on_rejected)
                    cursor = hi + 1
            except Exception:  # noqa: BLE001 - keep watching (the range is retried), but say why
                print("Event watcher error:\n" + traceback.format_exc())
            self.stop_event.wait(2)

    def stop(self):
        self.stop_event.set()

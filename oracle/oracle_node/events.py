import threading
import time
import traceback


class EventWatcher:
    """Polls TaskManager for oracle requests and verdicts (same events as before)."""

    def __init__(self, chain):
        self.chain = chain
        self.web3 = chain.web3
        self.stop_event = threading.Event()
        self._processing = set()
        self._lock = threading.Lock()

    def _make_filter(self, event_obj, from_block="latest"):
        try:
            return event_obj.create_filter(fromBlock=from_block)
        except (TypeError, AttributeError):
            return event_obj.createFilter(fromBlock=from_block)

    def start(self, on_request, on_verified=None, on_rejected=None):
        # look back up to 1000 blocks to catch requests made while the oracle was down
        current_block = self.web3.eth.block_number
        from_block = max(0, current_block - 1000)
        print(f"Starting event watcher from block {from_block} (current: {current_block})")
        ev = self.chain.contract.events
        try:
            req_filter = self._make_filter(ev.TaskOracleRequested(), from_block)
            ok_filter = self._make_filter(ev.TaskVerified(), from_block)
            no_filter = self._make_filter(ev.TaskRejected(), from_block)
            print("Watching oracle requests and outcomes")
        except Exception as e:  # noqa: BLE001
            print(f"Could not start watcher, {e}")
            return

        while not self.stop_event.is_set():
            try:
                for e in req_filter.get_new_entries():
                    tid = int(e["args"]["taskId"])
                    if self.web3.to_checksum_address(e["args"]["oracle"]) != self.chain.oracle_addr:
                        continue
                    with self._lock:
                        if tid in self._processing:
                            continue
                        self._processing.add(tid)
                    try:
                        on_request(tid)
                    finally:
                        with self._lock:
                            self._processing.discard(tid)
                for e in ok_filter.get_new_entries():
                    if on_verified:
                        on_verified(int(e["args"]["taskId"]))
                for e in no_filter.get_new_entries():
                    if on_rejected:
                        on_rejected(int(e["args"]["taskId"]), e["args"]["reason"])
            except Exception:  # noqa: BLE001 - keep watching, but say why
                print("Event watcher error:\n" + traceback.format_exc())
            time.sleep(2)

    def stop(self):
        self.stop_event.set()

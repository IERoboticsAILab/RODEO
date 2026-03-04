import threading
import time

class EventWatcher:
    def __init__(self, tm_client):
        self.tm = tm_client
        self.web3 = tm_client.web3
        self.stop_event = threading.Event()
        self._processing = set()
        self._lock = threading.Lock()

    def _make_filter(self, event_obj, from_block="latest"):
        try:
            return event_obj.create_filter(fromBlock=from_block)
        except (TypeError, AttributeError):
            return event_obj.createFilter(fromBlock=from_block)

    def start(self, on_request, on_verified=None, on_rejected=None):
        # Calculate starting block (look back up to 1000 blocks to catch missed events)
        current_block = self.web3.eth.block_number
        lookback_blocks = 1000
        from_block = max(0, current_block - lookback_blocks)
        
        print(f"Starting event watcher from block {from_block} (current: {current_block})")
        
        try:
            req_filter = self._make_filter(self.tm.contract.events.TaskOracleRequested(), from_block)
            ok_filter  = self._make_filter(self.tm.contract.events.TaskVerified(), from_block)
            no_filter  = self._make_filter(self.tm.contract.events.TaskRejected(), from_block)
            print("Watching oracle requests and outcomes")
        except Exception as e:
            print(f"Could not start watcher, {e}")
            return

        while not self.stop_event.is_set():
            try:
                for ev in req_filter.get_new_entries():
                    tid = int(ev["args"]["taskId"])
                    ev_oracle = self.web3.to_checksum_address(ev["args"]["oracle"])
                    if ev_oracle != self.tm.oracle_addr:
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

                for ev in ok_filter.get_new_entries():
                    if on_verified:
                        on_verified(int(ev["args"]["taskId"]))

                for ev in no_filter.get_new_entries():
                    if on_rejected:
                        on_rejected(int(ev["args"]["taskId"]), ev["args"]["reason"])
            except Exception:
                pass
            time.sleep(2)

    def stop(self):
        self.stop_event.set()

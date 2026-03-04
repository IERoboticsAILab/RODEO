import threading
from web3 import Web3
from .settings import Settings
from .task_manager import TaskManagerClient
from .events import EventWatcher
from .controller import OracleController

def main():
    settings = Settings()
    web3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    tm_addr = settings.contracts["TaskManager"]
    tm = TaskManagerClient(web3, settings, tm_addr)
    controller = OracleController(web3, settings, tm)

    watcher = EventWatcher(tm)

    thread = threading.Thread(
        target=watcher.start,
        kwargs={
            "on_request": controller.handle_request,
            "on_verified": controller.on_verified,
            "on_rejected": controller.on_rejected
        },
        daemon=True
    )
    thread.start()
    try:
        controller.run_menu()
    finally:
        watcher.stop()
        thread.join(timeout=2)

if __name__ == "__main__":
    main()

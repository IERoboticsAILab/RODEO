import threading

from web3 import Web3

from .chain import ChainClient
from .controller import OracleController
from .events import EventWatcher
from .settings import Settings


def main():
    settings = Settings()
    web3 = Web3(Web3.HTTPProvider(settings.rpc_url))
    chain = ChainClient(web3, settings)
    controller = OracleController(web3, settings, chain)
    watcher = EventWatcher(chain)
    thread = threading.Thread(
        target=watcher.start,
        kwargs={"on_request": controller.handle_request,
                "on_verified": controller.on_verified,
                "on_rejected": controller.on_rejected},
        daemon=True)
    if settings.watch:
        thread.start()
    else:
        print("Console only (ORACLE_WATCH=0): not watching the chain")
    try:
        controller.run_menu()
    finally:
        watcher.stop()
        if thread.is_alive():
            thread.join(timeout=2)


if __name__ == "__main__":
    main()

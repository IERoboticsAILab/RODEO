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
    thread.start()
    try:
        controller.run_menu()
    finally:
        watcher.stop()
        thread.join(timeout=2)


if __name__ == "__main__":
    main()

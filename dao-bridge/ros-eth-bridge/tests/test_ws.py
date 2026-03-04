import asyncio
from web3 import AsyncWeb3, WebSocketProvider

async def test_ws():
    w3 = AsyncWeb3(WebSocketProvider("ws://127.0.0.1:8545"))
    connected = await w3.is_connected()
    print("Connected:", connected)

asyncio.run(test_ws())


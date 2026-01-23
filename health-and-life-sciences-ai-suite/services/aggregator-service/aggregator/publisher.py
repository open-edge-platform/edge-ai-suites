import time
from aggregator.server import ws_manager
import asyncio

async def publish(workload, device_id, payload, timestamp=None):
    message = {
        "workload": workload,
        "device_id": device_id,
        "timestamp": timestamp or int(time.time()),
        "payload": payload
    }
    await ws_manager.broadcast(message)

from fastapi import WebSocket
from typing import Dict, Set
import asyncio
import json

class WebSocketManager:
    def __init__(self):
        # websocket -> set(workloads)
        self.connections: Dict[WebSocket, Set[str]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self.lock:
            # default: subscribe to everything
            self.connections[websocket] = {"ai-ecg", "rppg", "3d-pose", "mdpnp"}

    async def disconnect(self, websocket: WebSocket):
        async with self.lock:
            self.connections.pop(websocket, None)

    async def update_subscription(self, websocket: WebSocket, workloads: Set[str]):
        async with self.lock:
            if websocket in self.connections:
                self.connections[websocket] = workloads

    async def broadcast(self, message: dict):
        workload = message.get("workload")
        data = json.dumps(message)

        async with self.lock:
            for ws, subscriptions in list(self.connections.items()):
                if workload in subscriptions:
                    try:
                        await ws.send_text(data)
                    except Exception:
                        self.connections.pop(ws, None)

import asyncio
import json
from typing import Dict, Set, Optional


class SSEManager:
    """Manage Server-Sent Events (SSE) subscribers and broadcasts.

    Each subscriber is represented by an asyncio.Queue that the HTTP handler
    will drain and stream to the client as SSE frames.
    """

    def __init__(self):
        # queue -> set(workloads)
        self.subscribers: Dict[asyncio.Queue, Set[str]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, workloads: Optional[Set[str]] = None) -> asyncio.Queue:
        """Register a new SSE client and return its message queue.

        If workloads is None or empty, subscribe the client to all known
        workloads by default.
        """
        if not workloads:
            workloads = {"ai-ecg", "rppg", "3d-pose", "mdpnp"}

        queue: asyncio.Queue = asyncio.Queue()
        async with self.lock:
            self.subscribers[queue] = set(workloads)
        return queue

    async def disconnect(self, queue: asyncio.Queue) -> None:
        async with self.lock:
            self.subscribers.pop(queue, None)

    async def update_subscription(self, queue: asyncio.Queue, workloads: Set[str]) -> None:
        async with self.lock:
            if queue in self.subscribers:
                self.subscribers[queue] = set(workloads)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a message to all subscribers interested in its workload."""
        workload = message.get("workload") or message.get("workload_type")
        data = json.dumps(message)

        async with self.lock:
            for q, subscriptions in list(self.subscribers.items()):
                if workload in subscriptions:
                    try:
                        q.put_nowait(data)
                    except asyncio.QueueFull:
                        # If a client is too slow, drop the message for it.
                        pass

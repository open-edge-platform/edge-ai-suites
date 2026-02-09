import asyncio
import json
from typing import Dict, Set, Optional


class SSEManager:
    """Manage Server-Sent Events (SSE) subscribers and broadcasts."""

    def __init__(self):
        self.subscribers: Dict[asyncio.Queue, Set[str]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, workloads: Optional[Set[str]] = None) -> asyncio.Queue:
        """Register a new SSE client."""
        if not workloads:
            workloads = {"ai-ecg", "rppg", "3d-pose", "mdpnp"}

        queue: asyncio.Queue = asyncio.Queue()
        async with self.lock:
            self.subscribers[queue] = set(workloads)
        
        print(f"✓ [SSEManager] Client connected, subscribed to: {workloads}")
        return queue

    async def disconnect(self, queue: asyncio.Queue) -> None:
        async with self.lock:
            self.subscribers.pop(queue, None)
        print("✓ [SSEManager] Client disconnected")

    async def update_subscription(self, queue: asyncio.Queue, workloads: Set[str]) -> None:
        async with self.lock:
            if queue in self.subscribers:
                self.subscribers[queue] = set(workloads)

    async def broadcast(self, message: dict) -> None:
        """Broadcast message to all interested subscribers."""
        # ✅ Support both 'workload' and 'workload_type'
        workload = message.get("workload_type") or message.get("workload")
        
        if not workload:
            print(f"⚠️ [SSEManager] Message missing workload field: {list(message.keys())}")
            return
        
        data = json.dumps(message)
        
        async with self.lock:
            sent_count = 0
            for q, subscriptions in list(self.subscribers.items()):
                # ✅ Check if workload matches subscription
                if workload in subscriptions:
                    try:
                        q.put_nowait(data)
                        sent_count += 1
                    except asyncio.QueueFull:
                        print(f"⚠️ [SSEManager] Queue full, dropping message")
            
            if sent_count > 0:
                print(f"✓ [SSEManager] Broadcast '{workload}' → {sent_count} client(s)")
            else:
                print(f"⚠️ [SSEManager] No subscribers for '{workload}' (active: {[list(s) for s in self.subscribers.values()]})")
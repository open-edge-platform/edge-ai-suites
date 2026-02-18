"""EventManager - SSE Pub/Sub System for real-time event broadcasting."""

import asyncio
import logging
from typing import Set

logger = logging.getLogger(__name__)


class EventManager:
    """
    Manages SSE subscriptions and event broadcasting.
    
    Usage:
        manager = EventManager()
        queue = await manager.subscribe()  # Client connects
        await manager.broadcast("analysis", {"stream_id": "cam1", "results": {...}})
        await manager.unsubscribe(queue)   # Client disconnects
    """
    
    def __init__(self, max_queue_size: int = 50):
        """
        Initialize the EventManager.
        
        Args:
            max_queue_size: Maximum events to buffer per subscriber.
                           If exceeded, subscriber is considered "slow" and removed.
        """
        self._subscribers: Set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()
        self._max_queue_size = max_queue_size

    async def subscribe(self) -> asyncio.Queue:
        """
        Register a new SSE subscriber.
        
        Returns:
            asyncio.Queue: A queue that will receive all broadcast events.
        """
        queue = asyncio.Queue(maxsize=self._max_queue_size)
        async with self._lock:
            self._subscribers.add(queue)
        logger.info(f"SSE subscriber added. Total: {len(self._subscribers)}")
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        """
        Remove an SSE subscriber.
        
        Args:
            queue: The subscriber's queue to remove.
        """
        async with self._lock:
            self._subscribers.discard(queue)
        logger.info(f"SSE subscriber removed. Total: {len(self._subscribers)}")

    async def broadcast(self, event_type: str, data: dict):
        """
        Send an event to all connected subscribers.
        
        Args:
            event_type: The SSE event name (e.g., "analysis", "stream_added")
            data: The event payload (will be JSON serialized by the endpoint)
        
        Note:
            Slow subscribers (full queues) are automatically removed to prevent
            memory buildup and blocking.
        """
        if not self._subscribers:
            return

        payload = {"event": event_type, "data": data}
        
        async with self._lock:
            dead_queues = []
            for queue in self._subscribers:
                try:
                    # put_nowait raises QueueFull if subscriber is too slow
                    queue.put_nowait(payload)
                except asyncio.QueueFull:
                    dead_queues.append(queue)
                    logger.warning("Removing slow SSE subscriber (queue full)")
            
            # Clean up slow subscribers
            for q in dead_queues:
                self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        """Return the current number of SSE subscribers."""
        return len(self._subscribers)

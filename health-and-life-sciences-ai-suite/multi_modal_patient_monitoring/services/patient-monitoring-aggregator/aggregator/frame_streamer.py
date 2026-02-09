import asyncio
from typing import Dict, Optional

class FrameStreamManager:
    """Manage video frame streaming to multiple clients."""
    
    def __init__(self, max_queue_size: int = 10):
        self.subscribers: Dict[asyncio.Queue, bool] = {}
        self.lock = asyncio.Lock()
        self.max_queue_size = max_queue_size
    
    async def connect(self) -> asyncio.Queue:
        """Register a new video stream client and return its frame queue."""
        queue = asyncio.Queue(maxsize=self.max_queue_size)
        async with self.lock:
            self.subscribers[queue] = True
        print(f"[FrameStreamer] New client connected, total: {len(self.subscribers)}")
        return queue
    
    async def disconnect(self, queue: asyncio.Queue) -> None:
        """Remove a client from frame streaming."""
        async with self.lock:
            self.subscribers.pop(queue, None)
        print(f"[FrameStreamer] Client disconnected, remaining: {len(self.subscribers)}")
    
    async def broadcast_frame(self, frame_data: bytes) -> None:
        """Broadcast a frame to all connected clients."""
        if not self.subscribers:
            return
        
        async with self.lock:
            dropped_clients = []
            sent_count = 0
            
            for queue in list(self.subscribers.keys()):
                try:
                    # Non-blocking put, drop frame if queue is full
                    queue.put_nowait(frame_data)
                    sent_count += 1
                except asyncio.QueueFull:
                    # Drop oldest frame and add new one
                    try:
                        queue.get_nowait()  # Remove old frame
                        queue.put_nowait(frame_data)  # Add new frame
                        sent_count += 1
                    except:
                        # Client might be disconnected
                        dropped_clients.append(queue)
                except Exception:
                    dropped_clients.append(queue)
            
            # Clean up disconnected clients
            for queue in dropped_clients:
                self.subscribers.pop(queue, None)
            
            if sent_count > 0:
                print(f"[FrameStreamer] Broadcast frame to {sent_count} clients, "
                      f"dropped {len(dropped_clients)} dead clients")
import cv2
import threading
import time
import logging
from collections import deque
from src.config import settings

logger = logging.getLogger(__name__)

class LiveStreamManager:
    def __init__(self, rtsp_url: str):
        self.rtsp_url = rtsp_url
        self.frame_buffer = deque(maxlen=settings.FRAME_BUFFER_SIZE)
        self.running = False
        self.thread = None
        self._lock = threading.Lock()

    def start(self):
        if self.running: return
        self.running = True
        self.thread = threading.Thread(target=self._ingest_loop, daemon=True)
        self.thread.start()
        logger.info(f"Started LiveStreamManager for {self.rtsp_url}")

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)

    def get_recent_frames(self, count: int = 1):
        with self._lock:
            if len(self.frame_buffer) < count:
                return []
            return list(self.frame_buffer)[-count:]

    def _ingest_loop(self):
        cap = cv2.VideoCapture(self.rtsp_url)
        is_local_file = not str(self.rtsp_url).startswith(("rtsp://", "http://", "https://"))
        
        while self.running:
            if not cap.isOpened():
                cap = cv2.VideoCapture(self.rtsp_url)
                if not cap.isOpened():
                    time.sleep(5)
                    continue

            ret, frame = cap.read()
            if not ret:
                if is_local_file:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                
                logger.warning("Stream disconnected. Reconnecting...")
                cap.release()
                time.sleep(2)
                cap = cv2.VideoCapture(self.rtsp_url)
                continue

            with self._lock:
                self.frame_buffer.append(frame)
        
        cap.release()

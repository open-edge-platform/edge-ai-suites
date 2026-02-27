
from collections import defaultdict, deque
import time

class TimeWindowBuffer:
    def __init__(self, window_seconds=5):
        self.window = window_seconds
        self.buffers = defaultdict(deque)

    def add(self, key, timestamp, value):
        self.buffers[key].append((timestamp, value))
        self._evict_old(key)

    def _evict_old(self, key):
        now = time.time()
        while self.buffers[key] and (now - self.buffers[key][0][0]) > self.window:
            self.buffers[key].popleft()

    def get(self, key):
        return list(self.buffers[key])

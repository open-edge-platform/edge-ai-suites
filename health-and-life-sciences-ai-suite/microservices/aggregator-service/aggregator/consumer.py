
from .buffers import TimeWindowBuffer
from .processor import VitalProcessor

class VitalConsumer:
    def __init__(self, window_seconds=5):
        self.buffer = TimeWindowBuffer(window_seconds)
        self.processor = VitalProcessor()

    def consume(self, vital):
        key = (vital.device_id, vital.metric)
        ts_sec = vital.timestamp / 1000.0
        self.buffer.add(key, ts_sec, vital.value)

        samples = self.buffer.get(key)
        result = self.processor.process(vital.device_id, vital.metric, samples)
        if result:
            print("Aggregated:", result)

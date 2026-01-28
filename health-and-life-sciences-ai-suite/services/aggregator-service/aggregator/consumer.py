from .buffers import TimeWindowBuffer
from .processor import VitalProcessor


class VitalConsumer:
    def __init__(self, window_seconds=5):
        self.buffer = TimeWindowBuffer(window_seconds)
        self.processor = VitalProcessor()

    def consume(self, vital):
        key = (vital.device_id, vital.metric)
        ts_sec = vital.timestamp / 1000.0
        # ---- Waveform handling (ECG / other waveforms) ----
        if len(vital.waveform) > 0:
            result = {
                "device_id": vital.device_id,
                "metric": vital.metric,
                "timestamp": vital.timestamp,
                "waveform": list(vital.waveform),
                "waveform_frequency_hz": vital.waveform_frequency_hz,
            }
            print("[Aggregator] ECG/waveform forwarded:", {
                "device_id": vital.device_id,
                "metric": vital.metric,
                "samples": len(vital.waveform),
                "fs": vital.waveform_frequency_hz,
            })
            return result

        # ---- Numeric vitals (HR, SPO2, RR, BP, etc.) ----
        self.buffer.add(key, ts_sec, vital.value)
        samples = self.buffer.get(key)

        result = self.processor.process(
            vital.device_id,
            vital.metric,
            samples,
        )

        if result:
            print("[Aggregator] Aggregated result:", {
                "device_id": vital.device_id,
                "metric": vital.metric,
                "result": result,
            })
            return result

        return None

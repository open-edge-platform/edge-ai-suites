"""
VitalConsumer - Handles both waveform and numeric vitals.
"""

from .buffers import TimeWindowBuffer
from .processor import VitalProcessor


class VitalConsumer:
    """
    Consumes Vital messages and processes them based on type:
    - Waveform vitals: Forward immediately with waveform data
    - Numeric vitals: Aggregate over time window
    """
    
    def __init__(self, window_seconds=5):
        self.buffer = TimeWindowBuffer(window_seconds)
        self.processor = VitalProcessor()

    def consume(self, vital):
        """
        Process a Vital message.
        
        Returns:
            dict: Processed result ready for WebSocket broadcast, or None
        """
        key = (vital.device_id, vital.metric)
        # If the producer (e.g., DDS-bridge) provided a logical device_type
        # via the Vital.metadata map, propagate it into the payload so the
        # UI can easily distinguish different simulators/devices.
        device_type = None
        try:
            # vital.metadata is a dict-like mapping (string -> string)
            device_type = vital.metadata.get("device_type")
        except Exception:
            device_type = None
        ts_sec = vital.timestamp / 1000.0
        # ---- Waveform handling (ECG / other waveforms) ----
        if len(vital.waveform) > 0:
            result = {
                "device_id": vital.device_id,
                "metric": vital.metric,
                "timestamp": vital.timestamp,
                "waveform": list(vital.waveform),  # Raw waveform samples
                "waveform_frequency_hz": vital.waveform_frequency_hz,
            }
            if device_type:
                result["device_type"] = device_type
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
            if device_type and isinstance(result, dict):
                result.setdefault("device_type", device_type)
            print(f"[Consumer] Numeric aggregated: "
                  f"{vital.device_id}/{vital.metric} = {result}")
            return result

        return None


import statistics

class VitalProcessor:
    def process(self, device_id, metric, samples):
        if not samples:
            return None

        values = [v for _, v in samples]

        if metric in ("HR", "SPO2"):
            return {
                "device_id": device_id,
                "metric": metric,
                "avg": statistics.mean(values),
                "min": min(values),
                "max": max(values),
            }

        return {
            "device_id": device_id,
            "metric": metric,
            "value": values[-1],
        }

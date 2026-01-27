import time
import requests
import grpc
from proto import vital_pb2, vital_pb2_grpc


AI_ECG_URL = "http://localhost:8000/predict_stream_next"
AGGREGATOR_GRPC = "localhost:50051"


class AIECGClient:
    """Simple HTTP client for the AI-ECG backend.

    The client polls the AI-ECG service for the next prediction and returns
    a JSON-serializable dictionary that can be pushed directly to the
    aggregator's WebSocket message queue.
    """

    def __init__(self, url: str = AI_ECG_URL):
        self.url = url

    def poll_next(self):
        """Fetch the next ECG sample and inference result.

        Returns a dict with waveform and metadata or None on error.
        """
        try:
            resp = requests.get(self.url, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            signal = data.get("signal", [])
            result = data.get("result", {})

            return {
                "device_id": "ai-ecg-001",
                "metric": "ECG",
                "timestamp": int(time.time() * 1000),
                "waveform": signal,
                "waveform_frequency_hz": 360,
                "inference": result,
            }
        except Exception as e:
            print("[AI-ECG] poll_next error:", e)
            return None


def run_ai_ecg_stream():
    """Legacy helper that streams Vital messages to the gRPC server.

    Kept for compatibility with existing callers that expect a continuous
    gRPC stream of Vital protos.
    """
    channel = grpc.insecure_channel(AGGREGATOR_GRPC)
    stub = vital_pb2_grpc.VitalServiceStub(channel)

    def ecg_generator():
        while True:
            try:
                resp = requests.get(AI_ECG_URL, timeout=5)
                data = resp.json()
                signal = data["signal"]
                result = data["result"]
                yield vital_pb2.Vital(
                    device_id="ai-ecg-001",
                    metric="ECG",
                    value=float(result.get("label", 0)),
                    unit="class",
                    timestamp=int(time.time() * 1000),
                    waveform=signal,
                    waveform_frequency_hz=360,
                )
                time.sleep(1)
            except Exception as e:
                print("[AI-ECG] error:", e)
                time.sleep(2)

    stub.StreamVitals(ecg_generator())
import time
import requests
import grpc
import vital_pb2
import vital_pb2_grpc


AI_ECG_URL = "http://localhost:8000/predict_stream_next"
AGGREGATOR_GRPC = "localhost:50051"

def run_ai_ecg_stream():
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
                    waveform_frequency_hz=360
                )
                time.sleep(1)
            except Exception as e:
                print("[AI-ECG] error:", e)
                time.sleep(2)
    stub.StreamVitals(ecg_generator())
import asyncio
import json
import os
import threading
import queue
import time

import grpc
from concurrent import futures
from fastapi import FastAPI, WebSocket
import uvicorn
from google.protobuf.empty_pb2 import Empty

from proto import vital_pb2, vital_pb2_grpc, pose_pb2, pose_pb2_grpc
from .consumer import VitalConsumer
from .ws_broadcaster import WebSocketManager
from .ai_ecg_client import AIECGClient


app = FastAPI(title="Aggregator Service")
ws_manager = WebSocketManager()

# Thread-safe queue used to pass messages from the gRPC thread
# to the asyncio event loop that manages WebSocket broadcasts.
message_queue: "queue.Queue[dict]" = queue.Queue()

# Environment-configurable workload label for this instance
WORKLOAD_TYPE = os.getenv("WORKLOAD_TYPE", "mdpnp")


@app.websocket("/ws/stream")
async def stream_ws(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)

            # Subscription message from UI
            if data.get("action") == "subscribe":
                workloads = set(data.get("workloads", []))
                await ws_manager.update_subscription(websocket, workloads)
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(websocket)


async def broadcast_loop():
    """Background task that forwards queued messages to all subscribers."""
    while True:
        # Block in a worker thread waiting for the next message
        message = await asyncio.to_thread(message_queue.get)
        await ws_manager.broadcast(message)


class VitalService(vital_pb2_grpc.VitalServiceServicer):
    """gRPC service that receives Vital streams and enqueues aggregated results."""

    def __init__(self, workload_type: str):
        self.workload_type = workload_type
        self.consumer = VitalConsumer()

    def StreamVitals(self, request_iterator, context):
        for vital in request_iterator:
            # Infer event type based on presence of waveform samples
            event_type = "waveform" if len(vital.waveform) > 0 else "numeric"

            print("[Aggregator] Received Vital from gRPC:", {
                "device_id": vital.device_id,
                "metric": vital.metric,
                "value": vital.value,
                "unit": vital.unit,
                "timestamp": vital.timestamp,
                "waveform_len": len(vital.waveform),
                "waveform_frequency_hz": vital.waveform_frequency_hz
            })
            result = self.consumer.consume(vital)
            if result:
                message = {
                    "workload_type": self.workload_type,
                    "event_type": event_type,
                    "timestamp": vital.timestamp,                    
                    "payload": result,
                }
                print("[Aggregator] Enqueuing message for WebSocket:", message)
                message_queue.put(message)
        return Empty()


class PoseService(pose_pb2_grpc.PoseServiceServicer):
    """gRPC service that receives PoseFrame messages from 3D pose workloads.

    It converts PoseFrame protos into JSON-serializable dictionaries and
    enqueues them for broadcasting over WebSocket to interested UI clients.
    """

    def PublishPose(self, request: pose_pb2.PoseFrame, context):
        try:
            people_payload = []
            for person in request.people:
                joints_2d = [
                    {"x": j.x, "y": j.y}
                    for j in person.joints_2d
                ]
                joints_3d = [
                    {"x": j.x, "y": j.y, "z": j.z}
                    for j in person.joints_3d
                ]
                people_payload.append(
                    {
                        "person_id": person.person_id,
                        "joints_2d": joints_2d,
                        "joints_3d": joints_3d,
                        "confidence": list(person.confidence),
                    }
                )

            message = {
                "workload_type": "3d-pose",
                "event_type": "pose3d",
                "timestamp": request.timestamp_ms,
                "payload": {
                    "source_id": request.source_id,
                    "people": people_payload,
                },
            }

            print("[Aggregator] Received PoseFrame from gRPC:", message)
            message_queue.put(message)

            return pose_pb2.Ack(ok=True)
        except Exception as exc:
            print("[Aggregator] Error handling PoseFrame:", exc)
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(exc))
            return pose_pb2.Ack(ok=False)


async def ai_ecg_polling_loop():
    """Poll AI-ECG backend and enqueue waveform + inference results."""
    client = AIECGClient()
    while True:
        result = await asyncio.to_thread(client.poll_next)
        if result:
            message = {
                "workload_type": "ai-ecg",
                "event_type": "waveform",
                "timestamp": int(time.time() * 1000),
                "payload": result,
            }
            message_queue.put(message)
            print("[Aggregator] Broadcasted AI-ECG result", message)
        await asyncio.sleep(1.0)


def start_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    vital_pb2_grpc.add_VitalServiceServicer_to_server(
        VitalService(WORKLOAD_TYPE), server
    )
    pose_pb2_grpc.add_PoseServiceServicer_to_server(
        PoseService(), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    print("Aggregator gRPC server running on port 50051")
    server.wait_for_termination()


@app.on_event("startup")
async def on_startup():
    # Start background broadcaster task
    app.state.broadcast_task = asyncio.create_task(broadcast_loop())
    app.state.ai_ecg_task = asyncio.create_task(ai_ecg_polling_loop())

    # Start gRPC server in a background thread
    t = threading.Thread(target=start_grpc_server, daemon=True)
    t.start()
    app.state.grpc_thread = t


if __name__ == "__main__":
    uvicorn.run(
        "aggregator.server:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )

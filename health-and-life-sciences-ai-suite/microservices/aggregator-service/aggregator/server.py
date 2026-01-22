import asyncio
import json
import os
import threading
import queue

import grpc
from concurrent import futures
from fastapi import FastAPI, WebSocket
import uvicorn
from google.protobuf.empty_pb2 import Empty

import vital_pb2
import vital_pb2_grpc
from .consumer import VitalConsumer
from .ws_broadcaster import WebSocketManager


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
            print("[Aggregator] Received Vital from gRPC:", {
                "device_id": vital.device_id,
                "metric": vital.metric,
                "value": vital.value,
                "unit": vital.unit,
                "timestamp": vital.timestamp,
            })
            result = self.consumer.consume(vital)
            if result:
                message = {
                    "workload_type": self.workload_type,
                    "timestamp": vital.timestamp,
                    "payload": result,
                }
                print("[Aggregator] Enqueuing message for WebSocket:", message)
                message_queue.put(message)
        return Empty()


def start_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    vital_pb2_grpc.add_VitalServiceServicer_to_server(
        VitalService(WORKLOAD_TYPE), server
    )
    server.add_insecure_port("[::]:50051")
    server.start()
    print("Aggregator gRPC server running on port 50051")
    server.wait_for_termination()


@app.on_event("startup")
async def on_startup():
    # Start background broadcaster task
    app.state.broadcast_task = asyncio.create_task(broadcast_loop())

    # Start gRPC server in a background thread
    t = threading.Thread(target=start_grpc_server, daemon=True)
    t.start()
    app.state.grpc_thread = t


if __name__ == "__main__":
    uvicorn.run(
        "aggregator.server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
    )

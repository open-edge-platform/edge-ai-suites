import asyncio
import json
import os
import threading
import time

import grpc
from concurrent import futures
from fastapi import FastAPI, Request, Query
from fastapi.responses import StreamingResponse
import uvicorn
from google.protobuf.empty_pb2 import Empty

from proto import vital_pb2, vital_pb2_grpc, pose_pb2, pose_pb2_grpc
from .consumer import VitalConsumer
from .ws_broadcaster import SSEManager
from .ai_ecg_client import AIECGClient


app = FastAPI(title="Aggregator Service")
sse_manager = SSEManager()

# Main asyncio event loop reference for cross-thread broadcasts
event_loop: asyncio.AbstractEventLoop | None = None

# Environment-configurable workload label for this instance
WORKLOAD_TYPE = os.getenv("WORKLOAD_TYPE", "mdpnp")


@app.get("/events")
async def stream_events(
    request: Request,
    workloads: str | None = Query(
        None,
        description=(
            "Optional comma-separated list of workload types to subscribe to "
            "(e.g., ai-ecg,mdpnp). If omitted, all workloads are sent."
        ),
    ),
):
    """SSE endpoint that streams aggregator events to connected clients.

    If the "workloads" query param is provided, only those workloads are
    delivered to the client; otherwise all four workloads are streamed.
    """
    if workloads:
        workload_set = {w.strip() for w in workloads.split(",") if w.strip()}
    else:
        workload_set = None

    client_queue = await sse_manager.connect(workload_set)

    async def event_generator():
        try:
            while True:
                # Exit cleanly if the client disconnects
                if await request.is_disconnected():
                    break

                try:
                    data = await asyncio.wait_for(client_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                yield f"data: {data}\n\n"
        finally:
            await sse_manager.disconnect(client_queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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
                print("[Aggregator] Broadcasting message to SSE clients:", message)
                if event_loop is not None:
                    asyncio.run_coroutine_threadsafe(
                        sse_manager.broadcast(message), event_loop
                    )
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
            if event_loop is not None:
                asyncio.run_coroutine_threadsafe(
                    sse_manager.broadcast(message), event_loop
                )

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
            if event_loop is not None:
                await sse_manager.broadcast(message)
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
    # Capture the running loop for cross-thread broadcasts
    global event_loop
    event_loop = asyncio.get_running_loop()

    # Start background AI-ECG polling task
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

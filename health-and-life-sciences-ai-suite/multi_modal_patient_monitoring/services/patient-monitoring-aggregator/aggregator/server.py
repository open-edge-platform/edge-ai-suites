import asyncio
import grpc
import json
import os
import time
import threading
import requests
import base64 
from concurrent import futures
from typing import Optional

from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google.protobuf.empty_pb2 import Empty
import uvicorn

from proto import vital_pb2, vital_pb2_grpc, pose_pb2, pose_pb2_grpc
from .consumer import VitalConsumer
from .ws_broadcaster import SSEManager
from .frame_streamer import FrameStreamManager
from .ai_ecg_client import AIECGClient

# Add frame streaming manager initialization
frame_manager = FrameStreamManager()

app = FastAPI(title="Aggregator Service")

# CORS middleware so UI (on a different port) can call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev; narrow to specific origins if desired
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
sse_manager = SSEManager()

event_loop: asyncio.AbstractEventLoop | None = None

WORKLOAD_TYPE = os.getenv("WORKLOAD_TYPE", "mdpnp")
METRICS_SERVICE_URL = os.getenv("METRICS_SERVICE_URL", "http://localhost:9000")
DDS_BRIDGE_CONTROL_URL = os.getenv("DDS_BRIDGE_CONTROL_URL", "http://localhost:8082")
POSE_3D_CONTROL_URL = os.getenv("POSE_3D_CONTROL_URL", "http://localhost:8083")
RPPG_CONTROL_URL = os.getenv("RPPG_CONTROL_URL", "http://localhost:8084")


def _proxy_metrics_get(path: str):
    """Proxy GET request to metrics service."""
    url = f"{METRICS_SERVICE_URL}{path}"
    try:
        resp = requests.get(url, timeout=5)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"metrics-service unreachable: {exc}")
    
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Invalid JSON from metrics-service")
    
    return JSONResponse(content=data, status_code=200)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "aggregator",
        "version": "1.0.0",
        "timestamp": int(time.time() * 1000),
        "workload_type": WORKLOAD_TYPE,
        "grpc_port": int(os.getenv("GRPC_PORT", "50051")),
        "http_port": 8001
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Health AI Aggregator Service",
        "version": "1.0.0",
        "workload_type": WORKLOAD_TYPE,
        "endpoints": [
            "GET /health - Service health",
            "GET / - This info",
            "GET /events - SSE stream",
            "GET /video-stream - Video frames stream", 
            "GET /metrics - System metrics",
            "GET /platform-info - Platform info",
            "GET /memory - Memory usage",
            "GET /device-config - Device configuration summary",
            "POST /start - Start streaming",
            "POST /stop - Stop streaming"
        ]
    }


@app.get("/events")
async def stream_events(
    request: Request,
    workloads: str | None = Query(
        None,
        description="Comma-separated workload types (e.g., ai-ecg,mdpnp,rppg,3d-pose). If omitted, all workloads are sent."
    ),
):
    """SSE endpoint for streaming vitals."""
    if workloads:
        workload_set = {w.strip() for w in workloads.split(",") if w.strip()}
    else:
        workload_set = None
    
    print(f"[SSE] Client connected, filter: {workload_set or 'all'}")
    
    client_queue = await sse_manager.connect(workload_set)
    
    print(f"[SSE] Total subscribers: {len(sse_manager.subscribers)}")
    
    async def event_generator():
        message_count = 0
        try:
            while True:
                if await request.is_disconnected():
                    print(f"[SSE] Client disconnected after {message_count} messages")
                    break
                
                try:
                    data = await asyncio.wait_for(client_queue.get(), timeout=30.0)
                    message_count += 1
                    print(f"[SSE] Sending message {message_count}")
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
                    
        finally:
            await sse_manager.disconnect(client_queue)
            print(f"[SSE] Client cleanup complete")
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )



@app.get("/video-stream")
async def stream_video_frames(request: Request):
    """Stream video frames from 3D pose detection as MJPEG."""
    print("[VIDEO] Client connected to video stream")
    
    client_queue = await frame_manager.connect()
    
    async def frame_generator():
        frame_count = 0
        try:
            while True:
                if await request.is_disconnected():
                    print(f"[VIDEO] Client disconnected after {frame_count} frames")
                    break
                
                try:
                    # Wait for next frame with timeout
                    frame_data = await asyncio.wait_for(client_queue.get(), timeout=5.0)
                    frame_count += 1
                    
                    # MJPEG format: each frame is a separate JPEG with multipart boundary
                    yield (
                        b'--frame\r\n'
                        b'Content-Type: image/jpeg\r\n\r\n' +
                        frame_data + b'\r\n'
                    )
                    
                except asyncio.TimeoutError:
                    # Send a small keepalive frame or continue waiting
                    continue
                    
        except Exception as e:
            print(f"[VIDEO] Error in frame generator: {e}")
        finally:
            await frame_manager.disconnect(client_queue)
            print(f"[VIDEO] Client cleanup complete, sent {frame_count} frames")
    
    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/metrics")
async def metrics_summary():
    """Proxy for metrics service."""
    return _proxy_metrics_get("/metrics")


@app.get("/platform-info")
async def platform_info():
    """Proxy for platform info."""
    return _proxy_metrics_get("/platform-info")


@app.get("/memory")
async def memory_usage():
    """Proxy for memory usage."""
    return _proxy_metrics_get("/memory")


@app.get("/workload-devices")
async def device_config():
    """Proxy for device configuration summary."""
    return _proxy_metrics_get("/device-config")


@app.get("/streaming-status")
async def stream_window_state():
    """Return current streaming window state for UI (lock + remaining time)."""
    now = time.time()
    lock_until = getattr(app.state, "streaming_lock_until", None)

    if lock_until is None or now >= lock_until:
        return {
            "locked": False,
            "remaining_seconds": 0,
        }

    remaining = int(lock_until - now)
    return {
        "locked": True,
        "remaining_seconds": max(0, remaining),
    }

@app.post("/start")
async def start_workloads(target: str = Query("dds-bridge", description="Which workload to start (e.g., mdpnp, ai-ecg, 3d-pose, rppg, or all)")):
    """Wrapper API for UI to start streaming from backend workloads."""
    targets = {t.strip() for t in target.split(",")} if target else {"dds-bridge"}
    results: dict[str, str] = {}

    def _call(url: str) -> str:
        try:
            resp = requests.post(url, timeout=3)
            return f"{resp.status_code}: {resp.text}"
        except Exception as exc:
            return f"error: {exc}"
        
    def _check_status(url: str) -> bool:
        """Check if service is already running"""
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("enabled", False)
        except Exception:
            pass
        return False

    # MDPNP / DDS-Bridge
    if "all" in targets or "mdpnp" in targets:
        results["dds-bridge"] = _call(f"{DDS_BRIDGE_CONTROL_URL}/start")
    
    # AI-ECG
    if "all" in targets or "ai-ecg" in targets:
        if app.state.ai_ecg_task is None:
            app.state.ai_ecg_task = asyncio.create_task(ai_ecg_polling_loop())
            results["ai-ecg"] = "started"
        else:
            results["ai-ecg"] = "already running"

    # 3D Pose
    if "all" in targets or "3d-pose" in targets:
        is_running = _check_status(f"{POSE_3D_CONTROL_URL}/status")
        if is_running:
            results["3d-pose"] = "already running"
        else:
            results["3d-pose"] = _call(f"{POSE_3D_CONTROL_URL}/start")

    # RPPG
    if "all" in targets or "rppg" in targets:
        is_running = _check_status(f"{RPPG_CONTROL_URL}/status")
        if is_running:
            results["rppg"] = "already running"
        else:
            results["rppg"] = _call(f"{RPPG_CONTROL_URL}/start")

    # Schedule automatic stop after 60 seconds (instead of 300)
    window_seconds = 300.0
    now = time.time()
    app.state.streaming_lock_until = now + window_seconds

    # Cancel any previous auto-stop task before creating a new one
    existing_task = getattr(app.state, "auto_stop_task", None)
    if existing_task is not None:
        existing_task.cancel()

    app.state.auto_stop_task = asyncio.create_task(
        _auto_stop_after(window_seconds, targets)
    )

    return {
        "status": "ok",
        "results": results,
        "auto_stop_in_seconds": 0,
        "message": "Auto-stop disabled; workloads will continue until manually stopped."
    }


async def _stop_workloads_internal(targets: set[str]) -> dict[str, str]:
    """Shared implementation for stopping workloads (used by /stop and auto-stop)."""
    results: dict[str, str] = {}

    def _call(url: str) -> str:
        try:
            resp = requests.post(url, timeout=3)
            return f"{resp.status_code}: {resp.text}"
        except Exception as exc:
            return f"error: {exc}"

    def _check_status(url: str) -> bool:
        """Check if service is running"""
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("enabled", False)
        except Exception:
            pass
        return False

    # MDPNP / DDS-Bridge
    if "all" in targets or "mdpnp" in targets:
        results["dds-bridge"] = _call(f"{DDS_BRIDGE_CONTROL_URL}/stop")

    # AI-ECG
    if "all" in targets or "ai-ecg" in targets:
        task = getattr(app.state, "ai_ecg_task", None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            app.state.ai_ecg_task = None
            results["ai-ecg"] = "stopped"
        else:
            results["ai-ecg"] = "not running"

    # 3D Pose
    if "all" in targets or "3d-pose" in targets:
        is_running = _check_status(f"{POSE_3D_CONTROL_URL}/status")
        if not is_running:
            results["3d-pose"] = "not running"
        else:
            results["3d-pose"] = _call(f"{POSE_3D_CONTROL_URL}/stop")

    # RPPG
    if "all" in targets or "rppg" in targets:
        is_running = _check_status(f"{RPPG_CONTROL_URL}/status")
        if not is_running:
            results["rppg"] = "not running"
        else:
            results["rppg"] = _call(f"{RPPG_CONTROL_URL}/stop")

    return results


@app.post("/stop")
async def stop_workloads(target: str = Query("dds-bridge", description="Which workload to stop (e.g., mdpnp, ai-ecg, 3d-pose, rppg, or all)")):
    """Wrapper API for UI to stop streaming from backend workloads."""
    targets = {t.strip() for t in target.split(",")} if target else {"dds-bridge"}

    # Manual stop clears any scheduled auto-stop and lock.
    existing_task = getattr(app.state, "auto_stop_task", None)
    if existing_task is not None:
        existing_task.cancel()
        app.state.auto_stop_task = None
    app.state.streaming_lock_until = None

    results = await _stop_workloads_internal(targets)
    return {"status": "ok", "results": results}


async def _auto_stop_after(delay_seconds: float, targets: set[str]) -> None:
    """Background task that waits for the window then stops workloads."""
    try:
        await asyncio.sleep(delay_seconds)
        print(f"[AutoStop] Stopping workloads after {delay_seconds} seconds: {targets}")
        await _stop_workloads_internal(targets)
    except asyncio.CancelledError:
        print("[AutoStop] Cancelled before completion")
        raise
    finally:
        # Clear lock and task reference when done.
        app.state.streaming_lock_until = None
        app.state.auto_stop_task = None


class VitalService(vital_pb2_grpc.VitalServiceServicer):
    def __init__(self, workload_type: str):
        self.default_workload_type = workload_type
        self.consumer = VitalConsumer()
    
    def _detect_workload_type(self, device_id: str) -> str:
        """Auto-detect workload type from device_id prefix."""
        if device_id.startswith("rppg-"):
            return "rppg"
        elif device_id.startswith("ai-ecg-"):
            return "ai-ecg"
        elif device_id.startswith("pose-"):
            return "3d-pose"
        else:
            return self.default_workload_type
    
    def StreamVitals(self, request_iterator, context):
        """gRPC method: receive a stream of Vital messages."""
        global event_loop
        
        for vital in request_iterator:
            workload_type = self._detect_workload_type(vital.device_id)
            
            waveform_data = list(vital.waveform) if vital.waveform else []
            event_type = "waveform" if len(waveform_data) > 0 else "numeric"
            
            print(
                f"[{workload_type}] {vital.device_id}/{vital.metric}={vital.value:.1f} "
                f"wf_len={len(waveform_data)}"
            )
            
            result = self.consumer.consume(vital)
            
            if result:
                # Build base message first so we can control JSON key order.
                message = {
                    "workload_type": workload_type,
                    "event_type": event_type,
                    "timestamp": vital.timestamp,
                }

                # For MDPNP vitals, also expose device_type at the root level
                # (immediately after timestamp) in addition to inside payload,
                # so the UI can more easily filter/group by simulator/device type.
                if (
                    workload_type == "mdpnp"
                    and isinstance(result, dict)
                    and "device_type" in result
                ):
                    message["device_type"] = result["device_type"]

                # Payload comes last so JSON appears as:
                # {workload_type, event_type, timestamp, device_type?, payload}
                message["payload"] = result
                
                if event_loop is not None:
                    print(f"[Broadcast] Sending to SSE: {workload_type}/{event_type}")
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            sse_manager.broadcast(message),
                            event_loop,
                        )
                        future.result(timeout=0.5)
                    except Exception as e:
                        print(f"[Broadcast] Error: {e}")
                else:
                    print("[Broadcast] WARNING: event_loop is None!")
        
        # StreamVitals returns google.protobuf.Empty per the proto
        # definition; the Empty type is imported directly.
        return Empty()

class PoseServicer(pose_pb2_grpc.PoseServiceServicer):
    """Receives pose data from 3D pose workloads"""

    def PublishPose(self, request, context):
        """Handle single pose frame (unary - more reliable)"""
        try:
            people_payload = []
            
            for person in request.people:
                joints_2d = [
                    {"x": joint.x, "y": joint.y}
                    for joint in person.joints_2d
                ]
                joints_3d = [
                    {"x": joint.x, "y": joint.y, "z": joint.z}
                    for joint in person.joints_3d
                ]
                
                person_dict = {
                    "person_id": person.person_id,
                    "confidence": list(person.confidence),
                    "joints_2d": joints_2d,
                    "joints_3d": joints_3d,
                }
                people_payload.append(person_dict)
                
                avg_conf = sum(person.confidence) / len(person.confidence) * 100 if person.confidence else 0
                print(f"[POSE] Person {person.person_id}: "
                      f"2D={len(person.joints_2d)} joints, "
                      f"3D={len(person.joints_3d)} joints, "
                      f"Conf={avg_conf:.1f}%")
            
            # Convert frame_data (bytes) to base64 string for JSON transmission
            frame_base64 = base64.b64encode(request.frame_data).decode('utf-8') if request.frame_data else ""
            
            message = {
                "workload_type": "3d-pose",
                "event_type": "pose3d",
                "timestamp": request.timestamp_ms,
                "payload": {
                    "source_id": request.source_id,
                    "frame_number": request.frame_number,
                    "frame_base64": frame_base64,
                    "people": people_payload,
                },
            }
            
            # Stream raw frame data to video endpoint - ADD THIS BLOCK
            if request.frame_data and event_loop is not None:
                asyncio.run_coroutine_threadsafe(
                    frame_manager.broadcast_frame(request.frame_data), event_loop
                )
            
            frame_size_kb = len(request.frame_data) / 1024 if request.frame_data else 0
            print(f"[POSE] Frame {request.frame_number} from {request.source_id} @ {request.timestamp_ms}ms - "
                  f"{len(request.people)} people, {frame_size_kb:.1f}KB")
            
            if event_loop is not None:
                asyncio.run_coroutine_threadsafe(
                    sse_manager.broadcast(message), event_loop
                )
            
            return pose_pb2.Ack(ok=True, message="Frame received")
            
        except Exception as e:
            print(f"[POSE ERROR] {e}")
            import traceback
            traceback.print_exc()
            return pose_pb2.Ack(ok=False, message=str(e))
    

    def StreamPoseData(self, request_iterator, context):
        """Handle streaming pose frames (kept for backward compatibility)"""
        import base64
        frame_count = 0
        try:
            for pose_frame in request_iterator:
                frame_count += 1
                
                people_payload = []
                for person in pose_frame.people:
                    person_dict = {
                        "person_id": person.person_id,
                        "confidence": list(person.confidence),
                        "joints_2d": [{"x": j.x, "y": j.y} for j in person.joints_2d],
                        "joints_3d": [{"x": j.x, "y": j.y, "z": j.z} for j in person.joints_3d]
                    }
                    people_payload.append(person_dict)
                
                # Convert frame_data to base64
                frame_base64 = base64.b64encode(pose_frame.frame_data).decode('utf-8') if pose_frame.frame_data else ""
                
                message = {
                    "workload_type": "3d-pose",
                    "event_type": "pose3d",
                    "timestamp": pose_frame.timestamp_ms,
                    "payload": {
                        "source_id": pose_frame.source_id,
                        "frame_number": pose_frame.frame_number,
                        "frame_base64": frame_base64,  # Add frame data
                        "people": people_payload,
                    },
                }
                
                if event_loop is not None:
                    asyncio.run_coroutine_threadsafe(
                        sse_manager.broadcast(message), event_loop
                    )
            
            print(f"[POSE] Streaming session completed: {frame_count} frames received")
            return pose_pb2.Ack(ok=True, message=f"Received {frame_count} frames")
            
        except Exception as e:
            print(f"[POSE ERROR] Streaming error: {e}")
            import traceback
            traceback.print_exc()
            return pose_pb2.Ack(ok=False, message=str(e))


async def ai_ecg_polling_loop():
    client = AIECGClient()
    try:
        while True:
            result = await asyncio.to_thread(client.poll_next)
            if result and event_loop is not None:
                await sse_manager.broadcast({
                    "workload_type": "ai-ecg",
                    "event_type": "waveform",
                    "timestamp": int(time.time() * 1000),
                    "payload": result,
                })
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        print("[Aggregator] AI-ECG polling stopped")
        raise


def start_grpc_server():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    vital_pb2_grpc.add_VitalServiceServicer_to_server(
        VitalService(WORKLOAD_TYPE), server
    )
    pose_pb2_grpc.add_PoseServiceServicer_to_server(
        PoseServicer(), server
    )
    grpc_port = int(os.getenv("GRPC_PORT", "50051"))
    server.add_insecure_port(f"[::]:{grpc_port}")
    server.start()
    print(f"✓ Aggregator gRPC server running on port {grpc_port}")
    server.wait_for_termination()


@app.on_event("startup")
async def on_startup():
    global event_loop
    event_loop = asyncio.get_running_loop()

    print(f"✓ Event loop initialized: {event_loop}")
    
    app.state.ai_ecg_task = None
    app.state.auto_stop_task = None
    app.state.streaming_lock_until = None

    await asyncio.sleep(0.5)
    
    t = threading.Thread(target=start_grpc_server, daemon=True)
    t.start()
    app.state.grpc_thread = t
    
    print("✓ gRPC server thread started")


if __name__ == "__main__":
    print("=" * 70)
    print("Starting Aggregator Service")
    print("=" * 70)
    print(f"  gRPC port: {os.getenv('GRPC_PORT', '50051')}")
    print("  HTTP/SSE: http://0.0.0.0:8001")
    print("=" * 70)
    
    uvicorn.run(
        "aggregator.server:app",
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
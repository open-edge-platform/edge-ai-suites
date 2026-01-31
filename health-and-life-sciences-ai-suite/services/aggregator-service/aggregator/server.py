import asyncio
import json
import os
import threading
import time

import grpc
from concurrent import futures
from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import requests
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

# Metrics service base URL (same host, different port, via host networking)
METRICS_SERVICE_URL = os.getenv("METRICS_SERVICE_URL", "http://localhost:9000")

# DDS-Bridge control URL (host networking: use localhost inside containers)
DDS_BRIDGE_CONTROL_URL = os.getenv("DDS_BRIDGE_CONTROL_URL", "http://localhost:8082")

# 3D Pose control URL
POSE_3D_CONTROL_URL = os.getenv("POSE_3D_CONTROL_URL", "http://localhost:8083")


def _proxy_metrics_get(path: str):
    """Helper to proxy a GET request to the metrics-service.

    Raises HTTPException if the downstream call fails.
    """
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


@app.get("/events")
async def stream_events(
    request: Request,
    workloads: str | None = Query(
        None,
        description=(
            "Optional comma-separated list of workload types to subscribe to "
            "(e.g., ai-ecg,mdpnp,3d-pose). If omitted, all workloads are sent."
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


@app.get("/metrics")
async def metrics_summary():
    """Proxy for the metrics-service /metrics endpoint."""
    return _proxy_metrics_get("/metrics")


@app.get("/platform-info")
async def platform_info():
    """Proxy for the metrics-service /platform-info endpoint."""
    return _proxy_metrics_get("/platform-info")


@app.get("/memory")
async def memory_usage():
    """Proxy for the metrics-service /memory endpoint."""
    return _proxy_metrics_get("/memory")


@app.post("/start")
async def start_workloads(target: str = Query("dds-bridge", description="Which workload to start (e.g., mdpnp, ai-ecg, 3d-pose, or all)")):
    """Wrapper API for UI to start streaming from backend workloads.

    Supports starting: mdpnp (dds-bridge), ai-ecg, 3d-pose, or all workloads.
    """

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
        # Check status first
        is_running = _check_status(f"{POSE_3D_CONTROL_URL}/status")
        if is_running:
            results["3d-pose"] = "already running"
        else:
            results["3d-pose"] = _call(f"{POSE_3D_CONTROL_URL}/start")

    return {"status": "ok", "results": results}


@app.post("/stop")
async def stop_workloads(target: str = Query("dds-bridge", description="Which workload to stop (e.g., mdpnp, ai-ecg, 3d-pose, or all)")):
    """Wrapper API for UI to stop streaming from backend workloads.

    Supports stopping: mdpnp (dds-bridge), ai-ecg, 3d-pose, or all workloads.
    """

    targets = {t.strip() for t in target.split(",")} if target else {"dds-bridge"}
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
        task = app.state.ai_ecg_task
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
        # Check status first
        is_running = _check_status(f"{POSE_3D_CONTROL_URL}/status")
        if not is_running:
            results["3d-pose"] = "not running"
        else:
            results["3d-pose"] = _call(f"{POSE_3D_CONTROL_URL}/stop")

    return {"status": "ok", "results": results}


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


class PoseServicer(pose_pb2_grpc.PoseServiceServicer):
    """Receives pose data from 3D pose workloads"""

    def PublishPose(self, request, context):
        """Handle single pose frame (unary - more reliable)"""
        try:
            # Build people payload with detailed per-person logging
            people_payload = []
            
            for person in request.people:
                # Extract joints
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
                
                # Detailed per-person logging
                avg_conf = sum(person.confidence) / len(person.confidence) * 100 if person.confidence else 0
                print(f"[POSE] Person {person.person_id}: "
                      f"2D={len(person.joints_2d)} joints, "
                      f"3D={len(person.joints_3d)} joints, "
                      f"Conf={avg_conf:.1f}% | "
                      f"Sample 2D: {[(f'{j.x:.0f},{j.y:.0f}') for j in person.joints_2d[:2]]} | "
                      f"Sample 3D: {[(f'{j.x:.1f},{j.y:.1f},{j.z:.1f}') for j in person.joints_3d[:2]]}")
            
            # Nested message format
            message = {
                "workload_type": "3d-pose",
                "event_type": "pose3d",
                "timestamp": request.timestamp_ms,
                "payload": {
                    "source_id": request.source_id,
                    "people": people_payload,
                },
            }
            
            print(f"[POSE] Frame from {request.source_id} @ {request.timestamp_ms}ms - "
                  f"{len(request.people)} people broadcasted")
            
            # Broadcast to SSE clients
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
        frame_count = 0
        try:
            for pose_frame in request_iterator:
                frame_count += 1
                
                # Build people payload
                people_payload = []
                for person in pose_frame.people:
                    person_dict = {
                        "person_id": person.person_id,
                        "confidence": list(person.confidence),
                        "joints_2d": [{"x": j.x, "y": j.y} for j in person.joints_2d],
                        "joints_3d": [{"x": j.x, "y": j.y, "z": j.z} for j in person.joints_3d]
                    }
                    people_payload.append(person_dict)
                
                # Nested message format
                message = {
                    "workload_type": "3d-pose",
                    "event_type": "pose3d",
                    "timestamp": pose_frame.timestamp_ms,
                    "payload": {
                        "source_id": pose_frame.source_id,
                        "people": people_payload,
                    },
                }
                
                # Broadcast to SSE clients
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
    """Poll AI-ECG backend and enqueue waveform + inference results."""
    client = AIECGClient()
    try:
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
                print("[Aggregator] Broadcasted AI-ECG result")
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
    print(f"Aggregator gRPC server running on port {grpc_port}")
    server.wait_for_termination()


@app.on_event("startup")
async def on_startup():
    # Capture the running loop for cross-thread broadcasts
    global event_loop
    event_loop = asyncio.get_running_loop()

    # Initialize AI-ECG task as None (will be started via /start endpoint)
    app.state.ai_ecg_task = None

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









































# import asyncio
# import json
# import os
# import threading
# import time

# import grpc
# from concurrent import futures
# from fastapi import FastAPI, Request, Query, HTTPException
# from fastapi.responses import StreamingResponse, JSONResponse
# import requests
# import uvicorn
# from google.protobuf.empty_pb2 import Empty

# from proto import vital_pb2, vital_pb2_grpc, pose_pb2, pose_pb2_grpc
# from .consumer import VitalConsumer
# from .ws_broadcaster import SSEManager
# from .ai_ecg_client import AIECGClient


# app = FastAPI(title="Aggregator Service")
# sse_manager = SSEManager()

# # Main asyncio event loop reference for cross-thread broadcasts
# event_loop: asyncio.AbstractEventLoop | None = None

# # Environment-configurable workload label for this instance
# WORKLOAD_TYPE = os.getenv("WORKLOAD_TYPE", "mdpnp")

# # Metrics service base URL (same host, different port, via host networking)
# METRICS_SERVICE_URL = os.getenv("METRICS_SERVICE_URL", "http://localhost:9000")

# # DDS-Bridge control URL (host networking: use localhost inside containers)
# DDS_BRIDGE_CONTROL_URL = os.getenv("DDS_BRIDGE_CONTROL_URL", "http://localhost:8082")


# def _proxy_metrics_get(path: str):
#     """Helper to proxy a GET request to the metrics-service.

#     Raises HTTPException if the downstream call fails.
#     """
#     url = f"{METRICS_SERVICE_URL}{path}"
#     try:
#         resp = requests.get(url, timeout=5)
#     except Exception as exc:
#         raise HTTPException(status_code=502, detail=f"metrics-service unreachable: {exc}")

#     if resp.status_code != 200:
#         raise HTTPException(status_code=resp.status_code, detail=resp.text)

#     try:
#         data = resp.json()
#     except Exception:
#         raise HTTPException(status_code=502, detail="Invalid JSON from metrics-service")

#     return JSONResponse(content=data, status_code=200)


# @app.get("/events")
# async def stream_events(
#     request: Request,
#     workloads: str | None = Query(
#         None,
#         description=(
#             "Optional comma-separated list of workload types to subscribe to "
#             "(e.g., ai-ecg,mdpnp). If omitted, all workloads are sent."
#         ),
#     ),
# ):
#     """SSE endpoint that streams aggregator events to connected clients.

#     If the "workloads" query param is provided, only those workloads are
#     delivered to the client; otherwise all four workloads are streamed.
#     """
#     if workloads:
#         workload_set = {w.strip() for w in workloads.split(",") if w.strip()}
#     else:
#         workload_set = None

#     client_queue = await sse_manager.connect(workload_set)

#     async def event_generator():
#         try:
#             while True:
#                 # Exit cleanly if the client disconnects
#                 if await request.is_disconnected():
#                     break

#                 try:
#                     data = await asyncio.wait_for(client_queue.get(), timeout=1.0)
#                 except asyncio.TimeoutError:
#                     continue

#                 yield f"data: {data}\n\n"
#         finally:
#             await sse_manager.disconnect(client_queue)

#     return StreamingResponse(event_generator(), media_type="text/event-stream")


# @app.get("/metrics")
# async def metrics_summary():
#     """Proxy for the metrics-service /metrics endpoint."""
#     return _proxy_metrics_get("/metrics")


# @app.get("/platform-info")
# async def platform_info():
#     """Proxy for the metrics-service /platform-info endpoint."""
#     return _proxy_metrics_get("/platform-info")


# @app.get("/memory")
# async def memory_usage():
#     """Proxy for the metrics-service /memory endpoint."""
#     return _proxy_metrics_get("/memory")


# @app.post("/start")
# async def start_workloads(target: str = Query("dds-bridge", description="Which workload to start (currently only dds-bridge is supported)")):
#     """Wrapper API for UI to start streaming from backend workloads.

#     For now this controls only the dds-bridge, which in turn
#     forwards vitals from the mdpnp DDS domain into this service
#     over gRPC when enabled.
#     """

#     # Currently we only support dds-bridge, but keep the signature
#     # flexible for future extension.
#     targets = {t.strip() for t in target.split(",")} if target else {"dds-bridge"}
#     results: dict[str, str] = {}

#     def _call(url: str) -> str:
#         try:
#             resp = requests.post(url, timeout=3)
#             return f"{resp.status_code}: {resp.text}"
#         except Exception as exc:
#             return f"error: {exc}"

#     if "all" in targets or "mdpnp" in targets:
#         results["dds-bridge"] = _call(f"{DDS_BRIDGE_CONTROL_URL}/start")

#     # AI-ECG 
#     if "all" in targets or "ai-ecg" in targets:
#         if app.state.ai_ecg_task is None:
#             app.state.ai_ecg_task = asyncio.create_task(ai_ecg_polling_loop())
#             results["ai-ecg"] = "started"
#         else:
#             results["ai-ecg"] = "already running"

#     return {"status": "ok", "results": results}


# @app.post("/stop")
# async def stop_workloads(target: str = Query("dds-bridge", description="Which workload to stop (currently only dds-bridge is supported)")):
#     """Wrapper API for UI to stop streaming from backend workloads.

#     This turns off forwarding in dds-bridge so that no new vitals
#     are sent into this aggregator over gRPC.
#     """

#     targets = {t.strip() for t in target.split(",")} if target else {"dds-bridge"}
#     results: dict[str, str] = {}

#     def _call(url: str) -> str:
#         try:
#             resp = requests.post(url, timeout=3)
#             return f"{resp.status_code}: {resp.text}"
#         except Exception as exc:
#             return f"error: {exc}"

#     if "all" in targets or "mdpnp" in targets:
#         results["dds-bridge"] = _call(f"{DDS_BRIDGE_CONTROL_URL}/stop")

#     # AI-ECG 
#     if "all" in targets or "ai-ecg" in targets:
#         task = app.state.ai_ecg_task
#         if task:
#             task.cancel()
#             try:
#                 await task
#             except asyncio.CancelledError:
#                 pass
#             app.state.ai_ecg_task = None
#             results["ai-ecg"] = "stopped"
#         else:
#             results["ai-ecg"] = "not running"

#     return {"status": "ok", "results": results}


# class VitalService(vital_pb2_grpc.VitalServiceServicer):
#     """gRPC service that receives Vital streams and enqueues aggregated results."""

#     def __init__(self, workload_type: str):
#         self.workload_type = workload_type
#         self.consumer = VitalConsumer()

#     def StreamVitals(self, request_iterator, context):
#         for vital in request_iterator:
#             # Infer event type based on presence of waveform samples
#             event_type = "waveform" if len(vital.waveform) > 0 else "numeric"

#             print("[Aggregator] Received Vital from gRPC:", {
#                 "device_id": vital.device_id,
#                 "metric": vital.metric,
#                 "value": vital.value,
#                 "unit": vital.unit,
#                 "timestamp": vital.timestamp,
#                 "waveform_len": len(vital.waveform),
#                 "waveform_frequency_hz": vital.waveform_frequency_hz
#             })
#             result = self.consumer.consume(vital)
#             if result:
#                 message = {
#                     "workload_type": self.workload_type,
#                     "event_type": event_type,
#                     "timestamp": vital.timestamp,                    
#                     "payload": result,
#                 }
#                 print("[Aggregator] Broadcasting message to SSE clients:", message)
#                 if event_loop is not None:
#                     asyncio.run_coroutine_threadsafe(
#                         sse_manager.broadcast(message), event_loop
#                     )
#         return Empty()


# class PoseServicer(pose_pb2_grpc.PoseServiceServicer):
#     """Receives pose data from 3D pose workloads"""

#     def PublishPose(self, request, context):
#         """Handle single pose frame (unary - more reliable)"""
#         try:
#             # Build people payload with detailed per-person logging
#             people_payload = []
            
#             for person in request.people:
#                 # Extract joints
#                 joints_2d = [
#                     {"x": joint.x, "y": joint.y}
#                     for joint in person.joints_2d
#                 ]
#                 joints_3d = [
#                     {"x": joint.x, "y": joint.y, "z": joint.z}
#                     for joint in person.joints_3d
#                 ]
                
#                 person_dict = {
#                     "person_id": person.person_id,
#                     "confidence": list(person.confidence),
#                     "joints_2d": joints_2d,
#                     "joints_3d": joints_3d,
#                 }
#                 people_payload.append(person_dict)
                
#                 # Detailed per-person logging
#                 avg_conf = sum(person.confidence) / len(person.confidence) * 100 if person.confidence else 0
#                 print(f"[POSE] Person {person.person_id}: "
#                       f"2D={len(person.joints_2d)} joints, "
#                       f"3D={len(person.joints_3d)} joints, "
#                       f"Conf={avg_conf:.1f}% | "
#                       f"Sample 2D: {[(f'{j.x:.0f},{j.y:.0f}') for j in person.joints_2d[:2]]} | "
#                       f"Sample 3D: {[(f'{j.x:.1f},{j.y:.1f},{j.z:.1f}') for j in person.joints_3d[:2]]}")
            
#             # Nested message format
#             message = {
#                 "workload_type": "3d-pose",
#                 "event_type": "pose3d",
#                 "timestamp": request.timestamp_ms,
#                 "payload": {
#                     "source_id": request.source_id,
#                     "people": people_payload,
#                 },
#             }
            
#             print(f"[POSE] Frame from {request.source_id} @ {request.timestamp_ms}ms - "
#                   f"{len(request.people)} people broadcasted")
            
#             # Broadcast to SSE clients
#             if event_loop is not None:
#                 asyncio.run_coroutine_threadsafe(
#                     sse_manager.broadcast(message), event_loop
#                 )
            
#             return pose_pb2.Ack(ok=True, message="Frame received")
            
#         except Exception as e:
#             print(f"[POSE ERROR] {e}")
#             import traceback
#             traceback.print_exc()
#             return pose_pb2.Ack(ok=False, message=str(e))
    

#     def StreamPoseData(self, request_iterator, context):
#         """Handle streaming pose frames (kept for backward compatibility)"""
#         frame_count = 0
#         try:
#             for pose_frame in request_iterator:
#                 frame_count += 1
                
#                 # Build people payload
#                 people_payload = []
#                 for person in pose_frame.people:
#                     person_dict = {
#                         "person_id": person.person_id,
#                         "confidence": list(person.confidence),
#                         "joints_2d": [{"x": j.x, "y": j.y} for j in person.joints_2d],
#                         "joints_3d": [{"x": j.x, "y": j.y, "z": j.z} for j in person.joints_3d]
#                     }
#                     people_payload.append(person_dict)
                
#                 # Nested message format
#                 message = {
#                     "workload_type": "3d-pose",
#                     "event_type": "pose3d",
#                     "timestamp": pose_frame.timestamp_ms,
#                     "payload": {
#                         "source_id": pose_frame.source_id,
#                         "people": people_payload,
#                     },
#                 }
                
#                 # Broadcast to SSE clients
#                 if event_loop is not None:
#                     asyncio.run_coroutine_threadsafe(
#                         sse_manager.broadcast(message), event_loop
#                     )
            
#             print(f"[POSE] Streaming session completed: {frame_count} frames received")
#             return pose_pb2.Ack(ok=True, message=f"Received {frame_count} frames")
            
#         except Exception as e:
#             print(f"[POSE ERROR] Streaming error: {e}")
#             import traceback
#             traceback.print_exc()
#             return pose_pb2.Ack(ok=False, message=str(e))


# async def ai_ecg_polling_loop():
#     """Poll AI-ECG backend and enqueue waveform + inference results."""
#     client = AIECGClient()
#     try:
#         while True:
#             result = await asyncio.to_thread(client.poll_next)
#             if result:
#                 message = {
#                     "workload_type": "ai-ecg",
#                     "event_type": "waveform",
#                     "timestamp": int(time.time() * 1000),
#                     "payload": result,
#                 }
#                 if event_loop is not None:
#                     await sse_manager.broadcast(message)
#                 print("[Aggregator] Broadcasted AI-ECG result")
#             await asyncio.sleep(1.0)
#     except asyncio.CancelledError:
#         print("[Aggregator] AI-ECG polling stopped")
#         raise


# def start_grpc_server():
#     server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
#     vital_pb2_grpc.add_VitalServiceServicer_to_server(
#         VitalService(WORKLOAD_TYPE), server
#     )
#     pose_pb2_grpc.add_PoseServiceServicer_to_server(
#         PoseServicer(), server
#     )
#     grpc_port = int(os.getenv("GRPC_PORT", "50051"))
#     server.add_insecure_port(f"[::]:{grpc_port}")
#     server.start()
#     print(f"Aggregator gRPC server running on port {grpc_port}")
#     server.wait_for_termination()


# @app.on_event("startup")
# async def on_startup():
#     # Capture the running loop for cross-thread broadcasts
#     global event_loop
#     event_loop = asyncio.get_running_loop()

#     # Initialize AI-ECG task as None (will be started via /start endpoint)
#     app.state.ai_ecg_task = None

#     # Start gRPC server in a background thread
#     t = threading.Thread(target=start_grpc_server, daemon=True)
#     t.start()
#     app.state.grpc_thread = t


# if __name__ == "__main__":
#     uvicorn.run(
#         "aggregator.server:app",
#         host="0.0.0.0",
#         port=8001,
#         log_level="info",
#     )
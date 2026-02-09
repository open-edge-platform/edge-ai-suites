import asyncio
import json
import logging
import os
import subprocess
import time
from concurrent import futures
from typing import AsyncGenerator, Dict, Set

import grpc
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from google.protobuf.empty_pb2 import Empty

from aggregator.proto import pose_pb2, pose_pb2_grpc, vital_pb2, vital_pb2_grpc
from aggregator.sse_manager import SSEManager
from aggregator.vital_consumer import VitalConsumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Aggregator Service")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global SSE manager and event loop
sse_manager = SSEManager()
event_loop = None

# Track running workload processes
running_workloads: Dict[str, subprocess.Popen] = {}


@app.on_event("startup")
async def startup_event():
    """Initialize event loop for gRPC-to-SSE bridge"""
    global event_loop
    event_loop = asyncio.get_event_loop()
    logger.info("✓ Aggregator service started")
    logger.info(f"✓ Event loop initialized: {event_loop}")


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "sse_subscribers": len(sse_manager.subscribers),
        "running_workloads": list(running_workloads.keys()),
    }


@app.get("/events")
async def events(request: Request, workload: str = "all"):
    """
    SSE endpoint for real-time data streaming.
    
    Query params:
    - workload: Comma-separated list of workloads (e.g., "rppg,ai-ecg,3d-pose,mdpnp")
                or "all" to subscribe to everything
    """
    # Parse workload filter
    workload_filter = {w.strip() for w in workload.split(",")} if workload != "all" else {"all"}
    
    logger.info(f"[SSE] New subscriber: {request.client.host} (filter: {workload_filter})")
    
    async def event_generator() -> AsyncGenerator[str, None]:
        queue = asyncio.Queue()
        sse_manager.add_subscriber(queue, workload_filter)
        
        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'workload_filter': list(workload_filter)})}\n\n"
            
            while True:
                message = await queue.get()
                yield f"data: {json.dumps(message)}\n\n"
        
        except asyncio.CancelledError:
            logger.info(f"[SSE] Client disconnected: {request.client.host}")
        finally:
            sse_manager.remove_subscriber(queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================
# Workload Control Endpoints
# ============================================

WORKLOAD_CONFIGS = {
    "dds-bridge": {
        "container": "dds-bridge",
        "command": ["docker", "restart", "dds-bridge"],
        "health_check": "http://dds-bridge:8082/health",
    },
    "ai-ecg": {
        "container": "ai-ecg-service",
        "command": ["docker", "restart", "ai-ecg-service"],
        "health_check": "http://ai-ecg-service:8083/health",
    },
    "3d-pose": {
        "container": "pose-estimation-service",
        "command": ["docker", "restart", "pose-estimation-service"],
        "health_check": "http://pose-estimation-service:8084/health",
    },
    "rppg": {
        "container": "rppg-service",
        "command": ["docker", "restart", "rppg-service"],
        "health_check": "http://rppg-service:8085/health",
    },
}


async def _start_workload(workload_id: str) -> Dict[str, str]:
    """Start a specific workload container"""
    config = WORKLOAD_CONFIGS.get(workload_id)
    if not config:
        return {"workload": workload_id, "status": "error", "message": "Unknown workload"}
    
    try:
        # Start container
        result = subprocess.run(
            config["command"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            logger.info(f"✓ Started {workload_id}")
            return {"workload": workload_id, "status": "started"}
        else:
            logger.error(f"✗ Failed to start {workload_id}: {result.stderr}")
            return {"workload": workload_id, "status": "error", "message": result.stderr}
    
    except Exception as e:
        logger.error(f"✗ Exception starting {workload_id}: {e}")
        return {"workload": workload_id, "status": "error", "message": str(e)}


async def _stop_workload(workload_id: str) -> Dict[str, str]:
    """Stop a specific workload container"""
    config = WORKLOAD_CONFIGS.get(workload_id)
    if not config:
        return {"workload": workload_id, "status": "error", "message": "Unknown workload"}
    
    try:
        # Stop container
        result = subprocess.run(
            ["docker", "stop", config["container"]],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        if result.returncode == 0:
            logger.info(f"✓ Stopped {workload_id}")
            return {"workload": workload_id, "status": "stopped"}
        else:
            logger.error(f"✗ Failed to stop {workload_id}: {result.stderr}")
            return {"workload": workload_id, "status": "error", "message": result.stderr}
    
    except Exception as e:
        logger.error(f"✗ Exception stopping {workload_id}: {e}")
        return {"workload": workload_id, "status": "error", "message": str(e)}


async def _start_workloads_internal(targets: Set[str]) -> Dict[str, Dict]:
    """Internal helper to start multiple workloads"""
    results = {}
    for target in targets:
        results[target] = await _start_workload(target)
    return results


async def _stop_workloads_internal(targets: Set[str]) -> Dict[str, Dict]:
    """Internal helper to stop multiple workloads"""
    results = {}
    for target in targets:
        results[target] = await _stop_workload(target)
    return results


@app.post("/start")
async def start_workloads(target: str = "all"):
    """
    Start workload containers.
    
    Query params:
    - target: Comma-separated workload IDs (dds-bridge,ai-ecg,3d-pose,rppg) or "all"
    """
    targets = {t.strip() for t in target.split(",")} if target else {"all"}
    if "all" in targets:
        targets = {"dds-bridge", "ai-ecg", "3d-pose", "rppg"}
    
    results = await _start_workloads_internal(targets)
    return {"status": "ok", "results": results}


@app.post("/stop")
async def stop_workloads(target: str = "all"):
    """
    Stop workload containers.
    
    Query params:
    - target: Comma-separated workload IDs or "all"
    """
    targets = {t.strip() for t in target.split(",")} if target else {"all"}
    if "all" in targets:
        targets = {"dds-bridge", "ai-ecg", "3d-pose", "rppg"}
    
    results = await _stop_workloads_internal(targets)
    return {"status": "ok", "results": results}


# ============================================
# gRPC Servicers
# ============================================

class VitalService(vital_pb2_grpc.VitalServiceServicer):
    """gRPC servicer for vital signs data (MDPNP, AI-ECG, rPPG)."""
    
    def __init__(self, workload_type: str):
        self.workload_type = workload_type
        self.consumer = VitalConsumer()
    
    def StreamVitals(self, request_iterator, context):
        """
        Receive streaming vital signs from workload services.
        
        Each vital message contains:
        - workload_type: "mdpnp", "ai-ecg", or "rppg"
        - event_type: "numeric" or "waveform"
        - payload: JSON data
        - timestamp: Unix timestamp (ms)
        """
        for vital in request_iterator:
            # Parse vital data
            result = self.consumer.consume(vital)
            
            if result:
                # Extract metadata from protobuf message
                workload_type = vital.workload_type
                event_type = vital.event_type
                
                # Build SSE message with controlled JSON key order
                message = {
                    "workload_type": workload_type,
                    "event_type": event_type,
                    "timestamp": vital.timestamp,
                }

                # For MDPNP vitals, expose device_type at root level
                # (in addition to inside payload) for easier UI filtering
                if (
                    workload_type == "mdpnp"
                    and isinstance(result, dict)
                    and "device_type" in result
                ):
                    message["device_type"] = result["device_type"]

                # Payload comes last: {workload_type, event_type, timestamp, device_type?, payload}
                message["payload"] = result
                
                # Broadcast to SSE subscribers
                if event_loop is not None:
                    print(f"✓ [Broadcast] {workload_type}/{event_type}")
                    try:
                        future = asyncio.run_coroutine_threadsafe(
                            sse_manager.broadcast(message),
                            event_loop,
                        )
                        future.result(timeout=0.5)
                    except Exception as e:
                        print(f"✗ [Broadcast] Error: {e}")
                else:
                    print("⚠️ [Broadcast] WARNING: event_loop is None!")
        
        # Return Empty per proto definition
        return Empty()


class PoseServicer(pose_pb2_grpc.PoseServiceServicer):
    """gRPC servicer for 3D pose estimation data."""
    
    def PublishPose(self, request, context):
        """Handle single pose frame (unary RPC)"""
        try:
            people_payload = []
            
            # Convert protobuf Person messages to JSON
            for person in request.people:
                joints_2d = [
                    {"x": joint.x, "y": joint.y}
                    for joint in person.joints_2d
                ]
                joints_3d = [
                    {"x": joint.x, "y": joint.y, "z": joint.z}
                    for joint in person.joints_3d
                ]
                
                people_payload.append({
                    "id": person.id,
                    "joints_2d": joints_2d,
                    "joints_3d": joints_3d,
                    "confidence": person.confidence,
                })
            
            # Build SSE message
            message = {
                "workload_type": "3d-pose",
                "event_type": "pose",
                "timestamp": request.timestamp,
                "payload": {
                    "frame_id": request.frame_id,
                    "timestamp": request.timestamp,
                    "people": people_payload,
                },
            }
            
            # Broadcast to SSE subscribers
            if event_loop is not None:
                print(f"✓ [3D-Pose] Frame {request.frame_id} with {len(people_payload)} people")
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        sse_manager.broadcast(message),
                        event_loop,
                    )
                    future.result(timeout=0.5)
                except Exception as e:
                    print(f"✗ [3D-Pose] Broadcast error: {e}")
            
            return Empty()
        
        except Exception as e:
            print(f"✗ [3D-Pose] Error processing pose: {e}")
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(str(e))
            return Empty()


# ============================================
# gRPC Server Setup
# ============================================

def serve_grpc():
    """Start gRPC server for receiving data from workload services"""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register servicers for each workload type
    vital_pb2_grpc.add_VitalServiceServicer_to_server(
        VitalService("mdpnp"), server
    )
    vital_pb2_grpc.add_VitalServiceServicer_to_server(
        VitalService("ai-ecg"), server
    )
    vital_pb2_grpc.add_VitalServiceServicer_to_server(
        VitalService("rppg"), server
    )
    
    pose_pb2_grpc.add_PoseServiceServicer_to_server(
        PoseServicer(), server
    )
    
    server.add_insecure_port("[::]:50051")
    server.start()
    logger.info("✓ gRPC server started on port 50051")
    server.wait_for_termination()


# ============================================
# Application Entry Point
# ============================================

if __name__ == "__main__":
    import threading
    import uvicorn
    
    # Start gRPC server in background thread
    grpc_thread = threading.Thread(target=serve_grpc, daemon=True)
    grpc_thread.start()
    
    # Start FastAPI server (blocks)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="info",
    )
import io
import base64
import yaml
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from PIL import Image
import uvicorn
from layout_detection_v3 import LayoutDetectorV3

detection_service: Optional[LayoutDetectorV3] = None
server_config = {
    'model_path': None,
    'device': None,
    'precision': None,
    'threshold': None,
    'port': None
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    global detection_service
    model_path = server_config['model_path']
    device = server_config['device']
    precision = server_config['precision']
    threshold = server_config['threshold']
    port = server_config['port']

    print(f"\n{'='*80}")
    print(f"Starting PP-DocLayout Detection Server...")
    print(f"  Model Path: {model_path}")
    print(f"  Device: {device}")
    print(f"  Precision: {precision}")
    print(f"  Threshold: {threshold}")
    print(f"{'='*80}\n")

    try:
        detection_service = LayoutDetectorV3(
            model_path=model_path,
            device=device,
            threshold=threshold
        )
        print(f"\n{'='*80}")
        print(f"Server Ready!")
        print(f"  API Docs: http://localhost:{port}/docs")
        print(f"  Health Check: http://localhost:{port}/health")
        print(f"{'='*80}\n")
    except Exception as e:
        print(f"\nERROR: Failed to load model: {e}\n")
        raise

    yield

    print("\nShutting down detection service...")


app = FastAPI(
    title="PP-DocLayout Detection API Server",
    description="Document layout detection service for detecting text, tables, images, formulas, etc.",
    version="1.0.0",
    lifespan=lifespan
)


class Box(BaseModel):
    cls_id: int = Field(..., description="Class ID")
    label: str = Field(..., description="Region label (text, table, image, etc.)")
    score: float = Field(..., description="Confidence score")
    coordinate: List[float] = Field(..., description="Bounding box [x1, y1, x2, y2]")


class DetectionRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded image")


class DetectionResponse(BaseModel):
    success: bool
    boxes: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    inference_time: Optional[float] = None
    image_size: Optional[List[int]] = None
    num_regions: Optional[int] = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if detection_service is None:
        raise HTTPException(status_code=503, detail="Detection service not initialized")

    return {
        "status": "healthy",
        "model_loaded": True,
        "device": detection_service.device,
        "threshold": detection_service.threshold
    }


@app.post("/detect/base64", response_model=DetectionResponse)
async def detect_base64(request: DetectionRequest):
    """
    Detect layout regions from base64 encoded image

    Args:
        request: DetectionRequest with base64 encoded image

    Returns:
        DetectionResponse with detected boxes and metadata
    """
    if detection_service is None:
        raise HTTPException(status_code=503, detail="Detection service not initialized")

    try:
        # Decode base64 image
        image_bytes = base64.b64decode(request.image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert('RGB')

        # Run detection
        result = detection_service.detect(image)

        return DetectionResponse(
            success=True,
            boxes=result['boxes'],
            inference_time=result['inference_time'],
            image_size=list(result['image_size']),
            num_regions=len(result['boxes'])
        )

    except Exception as e:
        return DetectionResponse(
            success=False,
            error=str(e)
        )


@app.post("/detect/file", response_model=DetectionResponse)
async def detect_file(file: UploadFile = File(...)):
    """
    Detect layout regions from uploaded image file

    Args:
        file: Uploaded image file (JPEG, PNG, etc.)

    Returns:
        DetectionResponse with detected boxes and metadata
    """
    if detection_service is None:
        raise HTTPException(status_code=503, detail="Detection service not initialized")

    try:
        # Read uploaded file
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert('RGB')

        # Run detection
        start_time = time.time()
        result = detection_service.detect(image)
        inference_time = time.time() - start_time

        return DetectionResponse(
            success=True,
            boxes=result['boxes'],
            inference_time=inference_time,
            image_size=list(result['image_size']),
            num_regions=len(result['boxes'])
        )

    except Exception as e:
        return DetectionResponse(
            success=False,
            error=str(e)
        )


@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    if detection_service is None:
        raise HTTPException(status_code=503, detail="Detection service not initialized")

    times = detection_service.inference_times
    return {
        "model_load_time": detection_service.load_time,
        "total_inferences": len(times),
        "avg_inference_time": (sum(times) / len(times)) if times else 0
    }


def main():
    # Load configuration from config.yaml
    config_path = Path(__file__).parent / "config.yaml"

    if not config_path.exists():
        print(f"Error: Config file not found: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    svc_config = config.get('detection_service', {})
    layout_config = config.get('layout_detection', {})

    # Model config comes from detection_service, falling back to layout_detection
    model_path = svc_config.get('model_path') or layout_config.get('model_path', '../models/PP-DocLayoutV3-ov')
    precision = svc_config.get('precision') or layout_config.get('precision')
    device = svc_config.get('device') or layout_config.get('device', 'GPU')
    threshold = svc_config.get('threshold', layout_config.get('threshold', 0.5))

    # Resolve path (relative to config file) and append precision subdir
    model_path = Path(model_path)
    if not model_path.is_absolute():
        model_path = config_path.parent / model_path
    if precision:
        model_path = model_path / precision

    # Update server config
    server_config['model_path'] = str(model_path)
    server_config['device'] = device
    server_config['precision'] = precision
    server_config['threshold'] = threshold
    server_config['port'] = svc_config.get('port', 9902)

    # Start server
    uvicorn.run(
        app,
        host=config.get('detection_service', {}).get('host', '0.0.0.0'),
        port=server_config['port'],
        log_level="info"
    )


if __name__ == "__main__":
    main()

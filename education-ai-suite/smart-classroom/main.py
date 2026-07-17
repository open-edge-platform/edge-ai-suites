import sys
import warnings
warnings.filterwarnings("ignore", message=r"[\s\S]*torchcodec is not installed correctly")

from utils import system_checker

from utils.logger_config import setup_logger
setup_logger()

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from api.endpoints import register_routes
from model_manager.capability.runner import QueueFullError, OomError
from utils.runtime_config_loader import RuntimeConfig
from utils.ensure_model import ensure_model
from utils.preload_models import preload_models
import logging
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
from pathlib import Path


logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # For Testing ["*"]
    allow_credentials=True,          # cookies/auth allowed
    allow_methods=["*"],             # allow all HTTP methods
    allow_headers=["*"],             # allow all headers
    expose_headers=["x-session-id"]  # expose custom headers if needed
)

register_routes(app)


@app.exception_handler(QueueFullError)
async def _queue_full_handler(request: Request, exc: QueueFullError):
    """Map QueueFullError to HTTP 503 with a Retry-After hint."""
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "2"},
        content={"detail": str(exc), "retryAfterSeconds": 2},
    )


@app.exception_handler(OomError)
async def _oom_handler(request: Request, exc: OomError):
    """Map OomError (GPU/CPU memory pressure) to HTTP 503 with a Retry-After hint."""
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "5"},
        content={"detail": str(exc), "retryAfterSeconds": 5, "reason": "memory_pressure"},
    )


def system_check():
    if (not system_checker.check_system_requirements()) and (not system_checker.show_warning_and_prompt_user_to_continue()):
        sys.exit(1)

if __name__ == "__main__":
    
    #system_check()
    RuntimeConfig.ensure_config_exists()

    ensure_model()
    preload_models()

    import uvicorn
    logger.info("App started, Starting Server...")
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,
        timeout_graceful_shutdown=5,
    )

import sys
from utils import system_checker

from utils.logger_config import setup_logger
setup_logger()

from fastapi import FastAPI
from api.endpoints import register_routes
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

def system_check():
    if (not system_checker.check_system_requirements()) and (not system_checker.show_warning_and_prompt_user_to_continue()):
        sys.exit(1)

if __name__ == "__main__":
    
    system_check()
    RuntimeConfig.ensure_config_exists()
    ensure_model()
    preload_models()
    
    import uvicorn
    logger.info("App started, Starting Server...")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)

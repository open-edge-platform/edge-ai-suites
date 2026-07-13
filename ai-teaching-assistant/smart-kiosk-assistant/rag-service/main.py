from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.custom_endpoints import router as custom_router
from api.openai_endpoints import router as openai_router
from pipeline import close_shared_pipeline
from utils.config_loader import config
from utils.ensure_model import ensure_model
from utils.logger_config import setup_logger
from utils.preload_models import preload_models


setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_model()
    preload_models()
    logger.info("smart-kiosk-assistant rag-service initialized")
    try:
        yield
    finally:
        close_shared_pipeline()


app = FastAPI(title="smart-kiosk-assistant-rag-service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(getattr(config.api, "cors_allow_origins", ["http://127.0.0.1", "http://localhost"])),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(openai_router)
app.include_router(custom_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=str(getattr(config.server, "host", "0.0.0.0")),
        port=int(getattr(config.server, "port", 8020)),
        reload=False,
    )
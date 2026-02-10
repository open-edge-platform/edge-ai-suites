import os
import logging

class Settings:
    # Application Config
    PORT: int = int(os.getenv("PORT", 9000))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # AI Config
    RTSP_URL: str = os.getenv("RTSP_URL", "")
    VLM_URL: str = os.getenv("VLM_URL", "http://localhost:8000/v3")
    VLM_API_KEY: str = os.getenv("VLM_API_KEY", "dummy")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "Phi-3.5-Vision")
    
    # Performance Config
    ANALYSIS_INTERVAL: float = float(os.getenv("ANALYSIS_INTERVAL", 1.0))
    FRAME_BUFFER_SIZE: int = int(os.getenv("FRAME_BUFFER_SIZE", 30))

settings = Settings()

def setup_logging():
    """Configure structured logging for production"""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

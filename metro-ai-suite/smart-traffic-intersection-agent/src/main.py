"""
Traffic Intelligence Service - Lightweight traffic analysis for a single intersection
 
This service reads camera data from a single intersection via MQTT topics and provides
real-time traffic analysis with weather-enriched insights and VLM-powered alerts.

Key Features:
- MQTT subscription to scenescape/data/camera/camera<1,2,3> topics
- Weather-aware traffic analysis
- Structured VLM prompts for traffic and alert analysis
- Camera image synchronization with data readings
- Modular, well-documented codebase
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
import uvicorn
from fastapi import FastAPI

from api.routes import router
from services.config import ConfigService
from services.mqtt_service import MQTTService
from services.weather_service import WeatherService
from services.vlm_service import VLMService
from services.data_aggregator import DataAggregatorService


# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for traffic intelligence service."""
    logger.info("Starting Traffic Intelligence service")
    
    try:
        # Load configuration
        config_service = ConfigService()
        app.state.config = config_service
        
        # Initialize weather service
        weather_service = WeatherService(config_service)
        app.state.weather_service = weather_service
        
        # Start weather service with periodic updates
        await weather_service.start()
        
        # Initialize VLM service for traffic analysis
        vlm_service = VLMService(config_service, weather_service)
        app.state.vlm_service = vlm_service
        
        # Initialize data aggregator service
        data_aggregator = DataAggregatorService(config_service, vlm_service)
        app.state.data_aggregator = data_aggregator
        
        # Initialize and start MQTT service for camera data
        mqtt_service = MQTTService(config_service, data_aggregator, vlm_service)
        await mqtt_service.initialize()
        
        # Set the current event loop for async task scheduling
        current_loop = asyncio.get_running_loop()
        mqtt_service.set_event_loop(current_loop)
        
        app.state.mqtt = mqtt_service
        
        # Start MQTT service in background
        mqtt_task = asyncio.create_task(mqtt_service.start())
        app.state.mqtt_task = mqtt_task
        
        logger.info("Traffic Intelligence service started successfully", 
                   intersection_id=config_service.get_intersection_id(),
                   mqtt_topics=config_service.get_camera_topics())
        
        yield
        
    except Exception as e:
        logger.error("Failed to start Traffic Intelligence service", error=str(e))
        raise
    
    finally:
        # Cleanup
        logger.info("Shutting down Traffic Intelligence service")
        
        # Stop MQTT service
        if hasattr(app.state, 'mqtt_task'):
            app.state.mqtt_task.cancel()
            try:
                await app.state.mqtt_task
            except asyncio.CancelledError:
                pass
        
        if hasattr(app.state, 'mqtt'):
            await app.state.mqtt.stop()
        
        # Stop weather service
        if hasattr(app.state, 'weather_service'):
            await app.state.weather_service.stop()
        
        logger.info("Traffic Intelligence service stopped")


def create_app() -> FastAPI:
    """Create and configure FastAPI application for traffic intelligence."""
    api_name = os.getenv("API_NAME", "Traffic Intelligence Service")
    
    app = FastAPI(
        title=api_name,
        description="Single intersection monitoring Agent API for traffic analysis and alerts",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Include API routes
    app.include_router(router, prefix="/api/v1")
    
    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy", 
            "service": "traffic-intelligence",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    return app


def main():
    """Main entry point for traffic intelligence service."""
    # Set up logging level
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level))
    
    # Create FastAPI app
    app = create_app()
    
    # Get configuration
    port = int(os.getenv("TRAFFIC_INTELLIGENCE_PORT", "8081"))
    host = os.getenv("TRAFFIC_INTELLIGENCE_HOST", "0.0.0.0")
    
    logger.info("Starting Traffic Intelligence service", 
               host=host, port=port, log_level=log_level)
    
    # Run the application
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=log_level.lower(),
        access_log=True
    )


if __name__ == "__main__":
    main()
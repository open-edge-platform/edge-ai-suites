# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Configuration service for Traffic Intersection Agent."""

import os
import json
import hashlib
from typing import Dict, List, Optional
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


def hash_intersection_name(name: str, length: int = 16) -> str:
    hash_object = hashlib.sha256(name.encode('utf-8'))
    hex_digest = hash_object.hexdigest()
    return hex_digest[:length]


class ConfigService:
    """
    Configuration service for Traffic Intersection Agent.
    
    Manages configuration for single intersection monitoring,
    MQTT topics, weather API, and VLM service settings.
    """
    
    def __init__(self):
        """Initialize configuration service."""
        self._config_dir = Path(__file__).resolve().parent.parent / "config"
        self.config = self._load_config()
        logger.info("Configuration service initialized", 
                   intersection_id=self.get_intersection_id())
    
    def _load_config(self) -> dict:
        """Load configuration from environment and file."""
        config = {}

        agent_config_file = self._config_dir / "traffic_agent.json"
        deployment_config_file = self._config_dir / "deployment_instance.json"

        logger.info("Loading configuration files",
                    agent_config_path=str(agent_config_file),
                    deployment_config_path=str(deployment_config_file))

        try:
            if agent_config_file.exists():
                with open(agent_config_file, 'r') as f:
                    file_config = json.load(f)
                config.update(file_config)
                logger.info("Loaded configuration from file", path=agent_config_file)
            else:
                logger.error("Traffic agent config file does not exist", path=agent_config_file)
                raise FileNotFoundError(f"Config file not found: {agent_config_file}")

            # Create key for storing intersection/instance deployments specific configs
            if "intersection" not in config:
                    config["intersection"] = {}
            
            # Load deployment specific configuration from deployment_instance.json
            if deployment_config_file.exists():
                with open(deployment_config_file, 'r') as f:
                    deployment_config = json.load(f)
                config["intersection"].update(deployment_config)
                logger.info("Loaded deployment configuration from file", path=deployment_config_file)
            else:
                logger.error("Deployment instance config file does not exist", path=deployment_config_file)
                raise FileNotFoundError(f"Config file not found: {deployment_config_file}")
            
            # Override the deployment configs with environment variables if set
            if os.getenv("INTERSECTION_NAME"):
                config["intersection"]["name"] = os.getenv("INTERSECTION_NAME")
            if os.getenv("INTERSECTION_LATITUDE"):
                config["intersection"]["latitude"] = float(os.getenv("INTERSECTION_LATITUDE", 0.0))
            if os.getenv("INTERSECTION_LONGITUDE"):
                config["intersection"]["longitude"] = float(os.getenv("INTERSECTION_LONGITUDE", 0.0))
        
        # handle error while typecasting to float or some generic error
        except ValueError as e:
            logger.error("Invalid value in config file(s) or environment variables", error=str(e))
            raise e
        except Exception as e:
            logger.error("Error occurred while handling config file(s) or environment variables", error=str(e))
            raise e
        
        # MQTT configuration
        if os.getenv("MQTT_HOST"):
            if "mqtt" not in config:
                config["mqtt"] = {}
            config["mqtt"]["host"] = os.getenv("MQTT_HOST")
        if os.getenv("MQTT_PORT"):
            if "mqtt" not in config:
                config["mqtt"] = {}
            config["mqtt"]["port"] = int(os.getenv("MQTT_PORT"))
        
        # Weather configuration
        if os.getenv("WEATHER_MOCK"):
            if "weather" not in config:
                config["weather"] = {}
            config["weather"]["use_mock"] = os.getenv("WEATHER_MOCK").lower() in ["true", "1", "yes"]
        
        if os.getenv("ENABLE_FIRE_MARKERS"):
            if "weather" not in config:
                config["weather"] = {}
            config["weather"]["enable_fire_markers"] = os.getenv("ENABLE_FIRE_MARKERS").lower() in ["true", "1", "yes"]

        if os.getenv("ENABLE_STORM_MARKERS"):
            if "weather" not in config:
                config["weather"] = {}
            config["weather"]["enable_storm_markers"] = os.getenv("ENABLE_STORM_MARKERS").lower() in ["true", "1", "yes"]

        if os.getenv("ENABLE_FLOOD_MARKERS"):
            if "weather" not in config:
                config["weather"] = {}
            config["weather"]["enable_flood_markers"] = os.getenv("ENABLE_FLOOD_MARKERS").lower() in ["true", "1", "yes"]

        # VLM configuration
        if os.getenv("VLM_BASE_URL"):
            if "vlm" not in config:
                config["vlm"] = {}
            config["vlm"]["base_url"] = os.getenv("VLM_BASE_URL")
        if os.getenv("VLM_MODEL_NAME"):
            if "vlm" not in config:
                config["vlm"] = {}
            config["vlm"]["model"] = os.getenv("VLM_MODEL_NAME")
        if os.getenv("VLM_TIMEOUT_SECONDS"):
            if "vlm" not in config:
                config["vlm"] = {}
            config["vlm"]["timeout_seconds"] = int(os.getenv("VLM_TIMEOUT_SECONDS"))
        if os.getenv("VLM_MAX_COMPLETION_TOKENS"):
            if "vlm" not in config:
                config["vlm"] = {}
            config["vlm"]["max_completion_tokens"] = int(os.getenv("VLM_MAX_COMPLETION_TOKENS"))
        if os.getenv("VLM_TEMPERATURE"):
            if "vlm" not in config:
                config["vlm"] = {}
            config["vlm"]["temperature"] = float(os.getenv("VLM_TEMPERATURE"))
        if os.getenv("VLM_TOP_P"):
            if "vlm" not in config:
                config["vlm"] = {}
            config["vlm"]["top_p"] = float(os.getenv("VLM_TOP_P"))
        
        # Traffic configuration
        if os.getenv("HIGH_DENSITY_THRESHOLD"):
            if "traffic" not in config:
                config["traffic"] = {}
            config["traffic"]["high_density_threshold"] = float(os.getenv("HIGH_DENSITY_THRESHOLD"))
        if os.getenv("TRAFFIC_BUFFER_DURATION"):
            if "traffic" not in config:
                config["traffic"] = {}
            config["traffic"]["analysis_window_seconds"] = int(os.getenv("TRAFFIC_BUFFER_DURATION"))
        return config
    
    def get_intersection_id(self) -> str:
        name = self.get_intersection_name()
        return hash_intersection_name(name)
    
    def get_intersection_name(self) -> str:
        """Get the intersection name."""
        return self.config.get("intersection", {}).get("name", "Intersection-1")
    
    def get_intersection_coordinates(self) -> tuple[float, float]:
        """Get intersection coordinates (lat, lon)."""
        intersection = self.config.get("intersection", {})
        try:
            lat = float(intersection.get("latitude", 33.3091336))
            lon = float(intersection.get("longitude", -111.9353095))
            return (lat, lon)
        except (TypeError, ValueError) as e:
            logger.error("Invalid value in deployment configuration or environment variables for intersection coordinates", error=str(e))
            raise e
        
    def get_camera_topics(self) -> List[str]:
        """Get MQTT camera topics."""
        return self.config.get("mqtt", {}).get("camera_topics", [
            "scenescape/data/camera/camera1",
            "scenescape/data/camera/camera2", 
            "scenescape/data/camera/camera3",
            "scenescape/data/camera/camera4"
        ])

    def get_image_topics(self) -> List[str]:
        """Get MQTT image topics."""
        return self.config.get("mqtt", {}).get("image_topics", [
            "scenescape/image/camera/camera1",
            "scenescape/image/camera/camera2", 
            "scenescape/image/camera/camera3",
            "scenescape/image/camera/camera4"
        ])
    
    def get_mqtt_config(self) -> dict:
        """Get MQTT configuration."""
        return self.config.get("mqtt", {})
    
    def get_weather_config(self) -> dict:
        """Get weather API configuration."""
        return self.config.get("weather", {})
    
    def get_vlm_config(self) -> dict:
        """Get VLM service configuration."""
        return self.config.get("vlm", {})
    
    def get_traffic_config(self) -> dict:
        """Get traffic analysis configuration."""
        return self.config.get("traffic", {})
    
    def get_high_density_threshold(self) -> int:
        """Get high density threshold for traffic analysis."""
        return self.config.get("traffic", {}).get("high_density_threshold", 5)

    def update_config(self, key: str, value: any) -> None:
        """Update configuration value."""
        keys = key.split('.')
        config_ref = self.config
        
        # Navigate to the nested key
        for k in keys[:-1]:
            if k not in config_ref:
                config_ref[k] = {}
            config_ref = config_ref[k]
        
        # Set the value
        config_ref[keys[-1]] = value
        logger.info("Configuration updated", key=key, value=value)
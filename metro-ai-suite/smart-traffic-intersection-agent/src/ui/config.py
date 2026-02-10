# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Configuration module for the RSU Monitoring System
"""
import os
from typing import Dict, Any


class Config:
    """Configuration settings for the monitoring dashboard"""
    
    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """Get all configuration settings as a dictionary"""
        return {
            "refresh_interval": cls.get_refresh_interval(),
            "api_url": cls.get_api_url(),
            "app_title": cls.get_app_title(),
            "app_port": cls.get_app_port(),
            "app_host": cls.get_app_host(),
            "ui_theme": cls.get_ui_theme(),
            "high_density_threshold": cls.get_high_density_threshold(),
            "moderate_density_threshold": cls.get_moderate_density_threshold(),
        }
    
    @classmethod
    def print_settings(cls):
        """Print current configuration settings"""
        print("=== RSU Monitoring System Configuration ===")
        settings = cls.get_all_settings()
        for key, value in settings.items():
            print(f"{key.upper()}: {value}")
        print("=" * 45)

    @classmethod
    def get_value_from_env(cls, key: str, default: Any = None) -> Any:
        """Get a configuration value from environment variables"""
        value = os.getenv(key)
        if value:
            return value
        return default
    
    @classmethod
    def get_refresh_interval(cls) -> float:
        return float(cls.get_value_from_env("REFRESH_INTERVAL", 10.0))
    
    @classmethod
    def get_api_url(cls) -> str:
        return cls.get_value_from_env("AGENT_API_URL", "http://localhost:8081/api/v1/traffic/current")
    
    @classmethod
    def get_app_title(cls) -> str:
        return cls.get_value_from_env("APP_TITLE", "TRAFFIC MONITORING SYSTEM")
    
    @classmethod
    def get_app_port(cls) -> int:
        return int(cls.get_value_from_env("AGENT_UI_HOSTPORT", 7860))
    
    @classmethod
    def get_app_host(cls) -> str:   
        return cls.get_value_from_env("AGENT_UI_HOST", "0.0.0.0")
    
    @classmethod
    def get_ui_theme(cls) -> str:
        return cls.get_value_from_env("UI_THEME", "light")

    @classmethod
    def get_high_density_threshold(cls) -> int:
        return int(cls.get_value_from_env("HIGH_DENSITY_THRESHOLD", 10))
    
    @classmethod
    def get_moderate_density_threshold(cls) -> int:
        return int(cls.get_value_from_env("MODERATE_DENSITY_THRESHOLD", 5))
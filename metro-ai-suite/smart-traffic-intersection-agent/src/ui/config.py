# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""
Configuration module for the RSU Monitoring System
"""
import os
from typing import Dict, Any


class Config:
    """Configuration settings for the monitoring dashboard"""
    
    # Refresh settings
    REFRESH_INTERVAL_SECONDS: float = float(os.getenv("REFRESH_INTERVAL", "10.0"))
    
    # API settings
    API_URL: str = os.getenv("API_URL", "http://localhost:8081/api/v1/traffic/current")
    
    # UI settings
    APP_TITLE: str = os.getenv("APP_TITLE", "TRAFFIC MONITORING SYSTEM")
    APP_PORT: int = int(os.getenv("TRAFFIC_INTELLIGENCE_UI_PORT", "7860"))
    APP_HOST: str = "0.0.0.0"
    
    # Theme settings
    UI_THEME: str = os.getenv("UI_THEME", "light")
    
    # Alert thresholds
    HIGH_DENSITY_THRESHOLD: int = int(float(os.getenv("HIGH_DENSITY_THRESHOLD", "10")))
    MODERATE_DENSITY_THRESHOLD: int = int(float(os.getenv("MODERATE_DENSITY_THRESHOLD", "5")))

    # Weather alert thresholds
    HIGH_WIND_THRESHOLD: float = float(os.getenv("HIGH_WIND_THRESHOLD", "25.0"))
    HEAVY_RAIN_THRESHOLD: float = float(os.getenv("HEAVY_RAIN_THRESHOLD", "5.0"))
    
    @classmethod
    def get_all_settings(cls) -> Dict[str, Any]:
        """Get all configuration settings as a dictionary"""
        return {
            "refresh_interval": cls.REFRESH_INTERVAL_SECONDS,
            "api_url": cls.API_URL,
            "app_title": cls.APP_TITLE,
            "app_port": cls.APP_PORT,
            "app_host": cls.APP_HOST,
            "ui_theme": cls.UI_THEME,
            "high_density_threshold": cls.HIGH_DENSITY_THRESHOLD,
            "moderate_density_threshold": cls.MODERATE_DENSITY_THRESHOLD,
            "high_wind_threshold": cls.HIGH_WIND_THRESHOLD,
            "heavy_rain_threshold": cls.HEAVY_RAIN_THRESHOLD
        }
    
    @classmethod
    def print_settings(cls):
        """Print current configuration settings"""
        print("=== RSU Monitoring System Configuration ===")
        settings = cls.get_all_settings()
        for key, value in settings.items():
            print(f"{key.upper()}: {value}")
        print("=" * 45)
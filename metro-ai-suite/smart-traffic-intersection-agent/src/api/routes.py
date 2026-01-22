# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""API routes for Traffic Intersection Agent."""

from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import JSONResponse
import structlog

from services.data_aggregator import DataAggregatorService

logger = structlog.get_logger(__name__)

router = APIRouter()


def get_data_aggregator(request):
    """Dependency to get data aggregator service from app state."""
    return request.app.state.data_aggregator


def get_weather_service(request):
    """Dependency to get weather service from app state."""
    return request.app.state.weather_service


@router.get("/traffic/current", response_model=Dict[str, Any])
async def get_current_traffic_intelligence(
    request: Request,
    images: bool = Query(default=True, description="Include camera images in response")
) -> Dict[str, Any]:
    """
    Get current traffic intelligence data for the intersection.
    
    Returns complete traffic intelligence response using weather data and VLM analysis.
    
    Args:
        images: If False, camera_images will be excluded from response to reduce size
    """
    try:
        data_aggregator: DataAggregatorService = get_data_aggregator(request)
        
        # Get current traffic intelligence
        traffic_response = await data_aggregator.get_current_traffic_intelligence()
        
        if not traffic_response:
            raise HTTPException(status_code=404, detail="No traffic data available")

        # Get current weather data
        weather_service = get_weather_service(request)
        weather_data = await weather_service.get_current_weather()

        # Convert to dict for JSON response
        response_dict = {
            "timestamp": traffic_response.timestamp,
            "response_age": traffic_response.response_age if traffic_response.response_age else None,
            "intersection_id": traffic_response.intersection_id,
            "data": {
                "intersection_id": traffic_response.data.intersection_id,
                "intersection_name": traffic_response.data.intersection_name,
                "latitude": traffic_response.data.latitude,
                "longitude": traffic_response.data.longitude,
                "timestamp": traffic_response.data.timestamp.isoformat(),
                "north_camera": traffic_response.data.north_camera,
                "south_camera": traffic_response.data.south_camera,
                "east_camera": traffic_response.data.east_camera,
                "west_camera": traffic_response.data.west_camera,
                "total_density": traffic_response.data.total_density,
                "intersection_status": traffic_response.data.intersection_status,
                "north_pedestrian": traffic_response.data.north_pedestrian,
                "south_pedestrian": traffic_response.data.south_pedestrian,
                "east_pedestrian": traffic_response.data.east_pedestrian,
                "west_pedestrian": traffic_response.data.west_pedestrian,
                "total_pedestrian_count": traffic_response.data.total_pedestrian_count,
                "north_timestamp": traffic_response.data.north_timestamp,
                "south_timestamp": traffic_response.data.south_timestamp,
                "east_timestamp": traffic_response.data.east_timestamp,
                "west_timestamp": traffic_response.data.west_timestamp,
            },
            "weather_data": weather_data.__dict__,
            "vlm_analysis": {
                "traffic_summary": traffic_response.vlm_analysis.traffic_summary,
                "alerts": [
                    {
                        "alert_type": alert.alert_type.value,
                        "level": alert.level.value,
                        "description": alert.description,
                        "weather_related": alert.weather_related
                    }
                    for alert in traffic_response.vlm_analysis.alerts
                ],
                "recommendations": traffic_response.vlm_analysis.recommendations or [],
                "analysis_timestamp": traffic_response.vlm_analysis.analysis_timestamp.isoformat() if traffic_response.vlm_analysis.analysis_timestamp else None
            }
        }
        
        # Add camera images only if requested
        if images:
            response_dict["camera_images"] = traffic_response.camera_images
        
        logger.info("Current traffic intelligence served",
                   intersection_id=traffic_response.intersection_id,
                   total_density=traffic_response.data.total_density,
                   total_pedestrian_count=traffic_response.data.total_pedestrian_count,
                   alerts_count=len(traffic_response.vlm_analysis.alerts))
        
        return response_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get current traffic intelligence", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

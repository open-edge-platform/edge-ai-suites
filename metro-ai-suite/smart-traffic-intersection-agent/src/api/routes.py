# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Annotated, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder
import structlog

from services.data_aggregator import DataAggregatorService
from services.weather_service import WeatherService


logger = structlog.get_logger(__name__)
router = APIRouter()

def get_data_aggregator(request):
    """Dependency to get data aggregator service from app state."""
    return request.app.state.data_aggregator


def get_weather_service(request):
    """Dependency to get weather service from app state."""
    return request.app.state.weather_service


def _build_response_dict(traffic_response: Any, weather_data: Any, include_images: bool) -> Dict[str, Any]:
    """Helper to build traffic intelligence response dictionary."""
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
            "north_timestamp": traffic_response.data.north_timestamp.isoformat() if traffic_response.data.north_timestamp else None,
            "south_timestamp": traffic_response.data.south_timestamp.isoformat() if traffic_response.data.south_timestamp else None,
            "east_timestamp": traffic_response.data.east_timestamp.isoformat() if traffic_response.data.east_timestamp else None,
            "west_timestamp": traffic_response.data.west_timestamp.isoformat() if traffic_response.data.west_timestamp else None,
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
    if include_images:
        response_dict["camera_images"] = traffic_response.camera_images
        
    return response_dict


@router.get("/traffic/current", response_model=Dict[str, Any])
async def get_current_traffic_intelligence(
    request: Request,
    images: Annotated[bool, Query(description="Include camera images in response")] = True,
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
        weather_service: WeatherService = get_weather_service(request)
        weather_data = await weather_service.get_current_weather()

        # Convert to dict for JSON response
        response_dict = _build_response_dict(traffic_response, weather_data, images)
        
        logger.info("Current traffic intelligence served",
                   intersection_id=traffic_response.intersection_id,
                   total_density=traffic_response.data.total_density,
                   total_pedestrian_count=traffic_response.data.total_pedestrian_count)
        
        return response_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get current traffic intelligence", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


@router.websocket("/traffic/current/ws")
async def ws_current_traffic_intelligence(
    websocket: WebSocket, 
    images: Annotated[bool, Query()] = True,
):
    """
    WebSocket endpoint for real-time traffic intersection data.

    Pushes updated traffic intersection data to the client whenever
    new VLM analysis results become available. This is a drop-in
    alternative to the REST GET /traffic/current endpoint and returns
    the same data in the same format.

    Query Parameters:
        images: If false, camera_images will be excluded from response (default: true)
    """
    await websocket.accept()

    try:
        data_aggregator: DataAggregatorService = get_data_aggregator(websocket)
        weather_service: WeatherService = get_weather_service(websocket)

        # Run a loop to wait for new data events and push updates to the client
        while True:
            traffic_response = await data_aggregator.get_current_traffic_intelligence()
            if traffic_response:
                weather_data = await weather_service.get_current_weather()
                response_dict = _build_response_dict(traffic_response, weather_data, images)

                await websocket.send_json(jsonable_encoder(response_dict))

                logger.debug("Traffic Intersection data pushed to client",
                           intersection_id=traffic_response.intersection_id,
                           total_density=traffic_response.data.total_density,
                           total_pedestrian_count=traffic_response.data.total_pedestrian_count)
            else:
                await websocket.send_json({
                    "status": "waiting",
                    "message": "VLM analysis not yet available."
                })

            event = data_aggregator.new_data_event
            logger.debug("WebSocket waiting for new data event")
            await event.wait()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error in Smart Traffic Intersection Agent", error=str(e))
        try:
            await websocket.close(code=1011, reason="Internal server error")
        except Exception as e:
            logger.error("Failed to close WebSocket after error", error=str(e))

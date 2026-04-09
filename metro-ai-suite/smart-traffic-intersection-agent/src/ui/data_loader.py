# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import logging
from typing import Optional
from datetime import datetime, timezone
import json
import asyncio

from websockets.exceptions import WebSocketException, ConnectionClosed as WebsocketsConnectionClosed
from websockets.asyncio.client import connect as websocket_connect
import gradio as gr

from models import (
    MonitoringData, IntersectionData, RegionCount,
    VLMAnalysis, WeatherData, CameraData, TrafficContext
)
from ui_components import UIComponents
from config import Config

logger = logging.getLogger(__name__)
ui_update_queue = asyncio.Queue()

async def fetch_intersection_data(api_url: str = Config.get_api_url()) -> None:
    """
    Fetch data from the Traffic Intersection Agent API
    
    Args:
        api_url: URL of the Traffic Intersection Agent API endpoint
        
    Returns:
        None. Puts MonitoringData objects into the UI update queue.
    """
    try:
        logger.info(f"Connecting to WebSocket API at {api_url}")
        async for websocket in websocket_connect(api_url, max_size=100_000_000): 
            async for message in websocket:
                raw_data: dict = json.loads(message)
                traffic_data: Optional[MonitoringData] = await parse_api_response(raw_data)
                # Put data into the queue for the UI to consume
                await ui_update_queue.put(traffic_data)
    except WebsocketsConnectionClosed as e:
        logger.warning(f"WebSocket connection closed by server: {str(e)}")
        await asyncio.sleep(3)
    except WebSocketException as e:
        logger.error(f"WebSocket error: {str(e)}")
        await asyncio.sleep(3)
    except json.JSONDecodeError as e:
        logger.error("Received invalid JSON data from WebSocket")
        raise e
    except Exception as e:
        logger.error(f"Error Connecting to WebSocket: {str(e)}.")
        await asyncio.sleep(3)

async def update_components(debug_mode=False):
    """
    Get the latest monitoring data from the UI update queue

    Args:
        debug_mode: Whether to include the debug panel in the UI update
    
    Returns:
        AsyncGenerator yielding tuple of UI components to update the dashboard
    """
    while True:
        try:
            # Wait for new data from the queue, required to update the UI
            data = await ui_update_queue.get()
            if data is None:
                error_msg = "<div style='color: red; text-align: center; padding: 20px;'> 🤖 Waiting for Agent. This might take several seconds...</div>"
                yield error_msg, [], error_msg, error_msg, error_msg, error_msg, gr.HTML(visible=False)
                continue

            header = await UIComponents.create_header(data)
            camera_gallery = await UIComponents.create_camera_images(data)
            traffic = await UIComponents.create_traffic_summary(data)
            environmental = await UIComponents.create_environmental_panel(data)
            alerts = await UIComponents.create_alerts_panel(data)
            system_info = await UIComponents.create_system_info(data)
            debug_panel = await UIComponents.create_debug_panel(data)

            yield header, camera_gallery, traffic, environmental, alerts, system_info, gr.HTML(value=debug_panel, visible=debug_mode)
            
        except Exception as e:
            logger.error(f"Error getting monitoring data from queue: {str(e)}")
            error_msg = f"<div style='color: red; text-align: center; padding: 20px;'>❌ Error</div>"
            yield error_msg, [], error_msg, error_msg, error_msg, error_msg, gr.HTML(visible=False)
            await asyncio.sleep(5)

async def parse_api_response(raw_data: dict) -> Optional[MonitoringData]:
    """
    Parse the Traffic Intersection Agent API response and convert to MonitoringData
    
    Args:
        raw_data: Raw API response dictionary
        
    Returns:
        MonitoringData object or None if parsing fails
    """
    try:
        # Extract traffic data
        traffic_data = raw_data.get("data", {})

        if not traffic_data and raw_data.get("status") == "waiting":
            logger.warning("API response not yet available!")
            return None
        
        # Create region counts mapping pedestrian data from API
        # Map directional pedestrian counts to regions
        region_counts = {
            "region_1": RegionCount(  # North
                vehicle=0,  # API doesn't provide region-specific vehicle counts
                pedestrian=traffic_data.get("north_pedestrian", 0)
            ),
            "region_2": RegionCount(  # South  
                vehicle=0,
                pedestrian=traffic_data.get("south_pedestrian", 0)
            ),
            "region_3": RegionCount(  # East
                vehicle=0,
                pedestrian=traffic_data.get("east_pedestrian", 0)
            ),
            "region_4": RegionCount(  # West
                vehicle=0,
                pedestrian=traffic_data.get("west_pedestrian", 0)
            )
        }
        
        # Create IntersectionData from the main data
        intersection_data = IntersectionData(
            intersection_id=traffic_data["intersection_id"],
            intersection_name=traffic_data["intersection_name"],
            latitude=traffic_data["latitude"],
            longitude=traffic_data["longitude"],
            timestamp=traffic_data["timestamp"],
            northbound_density=traffic_data.get("north_camera", 0),  # Map north_camera to northbound_density
            southbound_density=traffic_data.get("south_camera", 0),  # Map south_camera to southbound_density
            eastbound_density=traffic_data.get("east_camera", 0),    # Map east_camera to eastbound_density
            westbound_density=traffic_data.get("west_camera", 0),    # Map west_camera to westbound_density
            total_density=traffic_data.get("total_density", 0),
            region_counts=region_counts,  # Use the region_counts created above
            total_pedestrian_count=traffic_data.get("total_pedestrian_count", 0),  # Get total pedestrian count from API
            north_timestamp=traffic_data.get("north_timestamp"),
            south_timestamp=traffic_data.get("south_timestamp"),
            east_timestamp=traffic_data.get("east_timestamp"),
            west_timestamp=traffic_data.get("west_timestamp"),
        )
        
        # Parse camera data - handle the new API structure
        camera_images = {}
        camera_data = raw_data.get("camera_images", {})
   
        # Handle the new API format where cameras are named like "west_camera", "north_camera", etc.
        for camera_key, camera_info in sorted(camera_data.items()):
            if isinstance(camera_info, dict):
                camera_images[camera_key] = camera_info  # Store as dict for UI compatibility
            else:
                # Fallback: create CameraData object if needed for old format
                camera_images[camera_key] = CameraData(
                    camera_id=camera_info.get("camera_id", camera_key),
                    direction=camera_info.get("direction", "unknown"),
                    timestamp=camera_info.get("timestamp", ""),
                    image_base64=camera_info.get("image_base64")
                )
        # Parse VLM analysis
        vlm_data = raw_data.get("vlm_analysis", {})
        
        # Create traffic context (simplified for API data)
        traffic_context = TrafficContext(
            analysis_period={"start": "", "end": ""},
            avg_densities={
                "northbound": traffic_data.get("north_camera", 0),
                "southbound": traffic_data.get("south_camera", 0),
                "eastbound": traffic_data.get("east_camera", 0),
                "westbound": traffic_data.get("west_camera", 0)
            },
            peak_densities={
                "northbound": traffic_data.get("north_camera", 0),
                "southbound": traffic_data.get("south_camera", 0),
                "eastbound": traffic_data.get("east_camera", 0),
                "westbound": traffic_data.get("west_camera", 0)
            }
        )
        
        # Process alerts from the new API format
        alerts = []
        api_alerts = vlm_data.get("alerts", [])
        for alert in api_alerts:
            if isinstance(alert, dict):
                # Store the full alert structure for UI processing
                alerts.append(alert)
            else:
                # Fallback for string format
                alerts.append(str(alert))
        
        # Process recommendations from the new API format
        recommendations = vlm_data.get("recommendations", [])
        
        # Calculate high density directions (threshold of 3+ vehicles)
        high_density_directions = []
        current_high_directions = []
        if traffic_data.get("north_camera", 0) >= 3:
            high_density_directions.append("northbound")
            current_high_directions.append("northbound")
        if traffic_data.get("south_camera", 0) >= 3:
            high_density_directions.append("southbound")
            current_high_directions.append("southbound")
        if traffic_data.get("east_camera", 0) >= 3:
            high_density_directions.append("eastbound")
            current_high_directions.append("eastbound")
        if traffic_data.get("west_camera", 0) >= 3:
            high_density_directions.append("westbound")
            current_high_directions.append("westbound")
        
        current_time = datetime.now(timezone.utc).timestamp()
        vlm_analysis = VLMAnalysis(
            analysis=vlm_data.get("traffic_summary", "No analysis available"),
            high_density_directions=high_density_directions,
            analysis_timestamp=vlm_data.get("analysis_timestamp", ""),
            current_high_directions=current_high_directions,
            analysis_age_minutes=0.0,
            traffic_context=traffic_context,
            alerts=alerts,
            recommendations=recommendations
        )

        # Parse weather data
        weather_data_raw = raw_data.get("weather_data", {})
        
        # Extract wind information from the new API format
        wind_speed_str = weather_data_raw.get("wind_speed", "0 mph")
        wind_direction_str = weather_data_raw.get("wind_direction", "N")
        
        # Parse wind speed to mph
        import re
        speed_match = re.search(r'(\d+)', wind_speed_str)
        wind_speed_mph = float(speed_match.group(1)) if speed_match else 0.0
        
        # Convert wind direction to degrees
        direction_map = {
            "N": 0, "NNE": 22, "NE": 45, "ENE": 67,
            "E": 90, "ESE": 112, "SE": 135, "SSE": 157,
            "S": 180, "SSW": 202, "SW": 225, "WSW": 247,
            "W": 270, "WNW": 292, "NW": 315, "NNW": 337
        }
        wind_direction_degrees = direction_map.get(wind_direction_str.upper(), 0)
        
        # Get precipitation probability directly from API instead of estimating
        precipitation_prob = weather_data_raw.get("precipitation_prob", 0.0)
        
        # Convert temperature to Fahrenheit if needed (API provides in F)
        temperature_f = weather_data_raw.get("temperature", 70)
        
        # Use relative humidity from API if available, otherwise estimate
        humidity = weather_data_raw.get("relative_humidity", 50)
        if humidity is None:
            # Fallback estimation if API doesn't provide humidity
            if weather_data_raw.get("is_precipitation", False):
                humidity = 75
            elif "clear" in weather_data_raw.get("short_forecast", "").lower():
                humidity = 40
            else:
                humidity = 50
        
        # Use short_forecast for conditions if available, otherwise detailed_forecast
        conditions = weather_data_raw.get("short_forecast", 
                                         weather_data_raw.get("detailed_forecast", "Unknown"))
        
        weather_data = WeatherData(
            timestamp=weather_data_raw.get("fetched_at", ""),
            temperature_fahrenheit=temperature_f,
            humidity_percent=int(humidity),
            precipitation_prob=precipitation_prob,
            wind_speed_mph=wind_speed_mph,
            wind_direction_degrees=wind_direction_degrees,
            conditions=conditions,
            # New hourly forecast fields
            dewpoint=weather_data_raw.get("dewpoint"),
            relative_humidity=weather_data_raw.get("relative_humidity"),
            is_daytime=weather_data_raw.get("is_daytime"),
            start_time=weather_data_raw.get("start_time"),
            end_time=weather_data_raw.get("end_time"),
            detailed_forecast=weather_data_raw.get("detailed_forecast"),
            temperature_unit=weather_data_raw.get("temperature_unit", "F")
        )
        
        # Create complete monitoring data object
        monitoring_data = MonitoringData(
            timestamp=traffic_data.get("timestamp", ""),
            intersection_id=traffic_data.get("intersection_id", "intersection_1"),
            data=intersection_data,
            camera_images=camera_images,
            vlm_analysis=vlm_analysis,
            weather_data=weather_data
        )
        
        return monitoring_data
        
    except Exception as e:
        logger.error(f"Error parsing API response: {str(e)}")
        return None

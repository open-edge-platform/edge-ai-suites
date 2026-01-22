# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Data aggregator service for Traffic Intersection Agent."""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from collections import deque
import structlog

from models import (
    CameraDataMessage, CameraImage, TrafficSnapshot, IntersectionData,
    TrafficIntersectionAgentResponse, WeatherData, VLMAnalysisData
)
from .config import ConfigService
from .vlm_service import VLMService


logger = structlog.get_logger(__name__)


class DataAggregatorService:
    """
    Data aggregator service for Traffic Intersection Agent.
    
    Aggregates camera data, coordinates with weather and VLM services,
    and maintains current traffic state for API responses.
    """

    def __init__(self, config_service: ConfigService, vlm_service: VLMService):
        """
        Initialize data aggregator service.
        
        Args:
            config_service: Configuration service
            vlm_service: VLM service for traffic analysis
        """
        self.config = config_service
        self.vlm_service = vlm_service
        
        # Data storage - separate temporary and VLM-analyzed data
        self.temp_camera_data: Dict[str, CameraDataMessage] = {}     # direction -> latest temp data
        self.temp_camera_images: Dict[str, CameraImage] = {}         # direction -> latest temp image
        self.temp_intersection_data: Optional[IntersectionData] = None
        
        # VLM-analyzed data storage (only data that was part of VLM analysis)
        self.vlm_analyzed_camera_images: Dict[str, CameraImage] = {}      # direction -> VLM-analyzed images
        self.vlm_analyzed_intersection_data: Optional[IntersectionData] = None
        self.vlm_analyzed_weather_data: Optional[WeatherData] = None
        
        # Current state
        self.current_vlm_analysis: Optional[VLMAnalysisData] = None
        self.last_analysis_time: Optional[float] = 0.0
        
        
        logger.info("Data aggregator service initialized")

    
    async def process_camera_image(self, camera_image: CameraImage) -> None:
        """
        Process incoming camera image separately from data.
        
        Args:
            camera_image: Camera image data from MQTT
        """
        try:
            direction = camera_image.direction
            
            # Update temporary camera image
            self.temp_camera_images[direction] = camera_image
            
            logger.info("Camera image updated (temporary)", 
                       direction=direction,
                       camera_id=camera_image.camera_id,
                       image_size=camera_image.image_size_bytes,
                       has_image_data=bool(camera_image.image_base64),
                       total_temp_images_stored=len(self.temp_camera_images))
                    
        except Exception as e:
            logger.error("Failed to process camera image", error=str(e))

    async def process_camera_data(self, camera_message: CameraDataMessage) -> None:
        """
        Process incoming camera data and update current state.
        
        Args:
            camera_message: Camera data message from MQTT
        """
        try:
            direction = camera_message.direction
            
            # Update temporary camera data
            self.temp_camera_data[direction] = camera_message
            
            logger.info("Camera data updated (temporary)")          
            
            # Update temporary intersection data
            await self._update_temp_intersection_data()

            if len(self.temp_camera_data) == 4:
                # Check if VLM analysis should be triggered
                self.temp_camera_data = {}  # Clear after processing all directions
                await self._check_analysis_trigger()
                
                    
        except Exception as e:
            logger.error("Failed to process camera data", error=str(e))
    
    async def _update_temp_intersection_data(self) -> None:
        """Update temporary intersection data from camera inputs."""
        intersection_id = self.config.get_intersection_id()
        intersection_name = self.config.get_intersection_name()
        lat, lon = self.config.get_intersection_coordinates()
        
        # Calculate directional counts from temporary data
        north_count = self.temp_camera_data.get('north', CameraDataMessage('', '', 'north', 0)).vehicle_count
        south_count = self.temp_camera_data.get('south', CameraDataMessage('', '', 'south', 0)).vehicle_count
        east_count = self.temp_camera_data.get('east', CameraDataMessage('', '', 'east', 0)).vehicle_count
        west_count = self.temp_camera_data.get('west', CameraDataMessage('', '', 'west', 0)).vehicle_count
        
        # Calculate pedestrian counts from temporary data
        north_pedestrian = self.temp_camera_data.get('north', CameraDataMessage('', '', 'north', 0, 0)).pedestrian_count
        south_pedestrian = self.temp_camera_data.get('south', CameraDataMessage('', '', 'south', 0, 0)).pedestrian_count
        east_pedestrian = self.temp_camera_data.get('east', CameraDataMessage('', '', 'east', 0, 0)).pedestrian_count
        west_pedestrian = self.temp_camera_data.get('west', CameraDataMessage('', '', 'west', 0, 0)).pedestrian_count

        # Get Traffic data timestamps
        north_timestamp = self.temp_camera_data.get('north').timestamp if 'north' in self.temp_camera_data else None
        south_timestamp = self.temp_camera_data.get('south').timestamp if 'south' in self.temp_camera_data else None
        east_timestamp = self.temp_camera_data.get('east').timestamp if 'east' in self.temp_camera_data else None
        west_timestamp = self.temp_camera_data.get('west').timestamp if 'west' in self.temp_camera_data else None
        
        total_count = north_count + south_count + east_count + west_count
        total_pedestrian_count = north_pedestrian + south_pedestrian + east_pedestrian + west_pedestrian
        
        # Calculate intersection-level traffic status based on total density
        high_density_threshold = self.config.get_high_density_threshold()
        
        if total_count >= (high_density_threshold * 2/3):
            intersection_status = "HIGH"
        elif total_count >= (high_density_threshold * 1/3):
            intersection_status = "MODERATE"
        else:
            intersection_status = "NORMAL"
        
        self.temp_intersection_data = IntersectionData(
            intersection_id=intersection_id,
            intersection_name=intersection_name,
            latitude=lat,
            longitude=lon,
            timestamp=datetime.now(timezone.utc),
            north_camera=north_count,
            south_camera=south_count,
            east_camera=east_count,
            west_camera=west_count,
            total_density=total_count,
            intersection_status=intersection_status,
            north_pedestrian=north_pedestrian,
            south_pedestrian=south_pedestrian,
            east_pedestrian=east_pedestrian,
            west_pedestrian=west_pedestrian,
            total_pedestrian_count=total_pedestrian_count,
            north_timestamp=north_timestamp,
            south_timestamp=south_timestamp,
            east_timestamp=east_timestamp,
            west_timestamp=west_timestamp,
        )
        
        logger.info("Temporary intersection data updated", 
                   total_density=total_count,
                   intersection_status=intersection_status,
                   total_pedestrian_count=total_pedestrian_count,
                   north=north_count, south=south_count, 
                   east=east_count, west=west_count,
                   north_ped=north_pedestrian, south_ped=south_pedestrian,
                   east_ped=east_pedestrian, west_ped=west_pedestrian,
                   north_timestamp=north_timestamp,
                   south_timestamp=south_timestamp,
                   east_timestamp=east_timestamp,
                   west_timestamp=west_timestamp)

    def _create_temp_traffic_snapshot(self) -> Optional[TrafficSnapshot]:
        """Create a traffic snapshot from temporary data for VLM analysis."""
        if not self.temp_intersection_data:
            return None
        
        directional_counts = {
            'north': self.temp_intersection_data.north_camera,
            'south': self.temp_intersection_data.south_camera,
            'east': self.temp_intersection_data.east_camera,
            'west': self.temp_intersection_data.west_camera
        }
      
        return TrafficSnapshot(
            timestamp=datetime.now(timezone.utc),
            intersection_id=self.temp_intersection_data.intersection_id,
            directional_counts=directional_counts,
            total_count=self.temp_intersection_data.total_density,
            camera_images=self.temp_camera_images.copy(),
            intersection_data=self.temp_intersection_data,
        )
    
    def _save_vlm_analyzed_data(self, vlm_analysis: VLMAnalysisData, traffic_snapshot: TrafficSnapshot) -> None:
        """Save data that was used in VLM analysis as the current analyzed data."""

        self.current_vlm_analysis = vlm_analysis

        # Copy temporary camera data to VLM-analyzed storage
        self.vlm_analyzed_camera_images = traffic_snapshot.camera_images
        self.vlm_analyzed_intersection_data = traffic_snapshot.intersection_data
        self.vlm_analyzed_weather_data = self.vlm_service.get_weather_details()
    

        # Add to historical snapshots (only VLM-analyzed data)
        
        logger.info("VLM-analyzed data saved",
                   total_density=traffic_snapshot.total_count,
                   analyzed_cameras=list(self.vlm_analyzed_camera_images.keys()),
                   intersection_id=traffic_snapshot.intersection_id)

    async def _check_analysis_trigger(self) -> None:
        """Check if VLM analysis should be triggered based on traffic conditions."""
        
        if not self.temp_intersection_data:
            logger.debug("No intersection data available for analysis trigger check")
            return
        
        # Get current threshold dynamically from config
        high_density_threshold = self.config.get_high_density_threshold()
        
        logger.info("Checking if VLM analysis should be triggered",
                   total_density=self.temp_intersection_data.total_density,
                   threshold=high_density_threshold,
                   last_analysis_time=self.last_analysis_time)
        
        # High traffic - always analyze
        if self.temp_intersection_data.total_density >= high_density_threshold:
            logger.info("High traffic detected, triggering VLM analysis",
                       total_density=self.temp_intersection_data.total_density,
                       threshold=high_density_threshold)
            await self._trigger_vlm_analysis()
            return
        
        # Low traffic - check if enough time has passed since last analysis
        if self.last_analysis_time == 0.0:
            logger.info("No previous analysis, triggering VLM analysis for low traffic",
                       total_density=self.temp_intersection_data.total_density)
            await self._trigger_vlm_analysis()
            return
        
        analysis_window_seconds = self.config.get_traffic_config().get("analysis_window_seconds", 30)
        time_since_last_analysis = datetime.now().timestamp() - self.last_analysis_time
        
        logger.info("Low traffic - checking analysis window",
                   total_density=self.temp_intersection_data.total_density,
                   time_since_last_analysis=time_since_last_analysis,
                   analysis_window_seconds=analysis_window_seconds)
        
        if time_since_last_analysis >= analysis_window_seconds:
            logger.info("Analysis window expired, triggering VLM analysis for low traffic",
                       total_density=self.temp_intersection_data.total_density,
                       time_since_last=time_since_last_analysis,
                       window_seconds=analysis_window_seconds)
            await self._trigger_vlm_analysis()
        else:
            logger.info("Skipping VLM analysis - within analysis window",
                       total_density=self.temp_intersection_data.total_density,
                       time_since_last=time_since_last_analysis,
                       window_seconds=analysis_window_seconds)
        
    async def _trigger_vlm_analysis(self) -> None:
        """Trigger VLM analysis with current traffic and weather data."""
        try:
            logger.info("Starting VLM analysis trigger")
            traffic_snapshot = self._create_temp_traffic_snapshot()

            if not traffic_snapshot:
                logger.warning("Cannot trigger VLM analysis: no traffic snapshot available")
                return
        
            # Trigger VLM analysis
            try:
                vlm_analysis: VLMAnalysisData = await self.vlm_service.analyze_traffic_non_blocking(
                    traffic_snapshot=traffic_snapshot
                )
            
                if vlm_analysis:
                    self._save_vlm_analyzed_data(vlm_analysis, traffic_snapshot)
                    self.last_analysis_time = datetime.now().timestamp()

                    logger.info("VLM analysis completed successfully and data saved",
                            alerts_count=len(vlm_analysis.alerts),
                            analyzed_total_density=traffic_snapshot.total_count)
                else:
                    logger.warning("VLM analysis returned no result - temporary data not saved")
                

            except Exception as vlm_error:
                logger.error("VLM analysis failed - temporary data not saved", error=str(vlm_error))
                # Don't update analysis on error
            
        except Exception as e:
            logger.error("Failed to trigger VLM analysis", error=str(e))
    
    async def get_current_traffic_intelligence(self) -> Optional[TrafficIntersectionAgentResponse]:
        """
        Get current traffic intelligence response.
        
        Returns:
            Complete traffic intelligence response or None if no VLM-analyzed data available
        """
        # Only return data that was part of VLM analysis
        if not self.vlm_analyzed_intersection_data or not self.current_vlm_analysis:
            logger.info("No VLM-analyzed data available for API response",
                       has_vlm_intersection_data=self.vlm_analyzed_intersection_data is not None,
                       has_vlm_analysis=self.current_vlm_analysis is not None)
            return None
        
        try:
            
            # Prepare camera images for response (only VLM-analyzed images)
            camera_images_dict = {}
            for direction, camera_image in self.vlm_analyzed_camera_images.items():
                camera_images_dict[f"{direction}_camera"] = {
                    'camera_id': camera_image.camera_id,
                    'direction': camera_image.direction,
                    'timestamp': camera_image.timestamp,
                    'image_base64': camera_image.image_base64,  # Include full base64 image
                    'image_size_bytes': camera_image.image_size_bytes
                }
            
            # Create response with VLM-analyzed data only
            response = TrafficIntersectionAgentResponse(
                timestamp=datetime.now(timezone.utc).isoformat(),
                intersection_id=self.vlm_analyzed_intersection_data.intersection_id,
                data=self.vlm_analyzed_intersection_data,
                camera_images=camera_images_dict,
                weather_data=self.vlm_analyzed_weather_data,
                vlm_analysis=self.current_vlm_analysis,
                response_age=(datetime.now(timezone.utc).timestamp() - self.last_analysis_time),
            )
            
            return response
            
        except Exception as e:
            logger.error("Failed to create traffic intelligence response", error=str(e))
            return None
    

    def _get_default_weather(self) -> WeatherData:
        """Get default weather data when none is available."""
        return WeatherData(
            name="Unknown", 
            temperature=72, 
            temperature_unit="F",
            detailed_forecast="Weather data unavailable", 
            fetched_at=datetime.now(timezone.utc),
            is_precipitation=False,
            is_mock=True
        )
    
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get current service status and statistics."""
        return {
            "intersection_id": self.config.get_intersection_id(),
            "intersection_name": self.config.get_intersection_name(),
            "current_traffic_density": self.vlm_analyzed_intersection_data.total_density if self.vlm_analyzed_intersection_data else 0,
            "current_pedestrian_count": self.vlm_analyzed_intersection_data.total_pedestrian_count if self.vlm_analyzed_intersection_data else 0,
            "analyzed_camera_directions": list(self.vlm_analyzed_camera_images.keys()),
            "active_analyzed_cameras": len(self.vlm_analyzed_camera_images),
            "has_weather_data": self.vlm_analyzed_weather_data is not None,
            "has_vlm_analysis": self.current_vlm_analysis is not None,
            "last_analysis_time": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            # "vlm_analyzed_history_count": len(self.traffic_history),
            # "analysis_tasks_running": self.analysis_task is not None and not self.analysis_task.done()
        }
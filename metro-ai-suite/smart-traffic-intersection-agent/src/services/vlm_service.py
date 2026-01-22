# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Enhanced VLM service for traffic intelligence with weather-aware analysis."""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from click import prompt
import aiohttp
import structlog

from models import (
    WeatherData, VLMAnalysisData, VLMAlert, AlertLevel, AlertType, 
    CameraImage, TrafficSnapshot, WeatherType
)
from .config import ConfigService
from .weather_service import WeatherService


# Update logger to show debug level logs for development
logger = structlog.get_logger(__name__)


class VLMService:
    """
    Enhanced VLM service for traffic intelligence with weather-aware analysis.
    
    Features:
    - Structured prompts for traffic analysis and alerts
    - Weather integration for contextual analysis
    - Alert generation with severity levels
    - Traffic pattern recognition
    """

    def __init__(self, config_service: ConfigService, weather_service: WeatherService):
        """Initialize VLM service with configuration and weather integration."""
        self.config = config_service
        self.weather_service = weather_service
        self.vlm_config = config_service.get_vlm_config()

        self.weather_data: Optional[WeatherData] = None
        
        # VLM service configuration
        self.base_url = self.vlm_config.get("base_url", "http://vlm-service:8080")
        self.model = self.vlm_config.get("model", "gpt-4-vision-preview")
        self.timeout = self.vlm_config.get("timeout_seconds", 300)  # Reduced from 300 to 30 seconds
        self.max_tokens = self.vlm_config.get("max_completion_tokens", 2000)
        self.temperature = self.vlm_config.get("temperature", 0.1)
        self.top_p = self.vlm_config.get("top_p", 0.1)
        
        # Store config service for dynamic threshold access
        self.config_service = config_service
        
        # Cache for recent analyses
        self._analysis_cache: Dict[str, VLMAnalysisData] = {}
        
        # Semaphore to ensure only one VLM request at a time
        self._vlm_semaphore = asyncio.Semaphore(1)
        
        # Store last successful analysis to reuse when service is busy
        self._last_analysis: Optional[VLMAnalysisData] = None
        self._last_analysis_timestamp: Optional[datetime] = None
        
        logger.info("Enhanced VLM service initialized", 
                   base_url=self.base_url,
                   model=self.model,
                   threshold=self.config_service.get_high_density_threshold())
        
    def get_vlm_semaphore(self) -> asyncio.Semaphore:
        """Get the VLM semaphore for external use."""
        return self._vlm_semaphore
        
    def get_weather_details(self) -> Optional[WeatherData]:
        """Get the last fetched weather data."""
        return self.weather_data or self.weather_service.get_default_weather()
    
    async def analyze_traffic_with_weather(
            self, 
            traffic_snapshot: TrafficSnapshot,
            camera_images: List[CameraImage]
    ) -> Optional[VLMAnalysisData]:
        """
        Perform comprehensive traffic analysis with weather context.
        
        Args:
            traffic_snapshot: Current traffic data
            camera_images: List of camera images from intersection
            weather_data: Current weather data (optional)
            
        Returns:
            VLMAnalysisData with structured analysis and alerts
        """ 
        try:
            try:
                self.weather_data = await self.weather_service.get_current_weather()
            except Exception as e:
                logger.warning("Weather fetch failed during VLM analysis, using cached or default data", error=str(e))
                self.weather_data = self.weather_data or self.weather_service.get_default_weather()

            # Create structured prompt with weather context
            prompt = self._create_structured_prompt(traffic_snapshot, self.weather_data)

            logger.info("Generated VLM prompt", prompt=prompt)
            
            # Prepare VLM request with images
            logger.info("Preparing VLM request", 
                       camera_images_available=len(camera_images),
                       camera_directions=[img.direction for img in camera_images],
                       image_data_present=[bool(img.image_base64) for img in camera_images])
            vlm_request = self._build_vlm_request(prompt, camera_images)
            
            # Call VLM service
            analysis_result = await self._call_vlm_service(vlm_request)
            
            if analysis_result:
                # Parse structured response
                structured_analysis = self._parse_vlm_response(
                    analysis_result, traffic_snapshot, self.weather_data
                )
                
                # Cache the analysis
                self._analysis_cache[traffic_snapshot.intersection_id] = structured_analysis
                
                # Store as last successful analysis for reuse when service is busy
                self._last_analysis = structured_analysis
                self._last_analysis_timestamp = datetime.now(timezone.utc)
                
                logger.info("VLM analysis completed successfully", 
                           intersection_id=traffic_snapshot.intersection_id,
                           alerts_count=len(structured_analysis.alerts))
                
                return structured_analysis
            else:
                logger.warning("VLM service returned no result, using fallback analysis")
                # Use fallback analysis instead of returning None
                fallback_analysis = self._create_fallback_analysis(
                    "VLM service returned no result", traffic_snapshot, self.weather_data
                )
                logger.info("Using fallback analysis", 
                           alerts_count=len(fallback_analysis.alerts))
                return fallback_analysis
                
        except Exception as e:
            logger.error("VLM analysis failed", error=str(e))
            fallback_analysis = self._create_fallback_analysis(
                    "VLM service returned no result", traffic_snapshot, self.weather_data
                )
            logger.info("Using fallback analysis", 
                           alerts_count=len(fallback_analysis.alerts))
            return fallback_analysis
    
    async def analyze_traffic_non_blocking(self, traffic_snapshot: TrafficSnapshot) -> Optional[VLMAnalysisData]:
        """
        Non-blocking traffic analysis that uses semaphore to prevent concurrent requests.
        Returns cached analysis if VLM service is busy.
        
        Args:
            traffic_snapshot: Current traffic data
            
        Returns:
            VLMAnalysisData - either new analysis or cached result if service is busy
        """
        try:
            # Try to acquire semaphore without blocking
            if self._vlm_semaphore.locked():
                current_time = datetime.now(timezone.utc)
                logger.info("VLM service is busy, returning cached analysis", 
                           has_cached_analysis=self._last_analysis is not None,
                           last_analysis_age_minutes=(current_time - self._last_analysis_timestamp).total_seconds() / 60 
                           if self._last_analysis_timestamp else None)
                
                # Return last successful analysis if available
                if self._last_analysis:
                    # Update timestamp to current time for the cached result
                    cached_analysis = VLMAnalysisData(
                        traffic_summary=self._last_analysis.traffic_summary,
                        alerts=self._last_analysis.alerts,
                        recommendations=self._last_analysis.recommendations,
                        analysis_timestamp=current_time  # Update to current time
                    )
                    logger.debug("Returning cached VLM analysis", 
                               original_timestamp=self._last_analysis.analysis_timestamp,
                               cached_alerts_count=len(cached_analysis.alerts))
                    return cached_analysis
                else:
                    logger.warning("VLM service busy and no cached analysis available")
                    return None
            
            # Semaphore is available, acquire it and perform analysis
            async with self._vlm_semaphore:
                logger.info("VLM service is free, performing new analysis")
                
                # Perform the actual analysis
                camera_images = list(traffic_snapshot.camera_images.values())
                analysis_result = await self.analyze_traffic_with_weather(
                    traffic_snapshot, camera_images
                )
                
                # Cache successful result
                if analysis_result:
                    self._last_analysis = analysis_result
                    self._last_analysis_timestamp = datetime.now(timezone.utc)
                    logger.info("New VLM analysis completed and cached", 
                               alerts_count=len(analysis_result.alerts))
                else:
                    logger.warning("New VLM analysis returned no result")
                
                return analysis_result
                
        except Exception as e:
            logger.error("Non-blocking VLM analysis failed", error=str(e))
            return self._last_analysis  # Return cached result on error if available
    
    
    def _create_structured_prompt(self, 
                                traffic_snapshot: TrafficSnapshot,
                                weather_data: Optional[WeatherData]) -> str:
        """
        Create structured prompt for VLM analysis with weather context.
        
        Args:
            traffic_snapshot: Current traffic data
            weather_data: Current weather conditions
            
        Returns:
            Structured prompt string
        """
        intersection_name = self.config.get_intersection_name()
        timestamp = traffic_snapshot.timestamp.strftime("%H:%M:%S")
        
        # Traffic density information
        high_density_threshold = self.config_service.get_high_density_threshold()
        density_info = []
        for direction, count in traffic_snapshot.directional_counts.items():
            if count  >= (high_density_threshold * 2/3):
                status = "HIGH"
            elif count >= (high_density_threshold * 1/3) and count < (high_density_threshold * 2/3):
                status = "MODERATE"
            else:
                status = "NORMAL"
            density_info.append(f"{direction.title()}: {count} vehicles ({status})")
        
        density_summary = "\n".join(density_info)
        
        # Weather context
        weather_context = "Weather conditions at the intersection: Clear"
        if weather_data:
            weather_context = f"""Weather conditions at the intersection: 
- Temperature: {weather_data.temperature}°{weather_data.temperature_unit}
- Conditions: {weather_data.detailed_forecast}"""

        # Create structured prompt
        prompt = f"""Analyze traffic conditions at a traffic intersection with 4 cameras in each of the 4 directions.

TRAFFIC DATA:
Total number of vehicles on intersection : {traffic_snapshot.total_count}
Directional traffic breakdown - Number of vehicles per direction:
{density_summary}

{weather_context}

ANALYSIS REQUIREMENTS:
Please provide a structured analysis in JSON format with the following key details about the traffic situation:

1. "analysis": Detailed human like overview of current traffic conditions based on the image data for the intersection's current state, referencing specific traffic image observations, traffic patterns and weather impacts.
2. "alerts": This field is an array of alert objects based on the traffic analysis. Each alert object should strictly contain:
   - "alert_type": value should be strictly one of the following: [congestion, weather_related, road_condition, accident, maintenance, normal]
   - "level": value should be strictly one of the following: [info, warning, critical]
   - "description": detailed context-rich alert description. This is based on the detailed traffic analysis.
   - "weather_related": strictly a boolean value. If weather is a factor for the traffic situation value should be True, otherwise False
   
3. "recommendations": Array of recommendation objects helping to make decisions while travelling through this intersection:
   - "recommendation": Clear advice for traffic management or safety.
Strictly respond ONLY with valid JSON format enclosed in markdown code blocks like:
```json
{{
  "analysis": "...",
  "alerts": [...],
  "recommendations": [...]
}}
```"""
        
        return prompt
    
    def _build_vlm_request(self, prompt: str, camera_images: List[CameraImage]) -> Dict[str, Any]:
        """Build VLM API request with multiple images."""
        
        logger.debug("Building VLM request", 
                   prompt_length=len(prompt),
                   camera_images_count=len(camera_images))
        
        # Prepare content with text prompt and images
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        
        # Add up to 4 camera images (one per direction)
        for i, camera_image in enumerate(camera_images[:4]):
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{camera_image.image_base64}"
                }
            })
        
        # Use configurable parameters - match working curl structure
        request = {
            "model": self.model,
            "max_completion_tokens": self.max_tokens,
            "top_p": self.top_p,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": content
                }
            ]
        }
        
        logger.debug("VLM request built", 
                   request)
        
        return request
    
    async def _call_vlm_service(self, request_data: Dict[str, Any]) -> Optional[str]:
        """
        Call VLM service API with error handling.
        
        Args:
            request_data: VLM API request payload
            
        Returns:
            VLM response text or None if failed
        """
        try:
            url = f"{self.base_url}/v1/chat/completions"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=request_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        logger.debug("VLM service raw response", response_keys=list(result.keys()) if isinstance(result, dict) else "non-dict")
                        
                        if 'choices' in result and len(result['choices']) > 0:
                            choice = result['choices'][0]
                            if 'message' in choice and 'content' in choice['message']:
                                content = choice['message']['content']
                                logger.info("VLM service response received successfully", 
                                          content_length=len(content))
                                return content.strip()
                            else:
                                logger.error("Missing message.content in VLM response", choice_keys=list(choice.keys()) if isinstance(choice, dict) else "non-dict")
                                return None
                        else:
                            logger.error("Invalid VLM response format - missing choices", response_keys=list(result.keys()) if isinstance(result, dict) else "non-dict")
                            return None
                    else:
                        error_text = await response.text()
                        logger.error("VLM service error", 
                                   status=response.status, error=error_text)
                        return None
        except aiohttp.ClientConnectorError as e:
            logger.warning("VLM service connection failed", error=str(e))
            return None
        except Exception as e:
            logger.error("VLM service call failed", error=str(e))
            return None
    
    def _parse_vlm_response(self, 
                           response_text: str,
                           traffic_snapshot: TrafficSnapshot,
                           weather_data: Optional[WeatherData]) -> VLMAnalysisData:
        """
        Parse VLM response into structured VLMAnalysisData.
        
        Args:
            response_text: Raw VLM response
            traffic_snapshot: Traffic data used for analysis
            weather_data: Weather data used for analysis
            
        Returns:
            Structured VLMAnalysisData object
        """
        try:
            # Extract JSON from markdown code blocks if present
            logger.debug(response_text)
            json_content = self._extract_json_from_response(response_text)
            
            
            # If extraction failed or returned None, use fallback
            if json_content is None or len(json_content.strip()) == 0:
                logger.warning("JSON extraction failed or returned empty content, using fallback")
                return self._create_fallback_analysis(response_text, traffic_snapshot, weather_data)
            
            # Parse JSON response
            logger.info("Attempting to parse JSON content")
            response_data = json.loads(json_content)
            
            logger.info("JSON parsing successful", 
                       response_type=type(response_data).__name__,
                       response_keys=list(response_data.keys()) if isinstance(response_data, dict) else "non-dict")
            
            # Parse alerts
            alerts = []
            for alert_data in response_data.get('alerts', []):
                try:
                    alert = VLMAlert(
                        alert_type=AlertType(alert_data.get('alert_type', 'congestion')),
                        level=AlertLevel(alert_data.get('level', 'info')),
                        description=alert_data.get('description', ''),
                        weather_related=alert_data.get('weather_related', False)
                    )
                    alerts.append(alert)
                except (ValueError, KeyError) as e:
                    logger.warning("Failed to parse alert", error=str(e), alert_data=alert_data)
                    continue
            
            # Parse recommendations - handle both array of objects and array of strings
            recommendations = []
            raw_recommendations = response_data.get('recommendations', [])
            for rec in raw_recommendations:
                if isinstance(rec, dict):
                    # Extract recommendation text from object
                    rec_text = rec.get('recommendation', rec.get('description', str(rec)))
                    recommendations.append(rec_text)
                else:
                    # Handle string recommendations directly
                    recommendations.append(str(rec))
            
            # Create structured analysis - map LLM response fields to our data model
            analysis_text = response_data.get('analysis', '')
            
            analysis = VLMAnalysisData(
                traffic_summary=analysis_text,  # Use the "analysis" field from LLM response
                alerts=alerts,
                recommendations=recommendations,
                analysis_timestamp=datetime.utcnow()
            )
            
            logger.debug("VLM response parsed successfully", 
                       alerts_count=len(alerts),
                       has_analysis=bool(analysis_text),
                       recommendations_count=len(analysis.recommendations))
            
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse VLM JSON response, using fallback", 
                        error=str(e), 
                        response_preview=response_text[:200])
            # Create fallback analysis
            fallback = self._create_fallback_analysis(response_text, traffic_snapshot, weather_data)
            return fallback
        except Exception as e:
            logger.error("Failed to parse VLM response, using fallback", 
                        error=str(e),
                        error_type=type(e).__name__)
            fallback = self._create_fallback_analysis(response_text, traffic_snapshot, weather_data)
            return fallback

    def _extract_json_from_response(self, response_text: str) -> Optional[str]:
        """
        Extract JSON content from VLM response, handling markdown code blocks.
        
        Args:
            response_text: Raw VLM response text
            
        Returns:
            JSON string content or None if extraction fails
        """
        # Check if response contains markdown code blocks
        if "```json" in response_text:
            # Extract content between ```json and ```
            start_marker = "```json"
            end_marker = "```"
            
            start_index = response_text.find(start_marker)
            if start_index != -1:
                start_index += len(start_marker)
                end_index = response_text.find(end_marker, start_index)
                if end_index != -1:
                    json_content = response_text[start_index:end_index].strip()
                    logger.debug("Extracted JSON from markdown code block", json_length=len(json_content))
                    return json_content
        
        # If no markdown code blocks, try to find JSON-like content
        # Look for content between { and }
        start_brace = response_text.find('{')
        if start_brace != -1:
            # Find the matching closing brace
            brace_count = 0
            end_brace = start_brace
            for i, char in enumerate(response_text[start_brace:]):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_brace = start_brace + i
                        break
            
            if end_brace > start_brace:
                json_content = response_text[start_brace:end_brace + 1]
                logger.info("Extracted JSON from response text", json_length=len(json_content))
                return json_content
        
        # Return None if no valid JSON structure found
        logger.warning("No valid JSON structure found in response")
        return None
    
    def _create_fallback_analysis(self, 
                                response_text: str,
                                traffic_snapshot: TrafficSnapshot,
                                weather_data: Optional[WeatherData]) -> VLMAnalysisData:
        """
        Create fallback analysis when JSON parsing fails.
        
        Args:
            response_text: Raw VLM response
            traffic_snapshot: Traffic data
            weather_data: Weather data
            
        Returns:
            Basic VLMAnalysisData with extracted information
        """
        try:
            # Create basic alert
            alerts = []
            weather_impact = False
            
            # Basic traffic analysis from data
            high_density_threshold = self.config_service.get_high_density_threshold()
            
            # Use high traffic statement only if total count exceeds threshold
            if traffic_snapshot.total_count > high_density_threshold:
                traffic_summary = f"High traffic detected with total {traffic_snapshot.total_count} vehicles at the Intersection"
                alert = VLMAlert(
                        alert_type=AlertType.CONGESTION,
                        level=AlertLevel.WARNING if traffic_snapshot.total_count > high_density_threshold * 1.5 else AlertLevel.INFO,
                        description=f"High traffic detected at the Intersection" if traffic_snapshot.total_count > high_density_threshold * 1.5 else f"Normal Traffic at the Intersection",
                        weather_related=weather_impact
                    )
                alerts.append(alert)
            else:
                traffic_summary = f"Traffic conditions monitored with {traffic_snapshot.total_count} vehicles at the Intersection"
            
            # Weather alert
            try:
                if weather_data:
                    weather_impact = True
                    
                    # Handle both WeatherType enum and string (defensive programming)
                    weather_type = weather_data.weather_type
                    if isinstance(weather_type, str):
                        weather_type = WeatherType(weather_type)
                    
                    CRITICAL_WEATHER = {WeatherType.FIRES, WeatherType.STORM, WeatherType.FLOOD}
                    alert_level = AlertLevel.CRITICAL if weather_type in CRITICAL_WEATHER else AlertLevel.WARNING
                    
                    alert = VLMAlert(
                        alert_type=AlertType.WEATHER_RELATED,
                        level=alert_level,
                        description=self.weather_service.get_current_weather_description(weather_type),
                        weather_related=weather_impact
                    )
                    alerts.append(alert)
            except Exception as e:
                logger.warning("Failed to create weather alert in fallback analysis", error=str(e))
            
            fallback_data = VLMAnalysisData(
                traffic_summary=traffic_summary,
                alerts=alerts,
                recommendations=["Monitor traffic flow", "Consider traffic signal optimization"],
                analysis_timestamp=datetime.utcnow()
            )
            
            logger.info("Fallback analysis created successfully", 
                       summary=traffic_summary,
                       alerts_count=len(alerts),
                       alert_types=[alert.alert_type.value for alert in alerts])
            
            return fallback_data
            
        except Exception as e:
            logger.error("Critical error in fallback analysis, returning minimal analysis", error=str(e))
            # Return absolute minimum fallback in case of complete failure
            return VLMAnalysisData(
                traffic_summary=f"Traffic analysis unavailable. Total vehicles: {traffic_snapshot.total_count}",
                alerts=[VLMAlert(
                    alert_type=AlertType.NORMAL,
                    level=AlertLevel.INFO,
                    description="Traffic monitoring active",
                    weather_related=False
                )],
                recommendations=["Monitor traffic conditions"],
                analysis_timestamp=datetime.utcnow()
            )
    
    
    def clear_cache(self) -> None:
        """Clear all cached analyses."""
        self._analysis_cache.clear()
        logger.info("VLM analysis cache cleared")
    
    def get_service_status(self) -> Dict[str, Any]:
        """
        Get current VLM service status including semaphore state and cached analysis info.
        
        Returns:
            Dictionary with service status information
        """
        return {
            "is_busy": self._vlm_semaphore.locked(),
            "has_cached_analysis": self._last_analysis is not None,
            "last_analysis_timestamp": self._last_analysis_timestamp.isoformat() if self._last_analysis_timestamp else None,
            "cached_analysis_age_minutes": (datetime.utcnow() - self._last_analysis_timestamp).total_seconds() / 60 
                                         if self._last_analysis_timestamp else None,
            "analysis_cache_size": len(self._analysis_cache)
        }
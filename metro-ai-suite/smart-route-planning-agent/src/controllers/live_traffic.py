# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
from typing import Optional, List
import asyncio

import websockets
from websockets.exceptions import WebSocketException

from config import (
    IncidentStatus,
    WeatherStatus,
)
from controllers.route_interface import RouteStatusInterface
from schema import GeoCoordinates, LiveTrafficData
from utils.logging_config import get_logger
from utils.helper import read_config_json

logger = get_logger(__name__)


class LiveTrafficController(RouteStatusInterface):
    """
    Controller for handling live traffic data from an external API.
    """

    def __init__(
        self, latitude: Optional[float] = None, longitude: Optional[float] = None
    ):
        self._latitude = latitude
        self._longitude = longitude

    @property
    def latitude(self) -> Optional[float]:
        return self._latitude

    @property
    def longitude(self) -> Optional[float]:
        return self._longitude

    @property
    def proximity_factor(self) -> float:
        """
        A float integer to help consider nearby latitude and longitudes as matching location coordinates.
        Uses the configured COORDINATE_MATCHING_PRECISION value.
        """
        return 0.0  # Exact Match

    async def _handle_response_data(self, raw_data: dict) -> Optional[LiveTrafficData]:
        """Handles the raw data received from the WebSocket and extracts relevant traffic information."""

        # Check if intersection data is present
        intersection_data = raw_data.get("data", {})
        if not intersection_data:
            return None

        # Get the intersection's coordinates and other details
        logger.info(
            f"Processing intersection data: {intersection_data.get('intersection_name', 'Unknown')}"
        )
        intersection_lat = intersection_data.get("latitude")
        intersection_lon = intersection_data.get("longitude")
        intersection_name = intersection_data.get(
            "intersection_name", "Unknown Intersection"
        )
        intersection_data_timestamp = intersection_data.get("timestamp", "")
        traffic_density = intersection_data.get("total_density", 0)

        # Get weather and incident status if available
        weather_status = raw_data.get("weather_data", {}).get(
            "short_forecast", WeatherStatus.CLEAR
        )
        incident_status = raw_data.get("incident", {}).get(
            "incident_type", IncidentStatus.CLEAR
        )

        return LiveTrafficData(
            location_coordinates=GeoCoordinates(
                latitude=intersection_lat,
                longitude=intersection_lon,
            ),
            intersection_name=intersection_name,
            timestamp=intersection_data_timestamp,
            traffic_density=traffic_density,
            weather_status=WeatherStatus(weather_status),
            incident_status=IncidentStatus(incident_status),
        )

    async def _plug_to_websocket(self, url: str) -> Optional[LiveTrafficData]:
        logger.debug(f"Connecting to WebSocket: {url}")

        # TODO: Implement fully persistent connection supporting receiving push notifications from the API.
        # NOTE: Because of several limitations - This is not being run as a persistent connection and has to be re-established
        # every time we want to fetch live traffic data. This is because, due to legacy design and multiple layers of abstraction,
        # yielding data from multiple connections and then merging it (as the current design expects) would require significant changes
        # in the current architecture of the agent. This is still not polling the API in the traditional sense, as we are still using WebSockets
        # to fetch data in real-time, an outer loop handles the re-connection logic and fetches data at regular intervals w/o blocking.

        try:
            async with websockets.connect(url) as websocket:
                async for message in websocket:
                    logger.debug(f"Received message from WebSocket: {message}")
                    raw_data: dict = json.loads(message)
                    return await self._handle_response_data(raw_data)

            return None

        except WebSocketException as e:
            logger.error(f"WebSocket connection error: {e}")
            return None
        except ConnectionRefusedError as e:
            logger.error(f"WebSocket connection refused: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from WebSocket {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error connecting to WebSocket {url}: {e}")
            return None

    async def fetch_route_status(self) -> List[LiveTrafficData]:
        """
        Fetch the live traffic data from the Traffic Intersection API.

        Returns:
            list[LiveTrafficData]: List of traffic data for all intersections.
        """
        try:
            logger.info("Fetching live traffic data ...")
            # Construct the API URL

            config = await asyncio.to_thread(read_config_json)
            api_endpoint = config.get("api_endpoint")
            if not api_endpoint:
                raise ValueError("API endpoint not found in configuration.")

            # Collect all WebSocket URLs from the configuration
            websocket_urls: list[str] = []
            for api_host in config.get("api_hosts", []):
                host = api_host.get("host")
                if host:
                    websocket_urls.append("".join([host, api_endpoint]))
                else:
                    logger.warning(f"API host entry missing 'host' key: {api_host}")

            websocket_tasks = [
                asyncio.create_task(self._plug_to_websocket(url))
                for url in websocket_urls
            ]

            gathered_response_from_websocket: List[
                Optional[LiveTrafficData]
            ] = await asyncio.gather(*websocket_tasks)

            # remove None values from the results
            live_traffic_intersection_records: List[LiveTrafficData] = [
                record
                for record in gathered_response_from_websocket
                if record is not None
            ]
            return live_traffic_intersection_records

        except Exception as e:
            logger.error(f"Error fetching live traffic data: {e}")
            return []

# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from pydantic import BaseModel, Field, computed_field
from typing_extensions import Annotated

from config import (
    CongestionLevel,
    HAZARDOUS_WEATHER,
    IncidentStatus,
    SEVERE_INCIDENTS,
    WeatherStatus,
)


class QueueItem(BaseModel):
    """Pydantic model for items passed in the data queue between agent and UI"""

    timestamp: float
    agent_status: str
    thinking_output: str
    map_output: str
    intersection_images: Optional[str] = None


class GeoCoordinates(BaseModel):
    """Pydantic model for location information"""

    latitude: Annotated[float, Field(description="Latitude of the location")]
    longitude: Annotated[float, Field(description="Longitude of the location")]


class RouteCondition(BaseModel):
    """Pydantic model for route condition information"""

    location_coordinates: GeoCoordinates


class TrafficTrendsData(RouteCondition):
    """Pydantic model for historical traffic trends information"""

    vehicle_count: Annotated[
        int, Field(description="Number of vehicles observed historically in the area")
    ]
    avg_speed: Annotated[
        int, Field(description="Average movement speed of vehicles in the area")
    ]
    congestion_level: Annotated[
        CongestionLevel, Field(description="Current congestion level at the location")
    ]


class WeatherData(RouteCondition):
    """Pydantic model for weather information along a route"""

    weather_condition: Annotated[
        WeatherStatus, Field(description="Current weather condition at the location")
    ]
    temperature: Annotated[
        float, Field(description="Current temperature at the location in Fahrenheit")
    ]
    visibility: Annotated[
        float, Field(description="Current visibility at the location in miles")
    ]


class PlannedEventsData(RouteCondition):
    """Pydantic model for planned events information along a route"""

    event_name: Annotated[
        str, Field(description="Name of the planned event affecting the route")
    ]
    congestion_level: Annotated[
        CongestionLevel, Field(description="Current congestion level at the location")
    ]


class LiveTrafficData(RouteCondition):
    """Pydantic model for live traffic data from an external API"""

    intersection_name: Annotated[
        str,
        Field(description="Name of the intersection where traffic is being monitored"),
    ]
    timestamp: Annotated[
        str, Field(description="Time when the traffic data was recorded")
    ]
    traffic_density: Annotated[
        int, Field(description="Number of vehicles at the intersection")
    ]
    traffic_description: Annotated[
        Optional[str], Field(description="Description of the traffic situation")
    ] = None
    weather_status: Annotated[
        Optional[WeatherStatus],
        Field(description="Current weather status at the location"),
    ] = None
    incident_status: Annotated[
        Optional[IncidentStatus],
        Field(description="Current incident status at the location"),
    ] = None


class RoutePoints(BaseModel):
    """Pydantic model for route coordinates"""

    main_route: List[List[float]]
    alternative_route: Optional[List[List[float]]] = None

    def get_all_points(self) -> List[List[float]]:
        """Get all route points for bounds calculation"""
        all_points = self.main_route.copy()
        if self.alternative_route:
            all_points.extend(self.alternative_route)
        return all_points


class IntersectionCondition(BaseModel):
    """A single live observation on a candidate route, as presented to the reasoning model."""

    intersection_name: Annotated[
        str, Field(description="Name of the monitored intersection")
    ]
    traffic_density: Annotated[
        int, Field(description="Number of vehicles observed at the intersection")
    ]
    weather_status: Annotated[
        str, Field(description="Weather condition observed at the intersection")
    ]
    incident_status: Annotated[
        str, Field(description="Incident reported at the intersection")
    ]


class RouteCandidate(BaseModel):
    """A selectable GPX route along with every live condition observed on it."""

    route_name: Annotated[str, Field(description="GPX file name identifying the route")]
    distance_km: Annotated[float, Field(description="Total route distance in km")]
    # Routes without live data must never be recommended, as we have no observation to justify them.
    has_live_data: Annotated[
        bool,
        Field(
            description="True when at least one monitored intersection lies on this route"
        ),
    ]
    conditions: Annotated[
        List[IntersectionCondition],
        Field(description="Live conditions observed along this route"),
    ] = []

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_severe_incident(self) -> bool:
        severe = {incident.value for incident in SEVERE_INCIDENTS}
        return any(condition.incident_status in severe for condition in self.conditions)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_hazardous_weather(self) -> bool:
        hazardous = {weather.value for weather in HAZARDOUS_WEATHER}
        return any(
            condition.weather_status in hazardous for condition in self.conditions
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def max_traffic_density(self) -> int:
        return max(
            (condition.traffic_density for condition in self.conditions), default=0
        )


class ReasoningDecision(BaseModel):
    """Route selection returned by the reasoning model, before validation against candidates."""

    selected_route: Annotated[
        str, Field(description="GPX file name of the route chosen by the model")
    ]
    is_sub_optimal: Annotated[
        bool,
        Field(
            default=False,
            description=(
                "True when the selected route still breaches a priority rule. Derived in code "
                "from the selected route's own conditions, not taken from the model."
            ),
        ),
    ]
    reason: Annotated[
        str, Field(description="Short justification naming the deciding condition")
    ]

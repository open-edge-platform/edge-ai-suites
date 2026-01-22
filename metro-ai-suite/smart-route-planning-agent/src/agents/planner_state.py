from operator import add
from typing import Annotated, List, TypedDict

from config import CongestionLevel, StaticOptimizerName, WeatherStatus
from schema import GeoCoordinates, LiveTrafficData

"""
States used in route planning by LangGraph based agent
"""


class RouteState(TypedDict):
    route_name: str  # Name of the route file
    distance: float  # Total distance covered by the route


class OptimalRouteState(RouteState):
    traffic_history: CongestionLevel
    weather_status: WeatherStatus
    event_name: str


class LiveTrafficState(RouteState):
    intersection_name: str  # Name of the intersection where traffic is being reported
    timestamp: str  # Time of recording the live traffic data
    location_coordinates: GeoCoordinates  # Latitude and Longitude for the traffic
    traffic_density: int  # Num of vehicles at the location
    traffic_description: str  # Description of the traffic situation
    intersection_images: dict[
        str, str
    ]  # Base64 encoded images from the intersection's cameras


class RoutePlannerState(TypedDict):
    source: str
    destination: str
    no_fly_list: Annotated[
        list[str], add
    ]  # List of roads not to be taken (Analysed and found to be non-optimal)
    direct_route: RouteState  # Stores details of direct least distance route
    optimal_route: OptimalRouteState  # Stores details of route updated using several route optimizers
    static_optimizers: list[
        StaticOptimizerName
    ]  # List of Route optimizers to be applied
    live_traffic: LiveTrafficState  # Details of live traffic recieved during real-time route optimization
    is_sub_optimal: bool  # Flag to indicate if the optimal route is sub-optimal
    is_unique_route: bool  # Flag to indicate if only one unique route exists
    blocked_routes: List[
        str
    ]  # List of routes blocked due to correct game moves by user based on actual route issues in the route
    blocked_routes_invalid: List[
        str
    ]  # List of routes blocked due to incorrect game moves by user i.e., setting an incorrect weather or incident in route
    all_routes_data: List[
        LiveTrafficData
    ]  # Complete list of LiveTrafficData for all Routes

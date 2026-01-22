from config import StaticOptimizerName as route_optimizer

from .planned_events import PlannedEventsController
from .traffic_trends import TrafficTrendsController
from .weather_report import WeatherReportController

"""
StaticRouteOptimizerFactory maps route optimizer names to their respective controller classes.
"""
StaticRouteOptimizerFactory = {
    route_optimizer.TRAFFIC: TrafficTrendsController,
    route_optimizer.WEATHER: WeatherReportController,
    route_optimizer.PLANNED_EVENTS: PlannedEventsController,
}

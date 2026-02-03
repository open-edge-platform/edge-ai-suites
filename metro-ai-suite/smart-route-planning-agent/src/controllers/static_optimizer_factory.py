# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import Callable

from config import StaticOptimizerName as route_optimizer

from .planned_events import PlannedEventsController
from .route_interface import RouteStatusInterface
from .traffic_trends import TrafficTrendsController
from .weather_report import WeatherReportController

"""
StaticRouteOptimizerFactory maps route optimizer names to their respective controller classes.
"""

# Type alias for a callable that creates a RouteStatusInterface instance
RouteOptimizerConstructor = Callable[[float, float], RouteStatusInterface]


class StaticRouteOptimizerFactory:
    """A factory class to get static route optimizer controller classes based on optimizer names."""

    _factory: dict[route_optimizer, RouteOptimizerConstructor] = {
        route_optimizer.TRAFFIC: TrafficTrendsController,
        route_optimizer.WEATHER: WeatherReportController,
        route_optimizer.PLANNED_EVENTS: PlannedEventsController,
    }

    @classmethod
    def get_optimizer_class(
        cls, optimizer_name: route_optimizer
    ) -> RouteOptimizerConstructor:
        """Get the optimizer constructor for the given optimizer name.

        Args:
            optimizer_name: The name of the optimizer to get.

        Returns:
            A callable that creates a RouteStatusInterface instance when called with (lat, lon).

        Raises:
            ValueError: If no controller is found for the given optimizer name.
        """
        concrete_class = cls._factory.get(optimizer_name)
        if concrete_class is None:
            raise ValueError(f"No controller found for optimizer: {optimizer_name}")
        return concrete_class

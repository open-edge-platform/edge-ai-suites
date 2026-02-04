# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

from typing import List, Optional

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents import RoutePlannerState as State
from agents.planner_state import LiveTrafficState, OptimalRouteState, RouteState
from config import (
    ADVERSE_WEATHER_CONDITIONS,
    GPX_DIR,
    IGNORED_ROUTES,
    CongestionLevel,
    PlannerNode,
    StaticOptimizerName,
)
from controllers import (
    LiveTrafficController,
    StaticRouteOptimizerFactory,
    ThresholdController,
)
from schema import LiveTrafficData, RouteCondition
from utils.gpx_parser import MapDataParser
from utils.helper import get_all_available_route_files as route_files
from utils.logging_config import get_logger

logger = get_logger(__name__)


class RoutePlanner:
    """
    Route Planning Agent - Helps to find direct and optimal routes based on various data sources. Also updates route
    based on Real Time traffic.
    """

    MAX_TRAFFIC_STATUS_BUFFER: int = 5

    def __init__(self):
        self.graph = StateGraph(State)
        self.all_routes: list[str] = route_files()

        # Construct all required nodes and edges and compile the graph
        self.compiled_graph = self._build_graph()

        self.live_traffic_status_list: list[LiveTrafficState] = []

    def _find_new_shortest_available_route(
        self, source: str, destination: str, no_fly_list: list[str]
    ) -> tuple[str, float]:
        """
        Finds the shortest available route between the source and destination waypoints,
        excluding any routes in the no-fly list i.e. already rejected routes.
        """

        shortest_distance: float = 0.0
        shortest_route: str = ""

        # Iterate over all available route files not present in no_fly_list
        for route_file in list(set(self.all_routes) - set(no_fly_list or [])):
            # Parse GPX file for current route
            temp_parser = MapDataParser(GPX_DIR / route_file)
            waypoints = temp_parser.get_waypoints()

            # Get source and destination waypoints
            source_wpt = waypoints[0] if waypoints else None
            destination_wpt = waypoints[-1] if waypoints else None

            # Check if waypoints match the source and destination in graph state
            if source_wpt and destination_wpt:
                if (
                    source_wpt["name"] == source or source_wpt["description"] == source
                ) and (
                    destination_wpt["name"] == destination
                    or destination_wpt["description"] == destination
                ):
                    # Get the route with shortest distance for given source and destination
                    route_distance = temp_parser.get_total_distance()
                    if route_distance < shortest_distance or shortest_distance == 0.0:
                        shortest_distance = route_distance
                        shortest_route = route_file

        return shortest_route, shortest_distance

    def find_direct_route(self, state: State) -> State:
        """Finds the direct route based on the available routes and provided source/destination."""

        logger.info("Finding direct shortest route ...")
        logger.debug(f"============= State of the state : {state} =============")
        shortest_route, shortest_distance = self._find_new_shortest_available_route(
            state.get("source", ""),
            state.get("destination", ""),
            state.get("no_fly_list", IGNORED_ROUTES),
        )

        # Update the direct_route dict with required information
        direct_route_state: RouteState = {
            "route_name": shortest_route,
            "distance": shortest_distance,
        }
        # For optimal_route, use OptimalRouteState (which extends RouteState)
        initial_optimal_route: OptimalRouteState = {
            "route_name": shortest_route,
            "distance": shortest_distance,
        }
        logger.debug(f"Direct Route: {direct_route_state}")

        return {
            "direct_route": direct_route_state,
            "optimal_route": initial_optimal_route,  # Initially, optimal route is same as direct route
            # "static_optimizers": STATIC_ROUTE_OPTIMIZER_STACK, Disabled static optimizers for now
            "no_fly_list": [*IGNORED_ROUTES],
        }

    def find_optimal_route(self, state: State) -> State:
        """
        Finds the optimal route based on the available route status and information.
        #TODO Uses Brute Force Search - Need to be Improved.
        """
        logger.info("Finding optimal routes based on static data ...")
        route_status: RouteCondition | None = None

        static_optimizers = state.get("static_optimizers")
        if static_optimizers:
            optimizer_name: StaticOptimizerName = static_optimizers.pop()
            # Get the controller constructor from factory
            route_optimizer_constructor = (
                StaticRouteOptimizerFactory.get_optimizer_class(optimizer_name)
            )
        else:
            logger.error(
                "Optimal route node invoked when no static optimizers are available!"
            )
            return state

        current_optimal_route = state.get("optimal_route", {})
        optimal_route_name: str = current_optimal_route.get("route_name", "")
        optimal_distance: float = current_optimal_route.get("distance", 0.0)

        if not optimal_route_name:
            logger.error("No optimal route name found in state")
            return state

        # Initialize optimal_route_state with current values
        optimal_route_state: OptimalRouteState = {
            "route_name": optimal_route_name,
            "distance": optimal_distance,
        }

        temp_parser = MapDataParser(GPX_DIR / optimal_route_name)
        route_data = temp_parser.get_route_data()

        for track in route_data["tracks"]:
            for track_point in track["track_points"]:
                # Instantiate the controller and call fetch_route_status
                controller_instance = route_optimizer_constructor(
                    track_point["lat"], track_point["lon"]
                )
                fetched_status = controller_instance.fetch_route_status()
                # Handle different return types from fetch_route_status
                if isinstance(fetched_status, list):
                    route_status = fetched_status[0] if fetched_status else None
                else:
                    route_status = fetched_status
                if route_status:
                    # check if route_status has a required attributes and proceed accordingly
                    if hasattr(route_status, "weather_condition"):
                        if route_status.weather_condition in ADVERSE_WEATHER_CONDITIONS:
                            optimal_route_name, optimal_distance = (
                                self._find_new_shortest_available_route(
                                    state.get("source", ""),
                                    state.get("destination", ""),
                                    state.get("no_fly_list", []),
                                )
                            )
                            optimal_route_state = {
                                "route_name": optimal_route_name,
                                "distance": optimal_distance,
                                "weather_status": route_status.weather_condition,
                            }
                            break
                    elif hasattr(route_status, "congestion_level"):
                        if route_status.congestion_level in [
                            CongestionLevel.HIGH,
                            CongestionLevel.SEVERE,
                        ]:
                            optimal_route_name, optimal_distance = (
                                self._find_new_shortest_available_route(
                                    state.get("source", ""),
                                    state.get("destination", ""),
                                    state.get("no_fly_list", []),
                                )
                            )
                            optimal_route_state = {
                                "route_name": optimal_route_name,
                                "distance": optimal_distance,
                                "traffic_history": route_status.congestion_level,
                            }
                            if hasattr(route_status, "event_name"):
                                optimal_route_state["event_name"] = (
                                    route_status.event_name
                                )
                            break

        return {
            "optimal_route": optimal_route_state,
            "no_fly_list": [optimal_route_name] if optimal_route_name else [],
        }

    def update_optimal_route_realtime(self, state: State) -> State:
        """Updates the optimal route in real-time based on live traffic data."""

        logger.info(
            "Fetching real-time traffic updates and optimizing route accordingly..."
        )

        # Get all routes from existing no_fly_list state.
        # IMPORTANT: A copy is required as get returns a reference to the list in state dictionary.
        # If we modify local_fly_list directly, it will modify the state itself, which is not desired.
        local_no_fly_list = state.get("no_fly_list", []).copy()

        # Default values for graph state to be returned if no traffic issues or new optimal routes are found
        current_optimal = state.get("optimal_route", {})
        optimal_route_state: OptimalRouteState = {
            "route_name": current_optimal.get("route_name", ""),
            "distance": current_optimal.get("distance", 0.0),
        }
        live_traffic_state: LiveTrafficState = {
            "route_name": "",
            "distance": 0.0,
        }

        # If none of the routes are optimal, we store sub-optimal route here.
        sub_optimal_route: OptimalRouteState | None = None
        sub_optimal_density: int = 0

        # fetch the available live traffic data
        live_traffic_controller = LiveTrafficController()
        all_routes_data: List[LiveTrafficData] = (
            live_traffic_controller.fetch_route_status()
        )

        # Iterate till no new routes are available
        while True:
            route_not_optimal: bool = False
            logger.debug(f"Roads not to be taken : {local_no_fly_list}")

            # Get next available shortest route
            next_shortest_route_name, next_shortest_distance = (
                self._find_new_shortest_available_route(
                    state.get("source", ""),
                    state.get("destination", ""),
                    local_no_fly_list,
                )
            )

            if not next_shortest_route_name or not next_shortest_distance:
                logger.info("No more alternate routes available.")
                break

            # Parse the next available shortest route
            map_parser = MapDataParser(GPX_DIR / next_shortest_route_name)
            route_data = map_parser.get_route_data()

            # Get the waypoints and first track and collect all trackpoints for the track
            trackpoints = route_data.get("waypoints", [])
            trackpoints.extend(
                route_data.get("tracks", [{}])[0].get("track_points", [])
            )

            logger.debug(f"Analyzing route: {next_shortest_route_name}")
            for i, trackpoint in enumerate(trackpoints):
                # If route has been found not to be optimal break out of loop
                if route_not_optimal:
                    break

                # Iterate over all routes/intersection found by live traffic controller and proceed with only those which
                # match the lats and longs of current trackpoint
                for traffic_status in all_routes_data:
                    if (
                        abs(
                            traffic_status.location_coordinates.latitude
                            - trackpoint["lat"]
                        )
                        <= live_traffic_controller.proximity_factor
                        and abs(
                            traffic_status.location_coordinates.longitude
                            - trackpoint["lon"]
                        )
                        <= live_traffic_controller.proximity_factor
                    ):
                        if (
                            traffic_status.traffic_density
                            > ThresholdController.TRAFFIC_DENSITY_THRESHOLD
                        ):
                            # If traffic is above threshold, stop looking for more trackpoints in current route
                            logger.info(
                                f"High traffic density ({traffic_status.traffic_density}) in {next_shortest_route_name}. Finding next shortest route..."
                            )
                            route_not_optimal = True

                            # Every route having density greater than threshold and is a "potential" sub-optimal route.
                            if (
                                not sub_optimal_route
                                or sub_optimal_density > traffic_status.traffic_density
                            ):
                                sub_optimal_route = {
                                    "route_name": next_shortest_route_name,
                                    "distance": next_shortest_distance,
                                }
                                sub_optimal_density = traffic_status.traffic_density
                                logger.info(
                                    f"Sub-optimal route updated to {sub_optimal_route} with traffic density {sub_optimal_density}"
                                )

                            # Update the live traffic data to provide details of traffic situation and intersection images
                            live_traffic_state = {
                                "route_name": next_shortest_route_name,
                                "distance": next_shortest_distance,
                                "intersection_name": traffic_status.intersection_name,
                                "timestamp": traffic_status.timestamp,
                                "location_coordinates": traffic_status.location_coordinates,
                                "traffic_density": traffic_status.traffic_density,
                            }

                            # Maintain a buffer of recent live traffic status updates
                            if (
                                len(self.live_traffic_status_list)
                                >= self.MAX_TRAFFIC_STATUS_BUFFER
                            ):
                                self.live_traffic_status_list.pop(0)

                            self.live_traffic_status_list.append(live_traffic_state)
                            logger.debug(
                                f"length of live_traffic_status_list: {len(self.live_traffic_status_list)}"
                            )
                            break

            if i == len(trackpoints) - 1 and not route_not_optimal:
                # If we reached the last trackpoint without finding high traffic, consider route to be optimal
                logger.info(f"Route {next_shortest_route_name} is optimal.")

                # Potential (Sub-Optimal Route) Wasted. Go for the best route, when you have it. Get rid of the second best.
                sub_optimal_route = None

                # Update the optimal_route_state for the graph state
                optimal_route_state = {
                    "route_name": next_shortest_route_name,
                    "distance": next_shortest_distance,
                }
                break
            else:
                logger.debug("Finding next shortest route")
                # Add current route to local no_fly_list and try next shortest route if any
                local_no_fly_list.append(next_shortest_route_name)

        # If live traffic status (the issues in traffic) is for same route as that of sub_optimal_route, then pick the live
        # traffic status of previous route. (Makes sure, the intersection marked red is never present in the current route selected)
        if (
            sub_optimal_route
            and self.live_traffic_status_list
            and sub_optimal_route.get("route_name")
            == live_traffic_state.get("route_name")
        ):
            logger.info(
                "Picking previous live traffic status as current optimal route is sub-optimal"
            )
            # Picks second last entry from list if num of entries > 1 else picks the only entry available.
            prev_traffic = self.live_traffic_status_list[
                len(self.live_traffic_status_list) - 2
            ]
            # Update live_traffic_state with previous traffic data
            prev_location = prev_traffic.get("location_coordinates")
            live_traffic_state = {
                "route_name": prev_traffic.get("route_name", ""),
                "distance": prev_traffic.get("distance", 0.0),
                "intersection_name": prev_traffic.get("intersection_name", ""),
                "timestamp": prev_traffic.get("timestamp", ""),
                "traffic_density": prev_traffic.get("traffic_density", 0),
            }
            # Only add location_coordinates if it exists
            if prev_location is not None:
                live_traffic_state["location_coordinates"] = prev_location

        return {
            "optimal_route": sub_optimal_route
            if sub_optimal_route
            else optimal_route_state,
            "live_traffic": live_traffic_state,
            "is_sub_optimal": bool(sub_optimal_route),
            "all_routes_data": all_routes_data,
        }

    def _should_rerun_static_route_optimizers(self, state: State) -> bool:
        """Re-run static route optimizers until optimizer stack is empty"""
        return len(state.get("static_optimizers", [])) > 0

    def _route_optimizers_selector(self, state: State) -> str:
        """
        Decide which optimizer node should be run first
        """
        # If direct route is not found, we need to find it first.
        if not state.get("direct_route"):
            return PlannerNode.DIRECT.value
        # if static optimizers are available, run static optimization node
        elif state.get("static_optimizers", []):
            return PlannerNode.OPTIMAL.value
        # Otherwise run realtime route optimization node
        else:
            return PlannerNode.REALTIME.value

    def _build_graph(self) -> CompiledStateGraph:
        """Builds the state graph using different nodes and edges."""

        # Added all three tools as nodes in Graph
        self.graph.add_node(PlannerNode.DIRECT.value, self.find_direct_route)
        self.graph.add_node(PlannerNode.OPTIMAL.value, self.find_optimal_route)
        self.graph.add_node(
            PlannerNode.REALTIME.value, self.update_optimal_route_realtime
        )

        # Add conditional edges from START node to each of the three nodes, based on _route_optimizers_selector response.
        self.graph.add_conditional_edges(START, self._route_optimizers_selector)

        # Add final edges from all three nodes to END node
        self.graph.add_edge(PlannerNode.DIRECT.value, END)
        # Add conditional edge between optimal_route and END node, as we need to re-run this node until
        # the static route optimizer stack exhausts.
        self.graph.add_conditional_edges(
            PlannerNode.OPTIMAL.value,
            self._should_rerun_static_route_optimizers,
            {PlannerNode.OPTIMAL.value, END},
        )
        self.graph.add_edge(PlannerNode.REALTIME.value, END)

        # Compile the graph to be able to execute it
        return self.graph.compile()

    def plan_route(
        self, source: str, destination: str, previous_state: Optional[State] = None
    ) -> State:
        """
        Plans a route from the source to the destination using most optimal path.

        Args:
            source (str): The starting point of the route.
            destination (str): The endpoint of the route.
            previous_state (Optional[State]): Previous route state for continuing optimization

        Returns:
            State: The planned route as a state object.
        """

        logger.info(f"Planning route from {source} to {destination}")

        current_state: State = {"source": source, "destination": destination}

        if previous_state:
            current_state = {**current_state, **previous_state}

        # Execute the graph to find the best route
        route_detail = self.compiled_graph.invoke(current_state)

        return route_detail

from pathlib import Path
from typing import List, Optional

from langgraph.graph import END, START, StateGraph

from agents import RoutePlannerState as State
from config import (
    ADVERSE_WEATHER_CONDITIONS,
    GPX_DIR,
    IGNORED_ROUTES,
    WEATHER_ISSUE_MAP,
    INCIDENT_ISSUE_MAP,
    CongestionLevel,
    IncidentStatus,
    PlannerNode,
    StaticOptimizerName,
    WeatherStatus,
)
from controllers import (
    LiveTrafficController,
    StaticRouteOptimizerFactory,
    RouteStatusInterface,
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
        self.all_routes: list[Path] = route_files()

        # Construct all required nodes and edges and compile the graph
        self.graph = self._build_graph()

        self.live_traffic_status_list: list[dict] = []

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
            state["source"],
            state["destination"],
            state.get("no_fly_list", IGNORED_ROUTES),
        )

        # Update the direct_route dict with required information
        direct_route_state = {
            "route_name": shortest_route,
            "distance": shortest_distance,
        }
        logger.debug(f"Direct Route: {direct_route_state}")

        return {
            "direct_route": direct_route_state,
            "optimal_route": direct_route_state,  # Initially, optimal route is same as direct route
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

        if state.get("static_optimizers"):
            optimizer_name: StaticOptimizerName = state.get("static_optimizers").pop()
            route_optimizer: RouteStatusInterface = StaticRouteOptimizerFactory[
                optimizer_name
            ]
        else:
            logger.error(
                "Optimal route node invoked when no static optimizers are available!"
            )
            return state

        current_optimal_route = state.get("optimal_route", {})
        optimal_route_name = current_optimal_route.get("route_name")
        optimal_distance = current_optimal_route.get("distance")

        temp_parser = MapDataParser(GPX_DIR / optimal_route_name)
        route_data = temp_parser.get_route_data()

        for track in route_data["tracks"]:
            for track_point in track["track_points"]:
                route_status = route_optimizer(
                    track_point["lat"], track_point["lon"]
                ).fetch_route_status()
                if route_status:
                    # check if route_status has a required attributes and proceed accordingly
                    if hasattr(route_status, "weather_condition"):
                        if route_status.weather_condition in ADVERSE_WEATHER_CONDITIONS:
                            optimal_route_name, optimal_distance = (
                                self._find_new_shortest_available_route(
                                    state["source"],
                                    state["destination"],
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
                                    state["source"],
                                    state["destination"],
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
            "no_fly_list": [optimal_route_name],
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
        optimal_route_state = state.get("optimal_route", {})
        live_traffic_state = {}

        # If none of the routes are optimal, we store sub-optimal route here.
        sub_optimal_route: dict[str, str] = {}
        sub_optimal_density: int = 0

        # fetch the available live traffic data
        live_traffic_controller = LiveTrafficController()
        all_routes_data: List[LiveTrafficData] = (
            live_traffic_controller.fetch_route_status()
        )

        # Storage for valid blocked routes and invalid blocked routes
        # Invalid blocked routes are those which are blocked due to incorrect game moves by user on intersections along the route
        blocked_routes: list[str] = []
        blocked_routes_invalid: list[str] = []
        # logger.debug(f"Available Intersections: {intersection_list}")

        available_route_count: int = 0
        unique_route: bool = False
        # Iterate till no new routes are available
        while True:
            route_not_optimal: bool = False
            logger.debug(f"Roads not to be taken : {local_no_fly_list}")

            # Get next available shortest route
            next_shortest_route_name, next_shortest_distance = (
                self._find_new_shortest_available_route(
                    state["source"], state["destination"], local_no_fly_list
                )
            )

            if not next_shortest_route_name or not next_shortest_distance:
                total_blocked_routes = len(blocked_routes) + len(blocked_routes_invalid)
                if available_route_count - total_blocked_routes == 1:
                    unique_route = True
                    live_traffic_state = {}
                logger.info("No more alternate routes available.")
                break

            available_route_count += 1

            # Parse the next available shortest route
            map_parser = MapDataParser(GPX_DIR / next_shortest_route_name)
            route_data = map_parser.get_route_data()

            # Get the waypoints and first track and collect all trackpoints for the track
            trackpoints = route_data.get("waypoints", [])
            trackpoints.extend(
                route_data.get("tracks", [{}])[0].get("track_points", [])
            )

            num_intersections_in_route: int = 0
            intersection_blocked_count_valid: int = (
                0  # Intersection blocked due to correct game move by user
            )
            intersection_blocked_count_invalid: int = (
                0  # Intersection blocked due to incorrect game move by user
            )
            logger.debug(f"Analyzing route: {next_shortest_route_name}")
            for i, trackpoint in enumerate(trackpoints):
                # If route has been found not to be optimal break out of loop
                # UPDATE: Disabling for finding all intersections along route irrespective of traffic density
                # if route_not_optimal:
                #     break

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
                        # Count the number of intersections in the current route
                        num_intersections_in_route += 1

                        # Verify if traffic status from Intersection API reflects the actual recorded scenario at the intersection
                        if (
                            WEATHER_ISSUE_MAP.get(next_shortest_route_name)
                            == traffic_status.weather_status
                            or INCIDENT_ISSUE_MAP.get(next_shortest_route_name)
                            == traffic_status.incident_status
                        ):
                            intersection_blocked_count_valid += 1
                        elif (
                            traffic_status.weather_status != WeatherStatus.CLEAR
                            or traffic_status.incident_status != IncidentStatus.CLEAR
                        ):
                            intersection_blocked_count_invalid += 1

                        logger.debug(
                            "Getting blocked routes when intersection is found to be in current route ..."
                        )
                        logger.debug(f"Blocked routes valid : {blocked_routes}")
                        logger.debug(
                            f"Blocked routes invalid : {blocked_routes_invalid}"
                        )

                        # Do not try to update sub_optimal_route or live_traffic_state if route is already blocked
                        if (
                            next_shortest_route_name
                            not in state.get("blocked_routes", [])
                            and next_shortest_route_name
                            not in state.get("blocked_routes_invalid", [])
                            and traffic_status.traffic_density
                            > ThresholdController.TRAFFIC_DENSITY_THRESHOLD
                        ):
                            # If traffic is above threshold, stop looking for more trackpoints in current route
                            logger.info(
                                f"High traffic density ({traffic_status.traffic_density}) in {next_shortest_route_name}. Finding next shortest route..."
                            )
                            route_not_optimal = True

                            # Every route having density greater than threshold and  is a "potential" sub-optimal route.
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

            if (
                0
                < intersection_blocked_count_valid + intersection_blocked_count_invalid
            ):
                logger.info(
                    f"Some intersections in route {next_shortest_route_name} report issues. Considering route as non-optimal."
                )
                route_not_optimal = True

                # Remove blocked route traffic details from live_traffic_status_list if present
                self.live_traffic_status_list = [
                    t
                    for t in self.live_traffic_status_list
                    if t.get("route_name") != next_shortest_route_name
                ]

                # Discard sub-optimal ad optimal route if it is current route
                if (
                    sub_optimal_route
                    and sub_optimal_route.get("route_name") == next_shortest_route_name
                ):
                    sub_optimal_route = {}

                if (
                    optimal_route_state
                    and optimal_route_state.get("route_name")
                    == next_shortest_route_name
                ):
                    optimal_route_state = {}

                # Keep it in blocked_route_invalid list, as long as at least one intersection is blocked due to incorrect game move by user.
                # If all intersections in route are blocked due to correct game move by user, put it in blocked_routes list.
                # blocked_route_invalid or blocked_route list required to :
                # 1. Color the route yellow or red, respectively on map UI
                # 2. Refrain the agent from taking this route again in current iteration
                if intersection_blocked_count_valid == num_intersections_in_route:
                    blocked_routes.append(next_shortest_route_name)
                    if next_shortest_route_name in blocked_routes_invalid:
                        blocked_routes_invalid.remove(next_shortest_route_name)
                else:
                    blocked_routes_invalid.append(next_shortest_route_name)
                    if next_shortest_route_name in blocked_routes:
                        blocked_routes.remove(next_shortest_route_name)

            else:
                # If in some other iterations different intersection_blocked_count zero out, remove route from blocked states.
                if next_shortest_route_name in blocked_routes:
                    blocked_routes.remove(next_shortest_route_name)
                if next_shortest_route_name in blocked_routes_invalid:
                    blocked_routes_invalid.remove(next_shortest_route_name)

            logger.debug("getting blocked routes when current route analysis done ...")
            logger.debug(f"Blocked routes valid : {blocked_routes}")
            logger.debug(f"Blocked routes invalid : {blocked_routes_invalid}")

            if i == len(trackpoints) - 1 and not route_not_optimal:
                # If we reached the last trackpoint without finding high traffic, consider route to be optimal
                logger.info(f"Route {next_shortest_route_name} is optimal.")

                # Potential (Sub-Optimal Route) Wasted. Go for the best route, when you have it. Get rid of the second best.
                sub_optimal_route = {}

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

        # If live traffic status (the issues in traffic) is for same route as that of sub_optimal_route
        # pick the live traffic status of previous route
        if (
            sub_optimal_route
            and self.live_traffic_status_list
            and sub_optimal_route["route_name"] == live_traffic_state.get("route_name")
        ):
            logger.info(
                "Picking previous live traffic status as current optimal route is sub-optimal"
            )
            # Picks second last entry from list if num of entries > 1 else picks the only entry available.
            live_traffic_state = self.live_traffic_status_list[
                len(self.live_traffic_status_list) - 2
            ]

        return {
            "optimal_route": sub_optimal_route or optimal_route_state,
            "live_traffic": live_traffic_state,
            "is_sub_optimal": bool(sub_optimal_route),
            "blocked_routes": blocked_routes,
            "blocked_routes_invalid": blocked_routes_invalid,
            "is_unique_route": unique_route,
            "all_routes_data": all_routes_data,
        }

    def _should_rerun_static_route_optimizers(self, state: State) -> bool:
        """Re-run static route optimizers until optimizer stack is empty"""
        return len(state["static_optimizers"]) > 0

    def _route_optimizers_selector(self, state: State) -> str:
        """
        Decide which optimizer node should be run first
        """
        # If direct route is not found, we need to find it first.
        if not state.get("direct_route"):
            return PlannerNode.DIRECT.value
        # if static optimizers are available, run static optimization node
        elif state.get("static_optimizers"):
            return PlannerNode.OPTIMAL.value
        # Otherwise run realtime route optimization node
        else:
            return PlannerNode.REALTIME.value

    def _build_graph(self) -> StateGraph:
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

        current_state = {"source": source, "destination": destination}

        if previous_state:
            current_state.update(previous_state)

        # Execute the graph to find the best route
        route_detail = self.graph.invoke(current_state)

        return route_detail

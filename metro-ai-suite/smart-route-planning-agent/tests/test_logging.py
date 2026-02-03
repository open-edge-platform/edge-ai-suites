#!/usr/bin/env python3
"""
Test script to verify logging functionality in the route agent
"""

import logging
import os
import sys

# Add the src directory to the Python path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from src.agents.route_planner import RoutePlanner

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("test_route_app.log"), logging.StreamHandler()],
)


def test_route_agent() -> None:
    """Test the route agent with logging"""
    print("Testing route agent with logging...")

    # Initialize the route planner
    planner = RoutePlanner()

    # Test route planning using the plan_route method
    route_state = planner.plan_route(
        source="Berkeley, California",
        destination="Santa Clara, California",
    )

    print("\n" + "=" * 50)
    print("ROUTE INFO:")
    print(f"Direct Route: {route_state.get('direct_route', {})}")
    print(f"Optimal Route: {route_state.get('optimal_route', {})}")
    print(f"Is Sub-Optimal: {route_state.get('is_sub_optimal', False)}")
    print("=" * 50)


if __name__ == "__main__":
    test_route_agent()

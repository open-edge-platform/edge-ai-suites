# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import json
from typing import List

from config import HAZARDOUS_WEATHER, SEVERE_INCIDENTS
from schema import RouteCandidate

"""
Prompt builders for the reasoning model based route selection.
"""


def build_system_prompt(all_disqualified: bool) -> str:
    """
    Build the system prompt describing the selection task and the exact output requirements.

    When all_disqualified is True, no acceptable route exists
    and the model is asked to pick the least bad one instead.
    """

    # TODO: Add threshold controller as a global config
    from controllers.threshold import ThresholdController

    severe_incidents = ", ".join(incident.value for incident in SEVERE_INCIDENTS)
    hazardous_weather = ", ".join(weather.value for weather in HAZARDOUS_WEATHER)
    threshold = ThresholdController.TRAFFIC_DENSITY_THRESHOLD

    if all_disqualified:
        task = f"""Every candidate route currently breaches a safety rule, so there is no clean
option. Choose the LEAST BAD route, preferring in this order:
  1. No severe incident (severe incidents are: {severe_incidents}).
  2. No hazardous weather (hazardous weather is: {hazardous_weather}).
  3. The lowest max_traffic_density.
  4. If still tied, the smallest distance_km."""
    else:
        task = f"""Every candidate route listed below has already been checked and is free of
severe incidents ({severe_incidents}), free of hazardous weather ({hazardous_weather}), and
below the heavy traffic threshold of {threshold} vehicles.

Choose the best of them, preferring the smallest distance_km, unless a clearly lower
max_traffic_density on a route of similar length makes it the better commute."""

    return f"""You are a route selection expert for a city traffic management system.
You are given a list of candidate routes between one source and one destination. Each route
lists the live conditions observed at monitored intersections along it, plus the summary
fields has_severe_incident, has_hazardous_weather and max_traffic_density.

{task}

The response shape is enforced by the server, so no formatting instructions are needed here.
One rule still matters, because it cannot be enforced structurally:
  - The reason must describe conditions actually present on the route you selected.
    Never claim a route avoids a condition that its own fields report as true.
    Keep it to one or two sentences naming the deciding condition."""


def build_response_format(candidates: List[RouteCandidate]) -> dict:
    """
    Build the OVMS ``response_format`` payload that constrains generation to our answer shape.

    ``enum`` field value is actual enum used to constrain the model to a known route name.
    ``is_sub_optimal`` not required here as it is derived in code from the selected
    route's own conditions.
    """

    return {
        "type": "json_schema",
        "json_schema": {
            "schema": {
                "type": "object",
                "properties": {
                    "selected_route": {
                        "type": "string",
                        "enum": [candidate.route_name for candidate in candidates],
                    },
                    "reason": {"type": "string"},
                },
                "required": ["selected_route", "reason"],
            }
        },
    }


def build_user_prompt(
    source: str, destination: str, candidates: List[RouteCandidate]
) -> str:
    """
    Serialise the candidate routes and their live conditions as JSON for the model to reason over.
    """

    payload = {
        "source": source,
        "destination": destination,
        "candidate_routes": [candidate.model_dump() for candidate in candidates],
    }
    return json.dumps(payload)

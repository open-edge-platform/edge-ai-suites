import json
from pathlib import Path
from typing import Optional

from config import GPX_DIR, CONFIG_FILE
from utils.logging_config import get_logger
from schema import GeoCoordinates, RouteCondition

logger = get_logger(__name__)


def get_all_available_route_files() -> list[Path]:
    """
    Get a list of all available GPX route files in the GPX_DIR.

    Returns:
        list[Path]: List of GPX file paths
    """
    if not GPX_DIR.is_dir():
        logger.error("Error reading GPX Routes Directory")
        return []

    return [
        Path(f).name
        for f in GPX_DIR.iterdir()
        if f.is_file() and str(f).endswith(".gpx")
    ]


def read_config_json(config_path: Optional[Path] = None) -> dict:
    """
    Read a JSON configuration file and return its contents as a dictionary.

    Args:
        config_path (Path): Path to the JSON configuration file.

    Returns:
        dict: Contents of the JSON file as a dictionary.
    """

    config_path = config_path or CONFIG_FILE

    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading config file {config_path}: {e}")
        return {}


def get_intersection_list(
    live_route_status: list[RouteCondition],
) -> dict[str, GeoCoordinates]:
    """Extracts the list of intersection coordinates from live traffic data."""
    intersection_list: dict[str, GeoCoordinates] = {}

    for intersection in live_route_status:
        intersection_list[intersection.intersection_name] = (
            intersection.location_coordinates
        )

    return intersection_list

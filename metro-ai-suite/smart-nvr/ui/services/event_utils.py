# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from ui.config import logger
from typing import List, Dict, Optional, Tuple
import gradio as gr


def format_timestamp(ts):
    try:
        if ts is None:
            return "N/A"
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        logger.error(f"Timestamp formatting error: {e}")
        return "Invalid Timestamp"


def display_events(recent_events) -> List[List]:
    """Format events for display in a table."""
    logger.info(f"Displaying {len(recent_events)} events in table")

    formatted_events = []
    for event in recent_events:
        try:
            top_score = "NA"
            description = "N/A"
            if event.get("data") and "description" in event.get("data", {}):
                top_score = event.get("data", {}).get("top_score", "N/A")
                description = event.get("data", {}).get("description", "N/A")

            # Handle thumbnail data
            thumbnail = event.get("thumbnail", "")
            if thumbnail:
                # Create HTML img tag for base64 thumbnail
                thumbnail_html = f'<img src="data:image/jpeg;base64,{thumbnail}" style="width:80px;height:60px;object-fit:cover;" alt="Event Thumbnail">'
            else:
                thumbnail_html = "No Image"

            formatted_row = [
                str(event.get("label", "N/A")),
                str(format_timestamp(event.get("start_time"))),
                str(format_timestamp(event.get("end_time"))),
                str(top_score),
                str(description),
                thumbnail_html,
            ]

            # Enforce row is a list, not a tuple
            formatted_events.append(list(formatted_row))
        except Exception as e:
            logger.error(f"Error formatting event {event}: {e}")
            continue

    return formatted_events

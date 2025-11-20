# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from service.redis_store import get_rules, store_response
from service.dispatcher import dispatch_action
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


async def process_event(event: dict, context: dict = None):
    """
    Process incoming events against configured rules and dispatch actions for matches.
    
    Args:
        event: Event data containing label, camera, timestamps, and optional count data
        context: Optional context with source information and topic details
    
    Returns:
        None: Actions are dispatched asynchronously for matching rules
    """
    logger.info("Processing Event.")
    if context:
        logger.info(f"Event context: {context}")

    logger.info(f"Detected label: {event.get('label')}")
    rules = await get_rules()
    logger.info(f"Loaded {len(rules)} rules")

    for rule in rules:
        logger.info(f"Evaluating rule: {rule}")
        if rule.get("label") != event.get("label"):
            logger.info("Rule did not match: label mismatch.")
            continue

        if rule.get("camera") and rule["camera"] != event.get("camera"):
            logger.info("Rule did not match: camera mismatch.")
            continue

        rule_source = rule.get("source")
        event_source = (context or {}).get("source") if context else None
        if rule_source and rule_source != event_source:
            logger.info(
                f"Rule did not match: source mismatch (rule={rule_source}, event={event_source})."
            )
            continue

        threshold = rule.get("count")
        if threshold is not None:
            # count based on the event_label
            event_label = event.get("label", "").lower()
            if event_label == "pedestrian":
                event_count = event.get("num_pedestrians")
                count_type = "pedestrian"
            else:
                event_count = event.get("num_vehicles") 
                count_type = "vehicle"
                
            if event_count is None:
                logger.info(
                    f"Rule did not match: {count_type} count missing on event when rule requires it."
                )
                continue
            if event_count < threshold:
                logger.info(
                    f"Rule did not match: {count_type} count {event_count} below threshold {threshold}."
                )
                continue

        logger.info("Match found.")
        event["rule_id"] = rule["id"]
        response = await dispatch_action(rule["action"], event)
        await store_response(rule["id"], response)

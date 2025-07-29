# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
from service.redis_store import get_rules, store_response
from service.dispatcher import dispatch_action
import logging
from fastapi import Request

logger = logging.getLogger(__name__)


async def process_event(event: dict, context: dict = None):
    logger.info(f"📌 Processing Event.")
    if context:
        logger.info(f"📌 Event context: {context}")

    logger.info(f"📌 Detected label: {event.get('label')}")
    rules = await get_rules()
    logger.info(f"📌 Loaded {len(rules)} rules")

    for rule in rules:
        logger.info(f"🔁 Evaluating rule: {rule}")
        if rule["label"] == event.get("label") and (
            not rule.get("camera") or rule["camera"] == event.get("camera")
        ):
            logger.info(f"✅ Match found.")
            event["rule_id"] = rule["id"]
            response = await dispatch_action(rule["action"], event)
            await store_response(rule["id"], response)
        else:
            logger.info("❌ Rule did not match.")

# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
import json
from fastapi import Request
from config import REDIS_HOST, REDIS_PORT
import redis.asyncio as redis

# --- RULE MANAGEMENT ---
# Fallback client for non-FastAPI contexts (like MQTT)
fallback_redis_client = redis.from_url(
    f"redis://{REDIS_HOST}:{REDIS_PORT}", decode_responses=True
)


async def add_rule(request: Request, rule_id: str, rule_data: dict) -> bool:
    """Adds a new rule if it doesn't already exist. Returns True if added, False if exists."""
    redis_client = request.app.state.redis_client
    key = f"rule:{rule_id}"
    if await redis_client.exists(key):
        return False
    await redis_client.set(key, json.dumps(rule_data))
    await redis_client.sadd("rules", rule_id)
    return True


async def store_rule(request: Request, rule_id: str, rule_data: dict):
    """Overwrites an existing rule and adds the rule ID to the 'rules' set."""
    redis_client = request.app.state.redis_client
    await redis_client.set(f"rule:{rule_id}", json.dumps(rule_data))
    await redis_client.sadd("rules", rule_id)


async def get_rule(request: Request, rule_id: str):
    """Gets a rule by its ID. Returns None if not found."""
    redis_client = request.app.state.redis_client
    data = await redis_client.get(f"rule:{rule_id}")
    return json.loads(data) if data else None


async def get_rules(request=None):
    """Fetches all rules from Redis."""
    redis_client = (
        getattr(request.app.state, "redis_client", None)
        if request
        else fallback_redis_client
    )
    rule_ids = await redis_client.smembers("rules")
    rules = []
    for rid in rule_ids:
        data = await redis_client.get(f"rule:{rid}")
        if data:
            rules.append(json.loads(data))
    return rules


import json
from fastapi import Request


async def delete_rule(request: Request, rule_id: str) -> bool:
    """Deletes a rule and all its associated data from Redis, including summaries."""
    redis_client = request.app.state.redis_client

    # Check if rule exists
    exists = await redis_client.exists(f"rule:{rule_id}")
    if not exists:
        return False

    # Delete the rule and its related keys
    await redis_client.delete(f"rule:{rule_id}")
    await redis_client.delete(f"search_results:{rule_id}")
    await redis_client.srem("rules", rule_id)

    # Delete associated summary_result keys from response list
    response_key = f"response:{rule_id}"
    response_entries = await redis_client.lrange(response_key, 0, -1)

    summary_keys_to_delete = []

    for entry in response_entries:
        try:
            item = json.loads(entry)
            summary_id = item.get("summary_id")
            if summary_id:
                summary_keys_to_delete.append(f"summary_ids:{rule_id}")
                summary_keys_to_delete.append(f"summary_result:{summary_id}")
        except Exception as e:
            # Log or ignore malformed entries
            pass

    # Delete response and all summary_result:* keys
    await redis_client.delete(response_key)
    if summary_keys_to_delete:
        await redis_client.delete(*summary_keys_to_delete)

    return True


# --- RESPONSE MANAGEMENT ---


async def store_response(rule_id: str, response: dict, request=None):
    """Appends a response to the list of responses for a rule."""
    redis_client = (
        getattr(request.app.state, "redis_client", None)
        if request
        else fallback_redis_client
    )
    await redis_client.rpush(f"response:{rule_id}", json.dumps(response))


async def get_responses(request: Request, rule_id: str):
    """Retrieves all stored responses for a rule."""
    redis_client = request.app.state.redis_client
    return await redis_client.lrange(f"response:{rule_id}", 0, -1)


# --- SUMMARY STORAGE ---


async def save_summary_id(rule_id: str, summary_id: str, request=None):
    """Save summary ID under a rule."""
    redis_client = (
        getattr(request.app.state, "redis_client", None)
        if request
        else fallback_redis_client
    )
    await redis_client.rpush(f"summary_ids:{rule_id}", summary_id)


async def save_search(rule_id: str, search_output: dict, request=None):
    """
    Save search video results under a rule in Redis.

    Args:
        rule_id (str): ID of the rule that triggered the search
        search_output (dict): {video_id: message}
    """
    redis_client = (
        getattr(request.app.state, "redis_client", None)
        if request
        else fallback_redis_client
    )

    entry = json.dumps(
        {"video_id": search_output["video_id"], "message": search_output["message"]}
    )

    await redis_client.rpush(f"search_results:{rule_id}", entry)


async def get_summary_ids(request: Request, rule_id: str):
    """Get all summary IDs for a rule."""
    redis_client = request.app.state.redis_client
    return await redis_client.lrange(f"summary_ids:{rule_id}", 0, -1)


async def save_summary_result(summary_id: str, summary_result: str, request=None):
    """Store summary response by summary ID."""
    redis_client = (
        getattr(request.app.state, "redis_client", None)
        if request
        else fallback_redis_client
    )
    await redis_client.set(f"summary_result:{summary_id}", summary_result)


async def get_search_results_by_rule(rule_id: str, request=None) -> list[dict]:
    """
    Retrieve search results for a given rule from Redis.

    Args:
        rule_id (str): The rule ID whose results are to be fetched.
        request (optional): FastAPI request object to access app-scoped Redis client.

    Returns:
        list[dict]: A list of search result entries, each as a dictionary with 'video_id' and 'message'.
    """
    redis_client = (
        getattr(request.app.state, "redis_client", None)
        if request
        else fallback_redis_client
    )
    key = f"search_results:{rule_id}"

    try:
        results = await redis_client.lrange(key, 0, -1)
        return [json.loads(entry) for entry in results]
    except Exception as e:
        logger.error(f"Failed to fetch search results for rule {rule_id}: {e}")
        return []


async def get_summary_result(request: Request, summary_id: str):
    """Retrieve stored summary response."""
    redis_client = request.app.state.redis_client
    return await redis_client.get(f"summary_result:{summary_id}")

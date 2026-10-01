# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Tests for rule CRUD endpoints."""
import pytest
from unittest.mock import AsyncMock, patch

RULE_OBJ = {"id": "rule1", "label": "person", "action": "summarize", "camera": "cam1"}

@pytest.mark.asyncio
async def test_add_rule_success(client):
    async def fake_add_rule(request, rule_id, data):
        return True
    with patch("api.router.redis_store.add_rule", fake_add_rule):
        resp = client.post("/rules/", json=RULE_OBJ)
        assert resp.status_code == 200
        assert resp.json()["message"] == "Rule added"

@pytest.mark.asyncio
async def test_add_rule_duplicate(client):
    async def fake_add_rule(request, rule_id, data):
        return False
    with patch("api.router.redis_store.add_rule", fake_add_rule):
        resp = client.post("/rules/", json=RULE_OBJ)
        assert resp.status_code == 400

@pytest.mark.asyncio
async def test_list_rules(client):
    async def fake_get_rules(request):
        return [RULE_OBJ]
    with patch("api.router.redis_store.get_rules", fake_get_rules):
        resp = client.get("/rules/")
        assert resp.status_code == 200
        assert resp.json()[0]["id"] == "rule1"

@pytest.mark.asyncio
async def test_get_rule_found(client):
    async def fake_get_rule(request, rid):
        return RULE_OBJ
    with patch("api.router.redis_store.get_rule", fake_get_rule):
        resp = client.get("/rules/rule1")
        assert resp.status_code == 200
        assert resp.json()["id"] == "rule1"

@pytest.mark.asyncio
async def test_get_rule_not_found(client):
    async def fake_get_rule(request, rid):
        return None
    with patch("api.router.redis_store.get_rule", fake_get_rule):
        resp = client.get("/rules/ruleX")
        assert resp.status_code == 404

@pytest.mark.asyncio
async def test_delete_rule_success(client):
    async def fake_delete_rule(request, rid):
        return True
    with patch("api.router.redis_store.delete_rule", fake_delete_rule):
        resp = client.delete("/rules/rule1")
        assert resp.status_code == 200
        assert "deleted" in resp.json()["message"]

@pytest.mark.asyncio
async def test_delete_rule_not_found(client):
    async def fake_delete_rule(request, rid):
        return False
    with patch("api.router.redis_store.delete_rule", fake_delete_rule):
        resp = client.delete("/rules/rule1")
        assert resp.status_code == 404

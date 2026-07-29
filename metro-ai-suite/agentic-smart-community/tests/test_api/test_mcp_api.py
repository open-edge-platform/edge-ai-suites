# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Contract tests for docs/user-guide/get-started/api-reference-mcp.md."""

from __future__ import annotations

import json

from conftest import McpApiClient


DOCUMENTED_TOOLS = {
    "smartbuilding_alert_query",
    "smartbuilding_plan_ctl",
    "smartbuilding_scene_query",
    "smartbuilding_generate_report",
    "smartbuilding_monitor_ctl",
    "smartbuilding_monitors_compose",
    "smartbuilding_video_db",
    "smartbuilding_use_case_validate",
    "smartbuilding_use_case_register",
    "smartbuilding_rule_eval",
}


def _initialized_client(mcp_api: McpApiClient) -> McpApiClient:
    client = McpApiClient(mcp_api.url)
    client.initialize()
    return client


def _tool_result(client: McpApiClient, name: str, arguments: dict) -> tuple[dict, object]:
    response = client.request(
        "tools/call",
        {"name": name, "arguments": arguments},
    )
    result = response["result"]
    text = result["content"][0]["text"]
    return result, json.loads(text)


def test_initialize_returns_session_and_server_capabilities(mcp_api: McpApiClient):
    client = McpApiClient(mcp_api.url)

    response = client.initialize()

    assert client.session_id
    assert response["result"]["serverInfo"]["name"] == "smartbuilding-video"
    assert response["result"]["capabilities"]["resources"]["subscribe"] is True


def test_discovery_lists_documented_tools_and_resources(mcp_api: McpApiClient):
    client = _initialized_client(mcp_api)

    tools = client.request("tools/list")["result"]["tools"]
    resources = client.request("resources/list")["result"]["resources"]
    templates = client.request("resources/templates/list")["result"]["resourceTemplates"]

    assert {tool["name"] for tool in tools} == DOCUMENTED_TOOLS
    assert {resource["uri"] for resource in resources} == {"smartbuilding://monitors"}
    template_uris = {template["uriTemplate"] for template in templates}
    assert "smartbuilding://monitor/{id}/stats" in template_uris
    assert "smartbuilding://monitor/{id}/alerts" in template_uris
    assert "smartbuilding://monitor/{id}/alerts{?since}" in template_uris


def test_documented_local_tool_calls_return_json(mcp_api: McpApiClient):
    client = _initialized_client(mcp_api)

    alert_result, alerts = _tool_result(
        client,
        "smartbuilding_alert_query",
        {"monitor_id": "cam_child", "action": "latest", "limit": 20},
    )
    monitor_result, monitors = _tool_result(
        client,
        "smartbuilding_monitor_ctl",
        {"action": "list"},
    )
    db_result, rows = _tool_result(
        client,
        "smartbuilding_video_db",
        {"query": "SELECT id, status, use_case FROM monitors WHERE id = ?", "params": ["cam_child"]},
    )

    assert alert_result.get("isError") is not True
    assert alerts == {"alerts": []}
    assert monitor_result.get("isError") is not True
    assert isinstance(monitors, list)
    assert db_result.get("isError") is not True
    assert rows == []


def test_plan_tool_round_trip(mcp_api: McpApiClient):
    client = _initialized_client(mcp_api)
    arguments = {
        "monitor_id": "cam_elder_bedroom",
        "action": "upsert",
        "name": "morning-check",
        "plan_date": "2026-07-29",
        "plan": {"expected_wakeup": "07:30"},
    }

    upsert_result, upserted = _tool_result(client, "smartbuilding_plan_ctl", arguments)
    list_result, plans = _tool_result(
        client,
        "smartbuilding_plan_ctl",
        {"monitor_id": "cam_elder_bedroom", "action": "list", "active_only": True},
    )

    assert upsert_result.get("isError") is not True
    assert upserted["name"] == "morning-check"
    assert list_result.get("isError") is not True
    assert any(plan["name"] == "morning-check" for plan in plans)


def test_resource_reads_match_documented_shapes(mcp_api: McpApiClient):
    client = _initialized_client(mcp_api)

    monitors = client.read_resource("smartbuilding://monitors")
    stats = client.read_resource("smartbuilding://monitor/cam_child/stats")
    alerts = client.read_resource("smartbuilding://monitor/cam_child/alerts")
    incremental = client.read_resource("smartbuilding://monitor/cam_child/alerts?since=42")

    assert monitors == {"monitors": []}
    assert stats["monitorId"] == "cam_child"
    assert stats["events"] == 0
    assert stats["alerts"] == 0
    assert alerts == {"monitorId": "cam_child", "latestId": 0, "alerts": []}
    assert incremental == {"monitorId": "cam_child", "latestId": 42, "alerts": []}


def test_video_db_rejects_state_changing_sql(mcp_api: McpApiClient):
    client = _initialized_client(mcp_api)

    response = client.request(
        "tools/call",
        {
            "name": "smartbuilding_video_db",
            "arguments": {"query": "DELETE FROM monitors"},
        },
    )

    assert response["result"]["isError"] is True
    assert "SELECT" in response["result"]["content"][0]["text"]


def test_negative_alert_cursor_returns_mcp_error(mcp_api: McpApiClient):
    client = _initialized_client(mcp_api)

    response = client.request(
        "resources/read",
        {"uri": "smartbuilding://monitor/cam_child/alerts?since=-1"},
    )

    assert "error" in response
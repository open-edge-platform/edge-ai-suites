# Copyright (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Focused backend tests for the Ask & Analyze API."""

import asyncio
import json
import os

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

os.environ["AGENT_SERVICE_URL"] = "http://mock-agent"
os.environ["STORAGE_SERVICE_URL"] = "http://mock-storage"
os.environ["LLM_BASE_URL"] = "http://mock-llm/v3"
os.environ["LLM_MODEL_NAME"] = "test-model"

import src.app as app_module
from src.app import app

app_module._AGENT_URL = "http://mock-agent"
app_module._DETECTION_URL = "http://mock-detection"
app_module._STORAGE_URL = "http://mock-storage"
app_module._LLM_BASE_URL = "http://mock-llm/v3"
app_module._LLM_MODEL = "test-model"
app_module._USE_CASE_ID = "test-case"
_REAL_GET_DETECTION_LABELS = app_module._get_detection_labels


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def detection_labels(monkeypatch):
    async def get_detection_labels(_client, _analysis):
        return ("Rupture", "Deformation", "Disconnect", "Obstacle", "Shipping Label")

    monkeypatch.setattr(app_module, "_get_detection_labels", get_detection_labels)


def _llm_response(content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


@respx.mock
def test_analysis_uses_latest_completed_run(client):
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "older", "status": "completed"},
        {"run_id": "active", "status": "running"},
        {"run_id": "latest", "status": "completed"},
    ]))
    respx.get("http://mock-agent/agents/results/latest").mock(return_value=httpx.Response(200, json={
        "run_id": "latest",
        "analysis": {"risk": "high", "finding": "Rupture"},
        "window": {"min_id": 10, "max_id": 20},
        "ticket": {"internal": "not returned as analysis data"},
    }))
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(
        return_value=_llm_response("Immediate inspection is recommended for the reported rupture.")
    )

    response = client.post("/api/chat", json={
        "message": "What needs attention?",
        "mode": "analysis",
    })

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Immediate inspection is recommended for the reported rupture.",
        "mode": "analysis",
        "query": None,
        "data": {
            "analysis": {
                "run_id": "latest",
                "analysis": {"risk": "high", "finding": "Rupture"},
                "window": {"min_id": 10, "max_id": 20},
            },
        },
    }
    sent_context = llm.calls[0].request.content.decode()
    assert "Rupture" in sent_context
    assert "not returned as analysis data" not in sent_context


@respx.mock
def test_detections_builds_and_executes_strict_plan(client):
    plan = (
        '{"operation":"group_by","group_by":["label"],'
        '"metrics":[{"function":"count","alias":"detections"}],'
        '"sort":[{"field":"detections","direction":"desc"}],"limit":10}'
    )
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(
        side_effect=[
            _llm_response(plan),
            _llm_response("Rupture is the most frequent detection."),
        ]
    )
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"label": "Rupture", "detections": 7}],
            "meta": {"operation": "group_by", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "Which defect occurs most often?",
        "mode": "detections",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Rupture is the most frequent detection."
    assert body["query"]["operation"] == "group_by"
    assert body["data"]["detections"]["data"] == [{"label": "Rupture", "detections": 7}]
    posted_plan = json.loads(storage.calls[0].request.content)
    assert posted_plan == body["query"]
    assert posted_plan["limit"] == 10
    assert posted_plan["offset"] == 0
    planner_request = json.loads(llm.calls[0].request.content)
    assert "Allowed detection fields" in planner_request["messages"][0]["content"]
    assert "query_schema" not in planner_request["messages"][1]["content"]
    assert planner_request["response_format"]["type"] == "json_schema"
    query_schema = planner_request["response_format"]["json_schema"]["schema"]
    assert "oneOf" in query_schema
    answer_request = json.loads(llm.calls[1].request.content)
    assert "response_format" not in answer_request
    assert "numeric count field inside the first data row" in answer_request["messages"][0]["content"]
    assert len(llm.calls) == 2


@respx.mock
def test_detection_query_without_label_has_no_label_filter(client):
    respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response('{"operation":"count","filters":[]}'),
        _llm_response("There are ten detections."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 10}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "How many detections are stored?",
        "mode": "detections",
    })

    assert response.status_code == 200
    assert json.loads(storage.calls[0].request.content)["filters"] == []


@respx.mock
def test_detection_query_canonicalizes_shipping_label(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_get_detection_labels",
        _REAL_GET_DETECTION_LABELS,
    )
    respx.get("http://mock-agent/agents/status/run-shipping").mock(
        return_value=httpx.Response(200, json={
            "run_id": "run-shipping",
            "status": "completed",
        })
    )
    respx.get("http://mock-agent/agents/results/run-shipping").mock(
        return_value=httpx.Response(200, json={
            "analysis": {"report": "complete"},
            "window": {"start_id": 0, "end_id": 27287},
        })
    )
    summary = respx.get(
        "http://mock-storage/detections/summary",
        params={"min_id": 0, "max_id": 27287},
    ).mock(
        return_value=httpx.Response(200, json={
            "by_class": [
                {"label": "Rupture", "count": 4},
                {"label": "Shipping Label", "count": 3},
            ],
        })
    )
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response(
            '{"operation":"list","fields":["label","confidence","timestamp"],'
            '"filters":[],'
            '"sort":[{"field":"confidence","direction":"desc"}],"limit":10,"offset":0}'
        ),
        _llm_response("Shipping Label detections have been prioritized."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"label": "Shipping Label", "confidence": 0.9}],
            "meta": {"operation": "list", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "Priortize detections for shipping_label",
        "mode": "detections",
        "run_id": "run-shipping",
    })

    assert response.status_code == 200
    assert summary.called
    assert json.loads(storage.calls[0].request.content)["filters"] == [
        {"field": "label", "operator": "eq", "value": "Shipping Label"},
        {"field": "id", "operator": "gt", "value": 0},
        {"field": "id", "operator": "lte", "value": 27287},
    ]
    planner_prompt = json.loads(llm.calls[0].request.content)["messages"][0]["content"]
    assert '"Shipping Label"' in planner_prompt


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("Prioritize shipping_label detections", "Shipping Label"),
        ("Prioritize rupture detections", "Rupture"),
    ],
)
def test_mentioned_labels_create_distinct_query_filters(message, expected):
    plan = app_module._add_mentioned_label_filter(
        {"operation": "count", "filters": []},
        message,
        ("Rupture", "Shipping Label"),
    )

    assert plan["filters"] == [{
        "field": "label",
        "operator": "eq",
        "value": expected,
    }]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("shipping_label", "Shipping Label"),
        ("shipping-label", "Shipping Label"),
        ("shipping label", "Shipping Label"),
        ("SHIPPING_LABEL", "Shipping Label"),
    ],
)
def test_label_canonicalization_accepts_separator_and_case_variants(value, expected):
    canonical = app_module._canonicalize_plan_labels({
        "operation": "count",
        "filters": [{"field": "label", "operator": "eq", "value": value}],
    }, ("Shipping Label",))

    assert canonical["filters"][0]["value"] == expected


def test_unknown_detection_label_is_rejected():
    with pytest.raises(app_module.HTTPException) as error:
        app_module._canonicalize_plan_labels({
            "operation": "count",
            "filters": [{"field": "label", "operator": "eq", "value": "Leak"}],
        }, ("Rupture", "Shipping Label"))

    assert error.value.status_code == 400
    assert error.value.detail == (
        'Unknown or ambiguous detection label "Leak". '
        "Available labels: Rupture, Shipping Label."
    )


@respx.mock
def test_unknown_detection_label_is_not_executed(client):
    respx.post("http://mock-llm/v3/chat/completions").mock(
        return_value=_llm_response(
            '{"operation":"count","filters":'
            '[{"field":"label","operator":"eq","value":"Leak"}]}'
        )
    )
    storage = respx.post("http://mock-storage/detections/query")

    response = client.post("/api/chat", json={
        "message": "Count Leak detections.",
        "mode": "detections",
    })

    assert response.status_code == 400
    assert "Available labels: Rupture" in response.json()["detail"]
    assert not storage.called


@respx.mock
def test_detection_label_catalog_failure_is_sanitized(client, monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_get_detection_labels",
        _REAL_GET_DETECTION_LABELS,
    )
    respx.get("http://mock-storage/detections/summary").mock(
        return_value=httpx.Response(500, text="database details")
    )
    llm = respx.post("http://mock-llm/v3/chat/completions")
    storage = respx.post("http://mock-storage/detections/query")

    response = client.post("/api/chat", json={
        "message": "Count detections.",
        "mode": "detections",
    })

    assert response.status_code == 502
    assert response.json()["detail"] == "Detection labels could not be loaded."
    assert "database details" not in response.text
    assert not llm.called
    assert not storage.called


@respx.mock
def test_detection_planner_normalizes_deployed_model_wrapper(client):
    respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response(
            '{"query":{"operation":"count","filters":{}},"analysis_window":null}'
        ),
        _llm_response("There are four detections."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 4}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "How many detections are stored?",
        "mode": "detections",
    })

    assert response.status_code == 200
    assert json.loads(storage.calls[0].request.content) == {
        "operation": "count",
        "filters": [],
    }


@respx.mock
def test_count_plan_drops_irrelevant_model_generated_keys(client):
    respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response(
            '{"operation":"count","filters":[],"sort":'
            '[{"field":"detection_count","direction":"desc"}],"limit":1,"offset":0}'
        ),
        _llm_response("There are four detections."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 4}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "How many detections were in this run?",
        "mode": "detections",
    })

    assert response.status_code == 200
    assert json.loads(storage.calls[0].request.content) == {
        "operation": "count",
        "filters": [],
    }


@respx.mock
def test_detection_planner_accepts_json_code_fence(client):
    respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response("```json\n{\"operation\":\"count\"}\n```"),
        _llm_response("There are four detections."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 4}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "How many detections are stored?",
        "mode": "detections",
    })

    assert response.status_code == 200
    assert response.json()["query"]["operation"] == "count"
    assert json.loads(storage.calls[0].request.content) == {
        "operation": "count",
        "filters": [],
    }


@respx.mock
def test_detection_planner_retries_one_invalid_response(client):
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response("I would use a count query."),
        _llm_response('{"operation":"count"}'),
        _llm_response("There are two detections."),
    ])
    respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 2}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "Count detections",
        "mode": "detections",
    })

    assert response.status_code == 200
    assert len(llm.calls) == 3
    retry_prompt = json.loads(llm.calls[1].request.content)["messages"][-1]["content"]
    assert "not a valid plan" in retry_prompt


@respx.mock
def test_detection_planner_falls_back_after_supported_invalid_plans(client):
    invalid_plan = (
        '{"operation":"aggregate","metrics":'
        '[{"function":"sum","alias":"total_detections"}]}'
    )
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response(invalid_plan),
        _llm_response(invalid_plan),
        _llm_response(invalid_plan),
        _llm_response("There are five rupture detections."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 5}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "What is the total number of Rupture detections?",
        "mode": "detections",
    })

    assert response.status_code == 200
    assert len(llm.calls) == 4
    posted_plan = json.loads(storage.calls[0].request.content)
    assert posted_plan == {
        "operation": "count",
        "filters": [
            {"field": "label", "operator": "eq", "value": "Rupture"},
        ],
    }


@respx.mock
def test_combined_mode_scopes_fallback_plan_to_selected_run(client):
    respx.get("http://mock-agent/agents/status/run-fallback").mock(
        return_value=httpx.Response(200, json={"status": "completed"})
    )
    respx.get("http://mock-agent/agents/results/run-fallback").mock(
        return_value=httpx.Response(200, json={
            "analysis": {"recommendation": "Inspect ruptures"},
            "window": {"min_id": 10, "max_id": 20},
        })
    )
    raw_detection = (
        '{"id":"1","frame_id":"2","label":"Rupture","confidence":1.0,'
        '"x":50,"y":50,"width":100,"height":100,"timestamp":1684379600000}'
    )
    respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response(raw_detection),
        _llm_response(raw_detection),
        _llm_response(raw_detection),
        _llm_response("The highest-confidence rupture detections are listed."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [],
            "meta": {"operation": "list", "returned": 0},
        })
    )

    response = client.post("/api/chat", json={
        "message": "Which Rupture detections need immediate attention?",
        "mode": "combined",
        "run_id": "run-fallback",
    })

    assert response.status_code == 200
    posted_plan = json.loads(storage.calls[0].request.content)
    assert posted_plan["operation"] == "list"
    assert {"field": "label", "operator": "eq", "value": "Rupture"} in posted_plan["filters"]
    assert {"field": "id", "operator": "gt", "value": 10} in posted_plan["filters"]
    assert {"field": "id", "operator": "lte", "value": 20} in posted_plan["filters"]


def test_detection_plan_repairs_confidence_metric_field():
    normalized = app_module._normalize_detection_plan({
        "operation": "aggregate",
        "metrics": [{"function": "min", "alias": "minimum_confidence"}],
    })

    assert normalized["metrics"] == [{
        "function": "min",
        "field": "confidence",
        "alias": "minimum_confidence",
    }]
    app_module._QUERY_ADAPTER.validate_python(normalized)


@respx.mock
def test_malformed_query_plan_is_visible_and_not_executed(client):
    respx.post("http://mock-llm/v3/chat/completions").mock(
        return_value=_llm_response("```json\n{\"operation\":\"sql\"}\n```")
    )
    storage = respx.post("http://mock-storage/detections/query")

    response = client.post("/api/chat", json={
        "message": "Run a query",
        "mode": "detections",
    })

    assert response.status_code == 502
    assert response.json()["detail"] == "The language model returned an invalid detection query plan."
    assert not storage.called


@respx.mock
def test_combined_grounds_answer_in_analysis_and_detection_data(client):
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "run-2", "status": "completed"},
    ]))
    respx.get("http://mock-agent/agents/results/run-2").mock(return_value=httpx.Response(200, json={
        "analysis": {"recommendation": "Inspect ruptures"},
        "window": {"min_id": 4, "max_id": 9},
    }))
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response(
            '{"operation":"count","filters":'
            '[{"field":"label","operator":"eq","value":"Rupture"}]}'
        ),
        _llm_response("The run recommends inspection and contains three rupture detections."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(return_value=httpx.Response(200, json={
        "data": [{"count": 3}],
        "meta": {"operation": "count", "returned": 1},
    }))

    response = client.post("/api/chat", json={
        "message": "Relate the run recommendation to rupture detections.",
        "mode": "combined",
    })

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "combined"
    assert body["data"]["analysis"]["run_id"] == "run-2"
    assert body["data"]["detections"]["data"] == [{"count": 3}]
    posted_plan = json.loads(storage.calls[0].request.content)
    assert {"field": "id", "operator": "gt", "value": 4} in posted_plan["filters"]
    assert {"field": "id", "operator": "lte", "value": 9} in posted_plan["filters"]
    final_prompt = json.loads(llm.calls[1].request.content)["messages"][1]["content"]
    assert "Inspect ruptures" in final_prompt
    assert '"count":3' in final_prompt


@respx.mock
def test_combined_accepts_top_level_agent_detection_window(client):
    respx.get("http://mock-agent/agents/status/run-window").mock(
        return_value=httpx.Response(
            200, json={"run_id": "run-window", "status": "completed"}
        )
    )
    respx.get("http://mock-agent/agents/results/run-window").mock(
        return_value=httpx.Response(200, json={
            "analysis": {"recommendation": "Inspect the pipeline"},
            "min_id": 30,
            "max_id": 40,
        })
    )
    respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response('{"operation":"count","filters":[]}'),
        _llm_response("Five detections were found."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 5}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "How many detections were in this run?",
        "mode": "combined",
        "run_id": "run-window",
    })

    assert response.status_code == 200
    assert response.json()["data"]["analysis"]["window"] == {
        "min_id": 30,
        "max_id": 40,
    }
    assert json.loads(storage.calls[0].request.content)["filters"] == [
        {"field": "id", "operator": "gt", "value": 30},
        {"field": "id", "operator": "lte", "value": 40},
    ]


@respx.mock
def test_explicit_run_must_be_completed(client):
    respx.get("http://mock-agent/agents/status/run-1").mock(
        return_value=httpx.Response(200, json={"run_id": "run-1", "status": "running"})
    )

    response = client.post("/api/chat", json={
        "message": "Summarize this run",
        "mode": "analysis",
        "run_id": "run-1",
    })

    assert response.status_code == 409
    assert response.json()["detail"] == "The selected run is not completed."


@respx.mock
def test_detection_run_id_enforces_canonical_window_without_exposing_analysis(
    client,
    monkeypatch,
):
    monkeypatch.setattr(
        app_module,
        "_get_detection_labels",
        _REAL_GET_DETECTION_LABELS,
    )
    respx.get("http://mock-agent/agents/status/run-3").mock(
        return_value=httpx.Response(200, json={"run_id": "run-3", "status": "completed"})
    )
    respx.get("http://mock-agent/agents/results/run-3").mock(return_value=httpx.Response(200, json={
        "analysis": {"report": "bounded"},
        "window": {"start_id": 20, "end_id": 25},
    }))
    summary = respx.get(
        "http://mock-storage/detections/summary",
        params={"min_id": 20, "max_id": 25},
    ).mock(return_value=httpx.Response(200, json={
        "by_class": [{"label": "Shipping Label", "count": 2}],
    }))
    respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response('{"operation":"count"}'),
        _llm_response("Two detections were found."),
    ])
    storage = respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": [{"count": 2}],
            "meta": {"operation": "count", "returned": 1},
        })
    )

    response = client.post("/api/chat", json={
        "message": "How many detections were in this run?",
        "mode": "detections",
        "run_id": "run-3",
    })

    assert response.status_code == 200
    assert "analysis" not in response.json()["data"]
    assert summary.called
    assert json.loads(storage.calls[0].request.content)["filters"] == [
        {"field": "id", "operator": "gt", "value": 20},
        {"field": "id", "operator": "lte", "value": 25},
    ]


@respx.mock
def test_invalid_analysis_window_is_rejected_before_storage(client):
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "bad-window", "status": "completed"},
    ]))
    respx.get("http://mock-agent/agents/results/bad-window").mock(
        return_value=httpx.Response(200, json={
            "analysis": {"report": "result"},
            "window": {"start_id": 10, "end_id": 5},
        })
    )
    respx.post("http://mock-llm/v3/chat/completions").mock(
        return_value=_llm_response('{"operation":"count"}')
    )
    storage = respx.post("http://mock-storage/detections/query")

    response = client.post("/api/chat", json={
        "message": "Count this run's detections",
        "mode": "combined",
    })

    assert response.status_code == 502
    assert response.json()["detail"] == "The analysis result has no valid detection window."
    assert not storage.called


@respx.mock
def test_storage_failure_returns_sanitized_error(client):
    respx.post("http://mock-llm/v3/chat/completions").mock(
        return_value=_llm_response('{"operation":"count"}')
    )
    respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(500, text="database details")
    )

    response = client.post("/api/chat", json={
        "message": "Count detections",
        "mode": "detections",
    })

    assert response.status_code == 502
    assert response.json()["detail"] == "The detection query could not be completed."
    assert "database details" not in response.text


async def _noop_sleep(_):
    return


@respx.mock
def test_llm_retries_on_server_error_then_succeeds(client, monkeypatch):
    monkeypatch.setattr(app_module, "asyncio", type("asyncio", (), {"sleep": staticmethod(_noop_sleep)}))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "retry-run", "status": "completed"},
    ]))
    respx.get("http://mock-agent/agents/results/retry-run").mock(return_value=httpx.Response(200, json={
        "analysis": {"finding": "Rupture"},
        "window": {"min_id": 1, "max_id": 5},
    }))
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        httpx.Response(502, text="Bad Gateway"),
        _llm_response("Inspection recommended."),
    ])

    response = client.post("/api/chat", json={
        "message": "What needs attention?",
        "mode": "analysis",
    })

    assert response.status_code == 200
    assert response.json()["answer"] == "Inspection recommended."
    assert len(llm.calls) == 2


@respx.mock
def test_proactive_context_trimming_fits_token_budget(client, monkeypatch):
    monkeypatch.setattr(app_module, "_LLM_CONTEXT_LIMIT", 1024)
    large_data = [{"label": f"item-{i}", "confidence": 0.9} for i in range(200)]
    respx.post("http://mock-storage/detections/query").mock(
        return_value=httpx.Response(200, json={
            "data": large_data,
            "meta": {"operation": "list", "returned": 200},
        })
    )
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(side_effect=[
        _llm_response('{"operation":"list","filters":[]}'),
        _llm_response("Detection summary complete."),
    ])

    response = client.post("/api/chat", json={
        "message": "List detections",
        "mode": "detections",
    })

    assert response.status_code == 200
    answer_body = json.loads(llm.calls[1].request.content)
    input_chars = sum(len(m["content"]) for m in answer_body["messages"])
    original_chars = sum(
        len(json.dumps(d, ensure_ascii=False, separators=(",", ":"))) for d in large_data
    )
    assert input_chars < original_chars, "Context should have been trimmed"


@respx.mock
def test_llm_exhausts_retries_returns_502(client, monkeypatch):
    monkeypatch.setattr(app_module, "asyncio", type("asyncio", (), {"sleep": staticmethod(_noop_sleep)}))
    respx.get("http://mock-agent/agents/runs").mock(return_value=httpx.Response(200, json=[
        {"run_id": "fail-run", "status": "completed"},
    ]))
    respx.get("http://mock-agent/agents/results/fail-run").mock(return_value=httpx.Response(200, json={
        "analysis": {"finding": "Rupture"},
        "window": {"min_id": 1, "max_id": 5},
    }))
    llm = respx.post("http://mock-llm/v3/chat/completions").mock(
        return_value=httpx.Response(502, text="Bad Gateway"),
    )

    response = client.post("/api/chat", json={
        "message": "What needs attention?",
        "mode": "analysis",
    })

    assert response.status_code == 502
    assert response.json()["detail"] == "The language model could not complete the request."
    assert len(llm.calls) == app_module._LLM_MAX_RETRIES + 1


@pytest.mark.parametrize("payload", [
    {"message": " ", "mode": "analysis"},
    {"message": "x" * 4_001, "mode": "analysis"},
    {"message": "question", "mode": "unknown"},
    {"message": "question", "mode": "analysis", "run_id": "../secret"},
    {"message": "question\x00", "mode": "analysis"},
    {"message": "question", "mode": "analysis", "unexpected": True},
])
def test_chat_request_is_bounded_and_strict(client, payload):
    response = client.post("/api/chat", json=payload)
    assert response.status_code == 422

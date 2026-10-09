"""Behavioral tests for the standalone weld MCP service."""

import json
import tarfile
import unittest
from unittest.mock import AsyncMock, call, patch

import httpx

import server


class WeldMCPServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=server.mcp.http_app(stateless_http=True)),
            base_url="http://localhost:8000",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_mcp_tools_are_registered(self) -> None:
        tools = await server.mcp.list_tools()
        self.assertEqual(
            {"start_pipeline", "stop_pipeline", "explain", "list_insights_data", "run_agent", "get_run_results", "describe"},
            {tool.name for tool in tools},
        )
        run_tool = next(tool for tool in tools if tool.name == "run_agent")
        time_range = run_tool.parameters["properties"]["time_range"]
        self.assertEqual(["30s", "1m", "5m", "10m", "30m"], time_range["enum"])
        self.assertEqual("30s", time_range["default"])

    async def test_describe_reflects_registered_tools_without_network_calls(self) -> None:
        with patch.object(server, "_request", side_effect=AssertionError("Unexpected upstream request")):
            description = await server.describe()

        registered = {tool.name: tool for tool in await server.mcp.list_tools()}
        self.assertEqual("Weld defect detection", description["name"])
        self.assertEqual(set(registered), {tool["name"] for tool in description["tools"]})
        self.assertEqual(len(registered), len(description["tools"]))
        for tool in description["tools"]:
            self.assertEqual(registered[tool["name"]].description, tool["description"])
            self.assertEqual(registered[tool["name"]].parameters, tool["input_schema"])
        self.assertIn("advisory", description["operational_guidance"])

    async def test_backend_requests_allow_three_minutes(self) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            self.assertEqual(
                {"connect": 5.0, "read": 180.0, "write": 180.0, "pool": 180.0},
                request.extensions["timeout"],
            )
            return httpx.Response(200, json={"ok": True})

        original_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            return original_client(*args, transport=httpx.MockTransport(respond), **kwargs)

        with patch.object(server.httpx, "AsyncClient", side_effect=client_factory):
            response = await server._request("GET", "http://example.invalid/test")
        self.assertEqual({"ok": True}, response.json())

    async def test_start_pipeline_uses_checked_in_payload(self) -> None:
        original = json.loads(server.PIPELINE_REQUEST_PATH.read_text(encoding="utf-8"))
        for device in ("CPU", "GPU", "NPU"):
            with self.subTest(device=device), patch.object(server, "_request", new_callable=AsyncMock) as upstream:
                upstream.side_effect = [
                    httpx.Response(200, json={"status": "success"}),
                    httpx.Response(200, json={"status": "success"}),
                    httpx.Response(200, json={"status": "enabled"}),
                    httpx.Response(200, json={"id": "pipeline-1"}),
                ]
                self.assertEqual(
                    {"id": "pipeline-1", "time_series_task": "weld_anomaly_detector",
                     "time_series_device": "CPU"},
                    await server.start_pipeline(device),
                )
                sent = upstream.await_args
                self.assertEqual("POST", sent.args[0])
                self.assertEqual(
                    "http://dlstreamer-pipeline-server:8080/pipelines/"
                    "user_defined_pipelines/weld_defect_classification",
                    sent.args[1],
                )
                expected = json.loads(json.dumps(original))
                expected["parameters"]["classification-properties"]["device"] = device
                self.assertEqual(expected, sent.kwargs["json"])
                self.assertEqual("CPU", upstream.await_args_list[1].kwargs["json"]["udfs"]["device"])
        self.assertEqual(original, json.loads(server.PIPELINE_REQUEST_PATH.read_text(encoding="utf-8")))

    async def test_start_accepts_independent_device_inputs(self) -> None:
        tools = await server.mcp.list_tools()
        start_tool = next(tool for tool in tools if tool.name == "start_pipeline")
        self.assertEqual(["CPU", "GPU", "NPU"], start_tool.parameters["properties"]["device"]["enum"])
        self.assertEqual(["CPU", "GPU"], start_tool.parameters["properties"]["time_series_device"]["enum"])
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = [
                httpx.Response(200),
                httpx.Response(200),
                httpx.Response(200, json={"status": "enabled"}),
                httpx.Response(200, json={"id": "pipeline-1"}),
            ]
            result = await self.client.post(
                "/start_pipeline", json={"device": "NPU", "time_series_device": "GPU"}
            )
            self.assertEqual(200, result.status_code)
            self.assertEqual("GPU", result.json()["time_series_device"])
            self.assertEqual("GPU", upstream.await_args_list[1].kwargs["json"]["udfs"]["device"])
            self.assertEqual(
                "NPU", upstream.await_args_list[3].kwargs["json"]["parameters"]["classification-properties"]["device"]
            )

            invalid = await self.client.post(
                "/start_pipeline", json={"device": "CPU", "time_series_device": "NPU"}
            )
            self.assertEqual(400, invalid.status_code)
            self.assertEqual(4, upstream.await_count)

    async def test_start_pipeline_uploads_and_configures_timeseries_first(self) -> None:
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = [
                httpx.Response(200, json={"status": "success"}),
                httpx.Response(200, json={"status": "success"}),
                httpx.Response(200, json={"status": "enabled"}),
                httpx.Response(200, json={"id": "pipeline-1"}),
            ]
            await server.start_pipeline("GPU", "GPU")

        self.assertEqual(
            [
                ("POST", "http://ia-time-series-analytics-microservice:5000/udfs/package"),
                ("POST", "http://ia-time-series-analytics-microservice:5000/config"),
                ("GET", "http://ia-time-series-analytics-microservice:9092/kapacitor/v1/"
                 "tasks/weld_anomaly_detector"),
                ("POST", "http://dlstreamer-pipeline-server:8080/pipelines/"
                 "user_defined_pipelines/weld_defect_classification"),
            ],
            [(request.args[0], request.args[1]) for request in upstream.await_args_list],
        )
        self.assertEqual("weld_anomaly_detector.tar", upstream.await_args_list[0].kwargs["files"]["file"][0])
        self.assertEqual("weld_anomaly_detector", upstream.await_args_list[1].kwargs["json"]["udfs"]["name"])
        self.assertEqual("GPU", upstream.await_args_list[1].kwargs["json"]["udfs"]["device"])

    async def test_start_waits_for_enabled_timeseries_task_before_dlstreamer(self) -> None:
        task_url = "http://ia-time-series-analytics-microservice:9092/kapacitor/v1/tasks/weld_anomaly_detector"
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = [
                httpx.Response(200, json={"status": "success"}),
                httpx.Response(200, json={"status": "success"}),
                httpx.Response(200, json={"status": "enabled"}),
                httpx.Response(200, json={"id": "pipeline-1"}),
            ]
            await server.start_pipeline()
            self.assertEqual(call("GET", task_url, timeout=10), upstream.await_args_list[2])
            self.assertEqual("POST", upstream.await_args_list[3].args[0])

    async def test_start_packages_mounted_udf_files_without_generated_tar(self) -> None:
        async def respond(method, url, **kwargs):
            if url.endswith("/udfs/package"):
                package = kwargs["files"]["file"][1]
                with tarfile.open(fileobj=package, mode="r") as archive:
                    members = set(archive.getnames())
                    self.assertIn("udfs/weld_anomaly_detector.py", members)
                    self.assertIn("tick_scripts/weld_anomaly_detector.tick", members)
                    self.assertIn("models/weld_anomaly_detector.pkl", members)
            if method == "GET":
                return httpx.Response(200, json={"status": "enabled"})
            return httpx.Response(200, json={"id": "pipeline-1"})

        with patch.object(server, "_request", side_effect=respond):
            self.assertEqual("pipeline-1", (await server.start_pipeline())["id"])

    async def test_start_retries_until_timeseries_task_is_enabled(self) -> None:
        task_url = "http://ia-time-series-analytics-microservice:9092/kapacitor/v1/tasks/weld_anomaly_detector"
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream, \
             patch.object(server.asyncio, "sleep", new_callable=AsyncMock) as delay:
            upstream.side_effect = [
                httpx.Response(200),
                httpx.Response(200),
                httpx.ConnectError("Starting", request=httpx.Request("GET", task_url)),
                httpx.Response(200, json={"status": "disabled"}),
                httpx.Response(200, json={"status": "enabled"}),
                httpx.Response(200, json={"id": "pipeline-1"}),
            ]
            self.assertEqual("pipeline-1", (await server.start_pipeline())["id"])
            self.assertEqual(2, delay.await_count)
            self.assertEqual(3, sum(request.args[0] == "GET" for request in upstream.await_args_list))

    async def test_start_times_out_without_starting_dlstreamer_when_task_is_disabled(self) -> None:
        with patch.object(server, "TIME_SERIES_READY_TIMEOUT", 0), \
             patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = [
                httpx.Response(200),
                httpx.Response(200),
                httpx.Response(200, json={"status": "disabled"}),
            ]
            result = await self.client.post("/start_pipeline", json={"device": "CPU"})
            self.assertEqual(502, result.status_code)
            self.assertEqual(
                {"error": "Time-series task did not become enabled",
                 "completed": {"configured_time_series_task": "weld_anomaly_detector"},
                 "failed": {"time_series": "not enabled"}},
                result.json(),
            )
            self.assertEqual(3, upstream.await_count)

    async def test_start_reports_partial_failure_when_dlstreamer_cannot_start(self) -> None:
        pipeline_url = ("http://dlstreamer-pipeline-server:8080/pipelines/"
                        "user_defined_pipelines/weld_defect_classification")
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = [
                httpx.Response(200),
                httpx.Response(200),
                httpx.Response(200, json={"status": "enabled"}),
                httpx.HTTPStatusError("Unavailable", request=httpx.Request("POST", pipeline_url),
                                      response=httpx.Response(503)),
            ]
            result = await self.client.post("/start_pipeline", json={"device": "CPU"})
            self.assertEqual(502, result.status_code)
            self.assertEqual(
                {"error": "Time-series configured but DLStreamer failed to start",
                 "completed": {"configured_time_series_task": "weld_anomaly_detector"},
                 "failed": {"dlstreamer": "HTTP 503"}},
                result.json(),
            )

    async def test_start_does_not_start_dlstreamer_when_package_upload_fails(self) -> None:
        package_url = "http://ia-time-series-analytics-microservice:5000/udfs/package"
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = httpx.HTTPStatusError(
                "Rejected", request=httpx.Request("POST", package_url), response=httpx.Response(422)
            )
            result = await self.client.post("/start_pipeline", json={"device": "GPU"})
            self.assertEqual(422, result.status_code)
            upstream.assert_awaited_once()

    async def test_stop_rejects_invalid_id_without_upstream_calls(self) -> None:
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            with self.assertRaises(ValueError):
                await server.stop_pipeline("../other")
            upstream.assert_not_awaited()

    async def test_stop_pipeline_disables_named_timeseries_task(self) -> None:
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            self.assertEqual(
                {
                    "stopped_pipeline_id": "pipeline-1",
                    "stopped_time_series_task": "weld_anomaly_detector",
                },
                await server.stop_pipeline("pipeline-1"),
            )
            self.assertEqual(
                [
                    call("DELETE", "http://dlstreamer-pipeline-server:8080/pipelines/pipeline-1"),
                    call("PATCH", "http://ia-time-series-analytics-microservice:9092/kapacitor/v1/"
                         "tasks/weld_anomaly_detector", json={"status": "disabled"}),
                ],
                upstream.await_args_list,
            )

    async def test_stop_reports_partial_failure_without_skipping_other_service(self) -> None:
        task_url = "http://ia-time-series-analytics-microservice:9092/kapacitor/v1/tasks/weld_anomaly_detector"
        dlstreamer_url = "http://dlstreamer-pipeline-server:8080/pipelines/pipeline-1"
        for responses, completed, failed in (
            (
                [httpx.Response(204), httpx.ConnectError("Refused", request=httpx.Request("PATCH", task_url))],
                {"stopped_pipeline_id": "pipeline-1"},
                {"time_series": "unavailable"},
            ),
            (
                [httpx.HTTPStatusError("Unavailable", request=httpx.Request("DELETE", dlstreamer_url),
                                       response=httpx.Response(503)), httpx.Response(200)],
                {"stopped_time_series_task": "weld_anomaly_detector"},
                {"dlstreamer": "HTTP 503"},
            ),
        ):
            with self.subTest(failed=failed), patch.object(server, "_request", new_callable=AsyncMock) as upstream:
                upstream.side_effect = responses
                result = await self.client.post("/stop_pipeline", json={"pipeline_id": "pipeline-1"})
                self.assertEqual(502, result.status_code)
                self.assertEqual(
                    {"error": "Could not stop both pipelines", "completed": completed, "failed": failed},
                    result.json(),
                )
                self.assertEqual(2, upstream.await_count)

    async def test_explain_forwards_single_timestamp(self) -> None:
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.return_value = httpx.Response(200, json={"markdown": "Weld report"})
            self.assertEqual({"markdown": "Weld report"}, await server.explain("2026-10-01T12:00:00Z"))
            upstream.assert_awaited_once_with(
                "POST",
                "http://multimodal-agentic-ui:5003/insights-ui/api/explain",
                json={"selected_times": ["2026-10-01T12:00:00Z"]},
            )

    async def test_list_insights_data_forwards_pagination(self) -> None:
        data = {
            "measurement": "fusion_result", "page": 2, "page_size": 25,
            "has_more": False, "rows": [{"time": "2026-10-08T12:00:00Z"}],
        }
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.return_value = httpx.Response(200, json=data)
            self.assertEqual(data, await server.list_insights_data())
            upstream.assert_awaited_once_with(
                "GET", "http://multimodal-agentic-ui:5003/insights-ui/api/data",
                params={"page": 1, "page_size": 10},
            )
            upstream.reset_mock()
            self.assertEqual(data, await server.list_insights_data(page=2, page_size=25))
            upstream.assert_awaited_once_with(
                "GET", "http://multimodal-agentic-ui:5003/insights-ui/api/data",
                params={"page": 2, "page_size": 25},
            )

    async def test_run_agent_returns_id_from_ui_redirect(self) -> None:
        run_id = "123e4567-e89b-12d3-a456-426614174000"
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.return_value = httpx.Response(
                303, headers={"location": f"/agentic-ui/results/{run_id}"}
            )
            self.assertEqual(
                {"run_id": run_id, "results_path": f"/agentic-ui/results/{run_id}"},
                await server.run_agent("5m"),
            )
            upstream.assert_awaited_once_with(
                "POST", "http://multimodal-agentic-ui:5003/run",
                data={"time_range": "5m"}, follow_redirects=False, allow_redirect=True,
            )
            upstream.reset_mock()
            self.assertEqual(run_id, (await server.run_agent())["run_id"])
            upstream.assert_awaited_once_with(
                "POST", "http://multimodal-agentic-ui:5003/run",
                data={"time_range": "30s"}, follow_redirects=False, allow_redirect=True,
            )
            upstream.return_value = httpx.Response(200, json={"status": "error"})
            with self.assertRaises(ValueError):
                await server.run_agent()
            upstream.return_value = httpx.Response(303, headers={"location": "/other"})
            with self.assertRaises(ValueError):
                await server.run_agent()

    async def test_run_agent_handles_http_redirect_without_masking_upstream_errors(self) -> None:
        run_id = "9bf093d6-9e2d-4527-a754-a060bda632a6"

        def redirect(request: httpx.Request) -> httpx.Response:
            self.assertEqual("POST", request.method)
            self.assertEqual(b"time_range=30s", request.content)
            return httpx.Response(303, headers={"location": f"/agentic-ui/results/{run_id}"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(redirect))
        with patch.object(server.httpx, "AsyncClient", return_value=client):
            self.assertEqual(run_id, (await server.run_agent())["run_id"])

        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(502)))
        with patch.object(server.httpx, "AsyncClient", return_value=client):
            with self.assertRaises(httpx.HTTPStatusError):
                await server.run_agent()

    async def test_get_run_results_matches_agent_status_and_completed_result(self) -> None:
        run_id = "123e4567-e89b-12d3-a456-426614174000"
        status_url = f"http://apm-agent:5002/agents/status/{run_id}"
        results_url = f"http://apm-agent:5002/agents/results/{run_id}"
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = [
                httpx.Response(200, json={"status": "running"}),
                httpx.Response(200, json={"status": "completed"}),
                httpx.Response(200, json={"ticket": "Inspect weld"}),
            ]
            self.assertEqual(
                {"run_id": run_id, "phase": "reasoning", "result": {"status": "running"}},
                await server.get_run_results(run_id),
            )
            self.assertEqual(
                {"run_id": run_id, "phase": "completed", "result": {"ticket": "Inspect weld"}},
                await server.get_run_results(run_id),
            )
            self.assertEqual(
                [call("GET", status_url), call("GET", status_url), call("GET", results_url)],
                upstream.await_args_list,
            )

    async def test_get_run_results_rejects_invalid_id(self) -> None:
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            with self.assertRaises(ValueError):
                await server.get_run_results("../other")
            upstream.assert_not_awaited()

    async def test_http_paths_share_tool_actions(self) -> None:
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            upstream.side_effect = [
                httpx.Response(200, json={"status": "success"}),
                httpx.Response(200, json={"status": "success"}),
                httpx.Response(200, json={"status": "enabled"}),
                httpx.Response(200, json={"id": "pipeline-1"}),
            ]
            response = await self.client.post(
                "/start_pipeline", json={"device": "GPU", "time_series_device": "GPU"}
            )
            self.assertEqual(200, response.status_code)
            self.assertEqual(
                {"id": "pipeline-1", "time_series_task": "weld_anomaly_detector", "time_series_device": "GPU"},
                response.json(),
            )
            self.assertEqual(
                "GPU", upstream.await_args.kwargs["json"]["parameters"]["classification-properties"]["device"]
            )

            upstream.side_effect = None
            response = await self.client.post("/stop_pipeline", json={"pipeline_id": "pipeline-1"})
            self.assertEqual(200, response.status_code)
            self.assertEqual(
                {"stopped_pipeline_id": "pipeline-1", "stopped_time_series_task": "weld_anomaly_detector"},
                response.json(),
            )

            upstream.return_value = httpx.Response(200, json={"markdown": "Weld report"})
            response = await self.client.post("/explain", json={"selected_time": "2026-10-01T12:00:00Z"})
            self.assertEqual(200, response.status_code)
            self.assertEqual({"markdown": "Weld report"}, response.json())

    async def test_http_rejects_bad_input_and_reports_upstream_failures(self) -> None:
        with patch.object(server, "_request", new_callable=AsyncMock) as upstream:
            for path, payload in (
                ("/start_pipeline", {"device": "FPGA"}),
                ("/stop_pipeline", {"pipeline_id": "../other"}),
                ("/explain", {}),
            ):
                with self.subTest(path=path):
                    response = await self.client.post(path, json=payload)
                    self.assertEqual(400, response.status_code)
            upstream.assert_not_awaited()

            request = httpx.Request("POST", "http://multimodal-agentic-ui:5003/insights-ui/api/explain")
            upstream.side_effect = httpx.HTTPStatusError(
                "Not found", request=request, response=httpx.Response(404, request=request)
            )
            response = await self.client.post("/explain", json={"selected_time": "2026-10-01T12:00:00Z"})
            self.assertEqual(404, response.status_code)

            upstream.side_effect = httpx.ConnectError("Connection refused", request=request)
            response = await self.client.post("/explain", json={"selected_time": "2026-10-01T12:00:00Z"})
            self.assertEqual(502, response.status_code)
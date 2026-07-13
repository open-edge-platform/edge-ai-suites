# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for backend.services.pipeline_server."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.models import RunInfo, StartRunRequest
from backend.state import RUNS
from backend.services.pipeline_server import PipelineServer


@pytest.fixture()
def server() -> PipelineServer:
    return PipelineServer()


def _running_run(
    run_id: str = "r1",
    peer_id: str = "peer-r1",
    rtsp_url: str = "rtsp://example/stream",
    pipeline_id: str = "pipe-r1",
) -> RunInfo:
    return RunInfo(
        runId=run_id,
        pipelineId=pipeline_id,
        peerId=peer_id,
        mqttTopic=f"topic/{run_id}",
        status="running",
        rtspUrl=rtsp_url,
        pipelineName="Video_Captioning_RTSP_Software",
    )


class TestPipelineServerHelpers:
    def test_linux_video_device_detection(self, server):
        assert server._is_linux_video_device("/dev/video0") is True
        assert server._is_linux_video_device("/dev/video12") is True
        assert server._is_linux_video_device("/dev/videoX") is False
        assert server._is_linux_video_device("rtsp://host/stream") is False

    def test_camera_pipeline_name_detection(self, server):
        assert server._is_camera_pipeline_name("Video_Captioning_Camera_Software") is True
        assert server._is_camera_pipeline_name("Video_Captioning_RTSP_Software") is False

    def test_resolve_pipeline_name_from_ui_prefers_default_resolution_alias(self, server):
        req = StartRunRequest(rtspUrl="rtsp://example/stream", streamSourceType="rtsp", decoder="cpu")
        with patch(
            "backend.services.pipeline_server.discover_pipelines_remote",
            return_value=[
                {"pipeline_name": "Video_Captioning_RTSP_Software_Default_Resolution"},
                {"pipeline_name": "Video_Captioning_RTSP_Software"},
            ],
        ) as mock_discover:
            name = server._resolve_pipeline_name_from_ui(req, req.rtspUrl)
        mock_discover.assert_called_once_with()
        assert name == "Video_Captioning_RTSP_Software_Default_Resolution"

    def test_resolve_pipeline_name_from_ui_returns_base_when_alias_missing(self, server):
        req = StartRunRequest(rtspUrl="rtsp://example/stream", streamSourceType="rtsp", decoder="cpu")
        with patch(
            "backend.services.pipeline_server.discover_pipelines_remote",
            return_value=[{"pipeline_name": "Video_Captioning_RTSP_Software"}],
        ):
            name = server._resolve_pipeline_name_from_ui(req, req.rtspUrl)
        assert name == "Video_Captioning_RTSP_Software"

    def test_resolve_pipeline_name_from_ui_unknown_raises_400(self, server):
        req = StartRunRequest(rtspUrl="rtsp://example/stream", streamSourceType="rtsp", decoder="cpu")
        with patch(
            "backend.services.pipeline_server.discover_pipelines_remote",
            return_value=[{"pipeline_name": "known"}],
        ):
            with pytest.raises(HTTPException) as exc_info:
                server._resolve_pipeline_name_from_ui(req, req.rtspUrl)

        assert exc_info.value.status_code == 400
        assert "No matching backend pipeline found" in exc_info.value.detail["message"]

    def test_normalize_pipeline_name_for_npu_strips_default_resolution_suffix(self, server):
        assert (
            server._normalize_pipeline_name_for_vlm_device(
                "Video_Captioning_RTSP_Hardware_Default_Resolution", "npu"
            )
            == "Video_Captioning_RTSP_Hardware"
        )

    def test_normalize_pipeline_name_for_non_npu_keeps_suffix(self, server):
        assert (
            server._normalize_pipeline_name_for_vlm_device(
                "Video_Captioning_RTSP_Hardware_Default_Resolution", "gpu"
            )
            == "Video_Captioning_RTSP_Hardware_Default_Resolution"
        )

    def test_normalize_pipeline_name_for_npu_without_suffix_keeps_name(self, server):
        assert (
            server._normalize_pipeline_name_for_vlm_device(
                "Video_Captioning_RTSP_Hardware", "npu"
            )
            == "Video_Captioning_RTSP_Hardware"
        )

    def test_build_unique_run_name_sanitizes_and_avoids_collisions(self, server):
        RUNS["My_Run"] = _running_run(run_id="My_Run")
        assert server._build_unique_run_name(" My Run ") == "My_Run_1"

    def test_build_unique_run_name_returns_none_when_sanitized_empty(self, server):
        assert server._build_unique_run_name("!!!@@@") is None

    def test_build_unique_run_name_returns_none_when_missing_or_blank(self, server):
        assert server._build_unique_run_name(None) is None
        assert server._build_unique_run_name("   ") is None

    def test_generate_peer_id_invalid_config_raises(self, server, monkeypatch):
        monkeypatch.setattr(server, "WEBRTC_PEER_ID_PREFIX", "toolongprefix")
        monkeypatch.setattr(server, "WEBRTC_PEER_ID_MAX_LENGTH", 3)

        with pytest.raises(RuntimeError, match="Invalid WebRTC peer ID configuration"):
            server._generate_peer_id()

    def test_generate_peer_id_skips_collision(self, server):
        RUNS["r1"] = _running_run(run_id="r1", peer_id="s1234567")

        with patch(
            "backend.services.pipeline_server.uuid.uuid4",
            side_effect=[
                SimpleNamespace(hex="1234567aaaa"),
                SimpleNamespace(hex="7654321bbbb"),
            ],
        ):
            peer_id = server._generate_peer_id()

        assert peer_id == "s7654321"


class TestPipelineParameterBuilding:
    def test_build_pipeline_parameters_rejects_cpu_for_hardware_detection(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            detectionDevice="cpu",
            detectionThreshold=0.4,
        )

        with pytest.raises(HTTPException) as exc_info:
            server._build_pipeline_parameters(
                req,
                run_id="r1",
                pipeline_name="Video_Captioning_RTSP_Detection_Hardware",
            )

        assert exc_info.value.status_code == 400
        assert "not supported" in exc_info.value.detail["message"]

    def test_build_pipeline_parameters_rejects_non_cpu_for_software_detection(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            detectionDevice="gpu",
            detectionThreshold=0.4,
        )

        with pytest.raises(HTTPException) as exc_info:
            server._build_pipeline_parameters(
                req,
                run_id="r1",
                pipeline_name="Video_Captioning_RTSP_Detection_Software",
            )

        assert exc_info.value.status_code == 400
        assert "Use 'cpu'" in exc_info.value.detail["message"]

    def test_build_pipeline_parameters_applies_detection_and_cpu_scheduler(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            vlmDevice="cpu",
            detectionDevice="cpu",
            detectionThreshold=0.65,
            chunkSize=2,
            modelName="OpenGVLab/InternVL2-2B",
            prompt="Describe",
        )

        params = server._build_pipeline_parameters(
            req,
            run_id="run1",
            pipeline_name="Video_Captioning_RTSP_Software",
        )

        assert params["detection_device"] == "CPU"
        assert params["detection_pre_process_backend"] == "opencv"
        assert params["detection_threshold"] == 0.65
        assert params["queue_size"] == 2
        assert params["captioner-properties"]["scheduler-config"] == server.CPU_SCHEDULER_CONFIG

    def test_build_pipeline_parameters_gpu_adds_cache_path(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            vlmDevice="gpu",
            chunkSize=3,
        )

        params = server._build_pipeline_parameters(
            req,
            run_id="run1",
            pipeline_name="Video_Captioning_RTSP_Hardware",
        )

        assert params["captioner-properties"]["device"] == "GPU"
        assert params["captioner-properties"]["scheduler-config"] == server.GPU_SCHEDULER_CONFIG
        assert params["captioner-properties"]["model-cache-path"] == "/tmp/ov_cache"

    def test_build_pipeline_parameters_npu_forces_resolution_and_uses_npu_captioner_config(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            vlmDevice="npu",
            frameWidth=1920,
            frameHeight=1080,
        )

        with patch("backend.services.pipeline_server.NPU_FORCED_RESOLUTION", 640):
            params = server._build_pipeline_parameters(
                req,
                run_id="run1",
                pipeline_name="GenAI_X_Pipeline",
            )

        assert params["frame_width"] == 640
        assert params["frame_height"] == 640
        assert params["captioner-properties"]["device"] == "NPU"
        assert "generation-config" in params["captioner-properties"]
        assert "scheduler-config" not in params["captioner-properties"]

    def test_build_pipeline_parameters_npu_vlm_override_excludes_scheduler(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            vlmDevice="npu",
            maxNewTokens=111,
        )

        params = server._build_pipeline_parameters(
            req,
            run_id="run1",
            pipeline_name="Video_Captioning_RTSP_Hardware",
        )

        assert params["captioner-properties"]["device"] == "NPU"
        assert "generation-config" in params["captioner-properties"]
        assert "scheduler-config" not in params["captioner-properties"]


class TestPayloadAndExtraction:
    def test_build_start_payload_for_webcam_source(self, server):
        req = StartRunRequest(rtspUrl="/dev/video0")

        with patch.object(server, "_build_pipeline_parameters", return_value={"k": "v"}):
            payload = server._build_start_payload(
                req,
                run_id="r1",
                peer_id="peer1",
                pipeline_name="Video_Captioning_Camera_Software",
            )

        assert payload["source"] == {"device": "/dev/video0", "type": "webcam"}
        assert payload["destination"]["frame"]["peer-id"] == "peer1"
        assert payload["destination"]["frame"]["overlay"] is False

    def test_build_start_payload_for_uri_source_when_overlay_enabled(self, server):
        req = StartRunRequest(rtspUrl="rtsp://host/stream", includeRoiBoundingBox=True)

        with patch.object(server, "_build_pipeline_parameters", return_value={"k": "v"}):
            payload = server._build_start_payload(
                req,
                run_id="r1",
                peer_id="peer1",
                pipeline_name="Video_Captioning_RTSP_Software",
            )

        assert payload["source"] == {"uri": "rtsp://host/stream", "type": "uri"}
        assert "overlay" not in payload["destination"]["frame"]

    def test_extract_pipeline_id_success(self, server):
        assert server._extract_pipeline_id('"abc123"') == "abc123"

    def test_extract_pipeline_id_empty_raises(self, server):
        with pytest.raises(HTTPException) as exc_info:
            server._extract_pipeline_id('"   "')

        assert exc_info.value.status_code == 502
        assert "empty pipeline id" in exc_info.value.detail["message"]


class TestRunLifecycle:
    @pytest.mark.asyncio
    async def test_start_run_success_with_custom_name(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            runName="My Run",
            vlmDevice="cpu",
            modelName="InternVL2-1B",
        )

        with patch.object(
            server,
            "_resolve_pipeline_name_from_ui",
            return_value="Video_Captioning_RTSP_Software",
        ), patch.object(
            server,
            "_generate_peer_id",
            return_value="speer001",
        ), patch(
            "backend.services.pipeline_server.http_json",
            return_value='"pipe-123"',
        ) as mock_http:
            info = await server.start_run(req)

        assert info.runId == "My_Run"
        assert info.pipelineId == "pipe-123"
        assert RUNS["My_Run"].peerId == "speer001"
        start_url = mock_http.call_args.args[1]
        assert "/user_defined_pipelines/Video_Captioning_RTSP_Software" in start_url

    @pytest.mark.asyncio
    async def test_start_run_rejects_camera_source_for_non_camera_pipeline(self, server):
        req = StartRunRequest(
            rtspUrl="/dev/video0",
        )

        with patch.object(
            server,
            "_resolve_pipeline_name_from_ui",
            return_value="Video_Captioning_RTSP_Software",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await server.start_run(req)

        assert exc_info.value.status_code == 400
        assert "camera-compatible pipeline" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_start_run_rejects_camera_source_with_default_non_camera_pipeline(self, server):
        req = StartRunRequest(
            rtspUrl="/dev/video0",
        )

        with patch.object(
            server,
            "_resolve_pipeline_name_from_ui",
            return_value="Video_Captioning_RTSP_Software",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await server.start_run(req)

        assert exc_info.value.status_code == 400
        assert "camera-compatible pipeline" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_start_run_rejects_camera_source_when_already_in_use(self, server):
        RUNS["existing"] = _running_run(
            run_id="existing",
            rtsp_url="/dev/video0",
        )
        req = StartRunRequest(
            rtspUrl="/dev/video0",
        )

        with patch.object(
            server,
            "_resolve_pipeline_name_from_ui",
            return_value="Video_Captioning_Camera_Software",
        ):
            with pytest.raises(HTTPException) as exc_info:
                await server.start_run(req)

        assert exc_info.value.status_code == 409
        assert "already in use" in exc_info.value.detail["message"]

    @pytest.mark.asyncio
    async def test_start_run_without_custom_name_uses_uuid_path(self, server):
        req = StartRunRequest(
            rtspUrl="rtsp://host/stream",
            runName=None,
        )

        with patch.object(
            server,
            "_resolve_pipeline_name_from_ui",
            return_value="Video_Captioning_RTSP_Software",
        ), patch.object(
            server,
            "_generate_peer_id",
            return_value="speer002",
        ), patch(
            "backend.services.pipeline_server.uuid.uuid4",
            return_value=SimpleNamespace(hex="0123456789abcdef"),
        ), patch(
            "backend.services.pipeline_server.http_json",
            return_value='"pipe-456"',
        ):
            info = await server.start_run(req)

        assert info.runId == "0123456789"
        assert info.runName is None

    def test_list_runs_returns_all_current_runs(self, server):
        RUNS["r1"] = _running_run(run_id="r1")
        RUNS["r2"] = _running_run(run_id="r2")

        run_ids = {r.runId for r in server.list_runs()}
        assert run_ids == {"r1", "r2"}

    @pytest.mark.asyncio
    async def test_stream_ready_returns_404_for_unknown_run(self, server):
        with pytest.raises(HTTPException) as exc_info:
            await server.stream_ready("missing")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stream_ready_unreachable_returns_not_ready_without_error(self, server):
        RUNS["r1"] = _running_run(run_id="r1", peer_id="peer-r1")

        with patch(
            "backend.services.pipeline_server.asyncio.to_thread",
            AsyncMock(return_value=(False, None, 0.0)),
        ):
            result = await server.stream_ready("r1")

        assert result == {
            "runId": "r1",
            "peerId": "peer-r1",
            "ready": False,
            "state": None,
            "error": False,
        }

    @pytest.mark.asyncio
    async def test_stream_ready_unhealthy_state_marks_error(self, server):
        RUNS["r1"] = _running_run(run_id="r1", peer_id="peer-r1")

        with patch(
            "backend.services.pipeline_server.asyncio.to_thread",
            AsyncMock(return_value=(True, "error", 0.0)),
        ):
            result = await server.stream_ready("r1")

        assert result["error"] is True
        assert RUNS["r1"].status == "error"

    @pytest.mark.asyncio
    async def test_stream_ready_running_with_frames_is_ready(self, server):
        RUNS["r1"] = _running_run(run_id="r1", peer_id="peer-r1")

        with patch(
            "backend.services.pipeline_server.asyncio.to_thread",
            AsyncMock(return_value=(True, "running", 12.4)),
        ):
            result = await server.stream_ready("r1")

        assert result["ready"] is True
        assert result["error"] is False

    def test_get_run_returns_existing(self, server):
        RUNS["r1"] = _running_run(run_id="r1")
        assert server.get_run("r1").pipelineId == "pipe-r1"

    def test_get_run_raises_404_when_missing(self, server):
        with pytest.raises(HTTPException) as exc_info:
            server.get_run("nope")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_run_raises_404_when_missing(self, server):
        with pytest.raises(HTTPException) as exc_info:
            await server.stop_run("missing")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_run_removes_run_when_backend_stop_succeeds(self, server):
        RUNS["r1"] = _running_run(run_id="r1", pipeline_id="pipe-r1")

        with patch("backend.services.pipeline_server.http_json", return_value="") as mock_http:
            result = await server.stop_run("r1")

        assert result == {"status": "stopped", "runId": "r1"}
        assert "r1" not in RUNS
        assert mock_http.call_args.args[0] == "DELETE"

    @pytest.mark.asyncio
    async def test_stop_run_removes_run_even_when_backend_stop_fails(self, server):
        RUNS["r1"] = _running_run(run_id="r1", pipeline_id="pipe-r1")

        with patch("backend.services.pipeline_server.http_json", side_effect=Exception("boom")):
            result = await server.stop_run("r1")

        assert result == {"status": "stopped", "runId": "r1"}
        assert "r1" not in RUNS


class TestMetadataStreaming:
    def test_metadata_stream_returns_sse_response_with_expected_headers(self, server):
        stream = server.metadata_stream()

        assert stream.media_type == "text/event-stream"
        assert stream.headers["cache-control"] == "no-cache"
        assert stream.headers["connection"] == "keep-alive"

    @pytest.mark.asyncio
    async def test_multiplexed_metadata_generator_yields_heartbeat(self, server):
        RUNS["r1"] = _running_run(run_id="r1")

        subscriber = MagicMock()

        async def _timeout_wait_for(awaitable, timeout):
            # Close the pending coroutine so pytest does not report it un-awaited.
            awaitable.close()
            raise asyncio.TimeoutError

        with patch(
            "backend.services.pipeline_server.get_mqtt_subscriber",
            new=AsyncMock(return_value=subscriber),
        ), patch(
            "backend.services.pipeline_server.asyncio.wait_for",
            new=AsyncMock(side_effect=_timeout_wait_for),
        ):
            gen = server._multiplexed_metadata_generator()
            payload = await gen.__anext__()
            await gen.aclose()

        assert '"type": "status"' in payload
        subscriber.subscribe_to_run.assert_called_once()
        subscriber.unsubscribe_from_run.assert_called_once_with("r1")

    @pytest.mark.asyncio
    async def test_multiplexed_metadata_generator_yields_message_envelope(self, server):
        RUNS["r1"] = _running_run(run_id="r1")

        subscriber = MagicMock()

        def _subscribe_and_emit(run_id, callback):
            callback(run_id, {"caption": "car"}, 123.0)

        subscriber.subscribe_to_run.side_effect = _subscribe_and_emit

        with patch(
            "backend.services.pipeline_server.get_mqtt_subscriber",
            new=AsyncMock(return_value=subscriber),
        ):
            gen = server._multiplexed_metadata_generator()
            payload = await gen.__anext__()
            await gen.aclose()

        assert '"runId": "r1"' in payload
        assert '"caption": "car"' in payload

    @pytest.mark.asyncio
    async def test_multiplexed_metadata_generator_unsubscribes_stopped_runs(self, server):
        RUNS["r1"] = _running_run(run_id="r1")

        subscriber = MagicMock()
        heartbeat_calls = {"count": 0}

        async def _wait_for_with_state_change(awaitable, timeout):
            awaitable.close()
            heartbeat_calls["count"] += 1
            if heartbeat_calls["count"] == 1:
                RUNS.pop("r1", None)
            raise asyncio.TimeoutError

        with patch(
            "backend.services.pipeline_server.get_mqtt_subscriber",
            new=AsyncMock(return_value=subscriber),
        ), patch(
            "backend.services.pipeline_server.asyncio.wait_for",
            new=AsyncMock(side_effect=_wait_for_with_state_change),
        ):
            gen = server._multiplexed_metadata_generator()
            _ = await gen.__anext__()
            _ = await gen.__anext__()
            await gen.aclose()

        subscriber.unsubscribe_from_run.assert_called_with("r1")

    @pytest.mark.asyncio
    async def test_multiplexed_metadata_generator_callback_error_logged(self, server):
        RUNS["r1"] = _running_run(run_id="r1")

        subscriber = MagicMock()

        def _subscribe_and_emit(run_id, callback):
            callback(run_id, {"caption": "car"}, 123.0)

        subscriber.subscribe_to_run.side_effect = _subscribe_and_emit

        async def _timeout_wait_for(awaitable, timeout):
            awaitable.close()
            raise asyncio.TimeoutError

        with patch(
            "backend.services.pipeline_server.get_mqtt_subscriber",
            new=AsyncMock(return_value=subscriber),
        ), patch(
            "backend.services.pipeline_server.asyncio.get_event_loop",
            side_effect=RuntimeError("loop unavailable"),
        ), patch(
            "backend.services.pipeline_server.asyncio.wait_for",
            new=AsyncMock(side_effect=_timeout_wait_for),
        ), patch("backend.services.pipeline_server.logger.error") as mock_log_error:
            gen = server._multiplexed_metadata_generator()
            payload = await gen.__anext__()
            await gen.aclose()

        assert '"type": "status"' in payload
        mock_log_error.assert_called()

    @pytest.mark.asyncio
    async def test_multiplexed_metadata_generator_emits_error_event_on_loop_exception(self, server):
        RUNS["r1"] = _running_run(run_id="r1")

        subscriber = MagicMock()
        subscriber.subscribe_to_run.side_effect = RuntimeError("subscribe failed")

        with patch(
            "backend.services.pipeline_server.get_mqtt_subscriber",
            new=AsyncMock(return_value=subscriber),
        ), patch(
            "backend.services.pipeline_server.asyncio.sleep",
            new=AsyncMock(return_value=None),
        ):
            gen = server._multiplexed_metadata_generator()
            payload = await gen.__anext__()
            # Advance once more so code after the first error yield runs,
            # including the backoff sleep path.
            payload2 = await gen.__anext__()
            await gen.aclose()

        assert payload == ": error\n\n"
        assert payload2 == ": error\n\n"

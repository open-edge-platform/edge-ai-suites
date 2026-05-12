#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""app.py — Wires config, logging, pipelines, and metrics. Run: python app.py config.yaml"""

from __future__ import annotations

import logging
import sys
import os
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent / "src"))

from app_runner import AppRunner
from config_loader import AppConfig, ModelConfig, PipelineEntry, load_config
from log import setup_logging
from media_service import MediaService
from metrics_collector import MetricsCollector
from metrics_exporters import LogExporter, MetricsExporter, PrometheusExporter
from pipeline_manager import PipelineManager

logger = logging.getLogger(__name__)


class App(AppRunner):
    """Orchestrates config loading, logging, pipeline management, and metrics export."""

    def __init__(self, config_path: str | Path) -> None:
        """Load config, set up logging and pipeline manager."""
        self._config: AppConfig = load_config(config_path)
        setup_logging(self._config.logging)
        self._manager: PipelineManager = PipelineManager()
        self._media_list: List[MediaService] = []
        self._metrics = None
        self._metrics_enabled: bool = self._config.metrics.enabled
        self._running = False
        self._stopped = False

    def start(self) -> None:
        """Start MediaMTX, metrics, and all configured pipelines, then block until done."""
        logger.info("App starting")
        self._running = True
        self._start_mediamtx()
        self._start_metrics()
        self._launch_pipelines()
        self._install_signal_handlers()
        self._wait_for_completion()

    def stop(self) -> None:
        """Gracefully stop all pipelines, the metrics collector, and MediaMTX."""
        if self._stopped:
            return
        self._stopped = True
        logger.info("App stopping")
        self._running = False
        # Stop pipelines first — they depend on MediaMTX.
        self._manager.shutdown(graceful=False)
        if self._metrics is not None:
            self._metrics.stop()
        for media in self._media_list:
            media.stop_server()
        logger.info("App stopped")

    def _start_mediamtx(self) -> None:
        """Start dedicated MediaMTX instance(s) — one per protocol actually used.

        Each instance is configured with ONLY its own protocol enabled (rtmp/hls/srt
        disabled) so streams cannot be read via any unintended protocol.
        """
        if self._config.raw_pipeline_mode:
            raw_vals = [val for val in self._config.raw_pipelines.values() if val.strip()]
            rtsp_needed = any("rtspclientsink" in val for val in raw_vals)
            webrtc_needed = any("whipclientsink" in val for val in raw_vals)
        else:
            frames = [entry.output.frame for entry in self._config.pipelines.values()
                      if entry.output.frame is not None]
            rtsp_needed = any(frame.has_active_rtsp() for frame in frames)
            webrtc_needed = any(frame.has_active_webrtc() for frame in frames)

        if not rtsp_needed and not webrtc_needed:
            return

        mediamtx_exe = os.environ.get("MEDIAMTX_PATH")
        if not mediamtx_exe:
            logger.error(
                "MEDIAMTX_PATH environment variable is not set. "
                "Set it to the path of the mediamtx executable and restart."
            )
            return

        cfg = self._config.mediamtx
        if rtsp_needed:
            svc = MediaService(mediamtx_exe=mediamtx_exe, port=cfg.port, instance_id="rtsp")
            if not svc.launch_server(rtsp_enabled=True, webrtc_enabled=False):
                logger.warning("MediaMTX RTSP instance did not start — RTSP output may fail")
            self._media_list.append(svc)

        if webrtc_needed:
            svc = MediaService(mediamtx_exe=mediamtx_exe, port=cfg.port, instance_id="webrtc")
            if not svc.launch_server(rtsp_enabled=False, webrtc_enabled=True):
                logger.warning("MediaMTX WebRTC instance did not start — WebRTC output may fail")
            self._media_list.append(svc)

    def _start_metrics(self) -> None:
        """Create and start the MetricsCollector with a Prometheus or log exporter."""
        cfg = self._config.metrics
        exporter = (PrometheusExporter(port=cfg.prometheus.port)
                    if cfg.enabled and cfg.prometheus.enabled else LogExporter())
        self._metrics = MetricsCollector(manager=self._manager, config=cfg, exporter=exporter)
        self._metrics.start()

    def _launch_pipelines(self) -> None:
        """Launch all configured pipelines.

        In raw pipeline mode, submits each non-empty string directly to the pipeline
        manager with no source/sink tracking. In structured mode, builds a GStreamer
        launch string from config and logs the RTSP/WebRTC viewer URLs.
        """
        if self._config.raw_pipeline_mode:
            active = {name: s.strip() for name, s in self._config.raw_pipelines.items() if s.strip()}
            logger.info("raw_pipeline_mode active — launching %d pipeline(s): %s", len(active), list(active))
            for name, launch_string in active.items():
                logger.info("[%s] launch string: %s", name, launch_string)
                pid = self._manager.create(
                    launch_string=launch_string, pipeline_id=name,
                    source_element_name="src", sink_element_name="sink",
                    on_state_change=self._on_state_change,
                    on_completed=self._on_completed, on_error=self._on_error,
                )
                logger.info("Launched raw pipeline '%s'", pid)
            return

        mtx = self._config.mediamtx
        self._ensure_output_dirs()
        for name, entry in self._config.pipelines.items():
            model = self._config.models[entry.inference.model_id]
            launch_string = self._build_launch_string(name, entry, model, mtx.host_ip, mtx.port, mtx.webrtc_port)
            logger.info("[%s] launch string: %s", name, launch_string)
            pid = self._manager.create(
                launch_string=launch_string, pipeline_id=name,
                source_element_name="src", sink_element_name="sink",
                on_state_change=self._on_state_change,
                on_completed=self._on_completed, on_error=self._on_error,
            )
            logger.info("Launched pipeline '%s'", pid)
            frame = entry.output.frame
            if frame is not None:
                if frame.has_active_rtsp():
                    logger.info("[%s] RTSP stream: rtsp://%s:%d%s", name, mtx.host_ip, mtx.port, frame.path)
                if frame.has_active_webrtc():
                    logger.info("[%s] WebRTC stream: http://%s:%d/%s", name, mtx.host_ip, mtx.webrtc_port, frame.peer_id)

    def _ensure_output_dirs(self) -> None:
        """Create parent directories for any file-based metadata outputs."""
        for entry in self._config.pipelines.values():
            for sink in entry.output.metadata:
                if sink.type == "file" and sink.path:
                    Path(sink.path).parent.mkdir(parents=True, exist_ok=True)

    def _build_launch_string(self, pipeline_name: str, entry: PipelineEntry, model: ModelConfig,
                              host_ip: str = "localhost", rtsp_port: int = 8554,
                              webrtc_port: int = 8889) -> str:
        """Build a GStreamer launch string (rtsp or webrtc output, never both)."""
        element = {"detection": "gvadetect", "classification": "gvaclassify"}.get(model.type)
        if not element:
            raise NotImplementedError(f"_build_launch_string: model type {model.type!r} not implemented")

        device = model.device.upper()
        device_opts = "device=CPU" if device == "CPU" else f"device={model.device} pre-process-backend=d3d11"
        fpscounter = f"gvafpscounter "
        tail = fpscounter if device == "CPU" else f"d3d11convert ! {fpscounter}"

        if model.type == "classification":
            inference = (
                f'{element} name=classification model="{model.model}" '
                f'inference-region=full-frame pre-process-config=reverse_input_channels=yes '
                f'{device_opts} model-instance-id={entry.inference.model_id} '
                f'batch-size={model.properties["batch_size"]}'
            )
        else:
            inference = (
                f'{element} model="{model.model}" '
                f'{device_opts} name=detection model-instance-id={entry.inference.model_id} '
                f'threshold={model.properties["threshold"]} batch-size={model.properties["batch_size"]}'
            )

        meta_sinks = " ! ".join(_build_metadata_output(s) for s in entry.output.metadata)
        metadata_chain = f"queue ! gvametaconvert add-empty-results=true ! {meta_sinks} ! " if meta_sinks else ""

        parts = [_get_source_elements(entry.input, device), inference, f"{metadata_chain}queue ! gvawatermark ! {tail}"]
        frame = entry.output.frame
        if frame is not None:
            encode = "identity name=sink ! mfh264enc bitrate=2000 gop-size=15 ! h264parse"
            if frame.has_active_rtsp():
                parts.append(f"{encode} ! rtspclientsink location=rtsp://{host_ip}:{rtsp_port}{frame.path}")
            elif frame.has_active_webrtc():
                parts.append(f"{encode} ! whipclientsink signaller::whip-endpoint=http://{host_ip}:{webrtc_port}/{frame.peer_id}/whip")
        return " ! ".join(parts)


    # _wait_for_completion, _install_signal_handlers, _on_state_change,
    # _on_completed, _on_error  ->  inherited from AppRunner (utils/app_runner.py)

def _get_source_elements(cfg, device: str = "CPU") -> str:
    """Return the GStreamer source fragment string for the given InputConfig.

    Raises NotImplementedError for unrecognised input types.
    """
    if cfg.type == "file":
        return f'filesrc location="{cfg.url}" ! decodebin3 name=src'
    if cfg.type == "rtsp":
        return f'rtspsrc location="{cfg.url}" latency=200 name=src ! rtph264depay ! h264parse ! d3d11h264dec'
    if cfg.type == "camera":
        src = (
            f'gencamsrc serial={cfg.serial} pixel-format=mono8 '
            f'width=1920 height=1080 name=src'
        )
        if device == "CPU":
            return f'{src} ! videoconvert'
        else:
            return f'{src} ! d3d11upload ! d3d11convert ! video/x-raw(memory:D3D11Memory),format=NV12 '
    raise NotImplementedError(f"_get_source_elements: type {cfg.type!r} not implemented")

def _build_metadata_output(cfg) -> str:
    """Return a gvametapublish GStreamer element fragment for the given MetadataOutputConfig.

    Raises NotImplementedError for unrecognised output types.
    """
    if cfg.type == "mqtt":
        return f"gvametapublish method=mqtt topic={cfg.topic} address=tcp://{cfg.host}:{cfg.port}"
    if cfg.type == "file":
        return f'gvametapublish method=file file-path={cfg.path}'
    raise NotImplementedError(f"_build_metadata_output: type {cfg.type!r} not implemented")




def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python app.py <config.yaml>", file=sys.stderr)
        sys.exit(1)
    App(sys.argv[1]).start()


if __name__ == "__main__":
    main()

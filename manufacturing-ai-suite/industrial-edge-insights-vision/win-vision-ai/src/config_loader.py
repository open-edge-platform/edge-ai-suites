#
# Apache v2 license
# Copyright (C) 2025 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
#
"""loader.py — YAML -> validated AppConfig dataclasses. See INSTRUCTIONS.md for schema."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from exceptions import ConfigError

logger = logging.getLogger(__name__)


@dataclass
class LogConfig:
    level: str = "INFO"
    format: str = "%(asctime)s %(levelname)-7s %(name)s - %(message)s"
    file: Optional[str] = None


@dataclass
class PrometheusConfig:
    enabled: bool = True
    port: int = 8000


@dataclass
class MetricsConfig:
    enabled: bool = True
    export_interval_s: float = 5.0
    prometheus: PrometheusConfig = field(default_factory=PrometheusConfig)


@dataclass
class ModelConfig:
    name: str
    type: str
    model: str
    device: str = "CPU"
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InputConfig:
    type: str
    url: str = ""
    # camera-specific field (only used when type == "camera")
    serial: Optional[str] = None


@dataclass
class InferenceConfig:
    model_id: str


@dataclass
class FrameOutputConfig:
    type: str              # "webrtc" | "rtsp"
    peer_id: str = ""     # used when type == "webrtc"
    path: str = ""        # used when type == "rtsp"

    def has_active_rtsp(self) -> bool:
        return self.type == "rtsp"

    def has_active_webrtc(self) -> bool:
        return self.type == "webrtc"


@dataclass
class MetadataOutputConfig:
    type: str
    topic: Optional[str] = None
    path: Optional[str] = None
    port: int = 1883
    host: str = "localhost"


@dataclass
class OutputConfig:
    frame: Optional[FrameOutputConfig] = None
    metadata: List[MetadataOutputConfig] = field(default_factory=list)


@dataclass
class PipelineEntry:
    name: str
    input: InputConfig
    inference: InferenceConfig
    output: OutputConfig
    auto_start: bool = True


@dataclass
class MediaMTXConfig:
    path: str = "mediamtx"
    port: int = 8554
    webrtc_port: int = 8889
    host_ip: str = "localhost"


@dataclass
class AppConfig:
    logging: LogConfig = field(default_factory=LogConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    mediamtx: MediaMTXConfig = field(default_factory=MediaMTXConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    models: Dict[str, ModelConfig] = field(default_factory=dict)
    pipelines: Dict[str, PipelineEntry] = field(default_factory=dict)
    raw_pipelines: Dict[str, str] = field(default_factory=dict)

    @property
    def raw_pipeline_mode(self) -> bool:
        """Return True if any raw pipeline string is non-empty, activating raw mode."""
        return any(val.strip() for val in self.raw_pipelines.values())


def load_config(path: str | Path) -> AppConfig:
    """Load and validate a YAML config file, returning a fully populated AppConfig.

    Raises FileNotFoundError if the file does not exist.
    Raises ConfigError on any validation failure.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return _parse_config(raw)


def _parse_config(raw: dict) -> AppConfig:
    """Parse a raw YAML dict into a validated AppConfig.

    In raw pipeline mode (any non-empty pipeline string), skips models/pipelines parsing.
    """
    raw_section = raw.get("raw_pipelines", {})
    if isinstance(raw_section, list):
        raw_pipelines: Dict[str, str] = {f"pipeline_{idx}": val for idx, val in enumerate(raw_section) if isinstance(val, str)}
    else:
        raw_pipelines = {key: str(val) for key, val in raw_section.items() if isinstance(val, str)}

    log_cfg = _parse_log_config(raw.get("logging", {}))
    metrics_cfg = _parse_metrics_config(raw.get("metrics", {}))

    if any(val.strip() for val in raw_pipelines.values()):
        logger.info("raw_pipeline_mode active — skipping models/pipelines config validation")
        return AppConfig(logging=log_cfg, metrics=metrics_cfg, raw_pipelines=raw_pipelines)

    models = _parse_models(raw.get("models", {}))
    output = _parse_output("<global>", raw.get("output", {}), require_path=False)
    return AppConfig(
        logging=log_cfg, metrics=metrics_cfg,
        output=output, models=models,
        pipelines=_parse_pipelines(raw.get("pipelines", {}), models, output),
        raw_pipelines=raw_pipelines,
    )


def _parse_log_config(raw: dict) -> LogConfig:
    """Parse the 'logging' section into a LogConfig. Raises ConfigError for invalid levels."""
    level = raw.get("level", "INFO").upper()
    if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        raise ConfigError(f"Invalid log level: {raw.get('level')!r}")
    cfg = LogConfig(level=level, file=raw.get("file"))
    if "format" in raw:
        cfg.format = raw["format"]
    return cfg


def _parse_metrics_config(raw: dict) -> MetricsConfig:
    """Parse the 'metrics' section into a MetricsConfig. Raises ConfigError if interval <= 0."""
    interval = float(raw.get("export_interval_s", 5.0))
    if interval <= 0:
        raise ConfigError("metrics.export_interval_s must be > 0")
    prom = raw.get("prometheus", {})
    return MetricsConfig(
        enabled=bool(raw.get("enabled", True)),
        export_interval_s=interval,
        prometheus=PrometheusConfig(enabled=bool(prom.get("enabled", True)), port=int(prom.get("port", 8000))),
    )


_VALID_INPUT_TYPES= {"rtsp", "file", "camera"}
_VALID_METADATA_OUTPUT_TYPES = {"mqtt", "file"}
_VALID_DEVICES = {"CPU", "GPU", "NPU", "AUTO"}
_VALID_MODEL_TYPES = {"detection", "classification"}


def _parse_models(raw: dict) -> Dict[str, ModelConfig]:
    """Parse the 'models' section into a dict of ModelConfig objects.

    Validates that required fields are present, model type is known, device is valid,
    and the model file exists on disk. Raises ConfigError on any failure.
    """
    models: Dict[str, ModelConfig] = {}
    for name, data in raw.items():
        for req in ("type", "model"):
            if req not in data:
                raise ConfigError(f"Model '{name}' missing required field: {req!r}")
        model_type = data["type"].lower()
        if model_type not in _VALID_MODEL_TYPES:
            raise ConfigError(f"Model '{name}': type {data['type']!r} must be 'detection' or 'classification'")
        device = data.get("device", "CPU").upper()
        if device not in _VALID_DEVICES:
            logger.warning("Model '%s': unknown device %r — defaulting to CPU", name, data["device"])
            device = "CPU"
        model_path = data["model"]
        models[name] = ModelConfig(name=name, type=model_type, model=model_path, device=device,
                                   properties=dict(data.get("properties", {})))
    return models


def _parse_pipelines(raw: dict, models: Dict[str, ModelConfig], default_output: OutputConfig) -> Dict[str, PipelineEntry]:
    """Parse the 'pipelines' section into a dict of PipelineEntry objects."""
    return {name: _parse_pipeline_entry(name, data, models, default_output) for name, data in raw.items()}


def _parse_pipeline_entry(name: str, raw: dict, models: Dict[str, ModelConfig], default_output: OutputConfig) -> PipelineEntry:
    """Parse a single pipeline entry, inheriting and deriving output config from defaults.

    When no per-pipeline output section is present, RTSP path and WebRTC peer_id are
    auto-derived from the pipeline name (e.g. pipeline 'front' → path='/front').
    """
    for req in ("input", "inference"):
        if req not in raw:
            raise ConfigError(f"Pipeline '{name}' missing required section: {req!r}")

    if "output" in raw:
        output_cfg = _parse_output(name, raw["output"])
    else:
        frame = default_output.frame
        if frame is not None:
            if frame.type == "rtsp":
                frame = FrameOutputConfig(type="rtsp", path=f"/{name}")
            else:
                frame = FrameOutputConfig(type="webrtc", peer_id=name)
        output_cfg = OutputConfig(frame=frame, metadata=list(default_output.metadata))

    return PipelineEntry(
        name=name,
        input=_parse_input(name, raw["input"]),
        inference=_parse_inference(name, raw["inference"], models),
        output=output_cfg,
        auto_start=bool(raw.get("auto_start", True)),
    )


def _parse_input(pipeline_name: str, raw: dict) -> InputConfig:
    """Parse a pipeline's 'input' section. Validates type and checks file existence.

    For camera inputs, 'url' is not required; 'serial' is required instead.
    """
    if "type" not in raw:
        raise ConfigError(f"Pipeline '{pipeline_name}': input missing required field 'type'")
    input_type = raw["type"].lower()
    if input_type not in _VALID_INPUT_TYPES:
        raise ConfigError(f"Pipeline '{pipeline_name}': invalid input type {input_type!r}. Valid: {_VALID_INPUT_TYPES}")

    if input_type == "camera":
        if "serial" not in raw:
            raise ConfigError(f"Pipeline '{pipeline_name}': camera input missing required field 'serial'")
        return InputConfig(
            type=input_type,
            serial=str(raw["serial"]),
        )

    if "url" not in raw:
        raise ConfigError(f"Pipeline '{pipeline_name}': input missing required field 'url'")
    url = raw["url"]
    if input_type == "file" and not Path(url).exists():
        raise ConfigError(f"Pipeline '{pipeline_name}': input file does not exist: {url!r}")
    return InputConfig(type=input_type, url=url)


def _parse_inference(pipeline_name: str, raw: dict, models: Dict[str, ModelConfig]) -> InferenceConfig:
    """Parse a pipeline's 'inference' section and validate model_id against the models dict."""
    model_id = raw.get("model_id")
    if not model_id:
        raise ConfigError(f"Pipeline '{pipeline_name}': inference missing required field 'model_id'")
    if model_id not in models:
        raise ConfigError(f"Pipeline '{pipeline_name}': inference.model_id '{model_id}' not found in models section")
    model_path = models[model_id].model
    if not Path(model_path).exists():
        raise ConfigError(f"Pipeline '{pipeline_name}': model file not found for '{model_id}': {model_path!r}")
    return InferenceConfig(model_id=model_id)


def _parse_output(pipeline_name: str, raw: dict, require_path: bool = True) -> OutputConfig:
    """Parse an 'output' section into an OutputConfig with optional frame and metadata sinks."""
    frame_raw = raw.get("frame")
    frame = _parse_frame_output(pipeline_name, frame_raw, require_path) if frame_raw else None
    metadata = [_parse_metadata_output(pipeline_name, idx, m) for idx, m in enumerate(raw.get("metadata") or [])]
    return OutputConfig(frame=frame, metadata=metadata)


def _parse_frame_output(pipeline_name: str, raw: dict, require_path: bool = True) -> FrameOutputConfig:
    """Parse the 'output.frame' section into a FrameOutputConfig.

    Expects a 'type' field of 'webrtc' or 'rtsp', plus 'peer_id' or 'path' respectively.
    """
    frame_type = raw.get("type", "").lower()
    if frame_type not in ("rtsp", "webrtc"):
        raise ConfigError(
            f"Pipeline '{pipeline_name}': output.frame.type must be 'rtsp' or 'webrtc', got {raw.get('type')!r}"
        )
    if frame_type == "rtsp":
        path = raw.get("path", "")
        if require_path and not path:
            raise ConfigError(f"Pipeline '{pipeline_name}': output.frame (rtsp) requires 'path'")
        return FrameOutputConfig(type="rtsp", path=path)
    # webrtc
    peer_id = raw.get("peer_id", "")
    if require_path and not peer_id:
        raise ConfigError(f"Pipeline '{pipeline_name}': output.frame (webrtc) requires 'peer_id'")
    return FrameOutputConfig(type="webrtc", peer_id=peer_id)


def _parse_metadata_output(pipeline_name: str, index: int, raw: dict) -> MetadataOutputConfig:
    """Parse a single 'output.metadata' entry. Validates type, required fields, and port."""
    if "type" not in raw:
        raise ConfigError(f"Pipeline '{pipeline_name}': output.metadata[{index}] missing 'type'")
    metadata_type = raw["type"].lower()
    if metadata_type not in _VALID_METADATA_OUTPUT_TYPES:
        raise ConfigError(f"Pipeline '{pipeline_name}': invalid metadata output type {metadata_type!r}. Valid: {_VALID_METADATA_OUTPUT_TYPES}")
    topic = raw.get("topic")
    path = raw.get("path")
    if metadata_type == "mqtt" and not topic:
        raise ConfigError(f"Pipeline '{pipeline_name}': output.metadata[{index}] mqtt sink requires 'topic'")
    if metadata_type == "file" and not path:
        raise ConfigError(f"Pipeline '{pipeline_name}': output.metadata[{index}] file sink requires 'path'")
    try:
        port = int(raw.get("port", 1883))
    except (TypeError, ValueError):
        raise ConfigError(f"Pipeline '{pipeline_name}': output.metadata[{index}].port must be an integer")
    host = str(raw.get("host", "localhost"))
    return MetadataOutputConfig(type=metadata_type, topic=topic, path=path, port=port, host=host)
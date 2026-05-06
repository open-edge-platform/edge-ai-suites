from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import requests

from backend_mvp.device_profiles import resolve_pipeline_settings


@dataclass(frozen=True)
class DLSPSControllerConfig:
    base_url: str
    health_endpoint: str = "/health"
    list_pipelines_endpoint: str = "/pipelines"
    start_endpoint_template: str = "/pipelines/{name}/{version}"
    status_endpoint_template: str = "/pipelines/{name}/{version}/{instance_id}/status"
    stop_endpoint_template: str = "/pipelines/{name}/{version}/{instance_id}"
    generic_status_endpoint_template: str = "/pipelines/{instance_id}/status"
    generic_stop_endpoint_template: str = "/pipelines/{instance_id}"
    legacy_start_endpoint: str = "/pipelines/start"
    legacy_stop_endpoint: str = "/pipelines/stop"
    legacy_status_endpoint: str = "/pipelines/status"
    frame_endpoint: str = "/pipelines/frame/latest"
    pipeline_name: str | None = None
    pipeline_version: str | None = None
    timeout_seconds: float = 2.0
    detections_path: str = "/shared/detections.jsonl"
    # MQTT destination settings (used when inference_mode is "dlsps")
    mqtt_broker: str = ""
    mqtt_topic: str = "nicu/detections"


class DLSPSController:
    """Small REST wrapper for DLSPS lifecycle actions."""

    def __init__(self, config: DLSPSControllerConfig) -> None:
        self._cfg = config
        self._pipeline_id: str | None = None
        self._pipeline_name: str | None = config.pipeline_name
        self._pipeline_version: str | None = config.pipeline_version
        self._resolved_settings: dict | None = None
        # Internal service calls must bypass host proxy env vars
        # so docker-compose DNS names resolve within the bridge network.
        self._session = requests.Session()
        self._session.trust_env = False

    def _base(self) -> str:
        return self._cfg.base_url.rstrip("/")

    def _resolve_pipeline_identity(self) -> bool:
        if self._pipeline_name and self._pipeline_version:
            return True

        try:
            url = f"{self._base()}{self._cfg.list_pipelines_endpoint}"
            response = self._session.get(url, timeout=self._cfg.timeout_seconds)
            if not response.ok:
                return False
            data = response.json()
            if isinstance(data, list) and data:
                first = data[0] if isinstance(data[0], dict) else {}
                name = first.get("name")
                version = first.get("version")
                if isinstance(name, str) and isinstance(version, str):
                    self._pipeline_name = name
                    self._pipeline_version = version
                    return True
            return False
        except Exception:
            return False

    @staticmethod
    def _runtime_status_from_state(state: str) -> str:
        mapping = {
            "RUNNING": "running",
            "COMPLETED": "completed",
            "ERROR": "error",
            "ABORTED": "completed",
        }
        return mapping.get(state, "unknown")

    @staticmethod
    def _extract_instance_id(response: requests.Response) -> str | None:
        content_type = response.headers.get("Content-Type", "")
        try:
            if "application/json" in content_type:
                body = response.json()
                if isinstance(body, str):
                    return body
                if isinstance(body, dict):
                    for key in ("instance_id", "pipeline_id", "id"):
                        value = body.get(key)
                        if isinstance(value, (str, int)):
                            return str(value)
        except Exception:
            pass

        text = (response.text or "").strip()
        if text:
            # Handle quoted JSON-string responses like "abc123".
            try:
                maybe = json.loads(text)
                if isinstance(maybe, str):
                    return maybe
            except Exception:
                pass
            return text.strip('"')
        return None

    def _build_start_payload(self, resolved_pipeline_path: str, user_overrides: dict | None = None) -> dict:
        """Build PipelineRequest payload expected by newer DLSPS APIs.

        We derive the source from the resolved NICU pipeline manifest.
        For relative paths we target the dlsps-mounted /data directory.

        When using the multi-model pipeline (nicu_tee), we set individual
        model parameters for each gvadetect element.

        ``user_overrides`` may contain:
          - video_file: uploaded filename → /data/uploads/<name>
          - roi: {top, left, bottom, right} for rPPG face ROI
          - devices: {detect, rppg, action} device overrides
        """
        overrides = user_overrides or {}
        payload: dict = {}
        try:
            manifest = json.loads(Path(resolved_pipeline_path).read_text(encoding="utf-8"))
            source = manifest.get("source", {}) if isinstance(manifest, dict) else {}
            source_path = source.get("path") if isinstance(source, dict) else None
            if isinstance(source_path, str) and source_path.strip():
                if source_path.startswith("/"):
                    container_path = source_path
                else:
                    container_path = f"/data/{Path(source_path).name}"
                payload["source"] = {
                    "type": "uri",
                    "uri": f"file://{container_path}",
                }

            # User-uploaded video overrides the manifest source
            uploaded = overrides.get("video_file")
            if isinstance(uploaded, str) and uploaded.strip():
                payload["source"] = {
                    "type": "uri",
                    "uri": f"file:///data/uploads/{uploaded}",
                }

            device = manifest.get("device", "CPU") if isinstance(manifest, dict) else "CPU"
            model_paths = manifest.get("model_paths", []) if isinstance(manifest, dict) else []
            analytics = manifest.get("analytics", {}) if isinstance(manifest, dict) else {}

            # Per-model device targeting — defaults from DEVICE_ENV profile env vars
            detect_device = analytics.get("detect_device", os.environ.get("DETECTION_DEVICE", "GPU"))
            rppg_device = analytics.get("rppg_device", os.environ.get("RPPG_DEVICE", "CPU"))
            action_device = analytics.get("action_device", os.environ.get("ACTION_DEVICE", "NPU"))

            # Apply user device overrides
            user_devices = overrides.get("devices")
            if isinstance(user_devices, dict):
                detect_device = user_devices.get("detect", detect_device)
                rppg_device = user_devices.get("rppg", rppg_device)
                action_device = user_devices.get("action", action_device)

            # Resolve optimal pipeline settings for the selected devices
            resolved = resolve_pipeline_settings({
                "detect": detect_device,
                "rppg": rppg_device,
                "action": action_device,
            })
            # Store resolved settings so the backend can expose them via API
            self._resolved_settings = resolved

            # Check if this is the multi-model pipeline (nicu_tee)
            if self._pipeline_version == "nicu_tee":
                # Derive model paths from analytics section or model_paths list
                person_model = analytics.get("person_model", model_paths[0] if len(model_paths) > 0 else "")
                patient_model = analytics.get("patient_model", model_paths[1] if len(model_paths) > 1 else "")
                latch_model = analytics.get("latch_model", model_paths[2] if len(model_paths) > 2 else "")

                if person_model and patient_model and latch_model:
                    # Build optimized detect properties from resolved device settings
                    detect_props_base: dict[str, str] = {"device": detect_device}
                    detect_opts = resolved["detect"].get("inference_options", "")
                    if detect_opts:
                        detect_props_base["ie-config"] = detect_opts.replace("ie-config=", "")

                    payload["parameters"] = {
                        "person-detect-properties": {
                            "model": f"/models/{Path(person_model).name}",
                            **detect_props_base,
                        },
                        "patient-detect-properties": {
                            "model": f"/models/{Path(patient_model).name}",
                            **detect_props_base,
                        },
                        "latch-detect-properties": {
                            "model": f"/models/{Path(latch_model).name}",
                            **detect_props_base,
                        },
                        "mqtt_publisher": {
                            "publish_frame": True,
                            "topic": self._cfg.mqtt_topic,
                        },
                        "rppg_callback": {
                            "model_path": os.environ.get("RPPG_MODEL", "/models/rppg/mtts_can.xml"),
                            "device": rppg_device,
                            "roi_top": float(overrides.get("roi", {}).get("top", 0.10)),
                            "roi_left": float(overrides.get("roi", {}).get("left", 0.30)),
                            "roi_bottom": float(overrides.get("roi", {}).get("bottom", 0.56)),
                            "roi_right": float(overrides.get("roi", {}).get("right", 0.70)),
                        },
                        "action_callback": {
                            "encoder_model": os.environ.get("ACTION_ENCODER", "/models/action/FP32/action-recognition-0001-encoder.xml"),
                            "decoder_model": os.environ.get("ACTION_DECODER", "/models/action/FP32/action-recognition-0001-decoder.xml"),
                            "labels_file": "/models/action/kinetics.txt",
                            "device": action_device,
                        },
                    }
            else:
                # Single-model pipeline: original behavior
                person_model = analytics.get("person_model") if isinstance(analytics, dict) else None
                if isinstance(person_model, str) and person_model.strip():
                    payload["parameters"] = {
                        "detection-properties": {
                            "model": f"/models/{Path(person_model).name}",
                            "device": device,
                        }
                    }

            # MQTT destination is hardcoded in the pipeline config (config.json).
            # File-based fallback still uses REST destination.
            mqtt_broker = self._cfg.mqtt_broker
            if not mqtt_broker:
                detections_path = self._cfg.detections_path
                if detections_path:
                    payload["destination"] = {
                        "metadata": {
                            "type": "file",
                            "path": detections_path,
                        }
                    }
        except Exception:
            # Keep payload empty as a safe fallback for older/default pipelines.
            pass
        return payload

    def is_reachable(self) -> bool:
        # /health is not available on all DLSPS versions; fall back to /pipelines
        for endpoint in [self._cfg.health_endpoint, self._cfg.list_pipelines_endpoint]:
            url = f"{self._base()}{endpoint}"
            try:
                response = self._session.get(url, timeout=self._cfg.timeout_seconds)
                if response.ok:
                    return True
            except Exception:
                continue
        return False

    def start(self, resolved_pipeline_path: str, user_overrides: dict | None = None) -> tuple[bool, str]:
        payload = self._build_start_payload(resolved_pipeline_path, user_overrides)

        if self._resolve_pipeline_identity() and self._pipeline_name and self._pipeline_version:
            url = f"{self._base()}{self._cfg.start_endpoint_template.format(name=self._pipeline_name, version=self._pipeline_version)}"
            try:
                response = self._session.post(url, json=payload, timeout=self._cfg.timeout_seconds)
                if response.ok:
                    self._pipeline_id = self._extract_instance_id(response)
                    return True, "started"
                # For contract mismatches keep legacy fallback below.
                if response.status_code not in {404, 405}:
                    return False, f"DLSPS start failed: {response.status_code} {response.text}"
            except Exception as exc:
                return False, f"DLSPS start exception: {exc}"

        # Legacy fallback for older servers.
        legacy_url = f"{self._base()}{self._cfg.legacy_start_endpoint}"
        legacy_payload = {"pipeline_path": resolved_pipeline_path}
        try:
            response = self._session.post(legacy_url, json=legacy_payload, timeout=self._cfg.timeout_seconds)
            if response.ok:
                self._pipeline_id = self._extract_instance_id(response)
                return True, "started"
            return False, f"DLSPS start failed: {response.status_code} {response.text}"
        except Exception as exc:
            return False, f"DLSPS start exception: {exc}"

    def status(self) -> tuple[bool, dict]:
        # Preferred: generic instance status endpoint /pipelines/{instance_id}/status
        # This works on DLSPS 2025.2+ where the name/version-scoped endpoint may return 400.
        if self._pipeline_id:
            url = f"{self._base()}{self._cfg.generic_status_endpoint_template.format(instance_id=self._pipeline_id)}"
            try:
                response = self._session.get(url, timeout=self._cfg.timeout_seconds)
                if response.ok:
                    data = response.json() if response.headers.get("Content-Type", "").startswith("application/json") else {}
                    if isinstance(data, dict):
                        state = str(data.get("state", ""))
                        runtime_status = self._runtime_status_from_state(state)
                        return True, {
                            "status": runtime_status,
                            "runtime_status": runtime_status,
                            "fps": float(data.get("avg_fps", 0.0) or 0.0),
                            "latency_ms": float(data.get("latency_ms", 0.0) or 0.0),
                            "frame_count": int(data.get("frame_count", 0) or 0),
                        }
                elif response.status_code not in {400, 404, 405}:
                    return False, {"error": f"DLSPS status failed: {response.status_code} {response.text}"}
            except Exception as exc:
                return False, {"error": f"DLSPS status exception: {exc}"}

        # Legacy fallback.
        legacy_url = f"{self._base()}{self._cfg.legacy_status_endpoint}"
        payload = {"pipeline_id": self._pipeline_id} if self._pipeline_id else None
        try:
            response = self._session.get(legacy_url, params=payload, timeout=self._cfg.timeout_seconds)
            if not response.ok:
                return False, {"error": f"DLSPS status failed: {response.status_code} {response.text}"}
            data = response.json() if response.headers.get("Content-Type", "").startswith("application/json") else {}
            if isinstance(data, dict):
                return True, data
            return True, {"status": "unknown"}
        except Exception as exc:
            return False, {"error": f"DLSPS status exception: {exc}"}

    def get_frame(self) -> tuple[bool, bytes | None]:
        """Fetch the latest JPEG frame from DLSPS.

        Returns (True, jpeg_bytes) on success, (False, None) otherwise.
        Failures are treated as transient so the caller can skip the frame
        without changing lifecycle state.
        """
        url = f"{self._base()}{self._cfg.frame_endpoint}"
        params = {"pipeline_id": self._pipeline_id} if self._pipeline_id else None
        try:
            response = self._session.get(url, params=params, timeout=self._cfg.timeout_seconds)
            if response.ok and response.content:
                return True, response.content
            return False, None
        except Exception:
            return False, None

    def stop(self) -> tuple[bool, str]:
        # Preferred: generic instance endpoint /pipelines/{instance_id}
        if self._pipeline_id:
            url = f"{self._base()}{self._cfg.generic_stop_endpoint_template.format(instance_id=self._pipeline_id)}"
            try:
                response = self._session.delete(url, timeout=self._cfg.timeout_seconds)
                if response.ok:
                    self._pipeline_id = None
                    return True, "stopped"
                if response.status_code not in {400, 404, 405}:
                    return False, f"DLSPS stop failed: {response.status_code} {response.text}"
            except Exception as exc:
                return False, f"DLSPS stop exception: {exc}"

        # Fallback: name/version-scoped endpoint.
        if self._pipeline_id and self._pipeline_name and self._pipeline_version:
            url = f"{self._base()}{self._cfg.stop_endpoint_template.format(name=self._pipeline_name, version=self._pipeline_version, instance_id=self._pipeline_id)}"
            try:
                response = self._session.delete(url, timeout=self._cfg.timeout_seconds)
                if response.ok:
                    self._pipeline_id = None
                    return True, "stopped"
                if response.status_code not in {400, 404, 405}:
                    return False, f"DLSPS stop failed: {response.status_code} {response.text}"
            except Exception as exc:
                return False, f"DLSPS stop exception: {exc}"

        # Legacy fallback.
        legacy_url = f"{self._base()}{self._cfg.legacy_stop_endpoint}"
        payload = {"pipeline_id": self._pipeline_id} if self._pipeline_id else None
        try:
            response = self._session.post(legacy_url, json=payload, timeout=self._cfg.timeout_seconds)
            if response.ok:
                self._pipeline_id = None
                return True, "stopped"
            return False, f"DLSPS stop failed: {response.status_code} {response.text}"
        except Exception as exc:
            return False, f"DLSPS stop exception: {exc}"

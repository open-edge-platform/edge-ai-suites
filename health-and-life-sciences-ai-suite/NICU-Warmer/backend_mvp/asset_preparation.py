from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json
import shlex
import subprocess
import urllib.request

import yaml


@dataclass(frozen=True)
class PreparationResult:
    checks: dict[str, bool]
    errors: list[dict[str, str]]
    resolved_manifest: dict[str, Any]


REASON_CONFIG_NOT_FOUND = "CONFIG_NOT_FOUND"
REASON_MISSING_MODEL = "MISSING_MODEL"
REASON_MISSING_VIDEO = "MISSING_VIDEO"
REASON_MISSING_PIPELINE_TEMPLATE = "MISSING_PIPELINE_TEMPLATE"
REASON_INVALID_PIPELINE_CONFIG = "INVALID_PIPELINE_CONFIG"
REASON_RPPG_DOWNLOAD_FAILED = "RPPG_DOWNLOAD_FAILED"
REASON_RPPG_CONVERSION_FAILED = "RPPG_CONVERSION_FAILED"
REASON_RPPG_ARTIFACT_MISSING = "RPPG_ARTIFACT_MISSING"


def reason(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}


class AssetPreparationService:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path

    def load_config(self) -> dict[str, Any]:
        if not self._config_path.exists():
            raise FileNotFoundError(
                f"{REASON_CONFIG_NOT_FOUND}: Config not found: {self._config_path}"
            )
        with self._config_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def prepare(self) -> PreparationResult:
        cfg = self.load_config()
        prep = cfg.get("preparation", {})
        dlsps_cfg = cfg.get("dlsps", {})

        model_paths = [Path(p) for p in prep.get("model_paths", [])]
        video_path = Path(prep.get("video_path", ""))
        pipeline_template = Path(prep.get("pipeline_template", ""))
        resolved_pipeline = Path(prep.get("resolved_pipeline", ""))

        checks = {
            "models_ready": bool(model_paths),
            "video_ready": bool(str(video_path)),
            "pipeline_ready": bool(str(pipeline_template) and str(resolved_pipeline)),
            "dlsps_reachable": False,
        }
        errors: list[dict[str, str]] = []

        for model in model_paths:
            if not model.exists():
                checks["models_ready"] = False
                errors.append(reason(REASON_MISSING_MODEL, f"Missing model: {model}"))

        if not video_path.exists():
            checks["video_ready"] = False
            errors.append(reason(REASON_MISSING_VIDEO, f"Missing video: {video_path}"))

        if not pipeline_template.exists():
            checks["pipeline_ready"] = False
            errors.append(
                reason(
                    REASON_MISSING_PIPELINE_TEMPLATE,
                    f"Missing pipeline template: {pipeline_template}",
                )
            )

        loop_cfg = dlsps_cfg.get("loop", True)
        loop_enabled = True
        loop_max = -1
        if isinstance(loop_cfg, dict):
            loop_enabled = bool(loop_cfg.get("enabled", True))
            loop_max = int(loop_cfg.get("max_loops", -1))
        elif isinstance(loop_cfg, bool):
            loop_enabled = loop_cfg

        resolved_manifest = {
            "video_path": str(video_path),
            "model_paths": [str(m) for m in model_paths],
            "device": dlsps_cfg.get("device", "CPU"),
            "thresholds": dlsps_cfg.get("thresholds", {}),
            "loop": {
                "enabled": loop_enabled,
                "max_loops": loop_max,
            },
            "dlsps_base_url": dlsps_cfg.get("base_url", "http://localhost:8080"),
        }

        rppg_result = self._prepare_rppg_assets(prep)
        if rppg_result["errors"]:
            errors.extend(rppg_result["errors"])
            checks["pipeline_ready"] = False
        if rppg_result["artifacts"]:
            resolved_manifest["rppg"] = rppg_result["artifacts"]

        if checks["pipeline_ready"]:
            template_text = pipeline_template.read_text(encoding="utf-8")
            # Minimal placeholder interpolation for early MVP scaffolding.
            if model_paths:
                template_text = template_text.replace("{{PERSON_MODEL_PATH}}", str(model_paths[0]))
            if len(model_paths) > 1:
                template_text = template_text.replace("{{PATIENT_MODEL_PATH}}", str(model_paths[1]))
            if len(model_paths) > 2:
                template_text = template_text.replace("{{LATCH_MODEL_PATH}}", str(model_paths[2]))
            template_text = template_text.replace("{{VIDEO_PATH}}", str(video_path))
            template_text = template_text.replace(
                "{{RPPG_MODEL_PATH}}",
                prep.get("rppg_model_path", rppg_result["artifacts"].get("xml", "/models/rppg/mtts_can.xml")),
            )
            template_text = template_text.replace("{{LOOP_ENABLED}}", "true" if loop_enabled else "false")
            template_text = template_text.replace("{{LOOP_MAX}}", str(loop_max))
            resolved_pipeline.parent.mkdir(parents=True, exist_ok=True)
            resolved_pipeline.write_text(template_text, encoding="utf-8")
            resolved_manifest["resolved_pipeline"] = str(resolved_pipeline)

            manifest_path = resolved_pipeline.with_suffix(".manifest.json")
            manifest_path.write_text(json.dumps(resolved_manifest, indent=2), encoding="utf-8")
        else:
            errors.append(
                reason(
                    REASON_INVALID_PIPELINE_CONFIG,
                    "Pipeline cannot be resolved because required inputs are missing",
                )
            )

        return PreparationResult(checks=checks, errors=errors, resolved_manifest=resolved_manifest)

    def _prepare_rppg_assets(self, prep_cfg: dict[str, Any]) -> dict[str, Any]:
        rppg_cfg = prep_cfg.get("rppg", {})
        xml_path = Path(prep_cfg.get("rppg_model_path", "/models/rppg/mtts_can.xml"))
        bin_path = xml_path.with_suffix(".bin")

        result = {
            "errors": [],
            "artifacts": {
                "xml": str(xml_path),
                "bin": str(bin_path),
            },
        }

        if not rppg_cfg.get("enabled", False):
            if xml_path.exists() and bin_path.exists():
                return result
            return result

        hdf5_path = Path(rppg_cfg.get("hdf5_path", ""))
        hdf5_url = rppg_cfg.get("hdf5_url")
        converter_command = rppg_cfg.get("converter_command", [])
        if isinstance(converter_command, str):
            converter_command = shlex.split(converter_command)

        try:
            if not hdf5_path.exists() and hdf5_url:
                hdf5_path.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(hdf5_url, hdf5_path)
        except Exception as exc:
            result["errors"].append(
                reason(REASON_RPPG_DOWNLOAD_FAILED, f"Failed to download rPPG model: {exc}")
            )
            return result

        if not hdf5_path.exists():
            result["errors"].append(
                reason(REASON_RPPG_DOWNLOAD_FAILED, f"rPPG HDF5 model missing: {hdf5_path}")
            )
            return result

        if not (xml_path.exists() and bin_path.exists()):
            if not converter_command:
                result["errors"].append(
                    reason(
                        REASON_RPPG_CONVERSION_FAILED,
                        "rPPG conversion command not configured and IR artifacts are missing",
                    )
                )
                return result

            xml_path.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                part.format(
                    hdf5_path=str(hdf5_path),
                    ir_xml_path=str(xml_path),
                    ir_bin_path=str(bin_path),
                )
                for part in converter_command
            ]
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            except Exception as exc:
                result["errors"].append(
                    reason(REASON_RPPG_CONVERSION_FAILED, f"rPPG conversion failed to run: {exc}")
                )
                return result

            if proc.returncode != 0:
                result["errors"].append(
                    reason(
                        REASON_RPPG_CONVERSION_FAILED,
                        f"rPPG conversion failed (exit {proc.returncode}): {proc.stderr.strip()}",
                    )
                )
                return result

        if not xml_path.exists() or not bin_path.exists():
            result["errors"].append(
                reason(
                    REASON_RPPG_ARTIFACT_MISSING,
                    f"Missing converted rPPG artifacts: xml={xml_path.exists()} bin={bin_path.exists()}",
                )
            )

        return result

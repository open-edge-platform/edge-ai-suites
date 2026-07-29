import json
from pathlib import Path
from typing import List, Dict
from fastapi import HTTPException
from ..config import PIPELINE_NAME, PIPELINE_SERVER_URL, ENABLE_DETECTION_PIPELINE
from ..models import ModelInfo
from .http_client import http_json

def _infer_pipeline_device(name: str) -> str:
    """Infer target device from the pipeline name.

    DL Streamer pipeline naming convention:
      *_Hardware  → gpu
      *_Software  → cpu
      anything else → any
    """
    upper = name.upper()
    if upper.endswith("_HARDWARE"):
        return "gpu"
    if upper.endswith("_SOFTWARE"):
        return "cpu"
    return "any"


def _gpu_device_exists() -> bool:
    """Detect whether a compute-capable GPU render device is available."""
    dri_dir = Path("/dev/dri")
    if not dri_dir.exists() or not dri_dir.is_dir():
        return False
    # Prefer render nodes for inference-capable device access.
    # Card nodes alone are display-oriented and can exist on systems
    # where GPU compute is not usable for this workload.
    return any(dri_dir.glob("renderD*"))


def has_gpu_device() -> bool:
    """Public helper for GPU capability checks used by API routes."""
    return _gpu_device_exists()


def _npu_device_exists() -> bool:
    """Detect whether an NPU accelerator device node is available."""
    accel_dir = Path("/dev/accel")
    if not accel_dir.exists() or not accel_dir.is_dir():
        return False
    return any(accel_dir.glob("accel*"))


def has_npu_device() -> bool:
    """Public helper for NPU capability checks used by API routes."""
    return _npu_device_exists()


def _default_pipeline_names(gpu_available: bool) -> set[str]:
    """Return preferred default pipeline names for current hardware."""
    if gpu_available:
        return {
            "Video_Captioning_Hardware",
            "Video_Captioning_RTSP_Hardware",
            "Video_Captioning_Camera_Hardware",
        }
    return {
        "Video_Captioning_Software",
        "Video_Captioning_RTSP_Software",
        "Video_Captioning_Camera_Software",
    }


def _fallback_pipeline_name(gpu_available: bool) -> str:
    """Return a fallback pipeline name consistent with detected GPU availability."""
    if not gpu_available and PIPELINE_NAME.endswith("_Hardware"):
        return PIPELINE_NAME[: -len("_Hardware")] + "_Software"
    return PIPELINE_NAME


def discover_models(root: Path) -> List[ModelInfo]:
    """Discover available models from the models directory.

        Expected layout:
            - ov_models/<device>/<model>

    Returns a list of ModelInfo objects with model name and device tag.
    """
    if not root.exists():
        return []

    valid_devices = {"cpu", "gpu", "npu"}
    model_file_suffixes = {".xml", ".bin", ".json"}
    models: List[ModelInfo] = []
    seen: set[tuple[str, str]] = set()

    def _append_model(name: str, device: str) -> None:
        key = (name, device)
        if key in seen:
            return
        seen.add(key)
        models.append(ModelInfo(name=name, device=device))

    for entry in sorted(root.iterdir()):
        if entry.name.startswith("."):
            continue

        # New flattened layout: ov_models/<device>/<model>
        entry_device = entry.name.lower()
        if entry.is_dir() and entry_device in valid_devices:
            for model_entry in sorted(entry.iterdir()):
                if model_entry.name.startswith("."):
                    continue
                if model_entry.is_dir():
                    _append_model(model_entry.name, entry_device)
                elif model_entry.suffix.lower() in model_file_suffixes:
                    _append_model(model_entry.name, entry_device)
            continue

        # Ignore entries outside the expected per-device layout.
        continue

    models.sort(key=lambda m: (m.name.lower(), m.device))
    return models


def discover_detection_models(root: Path) -> List[str]:
    """Discover available detection models from the detection models directory."""
    if not root.exists():
        return []
    models: List[str] = []
    for entry in sorted(root.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            # Check if this directory has the expected structure: model_name/public/model_name
            public_dir = entry / "public"
            if public_dir.exists() and public_dir.is_dir():
                # Check if there's a subdirectory with the same name as the parent
                model_subdir = public_dir / entry.name
                if model_subdir.exists() and model_subdir.is_dir():
                    models.append(entry.name)
    return models


def is_detection_pipeline(item: dict) -> bool:
    """Check if the given pipeline item represents a detection pipeline."""
    props = item.get("parameters", {}).get("properties", {})
    if isinstance(props, dict):
        # Any explicit detection fields
        detection_keys = {
            "detection_model_name",
            "detection_threshold",
        }
        # Either keys exist, or any key startswith 'detection_'
        if any(k in props for k in detection_keys):
            return True
        if any(
            isinstance(k, str) and k.lower().startswith("detection_")
            for k in props.keys()
        ):
            return True

    return False


def _infer_detection_from_name(pipeline_name: str) -> bool:
    """Best-effort fallback when payload lacks structured parameter metadata."""
    name = (pipeline_name or "").strip().lower()
    if not name:
        return False
    return "_detection_" in name or name.startswith("detection_") or name.endswith("_detection")


def discover_pipelines_remote() -> List[Dict[str, str]]:
    """
    Discover available pipelines from the pipeline server and return a List of dicts:
    {
      "pipeline_name": <name>,
      "pipeline_display_name": <display_name>,
      "pipeline_type": "detection" | "non-detection",
      "pipeline_default": true | false,
      "device": "cpu" | "gpu" | "npu" | "any"
    }

    Behavior:
    - Normalizes payload that may be List[str], List[dict], or dict with 'pipelines'/'items'
    - Classifies using is_detection_pipeline(item) when item is a dict
    - Defaults string-only items to 'non-detection' (no metadata to inspect)
    - Optionally filters out detection pipelines when ENABLE_DETECTION_PIPELINE is False
    - Infers device from pipeline name suffix (_Software/_Hardware)
    """
    url = f"{PIPELINE_SERVER_URL.rstrip('/')}/pipelines"
    try:
        raw = http_json("GET", url)
        payload = json.loads(raw)

        gpu_available = _gpu_device_exists()

        # Normalize to a List of items
        if isinstance(payload, List):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("pipelines") or payload.get("items") or []
        else:
            items = []

        if not isinstance(items, List):
            fallback_name = _fallback_pipeline_name(gpu_available)
            # Fallback to a single default pipeline
            # Optional filtering: if detection were disabled, 'non-detection' remains
            return [
                {
                    "pipeline_name": fallback_name,
                    "pipeline_display_name": fallback_name,
                    "pipeline_type": "non-detection",
                    "pipeline_default": True,
                    "device": _infer_pipeline_device(fallback_name),
                }
            ]

        results: List[Dict[str, str]] = []

        for item in items:
            # Determine pipeline name
            if isinstance(item, str):
                name = item
                # String-only payloads have no parameter schema; infer by name.
                pipeline_type = "detection" if _infer_detection_from_name(name) else "non-detection"
            elif isinstance(item, dict):
                # Preserve your original preference for 'version' as name
                if isinstance(item.get("version"), str):
                    name = item["version"]
                elif isinstance(item.get("name"), str):
                    name = item["name"]
                elif isinstance(item.get("id"), str):
                    name = item["id"]
                else:
                    # No usable identifier
                    continue

                pipeline_type = (
                    "detection" if is_detection_pipeline(item) else "non-detection"
                )
                if pipeline_type == "non-detection" and _infer_detection_from_name(name):
                    pipeline_type = "detection"
            else:
                continue

            results.append(
                {
                    "pipeline_name": name,
                    "pipeline_display_name": name,
                    "pipeline_type": pipeline_type,
                    "device": _infer_pipeline_device(name),
                }
            )

        # Optional filtering based on your existing flag
        if not ENABLE_DETECTION_PIPELINE:
            results = [r for r in results if r["pipeline_type"] != "detection"]

        # If GPU is unavailable, keep only software/CPU pipelines.
        if not gpu_available:
            results = [r for r in results if r["device"] in {"cpu", "any"}]

        preferred_defaults = _default_pipeline_names(gpu_available)
        for row in results:
            row["pipeline_default"] = row["pipeline_name"] in preferred_defaults

        if results and not any(r["pipeline_default"] for r in results):
            if not gpu_available:
                # Prefer a non-GPU fallback when GPU is not available.
                for row in results:
                    if "_GPU" not in row["pipeline_name"].upper():
                        row["pipeline_default"] = True
                        break

        if results and not any(r["pipeline_default"] for r in results):
            # Fall back to configured default if preferred defaults are not present.
            for row in results:
                if row["pipeline_name"] == PIPELINE_NAME:
                    row["pipeline_default"] = True
                    break

        # Fallback if nothing usable left
        if not results:
            fallback_name = _fallback_pipeline_name(gpu_available)
            return [
                {
                    "pipeline_name": fallback_name,
                    "pipeline_display_name": fallback_name,
                    "pipeline_type": "non-detection",
                    "pipeline_default": True,
                    "device": _infer_pipeline_device(fallback_name),
                }
            ]

        return results

    except HTTPException:
        raise
    except Exception:
        gpu_available = _gpu_device_exists()
        fallback_name = _fallback_pipeline_name(gpu_available)
        # Conservative fallback for parse / unexpected errors
        return [
            {
                "pipeline_name": fallback_name,
                "pipeline_display_name": fallback_name,
                "pipeline_type": "non-detection",
                "pipeline_default": True,
                "device": _infer_pipeline_device(fallback_name),
            }
        ]
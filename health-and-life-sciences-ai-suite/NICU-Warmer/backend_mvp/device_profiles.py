"""Device optimization profiles for NICU Warmer.

When a user selects a device (CPU/GPU/NPU) from the UI, this module provides
the optimal pipeline settings for that device — decode element, pre-process
backend, inference options, and model precision.

The lookup is used at runtime by dlsps_controller when building pipeline
requests, so settings adapt automatically to the user's device choice.
"""

from __future__ import annotations

# Per-device optimal settings for the GStreamer/DL Streamer pipeline.
# Each key is a device name (CPU, GPU, NPU).
DEVICE_SETTINGS: dict[str, dict] = {
    "CPU": {
        "decode": "decodebin3",
        "pre_process": "pre-process-backend=opencv",
        "inference_options": "ie-config=CPU_THROUGHPUT_STREAMS=2 nireq=2",
        "precision": "FP32",
    },
    "GPU": {
        "decode": 'decodebin3 ! vapostproc ! "video/x-raw(memory:VAMemory)"',
        "pre_process": "pre-process-backend=va-surface-sharing",
        "inference_options": "ie-config=GPU_THROUGHPUT_STREAMS=2 nireq=2",
        "precision": "FP32",
    },
    "NPU": {
        "decode": "decodebin3",
        "pre_process": "pre-process-backend=ie",
        "inference_options": "",
        "precision": "FP32",
    },
}


def get_device_settings(device: str) -> dict:
    """Return optimal pipeline settings for the given device.

    Falls back to CPU settings for unknown devices.
    """
    return DEVICE_SETTINGS.get(device.upper(), DEVICE_SETTINGS["CPU"])


def resolve_pipeline_settings(devices: dict[str, str]) -> dict:
    """Given per-workload device assignments, resolve the optimal pipeline settings.

    Args:
        devices: {"detect": "GPU", "rppg": "CPU", "action": "NPU"}

    Returns a dict with the resolved settings for each component:
        {
            "detect": {device settings for detection device},
            "rppg": {device settings for rppg device},
            "action": {device settings for action device},
            "decode": best decode element for the detection device (primary pipeline),
            "pre_process": best pre-process for the detection device,
        }
    """
    detect_dev = devices.get("detect", "GPU").upper()
    rppg_dev = devices.get("rppg", "CPU").upper()
    action_dev = devices.get("action", "NPU").upper()

    detect_settings = get_device_settings(detect_dev)
    rppg_settings = get_device_settings(rppg_dev)
    action_settings = get_device_settings(action_dev)

    # The decode element and pre-process are driven by the detection device
    # since gvadetect is the primary pipeline consumer of decoded frames.
    return {
        "detect": detect_settings,
        "rppg": rppg_settings,
        "action": action_settings,
        "decode": detect_settings["decode"],
        "pre_process": detect_settings["pre_process"],
        "detect_device": detect_dev,
        "rppg_device": rppg_dev,
        "action_device": action_dev,
    }

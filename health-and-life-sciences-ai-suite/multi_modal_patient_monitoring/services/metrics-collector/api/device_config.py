"""Device configuration summary for the multi-modal patient monitoring suite.

Ported from the previous ``app.py`` implementation of this service. This
endpoint is consumed by ``patient-monitoring-aggregator`` (``GET
/device-config``) and is specific to this suite's workloads (rPPG, AI-ECG,
mdpnp, 3D pose) -- it has no equivalent in the generic kiosk metrics-collector
this service was merged with, so it is kept as a standalone module rather
than folded into ``metrics.py``.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from metrics import get_platform_info

DEVICE_ENV_PATH = Path(os.getenv("DEVICE_ENV_PATH", "/configs/device.env"))


def _load_device_env(path: Path = DEVICE_ENV_PATH) -> Optional[Dict[str, str]]:
    """Load key=value pairs from the device env file.

    Lines starting with '#' and blank lines are ignored. Values are
    stripped of surrounding quotes.
    """
    try:
        with path.open() as f:
            result: Dict[str, str] = {}
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                if not key:
                    continue
                result[key] = value
        return result
    except FileNotFoundError:
        return None
    except OSError:
        return None


def build_device_config_payload() -> Dict[str, Any]:
    """Build a summary of device configuration per workload.

    Reads DEVICE_ENV_PATH (defaults to /configs/device.env) and maps
    configured devices (CPU/GPU/NPU/AUTO) to platform details from
    get_platform_info().
    """
    env_data = _load_device_env()
    platform_info = get_platform_info()

    def resolve_detail(device_code: Optional[str]) -> str:
        if not device_code:
            return "Unknown"
        code = device_code.strip().upper()
        if code == "CPU":
            return platform_info.get("Processor", "CPU")
        if code == "GPU":
            return platform_info.get("iGPU", "GPU")
        if code == "NPU":
            return platform_info.get("NPU", "NPU")
        if code == "AUTO":
            return "AUTO (platform decides: CPU/GPU/NPU)"
        return code

    workloads = {
        "rppg": {"env_key": "RPPG_DEVICE"},
        "ai_ecg": {"env_key": "ECG_DEVICE"},
        "mdpnp": {"env_key": "MDPNP_DEVICE"},
        "pose_3d": {"env_key": "POSE_3D_DEVICE"},
    }

    for _name, info in workloads.items():
        key = info["env_key"]
        configured = env_data.get(key) if env_data is not None else None
        info["configured_device"] = configured
        info["resolved_detail"] = resolve_detail(configured)

    return {"workloads": workloads}

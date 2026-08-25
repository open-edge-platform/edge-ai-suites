# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Edge AI Suites tool handlers."""

import os
import subprocess
from pathlib import Path

# Default to workspace root, override with WORKSPACE_DIR env var
WORKSPACE = Path(os.getenv("WORKSPACE_DIR", "/home/user/nathsudi"))
REPO = WORKSPACE / "edge-ai-suites"

APP_PATHS = {
    "pcb-anomaly-detection": "manufacturing-ai-suite/industrial-edge-insights-vision/apps/pcb-anomaly-detection",
    "pallet-defect-detection": "manufacturing-ai-suite/industrial-edge-insights-vision/apps/pallet-defect-detection",
    "weld-porosity": "manufacturing-ai-suite/industrial-edge-insights-vision/apps/weld-porosity",
    "worker-safety-gear-detection": "manufacturing-ai-suite/industrial-edge-insights-vision/apps/worker-safety-gear-detection",
    "wind-turbine-anomaly-detection": "manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection",
    "weld-defect-detection": "manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-defect-detection",
    "multimodal-weld": "manufacturing-ai-suite/industrial-edge-insights-multimodal",
    "hmi-augmented-worker": "manufacturing-ai-suite/hmi-augmented-worker",
}

APP_DESCRIPTIONS = {
    "pcb-anomaly-detection": "PCB defect and anomaly detection using computer vision",
    "pallet-defect-detection": "Warehouse pallet quality inspection",
    "weld-porosity": "Visual weld porosity and quality inspection",
    "worker-safety-gear-detection": "PPE/safety gear compliance monitoring",
    "wind-turbine-anomaly-detection": "Wind turbine predictive maintenance via time-series",
    "weld-defect-detection": "Sensor-based weld defect detection (time-series)",
    "multimodal-weld": "Vision + sensor fusion for weld quality",
    "hmi-augmented-worker": "RAG-enabled AI assistant for factory workers",
}


def deploy_app(arguments: dict) -> str:
    app_name = arguments.get("application", "")
    action = arguments.get("action", "info")

    rel_path = APP_PATHS.get(app_name)
    if not rel_path:
        return f"Unknown application: {app_name}\n\nAvailable: {list(APP_PATHS.keys())}"

    app_path = REPO / rel_path

    if not app_path.exists():
        return f"Application path not found: {app_path}\nRun setup.sh and ensure edge-ai-suites is cloned."

    if action == "info":
        readme = app_path / "README.md"
        if readme.exists():
            content = readme.read_text()[:4000]
            return f"## {app_name}\n\n**Path:** `{app_path}`\n**Description:** {APP_DESCRIPTIONS.get(app_name, '')}\n\n{content}"
        files = [f.name for f in app_path.iterdir()]
        return f"## {app_name}\n\n**Path:** `{app_path}`\n**Files:** {files}"

    elif action == "start":
        return _docker_compose(app_path, ["up", "-d"])

    elif action == "stop":
        return _docker_compose(app_path, ["down"])

    elif action == "logs":
        return _docker_compose(app_path, ["logs", "--tail", "50"])

    elif action == "status":
        return _docker_compose(app_path, ["ps"])

    return f"Unknown action: {action}"


def list_apps(arguments: dict) -> str:
    suite_filter = arguments.get("suite", "all")

    lines = ["## Available Edge AI Suite Applications\n"]

    categories = {
        "manufacturing": {
            "Vision": ["pcb-anomaly-detection", "pallet-defect-detection", "weld-porosity", "worker-safety-gear-detection"],
            "Time Series": ["wind-turbine-anomaly-detection", "weld-defect-detection"],
            "Multimodal": ["multimodal-weld"],
            "HMI": ["hmi-augmented-worker"],
        },
    }

    if suite_filter in ("manufacturing", "all"):
        lines.append("### Manufacturing AI Suite\n")
        for category, apps in categories["manufacturing"].items():
            lines.append(f"**{category}:**")
            for app in apps:
                path = REPO / APP_PATHS[app]
                status = "available" if path.exists() else "not found"
                lines.append(f"  - `{app}` — {APP_DESCRIPTIONS[app]} [{status}]")
            lines.append("")

    if suite_filter in ("metro", "all"):
        lines.append("### Metro AI Suite\n")
        lines.append("  - SDK Manager: `metro-ai-suite/metro-sdk-manager/`")
        lines.append("  - Live Video Captioning: `metro-ai-suite/live-video-analysis/live-video-captioning/`")
        lines.append("")

    if suite_filter in ("retail", "all"):
        lines.append("### Retail AI Suite\n")
        lines.append("  - See: `retail-ai-suite/`")
        lines.append("")

    return "\n".join(lines)


def sdk_install(arguments: dict) -> str:
    sdk = arguments.get("sdk", "")
    skip_images = arguments.get("skip_images", False)
    skip_git_clone = arguments.get("skip_git_clone", False)

    script_path = REPO / f"metro-ai-suite/metro-sdk-manager/scripts/{sdk}.sh"
    if not script_path.exists():
        return f"SDK install script not found: {script_path}"

    cmd = ["bash", str(script_path)]
    if skip_images:
        cmd.append("--skip-images")
    if skip_git_clone:
        cmd.append("--skip-git-clone")

    return f"""## Install SDK: {sdk}

**Script:** `{script_path}`

### Command
```bash
{' '.join(cmd)}
```

### What it does
- Pulls Docker images for the SDK components
- Clones required GitHub repositories
- Sets up the development environment

Run with `--help` for all options:
```bash
bash {script_path} --help
```
"""


def _docker_compose(app_path: Path, args: list) -> str:
    compose_file = app_path / "docker-compose.yml"
    if not compose_file.exists():
        compose_file = app_path / "compose.yaml"
    if not compose_file.exists():
        return f"No docker-compose.yml or compose.yaml found in {app_path}"

    cmd = ["docker", "compose"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(app_path),
            capture_output=True,
            text=True,
            timeout=120,
        )
        output = result.stdout + result.stderr
        return f"**Command:** `{' '.join(cmd)}`\n**Directory:** `{app_path}`\n\n```\n{output[:5000]}\n```"
    except subprocess.TimeoutExpired:
        return "Docker compose command timed out after 120s"
    except FileNotFoundError:
        return "Docker not found. Ensure Docker and Docker Compose are installed."


HANDLERS = {
    "deploy_app": deploy_app,
    "list_apps": list_apps,
    "sdk_install": sdk_install,
}

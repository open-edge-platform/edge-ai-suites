# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""Anomalib tool handlers."""

import os
import subprocess
from pathlib import Path

# Default to workspace root, override with WORKSPACE_DIR env var
WORKSPACE = Path(os.getenv("WORKSPACE_DIR", "/home/user/nathsudi"))
REPO = WORKSPACE / "anomalib"


def _run_anomalib(args: list, timeout: int = 300) -> str:
    cmd = ["anomalib"] + args
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout
        if result.returncode != 0:
            output += f"\n[STDERR]\n{result.stderr}"
        return output[:8000] if output else "(no output)"
    except FileNotFoundError:
        return (
            f"anomalib CLI not found. Install with:\n"
            f"  cd {REPO}\n"
            f"  uv sync\n"
            f"  source .venv/bin/activate"
        )
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"


def train(arguments: dict) -> str:
    model = arguments.get("model", "PatchCore")
    data_path = arguments.get("data_path", "")
    category = arguments.get("category", "")
    max_epochs = arguments.get("max_epochs")
    image_size = arguments.get("image_size")
    accelerator = arguments.get("accelerator", "auto")

    cmd = ["train", "--model", model, "--data.path", data_path]
    if category:
        cmd.extend(["--data.category", category])
    if max_epochs:
        cmd.extend(["--trainer.max_epochs", str(max_epochs)])
    if image_size:
        cmd.extend(["--data.image_size", str(image_size)])
    if accelerator != "auto":
        cmd.extend(["--trainer.accelerator", accelerator])

    result = _run_anomalib(cmd, timeout=3600)
    return f"## anomalib train\n\n**Command:** `anomalib {' '.join(cmd)}`\n\n```\n{result}\n```"


def predict(arguments: dict) -> str:
    model_path = arguments.get("model_path", "")
    data_path = arguments.get("data_path", "")
    output_path = arguments.get("output_path", "")

    cmd = ["predict", "--model", model_path, "--data.path", data_path]
    if output_path:
        cmd.extend(["--output", output_path])

    result = _run_anomalib(cmd, timeout=600)
    return f"## anomalib predict\n\n**Command:** `anomalib {' '.join(cmd)}`\n\n```\n{result}\n```"


def export(arguments: dict) -> str:
    model_path = arguments.get("model_path", "")
    export_type = arguments.get("export_type", "openvino")
    input_size = arguments.get("input_size", "")

    cmd = ["export", "--model", model_path, "--export_type", export_type]
    if input_size:
        cmd.extend(["--input_size", input_size])

    result = _run_anomalib(cmd, timeout=300)
    return f"## anomalib export\n\n**Command:** `anomalib {' '.join(cmd)}`\n\n```\n{result}\n```"


def benchmark(arguments: dict) -> str:
    data_path = arguments.get("data_path", "")
    models = arguments.get("models", ["PatchCore", "Padim", "EfficientAd"])
    category = arguments.get("category", "")
    config_path = arguments.get("config_path", "")

    if config_path:
        cmd = ["benchmark", "--config", config_path]
        result = _run_anomalib(cmd, timeout=7200)
        return f"## anomalib benchmark\n\n**Command:** `anomalib {' '.join(cmd)}`\n\n```\n{result}\n```"

    results = []
    for model in models:
        cmd = ["train", "--model", model, "--data.path", data_path]
        if category:
            cmd.extend(["--data.category", category])
        out = _run_anomalib(cmd, timeout=1800)
        results.append(f"### {model}\n```\n{out[:2000]}\n```")

    return f"## Benchmark Results\n\n**Models:** {models}\n**Data:** {data_path}\n\n" + "\n\n".join(results)


def openvino_inference(arguments: dict) -> str:
    model_path = arguments.get("model_path", "")
    image_path = arguments.get("image_path", "")
    device = arguments.get("device", "CPU")

    script = REPO / "tools/inference/openvino_inference.py"
    if not script.exists():
        return f"OpenVINO inference script not found at: {script}"

    cmd = [
        "python3", str(script),
        "--model_path", model_path,
        "--image_path", image_path,
        "--device", device,
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=300,
        )
        output = result.stdout + (f"\n{result.stderr}" if result.returncode != 0 else "")
        return f"## OpenVINO Inference\n\n**Command:** `{' '.join(cmd)}`\n\n```\n{output[:5000]}\n```"
    except Exception as e:
        return f"Error: {e}"


HANDLERS = {
    "train": train,
    "predict": predict,
    "export": export,
    "benchmark": benchmark,
    "openvino_inference": openvino_inference,
}

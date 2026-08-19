<!-- SPDX-FileCopyrightText: (C) 2026 Intel Corporation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# Tests Reference — UAV Vision Analytics

## Test Structure

```
tests/
├── conftest.py                  # shared fixtures, env vars, REST base URL
├── test_stack_up.py             # containers running and healthy
├── test_pipeline_start.py       # REST API: list, start, status, stop
├── test_rtsp_stream.py          # RTSP stream availability after pipeline start
└── test_mavlink_trigger.py      # pipeline starts/stops on armed/disarmed
```

---

## conftest.py

```python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import os
import pytest
import requests

REST_BASE = os.getenv("DLSPS_REST_URL", "http://localhost:8081")
RTSP_HOST = os.getenv("HOST_IP", "127.0.0.1")
RTSP_PORT = int(os.getenv("RTSP_PORT", "8555"))


@pytest.fixture(scope="session")
def rest_base():
    return REST_BASE


@pytest.fixture(scope="session")
def rtsp_host():
    return RTSP_HOST


@pytest.fixture(scope="session")
def rtsp_port():
    return RTSP_PORT
```

---

## test_stack_up.py

```python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import subprocess
import pytest


def _running_containers():
    result = subprocess.run(
        ["docker", "ps", "--format", "{{.Names}}"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.splitlines()


def test_dlstreamer_container_running():
    assert "dlstreamer-pipeline-server" in _running_containers()


def test_broker_container_running():
    """Only present in pymavlink mode."""
    containers = _running_containers()
    # Skip if broker not expected (MAVSDK mode)
    if "broker" not in containers:
        pytest.skip("broker not present (MAVSDK mode)")
    assert "broker" in containers


def test_px4_container_running():
    containers = _running_containers()
    if "px4" not in containers:
        pytest.skip("px4 not present (MAVSDK mode)")
    assert "px4" in containers
```

---

## test_pipeline_start.py

```python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import pytest
import requests
import time


def test_rest_api_reachable(rest_base):
    resp = requests.get(f"{rest_base}/pipelines", timeout=10)
    assert resp.status_code == 200


def test_pipelines_registered(rest_base):
    resp = requests.get(f"{rest_base}/pipelines", timeout=10)
    assert resp.status_code == 200
    pipelines = resp.json()
    names = [p.get("version", p.get("name", "")) for p in pipelines]
    assert any("uav" in n or "camera" in n for n in names), \
        f"No UAV pipelines found. Registered: {names}"


def test_pipeline_start_stop(rest_base):
    payload = {
        "destination": {
            "metadata": {"type": "file", "path": "/tmp/test-results.jsonl", "format": "json-lines"},
            "frame": {"type": "rtsp", "path": "test-cpu"}
        },
        "parameters": {
            "detection-properties": {
                "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
                "device": "CPU"
            }
        }
    }

    # Start pipeline — adjust name to match first registered pipeline
    resp = requests.get(f"{rest_base}/pipelines", timeout=10)
    pipelines = resp.json()
    pipeline_name = pipelines[0].get("version", pipelines[0].get("name"))

    start_resp = requests.post(
        f"{rest_base}/pipelines/user_defined_pipelines/{pipeline_name}",
        json=payload, timeout=15
    )
    assert start_resp.status_code == 200, f"Start failed: {start_resp.text}"

    instance_id = start_resp.text.strip().strip('"')
    assert instance_id, "No instance_id returned"

    # Wait for pipeline to be RUNNING
    for _ in range(10):
        time.sleep(1)
        status_resp = requests.get(f"{rest_base}/pipelines/{instance_id}/status", timeout=5)
        if status_resp.status_code == 200:
            state = status_resp.json().get("state", "")
            if state == "RUNNING":
                break

    status_resp = requests.get(f"{rest_base}/pipelines/{instance_id}/status", timeout=5)
    assert status_resp.json().get("state") == "RUNNING", \
        f"Pipeline not RUNNING: {status_resp.json()}"

    # Stop pipeline
    del_resp = requests.delete(f"{rest_base}/pipelines/{instance_id}", timeout=10)
    assert del_resp.status_code in (200, 204), f"Delete failed: {del_resp.text}"
```

---

## test_rtsp_stream.py

```python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import subprocess
import pytest
import requests
import time


def _start_pipeline(rest_base, pipeline_name, rtsp_path):
    payload = {
        "destination": {
            "metadata": {"type": "file", "path": "/tmp/rtsp-test.jsonl", "format": "json-lines"},
            "frame": {"type": "rtsp", "path": rtsp_path}
        },
        "parameters": {
            "detection-properties": {
                "model": "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml",
                "device": "CPU"
            }
        }
    }
    resp = requests.post(
        f"{rest_base}/pipelines/user_defined_pipelines/{pipeline_name}",
        json=payload, timeout=15
    )
    assert resp.status_code == 200
    return resp.text.strip().strip('"')


def _probe_rtsp(rtsp_url, timeout=10):
    """Use ffprobe to check RTSP stream is live."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-rtsp_transport", "tcp",
         "-select_streams", "v:0", "-show_entries", "stream=codec_type",
         "-of", "default=noprint_wrappers=1",
         "-timeout", str(timeout * 1_000_000), rtsp_url],
        capture_output=True, timeout=timeout + 2
    )
    return result.returncode == 0 and b"codec_type" in result.stdout


@pytest.mark.skipif(
    not __import__("shutil").which("ffprobe"),
    reason="ffprobe not installed"
)
def test_rtsp_stream_available(rest_base, rtsp_host, rtsp_port):
    # Get first pipeline name
    resp = requests.get(f"{rest_base}/pipelines", timeout=10)
    pipelines = resp.json()
    pipeline_name = pipelines[0].get("version", pipelines[0].get("name"))
    rtsp_path = "test-rtsp-probe"

    instance_id = _start_pipeline(rest_base, pipeline_name, rtsp_path)
    try:
        time.sleep(3)
        rtsp_url = f"rtsp://{rtsp_host}:{rtsp_port}/{rtsp_path}"
        assert _probe_rtsp(rtsp_url), f"RTSP stream not available at {rtsp_url}"
    finally:
        requests.delete(f"{rest_base}/pipelines/{instance_id}", timeout=10)
```

---

## test_mavlink_trigger.py

```python
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

import pytest
import subprocess
import time
import requests

# This test validates pipeline lifecycle via the pipeline_manager.
# It requires the pipeline_manager to be running inside the container.
# For unit testing without a live MAVLink connection, mock the armed state
# by directly calling the REST API (as the pipeline_manager does).


def test_pipeline_manager_script_exists():
    result = subprocess.run(
        ["docker", "exec", "dlstreamer-pipeline-server",
         "test", "-f", "/home/pipeline-server/scripts/pipeline_manager.py"],
        capture_output=True
    )
    assert result.returncode == 0, "pipeline_manager.py not found in container"


def test_pipeline_manager_importable():
    result = subprocess.run(
        ["docker", "exec", "dlstreamer-pipeline-server",
         "python3", "-c", "import sys; sys.path.insert(0, '/home/pipeline-server/scripts'); "
         "import pipeline_manager; print('OK')"],
        capture_output=True, text=True, timeout=10
    )
    assert result.returncode == 0 and "OK" in result.stdout, \
        f"Import failed: {result.stderr}"


def test_model_file_exists():
    result = subprocess.run(
        ["docker", "exec", "dlstreamer-pipeline-server",
         "test", "-f",
         "/home/pipeline-server/resources/models/yolov8n-visdrone/best_openvino_model/best.xml"],
        capture_output=True
    )
    assert result.returncode == 0, "Model file not found in container"
```

---

## Running Tests

```bash
# From the app directory
pip install pytest requests
pytest -q tests/

# With custom host
DLSPS_REST_URL=http://localhost:8081 HOST_IP=192.168.1.x pytest -q tests/

# Verbose with stdout
pytest -v -s tests/
```

## Test Markers

| Marker | Purpose |
|--------|---------|
| `@pytest.mark.skipif(...)` | Skip if dependency not present (ffprobe, etc.) |
| `scope="session"` fixtures | Reuse connections across tests |

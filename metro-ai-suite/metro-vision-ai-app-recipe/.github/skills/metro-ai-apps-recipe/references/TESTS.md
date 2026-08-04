# Tests reference

Tests live in `./{{STACK_DIR}}/tests/`. Python venv at `./.venv`
(`python -m venv .venv`) — system pip is PEP-668 blocked; `/tmp` may be
`noexec`.

## `tests/conftest.py`

```python
import os, subprocess, json, requests, pytest
os.environ["NO_PROXY"] = "*"
PROJECT = os.environ.get("COMPOSE_PROJECT_NAME", os.path.basename(os.getcwd()))
NET     = f"{PROJECT}_app_network"
HOST    = os.environ.get("HOST_IP", "localhost")

@pytest.fixture(scope="session")
def mqtt_sub():
    def _next(topic, timeout=10):
        out = subprocess.check_output([
            "docker","run","--rm","--network",NET,"eclipse-mosquitto:2.0.22",
            "mosquitto_sub","-h","broker","-t",topic,"-C","1","-W",str(timeout)
        ], text=True, timeout=timeout+5)
        try:    return json.loads(out)
        except: return out.strip()
    return _next

@pytest.fixture(scope="session")
def api():
    import urllib3; urllib3.disable_warnings()
    s = requests.Session(); s.verify = False
    s.base = f"https://{HOST}"
    return s
```

## `tests/test_frames_served.py`

```python
import time
def test_frame_updates(api):
    url = f"{api.base}/frames/{{DETECTIONS_TOPIC_PREFIX}}_1.jpg"
    r1 = api.get(url + f"?t={time.time()}", timeout=10); assert r1.status_code == 200
    assert r1.headers.get("Content-Type","").startswith("image/")
    time.sleep(2 / {{MJPEG_FPS}})
    r2 = api.get(url + f"?t={time.time()}", timeout=10); assert r2.status_code == 200
    assert r1.content != r2.content, "frame did not update"
```

## Assertion contract for the other test files

Empty files that always pass are a defect. `pytest --collect-only -q
tests/ | tail -1` MUST report `≥ 8 tests collected`.

**`test_stack_up.py`**
- `docker compose ps --format json` returns exactly the expected service
  set `{nginx, dlstreamer-pipeline-server, broker, node-red, grafana}`.
- Every service `State=="running"` and (if present) `Health=="healthy"`.
- `https://{HOST}/` returns 200.

**`test_pipeline_running.py`**
- `GET /api/pipelines/status` returns 200 and a list.
- All 3 variants (`{{PIPELINE_NAME}}`, `_gpu`, `_npu`) present.
- After `sample_start.sh cpu`, exactly `{{NUM_SOURCES}}` instances in
  `RUNNING` within 30 s (0 `QUEUED`, 0 `ERROR`).

**`test_mqtt_detections.py`**
- Subscribe `#`, receive ≥1 message per source on
  `{{DETECTIONS_TOPIC_PREFIX}}_X/{{PIPELINE_NAME}}` within 30 s.
- Payload parses as JSON; `label_id` int, `confidence` float 0–1.
- **Negative:** NO message on un-suffixed `{{DETECTIONS_TOPIC_PREFIX}}`
  (would mean `APPEND_PIPELINE_NAME_TO_PUBLISHER_TOPIC` is false).

**`test_nodered_alert.py`**
- Subscribe `{{COUNT_TOPIC}}/#`: `int()` succeeds on payload.
- **Negative:** payload MUST NOT start with `{`/`[` (JSON breaks Grafana
  MQTT scalar plotting).
- Same scalar rule for `stats/alert_active`, `stats/alert_total`.
- Inject 5 fake detections on
  `{{DETECTIONS_TOPIC_PREFIX}}_1/{{PIPELINE_NAME}}` within 1 s → within
  `rule_window+2 s` an `{{ALERT_TOPIC}}` JSON `{source, count, rule, ts}`
  arrives.

**`test_grafana_mqtt_data.py`**
- `GET /grafana/api/datasources` (basic auth admin/admin) returns a
  datasource with `type=="mqtt-datasource"`, `access=="proxy"`.
- Dashboard `{{DASHBOARD_SLUG}}` provisioned
  (`/grafana/api/search?query={{DASHBOARD_SLUG}}` ≥1 hit).
- Query datasource proxy for count topic over 60 s window: ≥1 datapoint
  arrives (guards against the 1.2.1 "invalid orgId" regression).

# Tests reference

Tests live in `./{{STACK_DIR}}/tests/`. Python venv at `./.venv` (`python -m venv .venv`) — system pip is PEP-668 blocked; `/tmp` may be `noexec`.

**If the host lacks python/pip/venv**, install Python 3 (with `venv`) on the host first, then create `./.venv` and run pytest from it. Split proxy for any test that pulls packages: `http_proxy` for `pip install`, `NO_PROXY=*` for LAN-host test HTTP. Tests drive the running stack via the already-published host ports (`https://<HOST_IP>/...`) and the `mosquitto_sub` container on the compose network — no host Docker socket is mounted.

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
            "docker","run","--rm","--network",NET,"eclipse-mosquitto:2.1.2-alpine",
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

## `tests/test_webrtc_stream.py`

```python
def test_webrtc_player_served(api):
    # MediaMTX serves a WHEP reader page at the stream path root once the
    # DLSPS WHIP publisher (peer-id) is connected.
    url = f"{api.base}/mediamtx/{{DETECTIONS_TOPIC_PREFIX}}_1/"
    r = api.get(url, timeout=10)
    assert r.status_code == 200, f"WHEP player not served: {r.status_code}"
    assert "text/html" in r.headers.get("Content-Type", "")

def test_whep_endpoint(api):
    # WHEP signalling endpoint should exist (405/415/201 depending on method),
    # never 404 (which means the stream path / nginx regex is wrong).
    r = api.post(f"{api.base}/{{DETECTIONS_TOPIC_PREFIX}}_1/whep", timeout=10)
    assert r.status_code != 404, "WHEP endpoint missing (check nginx regex / peer-id)"
```

## Assertion contract for the other test files

Empty always-pass files are defects. `pytest --collect-only -q tests/ | tail -1` MUST report `≥ 8 tests collected`.

**`test_stack_up.py`**
- `docker compose ps --format json` returns exactly `{nginx, dlstreamer-pipeline-server, broker, node-red, grafana, mediamtx, coturn}`.
- Every service `State=="running"` and optional `Health=="healthy"`.
- `https://{HOST}/` returns 200.

**`test_pipeline_running.py`**
- `GET /api/pipelines/status` returns 200 and a list.
- All 3 variants (`{{PIPELINE_NAME}}`, `_gpu`, `_npu`) present.
- After `sample_start.sh cpu`, exactly `{{NUM_SOURCES}}` instances in `RUNNING` within 30 s (0 `QUEUED`, 0 `ERROR`).

**`test_mqtt_detections.py`**
- Subscribe `{{DETECTIONS_TOPIC_PREFIX}}_X/#` (suffix `/{{PIPELINE_NAME}}` unreliable — see PIPELINE.md; `_X/#` matches suffixed and bare). Receive ≥1 message/source within 30 s. Retry (≈ 3×20 s): file-source watchdog gaps can briefly leave no live pipeline.
- Payload parses as JSON; class is `metadata.gva_meta[].tensor[0].label_id` (int) / `.tensor[0].label` (string) with `.tensor[0].confidence` float 0–1 — NOT `objects[]` or top-level `label_id`/`detection.label_id`. Accept legacy `objects[].detection.label_id` only as fallback.
- Do NOT assert un-suffixed `{{DETECTIONS_TOPIC_PREFIX}}_X` stays silent — bare topic is legitimate observed output, so that negative flakes.

**`test_nodered_alert.py`**
- Subscribe `{{COUNT_TOPIC}}/#`: `int()` succeeds.
- **Negative:** payload MUST NOT start with `{`/`[` (JSON breaks Grafana MQTT scalar plotting).
- Same scalar rule for `stats/alert_active`, `stats/alert_total`.
- Alert firing: flow emits `{{ALERT_TOPIC}}` only on OFF→ON rising edge, so fake injection can no-op if live video already holds alert ON. Prefer natural observation: subscribe `{{ALERT_TOPIC}}` for ~45 s and assert JSON `{ts, sourceId, count, rule}`. If injecting, payload MUST match real shape (`{"metadata":{"gva_meta":[{"tensor":[{"label":"{{OBJECT}}","label_id":0,"confidence":0.9}]}]}}`) on `{{DETECTIONS_TOPIC_PREFIX}}_1`, and first let window fall to 0.

**`test_grafana_mqtt_data.py`**
- `GET /grafana/api/datasources` (basic auth admin/admin) returns datasource with `type=="mqtt-datasource"`, `access=="proxy"`.
- Dashboard `{{DASHBOARD_SLUG}}` provisioned — look up **by uid** (`GET /grafana/api/dashboards/uid/{{DASHBOARD_SLUG}}` returns 200). Do NOT use `/grafana/api/search?query=`; it matches *title*, not slug/uid, and flakes when they differ.
- Query datasource proxy for count topic over 60 s: ≥1 datapoint (guards 1.2.1 "invalid orgId" regression).

**`test_grafana_dashboard_content.py`** — verifies dashboard *displays* video and MQTT, guarding common "green but empty/black" regressions.
- **MQTT connected:** `GET /grafana/api/datasources/uid/mqtt_ds/health` (admin/admin) returns `status=="OK"` and message containing `connected`. Catches `jsonData.uri` mistake: wrong key provisions "successfully" but health says `"Network error dial tcp: missing address"` and panels are blank.
- **Video panels present:** fetch dashboard (`/grafana/api/dashboards/uid/<uid>`) and assert exactly `{{NUM_SOURCES}}` `type=="text"` panels whose `options.content` is an `<iframe>` referencing `WEBRTC_URL` / `mediamtx`, each with distinct `{{DETECTIONS_TOPIC_PREFIX}}_N` peer-id.
- **Video playable:** resolve `WEBRTC_URL` and assert each `<WEBRTC_URL>/{{DETECTIONS_TOPIC_PREFIX}}_N/` returns 200 HTML (WHEP player served — requires running pipelines).
- **MQTT panels bound:** at least one panel's `datasource` resolves to `uid=="mqtt_ds"` (or type contains `mqtt`), proving count/alert panels wire to live broker.

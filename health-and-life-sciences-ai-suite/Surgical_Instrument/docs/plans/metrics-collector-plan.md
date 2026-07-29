# Metrics Collector Plan — Surgical Instrument

Replace the synthetic hardware-metrics sampler in the Surgical Instrument
backend with a real proxy to the shared `intel/hl-ai-metrics-collector`
sidecar (same pattern used by NICU-Warmer and multi-modal patient
monitoring). This document is written so an autonomous agent can execute
the git workflow after the code changes have been verified locally.

---

## 0. Background — Why this exists

The UI's Resource Utilisation panel was rendering a sine-wave from
`_sample_hardware()` in `backend/server/app.py`. The panel schema
(`cpu_utilization`, `gpu_utilization`, `npu_utilization`, `memory`,
`power`) already matches what NICU-Warmer exposes via its
`nicu-metrics-collector` service, so the fix is a straight port of that
pattern — add the sidecar container, proxy `/metrics` through the
backend, delete the fake sampler.

---

## 1. Code changes (ALREADY APPLIED to the working tree)

All source edits below have been applied in this workspace already. The
auto-agent should treat this list as a checklist to verify before
committing, not as work to redo.

### 1.1 `docker-compose.yaml`
- **Added** service `surgical-metrics-collector`
  - `image: intel/hl-ai-metrics-collector:${METRICS_COLLECTOR_TAG:-1.0.0}`
  - `pid: host`, `privileged: true`
  - Internal-only on `surgical-internal` (no host port publish)
  - Env: `METRICS_DIR=/tmp/results`, `NPU_LOG=/tmp/results/npu_usage.csv`
  - Mounts: `./metrics:/tmp/results`, `/sys`, `/dev`, `/run`
  - Healthcheck: `curl -sf http://localhost:9000/metrics`
- **Modified** service `surgical-backend`
  - Added `depends_on: surgical-metrics-collector: condition: service_healthy`
  - Added env `METRICS_COLLECTOR_URL: http://surgical-metrics-collector:9000`

### 1.2 `backend/config/model.yaml`
- **Added** top-level block:
  ```yaml
  metrics_collector:
    base_url: ${METRICS_COLLECTOR_URL:-http://surgical-metrics-collector:9000}
    poll_interval_s: 1.0
    max_points: 120
  ```

### 1.3 `configs/mvp-backend.yaml`
- **Replaced** the placeholder `metrics: { host, port, poll_interval_s }`
  block with the same `metrics_collector: { base_url, poll_interval_s }`
  shape used by NICU-Warmer / multi-modal.

### 1.4 `backend/consumer/metrics_client.py` (NEW)
- Thin HTTP client class `MetricsClient` with two methods:
  - `fetch_metrics()` — proxies `GET /metrics`, caps each series to
    `max_points`, returns canonical empty payload with
    `available: False` on any failure.
  - `fetch_platform_info()` — proxies `GET /platform-info` (optional).
- Uses `requests.Session(trust_env=False)` to bypass corporate HTTP
  proxies for internal container-network calls (same pattern as
  `PipelineClient`).

### 1.5 `backend/consumer/__init__.py`
- Export `MetricsClient` alongside `InferenceConsumer`.

### 1.6 `backend/server/app.py`
- **Removed** dead imports: `math`, `random`, `collections.deque`,
  `datetime.datetime`.
- **Removed** rolling deques `cpu_hist`, `gpu_hist`, `npu_hist`,
  `mem_hist`, `pwr_hist` from `ServerState`.
- **Removed** the `_sample_hardware()` function entirely.
- **Simplified** `_delta_loop()` to only publish SSE `delta` events for
  pipeline KPIs (no hardware sampling).
- **Rewrote** `GET /api/hardware-metrics` to delegate to a module-level
  `_metrics: MetricsClient` instance, with a safe empty-payload fallback
  when the collector is not wired.
- **Wired** `_metrics` inside `create_app()` — env
  `METRICS_COLLECTOR_URL` overrides the yaml `metrics_collector.base_url`
  which overrides the compose-network default.

---

## 2. Verification checklist (run BEFORE committing)

The auto-agent must run these steps from the workspace root
(`/home/intel/final/edge-ai-suites/health-and-life-sciences-ai-suite/Surgical_Instrument`)
and must abort the PR flow on any failure.

### 2.1 Static checks
```bash
python3 -m compileall backend/consumer/metrics_client.py \
                     backend/consumer/__init__.py \
                     backend/server/app.py
docker compose config >/dev/null
```

### 2.2 Confirm the fake sampler is gone
Both greps must return **zero** matches:
```bash
grep -n "_sample_hardware\|cpu_hist\|gpu_hist\|npu_hist\|mem_hist\|pwr_hist" backend/server/app.py
grep -n "^import math\|^import random\|from collections import deque\|from datetime import datetime" backend/server/app.py
```

### 2.3 Build and boot
```bash
make build
docker compose pull surgical-metrics-collector   # prebuilt image
docker compose up -d
docker compose ps                                # all Up (healthy)
```

### 2.4 Wait for the collector, then hit the proxy
```bash
# 1) Collector direct (internal network) — real numbers, not empty arrays
docker compose exec -T surgical-backend python3 -c 'import json,urllib.request; \
u="http://surgical-metrics-collector:9000/metrics"; \
d=json.loads(urllib.request.urlopen(u, timeout=10).read().decode()); \
assert len(d.get("cpu_utilization", [])) > 0, "empty cpu"; \
assert len(d.get("memory", [])) > 0, "empty memory"; \
print("collector internal ok:", {k: len(v) for k,v in d.items() if isinstance(v,list)})'

# 2) Backend proxy — same shape, same data (routes through nginx :8080)
curl -sf http://localhost:8080/api/hardware-metrics | \
  python3 -c 'import json,sys; d=json.load(sys.stdin); \
             assert d.get("available") is not False, "collector unreachable via backend"; \
             assert len(d.get("cpu_utilization", [])) > 0, "empty cpu via backend"; \
             print("proxy ok:", {k: len(v) for k,v in d.items() if isinstance(v,list)})'
```

Both invocations must exit 0 and print non-empty series lengths.

Notes:
- Surgical Instrument intentionally does not publish the collector port on
  the host. Only UI `:8080` is host-exposed.
- Collector diagnostics from the host should go through backend proxy
  (`/api/hardware-metrics`) or an internal-network container exec as above.

### 2.5 UI smoke
Open `http://localhost:8080/` in a browser and confirm the Resource
Utilisation accordion (CPU / GPU / NPU / Memory / Power) renders real,
non-sinusoidal traces that respond to real load (e.g. run `stress-ng
--cpu 4 --timeout 30s` and watch CPU % rise).

### 2.6 Rollback marker
Keep a running list of any commands that produced unexpected output
during 2.1–2.5; abort the git workflow (Section 3) if the list is
non-empty and surface it back to the user.

---

## 3. Git workflow — fork, branch, push, PR

The mainstream repo is the Intel `edge-ai-suites` monorepo. All work
lands on a fork under the developer's own GitHub account, then a PR is
opened against `mainstream/main`.

### 3.1 Preconditions the auto-agent must confirm

Run from the **repo root** (not the Surgical_Instrument subfolder — the
git repo lives higher up):
```bash
cd /home/intel/final/edge-ai-suites
git rev-parse --show-toplevel                # must be /home/intel/final/edge-ai-suites
git remote -v
```

Expected remotes:
- `origin` → the developer's fork
- `mainstream` (or `upstream`) → OPEA canonical repo (`open-edge-platform/edge-ai-suites`)

If the remotes are reversed (for example, `origin` points to OPEA and
there is no fork remote yet), normalize them before continuing:
```bash
git remote rename origin upstream                           # only if origin is OPEA
git remote add origin <fork-repo-url>                      # user-provided URL
git remote -v                                               # verify mapping
```

If either remote is missing, **stop and ask the user** which URL to add.
Never guess a GitHub URL. Once confirmed, add with:
```bash
git remote add mainstream <intel-repo-url>       # only if missing
git remote add origin     <fork-repo-url>        # only if missing
```

### 3.2 Sync from mainstream
```bash
git fetch mainstream --prune
git checkout main
git reset --hard mainstream/main                 # only if local main has no required local commits
git push origin main                             # optional: keep fork/main aligned with upstream
git status                                       # working tree must be clean of stray files
```

### 3.3 Create the feature branch
```bash
BRANCH="feat/surgical-metrics-collector"
git checkout -B "$BRANCH" main
```

### 3.4 Stage exactly the seven files this plan touches
```bash
cd health-and-life-sciences-ai-suite/Surgical_Instrument
git add \
  docker-compose.yaml \
  configs/mvp-backend.yaml \
  backend/config/model.yaml \
  backend/consumer/__init__.py \
  backend/consumer/metrics_client.py \
  backend/server/app.py \
  docs/plans/metrics-collector-plan.md
git status                                       # review — must show only the above
```

If `git status` shows unrelated modified files, **stop** — the auto-agent
must not sweep unknown edits into this commit.

### 3.5 Commit
```bash
git commit -m "surgical: proxy real hardware metrics via metrics-collector sidecar

Adds the shared intel/hl-ai-metrics-collector sidecar (same image and
compose shape as NICU-Warmer) and rewires GET /api/hardware-metrics
to proxy its /metrics payload. Deletes the synthetic sine-wave sampler
(_sample_hardware) and the associated rolling deques so the UI's
Resource Utilisation panel renders real CPU/GPU/NPU/memory/power
values instead of a placeholder.

- docker-compose.yaml: new surgical-metrics-collector service
  (pid=host, privileged, /sys /dev /run mounts) and backend
  depends_on + METRICS_COLLECTOR_URL env
- backend/consumer/metrics_client.py: thin HTTP proxy with per-series
  max_points cap and safe empty-payload fallback
- backend/server/app.py: replace synthetic sampler with proxy call
- backend/config/model.yaml, configs/mvp-backend.yaml: metrics_collector
  base_url + max_points settings"
```

### 3.6 Push to the fork
```bash
cd /home/intel/final/edge-ai-suites
git push -u origin "$BRANCH"
```

### 3.7 Open the pull request

Use `gh` if available; otherwise print the compare URL and stop.
```bash
if command -v gh >/dev/null; then
  gh pr create \
    --repo <mainstream-owner>/<mainstream-repo> \
    --base main \
    --head "$(gh api user -q .login):$BRANCH" \
    --title "surgical: proxy real hardware metrics via metrics-collector sidecar" \
    --body-file - <<'EOF'
### Summary
Replaces the synthetic hardware-metrics sampler in the Surgical
Instrument backend with a real proxy to the shared
`intel/hl-ai-metrics-collector` sidecar. Same pattern as NICU-Warmer.

### Motivation
The UI's Resource Utilisation panel was rendering a sine-wave from a
placeholder implementation. All Suites already share the collector
image and JSON schema; this PR wires Surgical Instrument to it.

### Changes
- New `surgical-metrics-collector` service in `docker-compose.yaml`
- `backend/consumer/metrics_client.py`: thin HTTP proxy
- `backend/server/app.py`: `/api/hardware-metrics` now delegates to the
  proxy; synthetic sampler and its rolling deques deleted
- `backend/config/model.yaml`, `configs/mvp-backend.yaml`:
  `metrics_collector` block

### Test
- `docker compose up -d` — all services healthy
- collector reachable from backend container network and returns populated series
- `curl http://localhost:8080/api/hardware-metrics` returns the same
  under the backend's canonical schema
- UI Resource Utilisation panel renders live traces

### Backwards compatibility
`/api/hardware-metrics` response shape is unchanged
(`cpu_utilization`, `gpu_utilization`, `npu_utilization`, `memory`,
`power` arrays). The fallback branch keeps returning that shape with
`available: False` when the collector is down, so the UI never sees a
schema break.
EOF
else
  echo "Open a PR manually: https://github.com/<mainstream-owner>/<mainstream-repo>/compare/main...<fork-owner>:$BRANCH"
fi
```

---

## 4. Rollback

If verification (Section 2) fails, revert with:
```bash
cd /home/intel/final/edge-ai-suites
git reset --hard mainstream/main       # only if no commits worth keeping
# ...or, if the commit already landed on the fork branch:
git revert HEAD
git push origin "$BRANCH"
```

If the PR was already opened, close it with a comment linking back to
the failing verification step.

---

## 5. Non-goals (explicitly out of scope)

- Building the `intel/hl-ai-metrics-collector` image from source in this
  repo — we consume the prebuilt one, same as NICU-Warmer.
- Rewriting `/api/platform-info` to use the collector — the existing
  local `/proc + /sys` implementation is fine.
- Adding history/persistence for hardware metrics inside the backend —
  the UI caps the returned window at 120 samples on the client side
  already.

# Gas Detection (Multimodal) — Use Case

Fused image + sensor classification for the gas-detection dataset (Mendeley),
reusing logic ported from the upstream reference implementation
([intel/predictive-maintenance-pipeline](https://github.com/intel/predictive-maintenance-pipeline))
and plugged into this repo's detection-service.

## Status: deployable via `setup.sh`, validated end-to-end

**What works today** (see `docs/user-guide/multimodal-pipeline-plan.md` for
full history):

- `services/detection-service/src/utility/{image_classifier,sensor_classifier,fusion}.py`
  — ported, unit-tested inference/fusion logic.
- `services/detection-service/src/utility/multimodal_runner.py` — config-driven
  orchestrator: classifies every image + its paired sensor row, fuses per
  sample, and persists results to storage-service via the additive
  `image_confidence`, `sensor_confidence`, `sensor_raw_json`, `source` columns.
- `POST /detection/run-multimodal` on detection-service — same
  single-run-lock / "batch-complete" MQTT handoff contract as the existing
  `POST /detection/run` (video) path, so the agent-service reacts identically
  regardless of which path produced a batch.
- Trained models: `models/{image,sensor_mlp}/` (98.6% and 96.6% individual
  validation accuracy; 97.5% fused).
- Full stack deployable via `setup.sh --use-case gas-detection-multimodal`:
  storage-service, detection-service (with the multimodal endpoint),
  agent-service (rule-based fallback reasoning), ui-service, nginx — all
  verified healthy, with a real end-to-end run (40/40 samples classified,
  fused, and persisted; agent-service reacted to both completed batches).

**Not yet done**:

- UI (`ui-service`) has no dedicated surface for per-modality confidence or a
  "Run Pipeline" button wired to `/detection/run-multimodal` yet — trigger it
  via `curl` (see below) until that's built.
- `dlstreamer-pipeline-server` still starts (it's part of the always-on base
  stack) with an empty pipeline list (`configs/pipeline-server-config.json`)
  since this use case has no live video source — cosmetic only, does not
  affect classification.

## Deploying

```bash
source setup.sh --use-case gas-detection-multimodal
```

Then trigger a classification run (classifies every image in the mounted
dataset + its paired sensor row, fuses both modalities, and persists results):

```bash
curl -X POST http://localhost:8080/api/detection/run-multimodal \
     -H "Content-Type: application/json" \
     -d '{"device":"CPU","config_path":"/app/configs/gas_detection.docker.json"}'
```

Check status and results:

```bash
curl http://localhost:8080/api/detection/status/<run_id>
curl "http://localhost:8080/api/storage/detections?limit=10"
```

**Note**: after any code change to `detection-service` or `storage-service`,
rebuild before `up` — `setup.sh` does not pass `--build` automatically:

```bash
docker compose -f docker/compose.base.yaml -f docker/compose.telemetry.yaml \
  -f docker/compose.detection.yaml -f docker/compose.agents.yaml \
  -f docker/compose.ui.yaml build apm-detection apm-storage
```

(Run this in the same shell right after `source setup.sh ...` — the
`USE_CASE_MODELS_DIR`/`USE_CASE_CONFIGS_DIR`/`REGISTRY` env vars it exports do
not persist across separate shells/processes.)

## Regenerating the dataset

```bash
python scripts/download_and_prep_data.py --use-case gas-detection
```

## Trying it locally (outside Docker)

Uses `configs/gas_detection.local.json` (repo-root-relative paths) instead of
`configs/gas_detection.docker.json` (container paths, used above):

```python
import sys
sys.path.insert(0, "services/detection-service")
from src.utility.multimodal_runner import load_config, run_multimodal_classification

config = load_config("apps/gas-detection-multimodal/configs/gas_detection.local.json")
results = run_multimodal_classification(config, device="CPU")
for r in results:
    print(r["source"], r["label"], r["confidence"])
```

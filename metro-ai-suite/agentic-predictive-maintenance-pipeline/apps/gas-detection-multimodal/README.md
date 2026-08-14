# Gas Detection (Multimodal) — Use Case

Fused image + sensor classification for the gas-detection dataset (Mendeley),
reusing logic ported from the upstream reference implementation
([intel/predictive-maintenance-pipeline](https://github.com/intel/predictive-maintenance-pipeline))
and plugged into this repo's detection-service.

## Status: application logic wired, deployment packaging not yet done

**What works today** (see `docs/user-guide/multimodal-pipeline-plan.md` for
full history):

- `services/detection-service/src/utility/{image_classifier,sensor_classifier,fusion}.py`
  — ported, unit-tested inference/fusion logic.
- `services/detection-service/src/utility/multimodal_runner.py` — config-driven
  orchestrator: loads this directory's `configs/gas_detection.json`, classifies
  every val image + its paired sensor row, fuses per sample, and persists
  results to storage-service via the additive `image_confidence`,
  `sensor_confidence`, `sensor_raw_json`, `source` columns.
- `POST /detection/run-multimodal` on detection-service — same
  single-run-lock / "batch-complete" MQTT handoff contract as the existing
  `POST /detection/run` (video) path, so the agent-service reacts identically
  regardless of which path produced a batch.
- Trained models: `models/ov_models/gas_detection/{image,sensor_mlp}/` (98.6%
  and 96.6% individual validation accuracy; 97.5% fused).

**Not yet done** — this use case is not yet a deployable `--use-case` target
for `setup.sh`:

- No `docker/compose.gas-detection-multimodal.yaml` — the existing compose
  files assume a live DL Streamer video pipeline; this use case classifies a
  static image/sensor dataset instead, so the compose wiring (volume mounts
  for `datasets/gas_detection/` and `models/ov_models/gas_detection/` into
  the detection-service container, since the dataset is gitignored and not
  shipped in the image) needs its own design pass.
- No `.env_gas-detection-multimodal` file.
- `configs/gas_detection.json` paths are relative to the repo root for local/
  direct testing (e.g. via `multimodal_runner.run_multimodal_classification`
  imported directly, or a future CLI/script) — they are **not** yet
  container-path-mapped for a Docker deployment.
- UI (`ui-service`) has no surface for per-modality confidence yet.

## Regenerating the dataset

```bash
python scripts/download_and_prep_data.py --use-case gas-detection
```

## Trying it locally (outside Docker)

```python
from services.detection_service.src.utility.multimodal_runner import (
    load_config, run_multimodal_classification, persist_results,
)

config = load_config("apps/gas-detection-multimodal/configs/gas_detection.json")
results = run_multimodal_classification(config, device="CPU")
for r in results:
    print(r["source"], r["label"], r["confidence"])
```

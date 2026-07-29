---
name: lvc-test
description: Run the Live Video Captioning unit test suite (pytest in app/). Use when asked to test, verify, or check coverage of backend changes.
---

# Test Live Video Captioning

Run from `live-video-captioning/app/`. Host Python 3.12 with deps already installed works; no venv needed on this box.

## Mandatory

```bash
cd app
python3 -m pytest -q                          # full suite, ~3 s, 251 tests
python3 -m pytest -q tests/test_routes_runs.py   # single file
```

- Tests mock MQTT and the pipeline server — the compose stack does NOT need to be running.
- Before committing: keep coverage ≥ 80% (`--cov=backend --cov=main --cov-fail-under=80`).
- End-to-end verification is a different job → use `/lvc-run-app`.

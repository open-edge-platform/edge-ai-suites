---
name: rtsu-testing
description: Run focused tests, the full Real Time Scene Understanding pytest suite, coverage, and runtime validation for code and configuration changes.
license: Apache-2.0
---

<!--
SPDX-FileCopyrightText: (C) 2026 Intel Corporation
SPDX-License-Identifier: Apache-2.0
-->

# Real Time Scene Understanding Testing

Use this skill when changing Python backend code, routes, services, configuration behavior, or tests, and when the user asks to verify the project.

## Test setup

Run from the application directory:

```bash
cd app
uv sync --group dev
```

The project requires Python 3.12 or newer. Use the project environment's `pytest` when `uv` is unavailable.

## Focused tests

Run the smallest relevant test file first. Examples:

```bash
cd app
uv run pytest tests/test_frame_registry.py
uv run pytest tests/test_routes_stream.py
uv run pytest tests/test_vlm_engine.py
```

For a single test, use pytest's node selection:

```bash
uv run pytest tests/test_main.py::TestMainEntrypoint::test_health_endpoint_works_via_main_app
```

Choose tests based on the changed area: routes for API changes, registry or stream manager tests for stream behavior, VLM tests for model parsing and inference helpers, and storage tests for object handling.

## Full test suite

After focused tests pass, run the complete suite from `app/`:

```bash
uv run pytest
```

The full suite is required before reporting a backend change as fully verified. It covers the tests under `app/tests/` as configured by `pyproject.toml`.

## Coverage

Run terminal coverage when assessing test completeness:

```bash
cd app
uv run pytest --cov=backend --cov=main --cov-report=term-missing
```

Generate an HTML report when detailed inspection is needed:

```bash
uv run pytest --cov=backend --cov=main --cov-report=html
```

## Runtime and Compose changes

For Compose, model, environment, or device changes, supplement unit tests with:

```bash
docker compose config --quiet
docker compose ps
curl --fail http://localhost:${PORT:-9100}/api/health
```

Use service logs when health checks fail. Do not claim that a runtime or hardware-specific change works based only on unit tests.

## Test change expectations

- Add focused tests for behavior changes.
- Keep tests deterministic and avoid real external cameras, model downloads, or cloud services unless the test explicitly requires an integration environment.
- Do not commit credentials, tokens, model weights, generated coverage output, or captured sensitive stream data.
- Report focused test results, full-suite results, and any runtime checks separately.
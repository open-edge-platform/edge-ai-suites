# Tests

Test suites for the smart-classroom backend. Split by layer:
- `tests/unit/` — fast unit tests for individual modules.
- `tests/integration/` — orchestration-layer tests over the `/api/v1/sessions` flow, with heavy components mocked.

## Required Python packages

```bash
pip install pytest fastapi httpx
```

`httpx` is required by FastAPI's `TestClient`.

## How to run

**Run from the `smart-classroom/` directory** (the tests import project-internal
`utils/`, `services/`, `api/`).

### Run all tests

```bash
python -m pytest
```

pytest reads `pytest.ini`: `testpaths = tests`, so it automatically collects both
`tests/unit/` and `tests/integration/`.

### Run only one layer

```bash
python -m pytest tests/unit          # unit tests only
python -m pytest tests/integration   # integration tests only
```

### Run a single test file

```bash
python -m pytest tests/unit/test_session_store.py
python -m pytest tests/integration/test_process_validation.py
```

### Run a single test case

```bash
python -m pytest tests/unit/test_session_store.py::test_create_and_update_new_columns
python -m pytest tests/integration/test_cancel.py::test_cancel_va_session
```

### Useful flags

```bash
python -m pytest -v        # verbose (one line per case)
python -m pytest -q        # quiet
python -m pytest -k cancel # only cases whose name contains "cancel"
```
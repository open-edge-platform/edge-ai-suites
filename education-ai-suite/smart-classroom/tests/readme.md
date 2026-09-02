# Unit Tests

## Required Python packages

```bash
pip install pytest
```

## How to run

**Run from the `smart-classroom/` directory** (the tests import project-internal
`utils/`, `services/`, `api/`).

### Run all tests

```bash
python -m pytest
```

pytest reads `pytest.ini`: `testpaths = tests`, so it automatically collects only the
tests under `tests/`.

### Run a single test file

```bash
python -m pytest tests/test_session_service.py
python -m pytest tests/test_orchestrator_registry.py
```

### Run a single test case

```bash
python -m pytest tests/test_session_service.py::test_cancel_calls_request_cancel
```

### Useful flags

```bash
python -m pytest -v        # verbose (one line per case)
python -m pytest -q        # quiet
python -m pytest -k cancel # only cases whose name contains "cancel"
```
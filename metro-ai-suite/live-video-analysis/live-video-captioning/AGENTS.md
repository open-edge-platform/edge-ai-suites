# AGENTS.md - Live Video Captioning

You are an AI assistant working on the Live Video Captioning project. This document provides the specific instructions, patterns, and boundaries for making changes to this codebase.

## Project Overview

Live Video Captioning is an AI-powered application that processes live RTSP video streams using Deep Learning Streamer (DL Streamer) and OpenVINO™ Vision Language Models (VLMs) to generate real-time captions. The system includes:

- **Backend**: FastAPI REST API with MQTT integration for pipeline management
- **Frontend**: Web UI with WebRTC video streaming and real-time caption display
- **Models**: OpenVINO-optimized VLMs (InternVL, MiniCPM) for video understanding
- **Infrastructure**: Docker Compose setup with MQTT broker, RTSP sources, and pipeline servers

## Tech Stack & Versions

- **Python**: >=3.12
- **FastAPI**: 0.128.0 (with standard extras)
- **Uvicorn**: 0.40.0
- **MQTT**: paho-mqtt 2.1.0
- **Testing**: pytest >=8.0, pytest-asyncio >=0.24, pytest-cov >=6.0, httpx >=0.27
- **Models**: OpenVINO Vision Language Models (InternVL2_5, InternVL3, MiniCPM-V)
- **Inference Engine**: OpenVINO (Intel hardware optimized)

## Project Structure

```
live-video-captioning/
├── app/                          # Main application package
│   ├── main.py                   # FastAPI app entry point
│   ├── pyproject.toml            # Python package config and dependencies
│   ├── Dockerfile                # Container image definition
│   ├── backend/                  # Core API implementation
│   │   ├── __init__.py
│   │   ├── config.py             # Environment configuration and defaults
│   │   ├── state.py              # Global application state (runs tracking)
│   │   ├── models/               # Model loading and inference utilities
│   │   ├── routes/               # FastAPI route handlers
│   │   │   ├── config.py         # GET config, GET/PUT detection pipeline settings
│   │   │   ├── health.py         # GET /health endpoint
│   │   │   ├── models.py         # GET available models, GET model details
│   │   │   ├── pipelines.py      # GET available pipelines, POST run
│   │   │   └── runs.py           # GET/POST runs, WebSocket for captions
│   │   └── services/             # Business logic and external integrations
│   │       ├── mqtt_subscriber.py # MQTT connection and topic subscription
│   │       └── http_client.py     # HTTP requests to pipeline server
│   ├── tests/                    # Test suite
│   │   ├── conftest.py           # Shared fixtures and test configuration
│   │   ├── test_*.py             # Unit and integration tests (one per module)
│   │   └── __pycache__/          # Cached test artifacts (ignore)
│   └── ui/                       # Frontend static files
│       ├── index.html
│       ├── js/                   # JavaScript application code
│       └── css/                  # Stylesheets
├── docs/user-guide/              # User documentation
│   ├── get-started.md
│   ├── api-reference.md
│   ├── how-it-works.md
│   └── _assets/                  # Images and diagrams
├── ov_models/                    # OpenVINO Vision Language Models
│   ├── InternVL2_5-1B/
│   ├── InternVL2_5-2B/
│   ├── InternVL3-1B/
│   └── ...                       # Tokenizer configs, model weights
├── ov_detection_models/          # Object detection models (YOLOv8)
│   └── yolov8s/
├── collector/                    # Metrics collection config
│   └── telegraf.conf
├── mosquitto/                    # MQTT broker configuration
│   └── mosquitto.conf
├── compose.yaml                  # Docker Compose orchestration
├── config.json                   # Application configuration
├── download_models.sh            # Model download helper script
└── README.md                     # User-facing documentation
```

## Core Build & Test Commands

Run these commands from the `app/` directory of the repository:

### Setup & Installation

```bash
# Install dependencies with test extras
pip install -e ".[test]"

# Or install just the core dependencies
pip install -e .
```

### Testing

```bash
# Run all tests with coverage report
pytest -v --cov=backend --cov=main --cov-report=html --cov-report=term-missing

# Run tests from a specific file
pytest -v tests/test_routes_runs.py

# Run a single test function
pytest -v tests/test_routes_runs.py::test_get_runs_returns_empty_list

# Run tests matching a pattern
pytest -v -k "test_config" --tb=short

# Run tests with asyncio debugging
pytest -v tests/ -o log_cli=true --log-cli-level=DEBUG
```

### Code Quality & Verification

```bash
# Check test coverage threshold (must be >= 80%)
pytest tests/ --cov=backend --cov=main --cov-fail-under=80

# Run linting (if configured)
# Note: Install linting tools as needed for your style checks
```

## Testing Guidelines

### Test Organization

- **File naming**: `test_<module_name>.py` (e.g., `test_routes_runs.py` for `routes/runs.py`)
- **Test location**: All tests belong in `app/tests/`
- **Fixture usage**: Use `conftest.py` for shared fixtures (client, mock_mqtt, _patch_config)

### Mandatory Test Coverage

- Minimum coverage: **80%** for `backend/` and `main.py`
- Always test error cases (missing IDs, invalid inputs, connection failures)
- For async code, use `@pytest.mark.asyncio` and `await` in test functions
- Mock external dependencies (MQTT, HTTP calls to pipeline server)

### Running Tests Before Changes

**Always run the full test suite before committing changes:**

```bash
# Full test suite with coverage
pytest -v --cov=backend --cov=main --cov-fail-under=80

# If coverage fails, identify missing coverage
pytest -v --cov=backend --cov=main --cov-report=html
open htmlcov/index.html  # Review uncovered lines
```

## API Structure (Routes)

The FastAPI application exposes these route groups:

### `/health` - Health Check
- `GET /health` - System health and component status

### `/config` - Configuration
- `GET /config` - Retrieve current configuration
- `PUT /config` - Update detection pipeline settings

### `/models` - Model Management
- `GET /models` - List all available vision language models
- `GET /models/{model_id}` - Get specific model details

### `/pipelines` - Pipeline Management
- `GET /pipelines` - List available inference pipelines
- `POST /pipelines/{pipeline_id}/run` - Start a new pipeline run

### `/runs` - Run Management & WebSocket
- `GET /runs` - List all active and historical runs
- `POST /runs` - Create a new run
- `GET /runs/{run_id}` - Get run status and metadata
- `WebSocket /runs/{run_id}/captions` - Real-time caption stream for a run

## File Modification Rules

### Always Do

✅ **Write tests** for any new route, service, or model function
✅ **Run full test suite** before submitting changes: `pytest -v --cov=backend --cov=main --cov-fail-under=80`
✅ **Update type hints** - all functions must have return types and parameter types
✅ **Add docstrings** if adding a new function, class, or module
✅ **Use environment variables** in `backend/config.py` for all configuration
✅ **Mock external services** (MQTT, HTTP clients) in tests using `pytest` fixtures
✅ **Keep tests isolated** - each test should clean up after itself; we have autouse fixtures for this
✅ **Follow naming conventions** - snake_case for functions, PascalCase for classes

### Ask First

⚠️ **Before adding new dependencies**: Check `pyproject.toml` and ensure no conflicts with existing versions
⚠️ **Before modifying `backend/config.py`**: Coordinate config changes across tests (tests override in fixtures)
⚠️ **Before changing test infrastructure** (conftest.py fixtures): Consider impact on all existing tests
⚠️ **Before modifying routes** that have WebSocket connections: Ensure backward compatibility with frontend
⚠️ **Before refactoring state management** in `backend/state.py`: This is shared global state; changes affect all routes

### Never Do

🚫 **Never commit API keys, credentials, or secrets** - use environment variables in `config.py` with defaults
🚫 **Never modify `ov_models/` or `ov_detection_models/`** directories directly - these are generated by download script
🚫 **Never import from `tests/`** in production code - tests are isolated
🚫 **Never use relative imports** - always use absolute imports (e.g., `from backend.config import ...`)
🚫 **Never disable test coverage checks** - maintain the 80% threshold
🚫 **Never add synchronous blocking calls** in async functions - use async libraries (httpx, asyncio)
🚫 **Never hardcode configuration values** - all config must go through `backend/config.py`
🚫 **Never commit model files** - only include config, tokenizers, and references; models are downloaded at build time

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app creation, router registration, lifespan events |
| `app/backend/config.py` | Environment variable defaults and configuration constants |
| `app/backend/state.py` | Global `RUNS` dict and run state management |
| `app/backend/routes/*.py` | Endpoint implementations (config, models, pipelines, runs, health) |
| `app/backend/services/*.py` | Business logic (MQTT, HTTP client functions) |
| `app/tests/conftest.py` | Shared test fixtures, mocks, and test setup |
| `app/pyproject.toml` | Python package metadata, dependencies, pytest config, coverage config |
| `compose.yaml` | Docker Compose definitions for all services |
| `docs/user-guide/` | User-facing documentation (not for agents) |

## Additional Resources

- **API Documentation**: See `docs/user-guide/api-reference.md`
- **System Architecture**: See `docs/user-guide/how-it-works.md`
- **Getting Started**: See `docs/user-guide/get-started.md`
- **Release Notes**: See `docs/user-guide/release-notes.md`

---

**Last Updated**: March 2025

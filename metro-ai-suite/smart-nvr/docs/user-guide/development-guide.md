# Development Guide

Quick reference for developers contributing to Smart NVR.

## Setup

Install [uv](https://docs.astral.sh/uv/), then create the development environment
(runtime + test dependencies) from the lockfile:

```bash
uv sync
```

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov=ui --cov-report=term-missing:skip-covered

# Generate HTML coverage report (optional)
uv run coverage html
```

Open `htmlcov/index.html` to view coverage details.

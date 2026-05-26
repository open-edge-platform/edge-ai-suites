# Development Guide

Quick reference for developers contributing to Smart NVR.

## Setup

Install development dependencies:

```bash
poetry install --with test
```

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run with coverage report
poetry run pytest --cov=src --cov=ui --cov-report=term-missing:skip-covered

# Generate HTML coverage report (optional)
poetry run coverage html
```

Open `htmlcov/index.html` to view coverage details.


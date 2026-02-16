# Running Unit Tests for Smart Traffic Intersection Agent

This guide will help you run the unit tests for the Smart Traffic Intersection Agent project using the pytest framework.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Running Tests in a Virtual Environment](#running-tests-in-a-virtual-environment)
- [Test Files](#test-files)

---

## Prerequisites

Before running the tests, ensure you have the following installed:

- Python 3.10+
- `pip` (Python package installer)
- `uv` (Python package and project manager) - Optional but recommended

You can install `uv` using the following command:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Running Tests in a Virtual Environment

Follow these steps to run the tests:

1. **Clone the Repository**

   Clone the repository to your local machine:

   ```bash
   git clone https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites/metro-ai-suite/smart-traffic-intersection-agent
   ```

2. **Create and Activate a Virtual Environment**

   Navigate to the project directory and create a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Dependencies**

   Install application and dev dependencies:

   ```bash
   # Using uv (recommended)
   cd src
   uv pip install -e ".[dev]"
   
   # Or using pip
   cd src
   pip install -e ".[dev]"
   ```

4. **Navigate to the Project Root**

   Change to the project root directory (where `pytest.ini` is located):

   ```bash
   cd /path/to/edge-ai-suites/metro-ai-suite/smart-traffic-intersection-agent
   ```

5. **Run the Tests**

   **Important:** Make sure the virtual environment is activated before running tests. You should see `(.venv)` in your terminal prompt.

   ```bash
   # Verify you're in the virtual environment (should show .venv path)
   which python
   # Expected: /path/to/smart-traffic-intersection-agent/.venv/bin/python
   
   # If not activated, activate it first:
   source .venv/bin/activate
   ```

   Use the below command to run all unit tests:

   ```bash
   pytest tests/unit -v
   ```

   To run a specific test file:

   ```bash
   pytest tests/unit/test_data_aggregator.py -v
   ```

   To run tests with coverage report:

   ```bash
   pytest tests/unit --cov=src --cov-report=term-missing
   ```

6. **Deactivate Virtual Environment**

   When you are done with testing:

   ```bash
   deactivate
   ```

---

## Test Files

The following unit test files are available:

| Test File | Description |
|-----------|-------------|
| `test_api_routes.py` | Tests for FastAPI route endpoints |
| `test_config_service.py` | Tests for configuration service |
| `test_data_aggregator.py` | Tests for data aggregation service |
| `test_main.py` | Tests for main application entry point |
| `test_mqtt_service.py` | Tests for MQTT communication service |
| `test_run.py` | Tests for application runner |
| `test_ui_components.py` | Tests for UI components |
| `test_vlm_service.py` | Tests for VLM (Vision Language Model) service |
| `test_weather_service.py` | Tests for weather data service |

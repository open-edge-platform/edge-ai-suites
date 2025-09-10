<!--
# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.
-->

# Testing with Pytest

- [Testing with Pytest](#testing-with-pytest)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Running tests](#running-tests)

## Prerequisites

- Python 3.12 or higher
- Python venv installed
- Latest Chrome browser installed
- **For remote endpoint tests**: Configure remote URLs in the `.env` file inside smart-instersection directory for the following variables:
  - `SCENESCAPE_REMOTE_URL`
  - `GRAFANA_REMOTE_URL`
  - `INFLUX_REMOTE_DB_URL`
  - `NODE_RED_REMOTE_URL`
  
  These should contain the external IP address of the machine running the Docker containers and the corresponding service ports. For example:
  ```
  SCENESCAPE_REMOTE_URL="https://YOUR_MACHINE_IP"
  GRAFANA_REMOTE_URL="http://YOUR_MACHINE_IP:3000"
  INFLUX_REMOTE_DB_URL="http://YOUR_MACHINE_IP:8086"
  NODE_RED_REMOTE_URL="http://YOUR_MACHINE_IP:1880"
  ```
  
  Replace `YOUR_MACHINE_IP` with the actual IP address of your machine. If you do not set those URLs, remote endpoint tests will be skipped.

**Note:** Some tests executed in the Kubernetes environment require privileged port forwarding using `kubectl port-forward` with `sudo`. In such cases (e.g., port 443), you need to set the `SUDO_PASSWORD` environment variable to your sudo password before running the tests, or they will fail.  

```bash
export SUDO_PASSWORD=your_sudo_password
```

## Installation

- Clone the repository and install prerequisites according to the following guides (for Kubernetes, also set up proxy settings if needed):
  - [Docker Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/get-started.md)
  - [Kubernetes Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/how-to-deploy-helm.md)

1. **Navigate to the smart-intersection directory:**

   ```bash
   cd smart-intersection
   ```

2. **Create a virtual environment on your system:**

   ```bash
   python3 -m venv venv
   ```

3. **Activate the virtual environment:**

   ```bash
   source venv/bin/activate
   ```

4. **Install the required packages using pip:**

   ```bash
   python3 -m pip install -r requirements.txt
   ```

Now you are ready to run tests on your system. 

## Running tests

Use `pytest` to run tests based on either Docker or Kubernetes, using the `-m docker` or `-m kubernetes` options. Docker is the default, so you do not need to define it explicitly.

```bash
# Run all Docker tests (default)
pytest tests

# Run all Docker tests (explicit)
pytest -m docker

# Run all Kubernetes tests
pytest -m kubernetes

# Run a specific Docker test
pytest tests/test_admin.py::test_login_docker

# Run a specific Kubernetes test
pytest -m kubernetes tests/test_admin.py::test_login_kubernetes
```
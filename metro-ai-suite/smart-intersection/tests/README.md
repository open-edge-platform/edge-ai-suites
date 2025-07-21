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
- **For remote endpoint tests**: Configure remote URLs in the `.env` file for the following variables:
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

- Prepare your environment according to the following guides:
  - [Get Started Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-intersection/docs/user-guide/get-started.md)
  - [Docker Deployment Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-intersection/docs/user-guide/how-to-deploy-docker.md)

## Installation

1. **Create a virtual environment on your system:**

   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment:**

   ```bash
   source venv/bin/activate
   ```

3. **Install the required packages using pip:**

   ```bash
   python3 -m pip install -r requirements.txt
   ```

Now you are ready to run tests on your system. 

## Running tests

Use pytest to run all or selected tests:

```bash
# Run all tests
pytest tests

# Run a specific test
pytest tests/test_admin.py::test_login
```

# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
import time
from tests.utils.utils import run_command

DOCKER_COMPOSE_FILE = "compose.yml" 
SMART_INTERSECTION_URL = "https://localhost"
GRAFANA_URL = "http://localhost:3000"
INFLUX_DB_URL = "http://localhost:8086"
NODE_RED_URL = "http://localhost:1880"

@pytest.fixture(scope="session", autouse=True)
def build_and_deploy():
  # Build docker images
  out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} build")
  assert code == 0, f"Build failed: {err}"

  # Deploy (up) docker containers
  out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} up -d")
  assert code == 0, f"Deploy failed: {err}"

  # Wait for services to be healthy (adjust timeout as needed)
  time.sleep(120)

  yield

  # Teardown: stop and remove containers
  run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} down")
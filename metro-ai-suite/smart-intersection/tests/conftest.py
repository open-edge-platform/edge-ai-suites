# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
import time
import os
import subprocess
import requests
from dotenv import load_dotenv
from tests.utils.utils import run_command, check_components_access

load_dotenv()

DOCKER_COMPOSE_FILE = os.getenv("DOCKER_COMPOSE_FILE", "compose.yml")
SMART_INTERSECTION_URL = os.getenv("SMART_INTERSECTION_URL", "https://localhost")
GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
INFLUX_DB_URL = os.getenv("INFLUX_DB_URL", "http://localhost:8086")
NODE_RED_URL = os.getenv("NODE_RED_URL", "http://localhost:1880")


def wait_for_services_readiness(services_urls, timeout=120, interval=2):
    """
    Waits for services to become available.

    :param services_urls: List of URLs to check.
    :param timeout: Maximum time to wait for services to be available (in seconds).
    :param interval: Time between checks (in seconds).
    :raises TimeoutError: If services are not available within the timeout period.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        all_services_ready = True
        for url in services_urls:
            try:
                check_components_access(url)
            except AssertionError as e:
                all_services_ready = False
                break
        if all_services_ready:
            print("All services are ready.")
            return True
        print("Waiting for services to be ready...")
        time.sleep(interval)
    raise TimeoutError("Services did not become ready in time.")

@pytest.fixture(scope="session", autouse=True)
def build_and_deploy():
    """
    Fixture to build and deploy Docker containers for testing.

    This fixture is automatically used for the entire test session.
    """
    # Build Docker images
    out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} build")
    assert code == 0, f"Build failed: {err}"

    # Deploy (up) Docker containers
    out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} up -d")
    assert code == 0, f"Deploy failed: {err}"

    # Wait for services to be ready    
    services_urls = [SMART_INTERSECTION_URL, GRAFANA_URL, INFLUX_DB_URL, NODE_RED_URL]
    wait_for_services_readiness(services_urls)

    yield

    # Teardown: stop and remove containers
    run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} down")

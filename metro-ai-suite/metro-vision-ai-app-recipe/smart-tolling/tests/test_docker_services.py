# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import subprocess
import time
import logging
import docker
import pytest
import json
from tests.utils.docker_utils import get_all_services, get_running_services
from tests.utils.ui_utils import waiter, driver
from tests.utils.utils import run_command, check_urls_access
from .conftest import (
  wait_for_services_readiness,
  SCENESCAPE_URL,
  GRAFANA_URL,
  INFLUX_DB_URL,
  NODE_RED_URL
)

logger = logging.getLogger(__name__)

DLSTREAMER_CONTAINER = "metro-vision-ai-app-recipe-dlstreamer-pipeline-server-1"
SERIVES_URLS = [
  SCENESCAPE_URL,
  GRAFANA_URL,
  INFLUX_DB_URL,
  NODE_RED_URL,
]

def wait_for_container_to_start(container, timeout=30):
  """Wait for the container to be in 'running' state."""
  for _ in range(timeout):
    container.reload()
    if container.status == 'running':
      return True
    time.sleep(1)
  return False

def get_running_dlstreamer_container():
  """Get DLStreamer container if it exists and is running, otherwise fail test."""
  client = docker.from_env()
  try:
    container = client.containers.get(DLSTREAMER_CONTAINER)
    assert container.status == 'running', f"DLStreamer container is not running (status: {container.status})"
    return container
  except docker.errors.NotFound:
    assert False, f"DLStreamer container '{DLSTREAMER_CONTAINER}' not found"


@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9625")
def test_components_access_with_no_dlstreamer_docker():
  """Test that all application components are accessible without DLStreamer."""
  container = get_running_dlstreamer_container()

  # Check initial access - all services should be running
  check_urls_access(SERIVES_URLS)

  # Stop the container
  container.stop()

  # Wait for the container to stop with a timeout
  try:
    result = container.wait(timeout=30)
    logger.info(f"Container stopped with status: {result['StatusCode']}")
  except docker.errors.APIError as e:
    logger.error(f"Error waiting for container to stop: {e}")
    assert False, f"Container failed to stop: {e}"

  # Check URL access after stopping the container
  check_urls_access(SERIVES_URLS)

  # Start the container
  container.start()

  # Wait for the container to start
  assert wait_for_container_to_start(container, timeout=30), "Container did not start - next tests may fail"

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9626")
def test_components_access_after_dlstreamer_restart_docker():
  """Test that all application components are accessible after DLStreamer container restart."""
  container = get_running_dlstreamer_container()

  # Check initial access - all services should be running
  check_urls_access(SERIVES_URLS)

  # Restart the container
  container.restart(timeout=30)

  # Wait for the container to be ready after restart
  assert wait_for_container_to_start(container, timeout=30), "Container did not start after restart"

  # Check URL access after restart
  check_urls_access(SERIVES_URLS)


@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9366")
def test_docker_build_and_deployment_docker():
  """Test that all docker-compose services are running after build and deploy."""
  running = get_running_services()
  expected = get_all_services()
  assert expected == running, f"Not all services are running. Expected: {expected}, Running: {running}"

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9376")
def test_docker_application_restart_docker():
  """Test that all application components are accessible after Docker restart."""
  # Teardown: stop and remove containers
  logger.info("Tearing down Docker containers...")
  run_command(f"docker compose down")
  logger.info("Docker containers stopped and removed.")
    
  # Build and Deploy Docker images
  logger.info("Building and deploying Docker containers...")
  out, err, code = run_command(f"docker compose up -d")
  assert code == 0, f"Build and Deploy failed: {err}"
  logger.info("Docker containers deployed.")

  # Wait for services to be ready
  wait_for_services_readiness(SERIVES_URLS)

  check_urls_access(SERIVES_URLS)

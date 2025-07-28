# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
import logging
import time
import os
import subprocess
import requests
from dotenv import load_dotenv
from tests.utils.utils import (
  run_command,
  check_url_access,
  get_password_from_supass_file,
  get_username_from_influxdb2_admin_username_file,
  get_password_from_influxdb2_admin_password_file
)

load_dotenv()
logger = logging.getLogger(__name__)

SCENESCAPE_URL = os.getenv("SCENESCAPE_URL", "https://localhost")
SCENESCAPE_REMOTE_URL = os.getenv("SCENESCAPE_REMOTE_URL")

SCENESCAPE_USERNAME = os.getenv("SCENESCAPE_USERNAME", "admin")
SCENESCAPE_PASSWORD = os.getenv("SCENESCAPE_PASSWORD", get_password_from_supass_file())

GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3000")
GRAFANA_REMOTE_URL = os.getenv("GRAFANA_REMOTE_URL")
GRAFANA_USERNAME = os.getenv("GRAFANA_USERNAME", "admin")
GRAFANA_PASSWORD = os.getenv("GRAFANA_PASSWORD", "admin")

INFLUX_DB_URL = os.getenv("INFLUX_DB_URL", "http://localhost:8086")
INFLUX_REMOTE_DB_URL = os.getenv("INFLUX_REMOTE_DB_URL")
INFLUX_DB_ADMIN_USERNAME = os.getenv("INFLUX_DB_ADMIN_USERNAME", get_username_from_influxdb2_admin_username_file())
INFLUX_DB_ADMIN_PASSWORD = os.getenv("INFLUX_DB_ADMIN_PASSWORD", get_password_from_influxdb2_admin_password_file())

NODE_RED_URL = os.getenv("NODE_RED_URL", "http://localhost:1880")
NODE_RED_REMOTE_URL = os.getenv("NODE_RED_REMOTE_URL")

PROJECT_GITHUB_URL = os.getenv("PROJECT_GITHUB_URL", "https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-intersection")

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
        check_url_access(url)
      except AssertionError as e:
        all_services_ready = False
        break
    if all_services_ready:
      logger.info("All services are ready.")
      return True
    logger.info("Waiting for services to be ready...")
    time.sleep(interval)
  raise TimeoutError("Services did not become ready in time.")

@pytest.fixture(scope="session", autouse=True)
def build_and_deploy():
  """
  Fixture to build and deploy Docker containers for testing.
  This fixture is automatically used for the entire test session.
  """

  # Build and Deploy Docker images
  logger.info("Building and deploying Docker containers...")
  out, err, code = run_command(f"docker compose up -d")
  assert code == 0, f"Build and Deploy failed: {err}"
  logger.info("Docker containers deployed.")

  # Wait for services to be ready
  services_urls = [SCENESCAPE_URL, GRAFANA_URL, INFLUX_DB_URL, NODE_RED_URL]
  wait_for_services_readiness(services_urls)

  yield

  # Teardown: stop and remove containers
  logger.info("Tearing down Docker containers...")
  run_command(f"docker compose down")
  logger.info("Docker containers stopped and removed.")

  # Remove Docker volumes
  logger.info("Removing Docker volumes...")
  run_command("docker volume ls | grep metro-vision-ai-app-recipe | awk '{ print $2 }' | xargs docker volume rm")
  logger.info("Docker volumes removed.")

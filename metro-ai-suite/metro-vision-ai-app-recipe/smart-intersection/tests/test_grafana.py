# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tests.utils.ui_utils import waiter, driver
from .conftest import GRAFANA_URL, GRAFANA_REMOTE_URL, GRAFANA_USERNAME, GRAFANA_PASSWORD


def check_grafana_panel_value(waiter):
  """Check the value of one of the Grafana panels."""

  # Wait for the section to be present
  section = waiter.wait_and_assert(
    EC.presence_of_element_located((By.CSS_SELECTOR, "section[data-testid='data-testid Panel header South Bound lane - dwell time']")),
    error_message="Panel section is not present on the page"
  )
  
  # Locator for the span element
  span_locator = (By.CSS_SELECTOR, "span.flot-temp-elem")

  # Wait for the text to change from "No data"
  waiter.wait_for_text_change(span_locator, "No data", error_message="'No data' is displayed in the span element")


def navigate_to_dashboard(waiter, url):
  """Perform login and navigate to the Anthem dashboard."""
  waiter.perform_login(
    url,
    By.CSS_SELECTOR, "[data-testid='data-testid Username input field']",
    By.CSS_SELECTOR, "[data-testid='data-testid Password input field']",
    By.CSS_SELECTOR, "[data-testid='data-testid Login button']",
    GRAFANA_USERNAME, GRAFANA_PASSWORD
  )

  skip_button = waiter.wait_and_assert(
    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-testid Skip change password button']")),
    error_message="Skip button is not present on the page"
  )
  skip_button.click()

  dashboards_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-testid Nav menu item'][href='/dashboards']")),
    error_message="Dashboards link is not present on the page"
  )
  dashboards_link.click()

  anthem_dashboard_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.LINK_TEXT, "Anthem-ITS-Data")),
    error_message="Anthem-ITS-Data dashboard link is not present on the page"
  )
  anthem_dashboard_link.click()

def grafana_anthem_dashboard_availability_check(waiter, grafana_url):
  """Test the availability of the Anthem dashboard in Grafana."""
  navigate_to_dashboard(waiter, grafana_url)
  check_grafana_panel_value(waiter)

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T10680")
def test_grafana_anthem_dashboard_availability_kubernetes(waiter):
  """Test the availability of the Anthem dashboard in Grafana for Kubernetes deployment."""
  grafana_anthem_dashboard_availability_check(waiter, GRAFANA_URL)

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9371")
def test_grafana_anthem_dashboard_availability_docker(waiter):
  """Test the availability of the Anthem dashboard in Grafana for Docker deployment."""
  grafana_anthem_dashboard_availability_check(waiter, GRAFANA_URL)

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T10682")
def test_remote_grafana_anthem_dashboard_availability_kubernetes(waiter):
  """Test the availability of the Anthem dashboard in remote Grafana."""
  if not GRAFANA_REMOTE_URL:
    pytest.skip("GRAFANA_REMOTE_URL is not set")

  grafana_anthem_dashboard_availability_check(waiter, GRAFANA_REMOTE_URL)

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9373")
def test_remote_grafana_anthem_dashboard_availability_docker(waiter):
  """Test the availability of the Anthem dashboard in remote Grafana."""
  if not GRAFANA_REMOTE_URL:
    pytest.skip("GRAFANA_REMOTE_URL is not set")

  grafana_anthem_dashboard_availability_check(waiter, GRAFANA_REMOTE_URL)

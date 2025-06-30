# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from .conftest import SMART_INTERSECTION_URL, GRAFANA_URL, INFLUX_DB_URL, NODE_RED_URL
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from tests.utils.ui_utils import driver
from tests.utils.utils import check_components_access, perform_login, get_username_from_influxdb2_admin_username_file, get_password_from_influxdb2_admin_password_file

@pytest.mark.zephyr_id("NEX-T9368")
def test_components_access():
  """Test that all application components are accessible."""
  urls_to_check = [
    SMART_INTERSECTION_URL,
    GRAFANA_URL,
    INFLUX_DB_URL,
    NODE_RED_URL
  ]

  for url in urls_to_check:
    check_components_access(url)


@pytest.mark.zephyr_id("NEX-T9623")
def test_gragana_failed_login(driver):
  perform_login(
    driver,
    GRAFANA_URL,
    By.CSS_SELECTOR, "[data-testid='data-testid Username input field']",
    By.CSS_SELECTOR, "[data-testid='data-testid Password input field']",
    By.CSS_SELECTOR, "[data-testid='data-testid Login button']",
    "wrong_username", "wrong_password"
  )

  try:
    # Wait for the error message element to appear
    WebDriverWait(driver, 10).until(
      EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-testid Alert error']"))
    )    
  except TimeoutException:
    assert False, "Login error message not found within 10 seconds"

@pytest.mark.zephyr_id("NEX-T9617")
def test_influx_db_login(driver):
  perform_login(
    driver,
    INFLUX_DB_URL,
    By.CSS_SELECTOR, "[data-testid='username']",
    By.CSS_SELECTOR, "[data-testid='password']",
    By.CSS_SELECTOR, "[data-testid='button']",
    get_username_from_influxdb2_admin_username_file(), get_password_from_influxdb2_admin_password_file()
  )

  try:
    # Wait for the header element to be visible after login
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='home-page--header']")))
  except TimeoutException:
    assert False, 'Welcome message not visible within 10 seconds after login'

@pytest.mark.zephyr_id("NEX-T9621")
def test_influx_db_failed_login(driver):
  perform_login(
    driver,
    INFLUX_DB_URL,
    By.CSS_SELECTOR, "[data-testid='username']",
    By.CSS_SELECTOR, "[data-testid='password']",
    By.CSS_SELECTOR, "[data-testid='button']",
    "wrong_username", "wrong_password"
  )

  try:
    # Wait for the error notification to be visible after failed login
    WebDriverWait(driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-testid='notification-error--children']")))
  except TimeoutException:
    assert False, 'Error notification not visible within 10 seconds after failed login'

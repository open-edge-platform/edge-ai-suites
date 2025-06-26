# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
import requests
from tests.utils.utils import suppress_insecure_request_warning
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from .conftest import SMART_INTERSECTION_URL, GRAFANA_URL, INFLUX_DB_URL, NODE_RED_URL
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException
from tests.utils.ui_utils import driver

def check_components_access(url):
  """Helper function to check if an components is accessible."""
  try:
    # Send a GET request to the URL, ignoring SSL certificate errors
    response = requests.get(url, verify=False)
    
    # Check if the response status code is 200 (OK)
    assert response.status_code == 200, f"Expected status code 200 for {url}, but got {response.status_code}"
  except requests.exceptions.RequestException as e:
    assert False, f"Request to {url} failed: {e}"

@pytest.mark.zephyr_id("NEX-T9368")
@suppress_insecure_request_warning
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
  driver.get(GRAFANA_URL)  # Load home page

  try:
    # Wait for the 'Username' input to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-testid Username input field']")))
  except TimeoutException:
    assert False, 'Input field not found within 10 seconds'

  username_input = driver.find_element(By.CSS_SELECTOR, "[data-testid='data-testid Username input field']")
  password_input = driver.find_element(By.CSS_SELECTOR, "[data-testid='data-testid Password input field']")
  login_button = driver.find_element(By.CSS_SELECTOR, "[data-testid='data-testid Login button']")

  username_input.send_keys("wrong_username")
  password_input.send_keys("wrong_password")
  login_button.click()  # Try to log in

  try:
    # Wait for the error message element to appear
    WebDriverWait(driver, 10).until(
      EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='data-testid Alert error']"))
    )    
  except TimeoutException:
    assert False, "Login error message not found within 10 seconds"

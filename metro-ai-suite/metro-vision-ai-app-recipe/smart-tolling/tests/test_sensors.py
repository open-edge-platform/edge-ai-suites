# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tests.utils.kubernetes_utils import get_scenescape_kubernetes_url
from tests.utils.ui_utils import waiter, driver
from .conftest import (
  SCENESCAPE_URL,
  SCENESCAPE_USERNAME,
  SCENESCAPE_PASSWORD,  
)

def add_sensor(waiter, sensor_name, sensor_id, url=SCENESCAPE_URL):
  """Helper function to log in and add a new sensor."""
  waiter.perform_login(
    url,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    SCENESCAPE_USERNAME, SCENESCAPE_PASSWORD
  )

  # Find the 'Sensors' navigation link and click it
  sensors_nav_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "nav-sensors")),
    error_message="Sensors navigation link is not present on the page"
  )
  sensors_nav_link.click()

  # Wait for the '+ New Sensor' link to be present and clickable
  new_sensor_link = waiter.wait_and_assert(
    EC.element_to_be_clickable((By.XPATH, "//a[@class='btn btn-primary float-right' and @href='/singleton_sensor/create/']")),
    error_message="'+ New Sensor' link is not clickable"
  )
  new_sensor_link.click()

  # Wait for the 'Add New Sensor' button to be present and clickable
  add_sensor_button = waiter.wait_and_assert(
    EC.element_to_be_clickable((By.XPATH, "//input[@value='Add New Sensor']")),
    error_message="'Add New Sensor' button is not clickable"
  )

  # Fill new sensor form fields
  sensor_id_input = waiter.driver.find_element(By.ID, "id_sensor_id")
  id_name_input = waiter.driver.find_element(By.ID, "id_name")
  id_scene_select = waiter.driver.find_element(By.ID, "id_scene")

  sensor_id_input.send_keys(sensor_id)
  id_name_input.send_keys(sensor_name)
  select = Select(id_scene_select)
  select.select_by_visible_text("Intersection-Demo")

  add_sensor_button.click()

  # Check if the 'Sensors Tab' element is present and click it
  sensors_tab = waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "sensors-tab")),
    error_message="Sensors Tab is not present on the page"
  )
  sensors_tab.click()

  # Verify the sensor ID was added by checking the sensor ID element directly
  waiter.wait_and_assert(
    EC.text_to_be_present_in_element((By.XPATH, f"//td[@class='small sensor-id' and text()='{sensor_id}']"), sensor_id),
    error_message=f"Expected sensor ID '{sensor_id}' not found in sensor ID element"
  )

def delete_sensor_functionality_check(waiter, sensor_name, sensor_id, url):
  """
  Helper function to add and delete a sensor, verifying deletion.
  """
  add_sensor(waiter, sensor_name, sensor_id, url)

  # Verify the presence of the delete link in the same card body
  delete_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, f"//td[@class='small sensor-id' and text()='{sensor_id}']/ancestor::div[@class='card-body']//a[@class='btn btn-secondary btn-sm' and contains(@href, '/delete/')]")),
    error_message=f"Delete link not found for sensor ID '{sensor_id}'"
  )
  delete_link.click()

  # Wait for the 'Yes, Delete the Sensor!' button to be present and clickable
  delete_confirm_button = waiter.wait_and_assert(
    EC.element_to_be_clickable((By.XPATH, "//input[@class='btn btn-primary' and @value='Yes, Delete the Sensor!']")),
    error_message="'Yes, Delete the Sensor!' button is not clickable"
  )
  delete_confirm_button.click()

  # Check if the 'Sensors Tab' element is present and click it
  sensors_tab = waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "sensors-tab")),
    error_message="Sensors Tab is not present on the page"
  )
  sensors_tab.click()

  # Verify the sensor ID was deleted by checking the sensor ID element is no longer present
  waiter.wait_and_assert(
    EC.invisibility_of_element_located((By.XPATH, f"//td[@class='small sensor-id' and text()='{sensor_id}']")),
    error_message=f"Expected sensor ID '{sensor_id}' should not be present after deletion"
  )

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T13925")
def test_add_sensor_kubernetes(waiter):
  """Test that the admin can add a new sensor."""
  name_of_new_sensor = "sensor_NEX-T13925"
  id_of_new_sensor = "sensor_id_NEX-T13925"
  add_sensor(waiter, name_of_new_sensor, id_of_new_sensor, get_scenescape_kubernetes_url())

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9384")
def test_add_sensor_docker(waiter):
  """Test that the admin can add a new sensor."""
  name_of_new_sensor = "sensor_NEX-T9384"
  id_of_new_sensor = "sensor_id_NEX-T9384"
  add_sensor(waiter, name_of_new_sensor, id_of_new_sensor)

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T13926")
def test_delete_sensor_kubernetes(waiter):
  """Test that the admin can delete a new sensor."""
  name_of_new_sensor = "sensor_NEX-T13926"
  id_of_new_sensor = "sensor_id_NEX-T13926"
  delete_sensor_functionality_check(waiter, name_of_new_sensor, id_of_new_sensor, get_scenescape_kubernetes_url())

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9385")
def test_delete_sensor_docker(waiter):
  """Test that the admin can delete a new sensor."""
  name_of_new_sensor = "sensor_NEX-T9385"
  id_of_new_sensor = "sensor_id_NEX-T9385"
  delete_sensor_functionality_check(waiter, name_of_new_sensor, id_of_new_sensor, SCENESCAPE_URL)

# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tests.utils.ui_utils import waiter, driver
from .conftest import SCENESCAPE_URL, SCENESCAPE_USERNAME, SCENESCAPE_PASSWORD


def add_sensor(waiter, sensor_name, sensor_id):
  """Helper function to log in and add a new sensor."""
  waiter.perform_login(
    SCENESCAPE_URL,
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


@pytest.mark.zephyr_id("NEX-T9384")
def test_add_sensor(waiter):
  """Test that the admin can add a new sensor."""
  name_of_new_sensor = "sensor_NEX-T9384"
  id_of_new_sensor = "sensor_id_NEX-T9384"  

  add_sensor(waiter, name_of_new_sensor, id_of_new_sensor)


@pytest.mark.zephyr_id("NEX-T9385")
def test_delete_sensor(waiter):
  """Test that the admin can delete a new sensor."""
  name_of_new_sensor = "sensor_NEX-T9385"
  id_of_new_sensor = "sensor_id_NEX-T9385"

  add_sensor(waiter, name_of_new_sensor, id_of_new_sensor)

  # Verify the presence of the delete link in the same card body
  delete_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, f"//td[@class='small sensor-id' and text()='{id_of_new_sensor}']/ancestor::div[@class='card-body']//a[@class='btn btn-secondary btn-sm' and contains(@href, '/delete/')]")),
    error_message=f"Delete link not found for sensor ID '{id_of_new_sensor}'"
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
    EC.invisibility_of_element_located((By.XPATH, f"//td[@class='small sensor-id' and text()='{id_of_new_sensor}']")),
    error_message=f"Expected sensor ID '{id_of_new_sensor}' should not be present after deletion"
  )

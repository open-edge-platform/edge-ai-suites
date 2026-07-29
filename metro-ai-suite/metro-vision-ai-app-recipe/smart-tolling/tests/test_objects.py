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

def add_object(waiter, object_name, url=SCENESCAPE_URL):
  """Helper function to log in and add a new object."""
  waiter.perform_login(
    url,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    SCENESCAPE_USERNAME, SCENESCAPE_PASSWORD
  )

  # Wait for the 'Object Library' navigation link and click it
  object_library_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "nav-object-library")),
    error_message="Object Library navigation link is not present on the page"
  )
  object_library_link.click()

  # Wait for the '+ New Object' button and click it
  new_object_button = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, "//a[@class='btn btn-primary float-right' and @href='/asset/create/']")),
    error_message="+ New Object button is not present on the page"
  )
  new_object_button.click()

  # Wait for the 'Add New Object'
  add_new_object_button = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, "//input[@class='btn btn-primary' and @value='Add New Object']")),
    error_message="Add New Object button is not present on the page"
  )

  object_name_input = waiter.driver.find_element(By.ID, "id_name")
  object_name_input.send_keys(object_name)

  add_new_object_button.click()

  # Wait for the table row containing the object name
  object_row = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, f"//tr/td[text()='{object_name}']")),
    error_message=f"Table row with object name '{object_name}' is not present on the page"
  )

def delete_object_functionality_check(waiter, object_name, url=SCENESCAPE_URL):
  """
  Helper function to test that the admin can delete an existing object.
  """
  add_object(waiter, object_name, url)

  # Find the delete link in the same row and click it
  delete_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, f"//tr[td[text()='{object_name}']]/td/a[contains(@href, '/asset/delete/')]")),
    error_message=f"Delete link for object '{object_name}' is not present on the page"
  )
  delete_link.click()

  # Wait for the 'Yes, Delete the Object!' button and click it
  confirm_delete_button = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, "//input[@class='btn btn-primary' and @value='Yes, Delete the Object!']")),
    error_message="Confirmation button 'Yes, Delete the Object!' is not present on the page"
  )
  confirm_delete_button.click()

  # Wait to verify that the object row is no longer present
  waiter.wait_and_assert(
    EC.invisibility_of_element_located((By.XPATH, f"//tr/td[text()='{object_name}']")),
    error_message=f"Table row with object name '{object_name}' is not present on the page"
  )

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T13921")
def test_add_object_kubernetes(waiter):
  """Test that the admin can add a new object."""
  add_object(waiter, "object_NEX-T13921", get_scenescape_kubernetes_url())

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9386")
def test_add_object_docker(waiter):
  """Test that the admin can add a new object."""
  add_object(waiter, "object_NEX-T9386")

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T13922")
def test_delete_object_kubernetes(waiter):
  """Test that the admin can delete an existing object."""
  delete_object_functionality_check(waiter, "object_NEX-T13922", get_scenescape_kubernetes_url())

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9387")
def test_delete_object_docker(waiter):
  """Test that the admin can delete an existing object."""
  delete_object_functionality_check(waiter, "object_NEX-T9387")

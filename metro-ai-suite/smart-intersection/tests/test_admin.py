# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import time
import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from tests.utils.ui_utils import driver
from tests.utils.utils import perform_login, get_password_from_supass_file
from .conftest import SMART_INTERSECTION_URL

@pytest.mark.zephyr_id("NEX-T9389")
def test_login(driver):
  """Test that the admin login functionality works correctly."""
  perform_login(
    driver,
    SMART_INTERSECTION_URL,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    "admin", get_password_from_supass_file()
  )

  # Verify that the expected elements are present on the page
  assert (
    driver.find_element(By.ID, "nav-scenes") and
    driver.find_element(By.ID, "nav-cameras")
  )


@pytest.mark.zephyr_id("NEX-T9390")
def test_logout(driver):
  """Test that the admin login functionality works correctly."""
  perform_login(
    driver,
    SMART_INTERSECTION_URL,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    "admin", get_password_from_supass_file()
  )

  # Verify that the expected elements are present on the page
  assert (
    driver.find_element(By.ID, "nav-scenes") and
    driver.find_element(By.ID, "nav-cameras")
  )

    # Perform logout action
  logout_link = driver.find_element(By.ID, "nav-sign-out")
  logout_link.click()

  try:
    # Wait for the 'username' input to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))
  except TimeoutException:
    assert False, '"username" input field not found within 10 seconds'


@pytest.mark.zephyr_id("NEX-T9388")
def test_change_password(driver):
  """Test that the admin can change the password successfully."""
  perform_login(
    driver,
    SMART_INTERSECTION_URL,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    "admin", get_password_from_supass_file()
  )

  # Navigate to Password change page
  driver.get(SMART_INTERSECTION_URL + "/admin/password_change")

  try:
    # Wait for the password fields to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_old_password")))
  except TimeoutException:
    assert False, 'Password fields not found within 10 seconds'

  old_password_input = driver.find_element(By.ID, "id_old_password")
  new_password1_input = driver.find_element(By.ID, "id_new_password1")
  new_password2_input = driver.find_element(By.ID, "id_new_password2")

  old_password_input.send_keys(get_password_from_supass_file())
  new_password1_input.send_keys(get_password_from_supass_file())
  new_password2_input.send_keys(get_password_from_supass_file())

  # Submit the password change
  submit_button = driver.find_element(By.XPATH, "//input[@type='submit' and @value='Change my password']")
  submit_button.click()

  try:
    # Wait for the success message to be present
    WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Password change successful"))
  except TimeoutException:
    assert False, '"Password change successful" message not found within 10 seconds'

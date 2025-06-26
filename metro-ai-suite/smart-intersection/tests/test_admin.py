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
from tests.utils.utils import get_password_from_supass_file
from .conftest import SMART_INTERSECTION_URL

def perform_successful_login(driver):
  """Helper function to perform successful login with default credentials."""
  username = "admin"
  password = get_password_from_supass_file()
  login(driver, username, password)

def login(driver, username, password):
  """Helper function to log in to the application."""
  driver.get(SMART_INTERSECTION_URL) # load home page
  
  try:
    # Wait for the 'username' input to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username")))
  except TimeoutException:
    assert False, '"username" input field not found within 10 seconds'
    
  username_input = driver.find_element(By.ID, "username")
  password_input = driver.find_element(By.ID, "password")
  login_button = driver.find_element(By.ID, "login-submit")

  username_input.send_keys(username)
  password_input.send_keys(password)
  login_button.click() # try to log in
 
  try:
    # Wait for either the next page element or the login error message
    WebDriverWait(driver, 10).until(
      EC.any_of(
        EC.presence_of_element_located((By.ID, "nav-scenes")),
        EC.presence_of_element_located((By.CLASS_NAME, "login-error"))
      )
    )
  except TimeoutException:
    assert False, "Neither next page element nor login error found within 10 seconds"

  # Check if login error is present
  if driver.find_elements(By.CLASS_NAME, "login-error"):
    assert False, "Login failed: Incorrect username or password"

def fill_password_fields(driver):
  """Helper function to fill in the password fields."""
  old_password_input = driver.find_element(By.ID, "id_old_password")
  new_password1_input = driver.find_element(By.ID, "id_new_password1")
  new_password2_input = driver.find_element(By.ID, "id_new_password2")

  old_password_input.send_keys(get_password_from_supass_file())
  new_password1_input.send_keys(get_password_from_supass_file())
  new_password2_input.send_keys(get_password_from_supass_file())

@pytest.mark.zephyr_id("NEX-T9389")
def test_login(driver):
  """Test that the admin login functionality works correctly."""
  perform_successful_login(driver)  # Use the helper function to log in

  # Verify that the expected elements are present on the page
  assert (
    driver.find_element(By.ID, "nav-scenes") and
    driver.find_element(By.ID, "nav-cameras")
  )


@pytest.mark.zephyr_id("NEX-T9390")
def test_logout(driver):
  """Test that the admin login functionality works correctly."""
  perform_successful_login(driver)  # Use the helper function to log in

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
  perform_successful_login(driver)  # Use the helper function to log in

  # Navigate to Password change page
  driver.get(SMART_INTERSECTION_URL + "/admin/password_change")

  try:
    # Wait for the password fields to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "id_old_password")))
  except TimeoutException:
    assert False, 'Password fields not found within 10 seconds'

  # Use the helper function to fill in the password fields
  fill_password_fields(driver)

  # Submit the password change
  submit_button = driver.find_element(By.XPATH, "//input[@type='submit' and @value='Change my password']")
  submit_button.click()

  try:
    # Wait for the success message to be present
    WebDriverWait(driver, 10).until(EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Password change successful"))
  except TimeoutException:
    assert False, '"Password change successful" message not found within 10 seconds'

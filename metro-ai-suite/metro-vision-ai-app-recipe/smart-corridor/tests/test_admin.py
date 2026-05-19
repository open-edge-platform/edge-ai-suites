# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import pytest
import logging
import os
import subprocess
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from tests.utils.ui_utils import waiter, driver
from tests.utils.kubernetes_utils import get_node_port, get_scenescape_kubernetes_url
from tests.utils.utils import check_urls_access
from .conftest import (
  SCENESCAPE_URL,
  SCENESCAPE_USERNAME,
  SCENESCAPE_PASSWORD,
)

logger = logging.getLogger(__name__)

def web_options_availability_check(waiter, scenescape_url):
  """Common function to test that the web option is available in the admin interface."""
  waiter.perform_login(
    scenescape_url,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    SCENESCAPE_USERNAME, SCENESCAPE_PASSWORD
  )

  # Define static list of navbar links
  navbar_links = [
    scenescape_url + "/",  # Scenes
    scenescape_url + "/cam/list/",  # Cameras
    scenescape_url + "/singleton_sensor/list/",  # Sensors
    scenescape_url + "/asset/list/",  # Object Library
    "https://docs.openedgeplatform.intel.com/scenescape/main/toc.html",  # Documentation
    scenescape_url + "/admin"  # Admin
  ]

  # Check all URLs using the common function
  check_urls_access(navbar_links)

def login_functionality(waiter, url):
  """Common function to perform login."""
  logger.info(f"Performing login at URL: {url}")
  waiter.perform_login(
    url,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    SCENESCAPE_USERNAME, SCENESCAPE_PASSWORD
  )

  logger.info("Verifying presence of 'nav-scenes' element")
  waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "nav-scenes")),
    error_message='"nav-scenes" element not found on the page'
  )
  logger.info("Login verification completed")

def logout_functionality_check(waiter, url):
  """Common function to perform logout test."""
  waiter.perform_login(
    url,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    SCENESCAPE_USERNAME, SCENESCAPE_PASSWORD
  )

  # Perform logout action
  logout_link = waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "nav-sign-out")),
    error_message='"nav-sign-out" element not found on the page'
  )
  logout_link.click()

  # Wait for the 'username' input to be present
  waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "username")),
    error_message='"username" input field not found within 10 seconds'
  )

def change_password_functionality_check(waiter, url):
  """Common function to test that the admin can change the password successfully."""
  waiter.perform_login(
    url,
    By.ID, "username",
    By.ID, "password",
    By.ID, "login-submit",
    SCENESCAPE_USERNAME, SCENESCAPE_PASSWORD
  )

  # Verify that the element visible after login is present on the page
  waiter.wait_and_assert(
    EC.presence_of_element_located((By.ID, "nav-scenes")),
    error_message='"nav-scenes" element not found on the page'
  )

  # Navigate to Password change page
  waiter.driver.get(url + "/admin/password_change")

  # Wait for the 'Change my password' button to be present
  change_password_button = waiter.wait_and_assert(
    EC.presence_of_element_located((By.XPATH, "//input[@type='submit' and @value='Change my password']")),
    error_message='"Change my password" button not found within 10 seconds'
  )

  old_password_input = waiter.driver.find_element(By.ID, "id_old_password")
  new_password1_input = waiter.driver.find_element(By.ID, "id_new_password1")
  new_password2_input = waiter.driver.find_element(By.ID, "id_new_password2")

  old_password_input.send_keys(SCENESCAPE_PASSWORD)
  new_password1_input.send_keys(SCENESCAPE_PASSWORD)
  new_password2_input.send_keys(SCENESCAPE_PASSWORD)

  # Submit the password change
  change_password_button.click()

  # Wait for the success message to be present
  waiter.wait_and_assert(
    EC.text_to_be_present_in_element((By.TAG_NAME, "body"), "Password change successful"),
    error_message='"Password change successful" message not found within 10 seconds'
  )


@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9389")
def test_login_docker(waiter):
  """Test login functionality for Docker environment."""
  login_functionality(waiter, SCENESCAPE_URL)

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T13559")
def test_login_kubernetes(waiter):
  """Test login functionality for Kubernetes environment."""
  kubernetes_url = get_scenescape_kubernetes_url()
  logger.info(f"Using Kubernetes URL: {kubernetes_url}")
  login_functionality(waiter, kubernetes_url)
  logger.info("Kubernetes login test completed")

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T13911")
def test_logout_kubernetes(waiter):
  """Test that the admin logout functionality works correctly."""
  logout_functionality_check(waiter, get_scenescape_kubernetes_url())

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9390")
def test_logout_docker(waiter):
  """Test that the admin logout functionality works correctly."""
  logout_functionality_check(waiter, SCENESCAPE_URL)

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T13912")
def test_change_password_kubernetes(waiter):
  """Test that the admin can change the password successfully."""
  change_password_functionality_check(waiter, get_scenescape_kubernetes_url())

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9388")
def test_change_password_docker(waiter):
  """Test that the admin can change the password successfully."""
  change_password_functionality_check(waiter, SCENESCAPE_URL)

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T10683")
def test_web_options_availability_kubernetes(waiter):
  """Test that the web option is available in the admin interface."""
  kubernetes_url = get_scenescape_kubernetes_url()
  web_options_availability_check(waiter, kubernetes_url)

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9374")
def test_web_options_availability_docker(waiter):
  """Test that the web option is available in the admin interface."""
  web_options_availability_check(waiter, SCENESCAPE_URL)

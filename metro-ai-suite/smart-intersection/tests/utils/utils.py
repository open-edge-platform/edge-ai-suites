# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import os
import subprocess
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException

def run_command(cmd):
  """Run a shell command and return (stdout, stderr, returncode)."""
  proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = proc.communicate()
  return out.decode(), err.decode(), proc.returncode

def perform_login(driver, url, selector_type1, selector_value1, selector_type2, selector_value2, selector_type3, selector_value3, username, password):
  """
  Performs login action.

  Args:
    driver: WebDriver instance.
    url: URL of the login page.
    selector_type1: Type of selector for username input (e.g., By.CSS_SELECTOR).
    selector_value1: Selector value for username input.
    selector_type2: Type of selector for password input.
    selector_value2: Selector value for password input.
    selector_type3: Type of selector for login button.
    selector_value3: Selector value for login button.
    username: Username string.
    password: Password string.
  """
  driver.get(url)  # Load login page

  try:
    # Wait for the 'Username' input to be present
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((selector_type1, selector_value1)))
  except TimeoutException:
    assert False, 'Input field not found within 10 seconds'

  username_input = driver.find_element(selector_type1, selector_value1)
  password_input = driver.find_element(selector_type2, selector_value2)
  login_button = driver.find_element(selector_type3, selector_value3)

  username_input.send_keys(username)
  password_input.send_keys(password)
  login_button.click()  # Try to log in

def get_password_from_supass_file():
  """Read the password from a supass file."""
  # Path to the supass password file
  file_path = os.path.join('src', 'secrets', 'supass')
  
  # Read the password from the file
  with open(file_path, 'r') as file:
    password = file.read().strip()
    
  return password

def get_username_from_influxdb2_admin_username_file():
  """Read the username from a influxdb2-admin-username file."""
  # Path to the file with influxdb2-admin-username
  file_path = os.path.join('src', 'secrets', 'influxdb2', 'influxdb2-admin-username')

  # Read the username from the file
  with open(file_path, 'r') as file:
    username = file.read().strip()

  return username

def get_password_from_influxdb2_admin_password_file():
  """Read the password from a influxdb2-admin-password file."""
  # Path to the file with influxdb2-admin-password
  file_path = os.path.join('src', 'secrets', 'influxdb2', 'influxdb2-admin-password')

  # Read the password from the file
  with open(file_path, 'r') as file:
    password = file.read().strip()

  return password

def suppress_insecure_request_warning(func):
  """Decorator to suppress InsecureRequestWarning during test execution."""
  def wrapper(*args, **kwargs):
    # Ignore the InsecureRequestWarning
    warnings.filterwarnings("ignore", category=InsecureRequestWarning)
    try:
      return func(*args, **kwargs)
    finally:
      # Restore the default warning behavior
      warnings.filterwarnings("default", category=InsecureRequestWarning)
  return wrapper

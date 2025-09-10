# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import os
import subprocess
import warnings
import logging
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import TimeoutException


logger = logging.getLogger(__name__)

def run_command(cmd):
  """Run a shell command and return (stdout, stderr, returncode)."""
  proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = proc.communicate()
  return out.decode(), err.decode(), proc.returncode


def read_from_file(file_path):
  """Read content from a specified file."""
  try:
    with open(file_path, 'r') as file:
      content = file.read().strip()
    return content
  except FileNotFoundError:
    logger.error(f"Error: The file '{file_path}' was not found.")
  except IOError:
    logger.error(f"Error: Could not read the file '{file_path}'.")
  return None

def get_password_from_supass_file():
  """Read the password from a supass file."""
  file_path = os.path.join('src', 'secrets', 'supass')
  return read_from_file(file_path)

def get_username_from_influxdb2_admin_username_file():
  """Read the username from a influxdb2-admin-username file."""
  file_path = os.path.join('src', 'secrets', 'influxdb2', 'influxdb2-admin-username')
  return read_from_file(file_path)

def get_password_from_influxdb2_admin_password_file():
  """Read the password from a influxdb2-admin-password file."""
  file_path = os.path.join('src', 'secrets', 'influxdb2', 'influxdb2-admin-password')
  return read_from_file(file_path)

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

@suppress_insecure_request_warning
def check_url_access(url, timeout=10):
  """Helper function to check if a component is accessible."""
  logger.info(f"Checking access to service: {url}")

  # Add browser-like headers
  headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1'
  }

  try:
    # Create session for cookie handling
    session = requests.Session()
    session.headers.update(headers)

    response = session.get(url, verify=False, timeout=timeout, allow_redirects=True)

    # Accept both 200 and 3xx redirects as success
    if response.status_code in [200, 301, 302, 303, 307, 308]:
      logger.info(f"Successfully accessed service: {url} (status: {response.status_code})")
      return True
    else:
      logger.error(f"Service access failed: {url} (status: {response.status_code})")
      return False

  except requests.exceptions.RequestException as e:
    logger.error(f"Service access failed: {url} (error: {e})")
    return False

def check_urls_access(urls_to_check):
  """
  Common function to check access to multiple URLs and collect failures.

  Args:
    urls_to_check: List of URLs to check

  Raises:
    AssertionError: If any URLs fail with list of failed URLs
  """
  failed_urls = []
  for url in urls_to_check:
    if not check_url_access(url):
      failed_urls.append(url)
      logger.error(f"Failed to access URL: {url}")

  if failed_urls:
    assert False, f"Failed to access the following URLs: {failed_urls}"

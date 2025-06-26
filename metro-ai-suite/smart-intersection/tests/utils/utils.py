# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import os
import subprocess
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning

def run_command(cmd):
  """Run a shell command and return (stdout, stderr, returncode)."""
  proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  out, err = proc.communicate()
  return out.decode(), err.decode(), proc.returncode

def get_password_from_supass_file():
  """Read the password from a supass file."""
  # Path to the supass password file
  file_path = os.path.join('src', 'secrets', 'supass')
  
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

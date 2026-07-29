# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import os
import re
import pytest
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse
from tests.utils.utils import check_url_access
from .conftest import PROJECT_GITHUB_URL

logger = logging.getLogger(__name__)

def find_md_files(directory):
  """Find all markdown files in the given directory."""
  md_files = []
  for root, _, files in os.walk(directory):
    for file in files:
      if file.endswith('.md'):
        md_files.append(os.path.join(root, file))
  return md_files

def extract_links_from_file(file_path):
  """Extract all links from a markdown file."""
  with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()
    # Regular expression to find markdown links, including relative paths
    links = re.findall(r'\[.*?\]\((.*?)\)', content)
  return links

def should_skip_url(url):
  """Check if the URL should be skipped."""
  # Skip all localhost URLs (both http and https)
  parsed_url = urlparse(url)
  if parsed_url.hostname in ['localhost', '127.0.0.1']:
    return True
  return False

def prepend_project_github_url(file_path, url, repo_root):
  """Prepend PROJECT_GITHUB_URL to a relative URL."""
  # Remove leading '.' if present
  url = url.lstrip('.')
  # Get the relative path from the repo root to the file's directory
  try:
    relative_path = Path(file_path).relative_to(repo_root)
  except ValueError:
    logger.error(f"File path {file_path} is not relative to the repository root {repo_root}.")
    return None  # Skip processing this URL
  # Construct the full URL
  return f"{PROJECT_GITHUB_URL}/{relative_path.parent}/{url}"

def links_in_md_files_functionality():
  """Common function to test all links in markdown files for HTTP 200 response."""
  # Determine the directory one level above the current tests folder
  current_file = Path(__file__).resolve()
  repo_root = current_file.parent.parent

  # Find all markdown files in the determined directory
  md_files = find_md_files(repo_root)

  # Prepare a list of URLs to check
  urls_to_check = []
  for md_file in md_files:
    links = extract_links_from_file(md_file)
    urls_to_check.extend([(md_file, link) for link in links])

  # Boolean to track if any URL checks fail
  any_failed_urls = False

  # Check each URL using the check_url_access method
  for file_path, url in urls_to_check:
    if should_skip_url(url):
      continue

    # Check if the URL is relative
    if not url.startswith(('http://', 'https://')):
      # Prepend PROJECT_GITHUB_URL to relative URLs
      url = prepend_project_github_url(file_path, url, repo_root)
      if not url:
        any_failed_urls = True
        continue

    try:
      check_url_access(url)  # Use the predefined method to check URL accessibility
    except AssertionError as e:
      logger.error(f"URL {url} in file {file_path} failed with exception: {e}")
      any_failed_urls = True

  # Assert at the end if there are any failed URLs
  if any_failed_urls:
    error_message = "Some links were inaccessible"
    assert False, error_message

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T10674")
def test_links_in_md_files_kubernetes():
  """Test all links in markdown files for HTTP 200 response."""
  links_in_md_files_functionality()

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9364")
def test_links_in_md_files_docker():
  """Test all links in markdown files for HTTP 200 response."""
  links_in_md_files_functionality()

# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import os
import json
import pytest

SOURCE = "src"
VIDEO_DIR = os.path.join(SOURCE, "dlstreamer-pipeline-server/videos")
VIDEOS = ["1122east.ts", "1122west.ts", "1122north.ts", "1122south.ts"]
SECRETS_DIR = os.path.join(SOURCE, "secrets")

def setup_functionality_check():
  """Common function to verify that secrets and videos have been set up."""
  
  # Check if browser.auth file exists
  browser_auth = os.path.join(SECRETS_DIR, "browser.auth")
  assert os.path.isfile(browser_auth), "Browser auth file is not generated."
  
  # Validate browser.auth content
  with open(browser_auth, 'r') as f:
    auth_data = json.load(f)
    assert auth_data.get("user") == "webuser", "Browser auth user incorrect."
    assert len(auth_data.get("password", "")) > 0, "Browser auth password missing."

  # Check that other secret files exist
  secret_files = [
    "controller.auth",
    "supass", 
    "certs/scenescape-ca.pem",
    "influxdb2/influxdb2-admin-password"
  ]
  
  for secret_file in secret_files:
    secret_path = os.path.join(SECRETS_DIR, secret_file)
    assert os.path.isfile(secret_path), f"Essential secret file {secret_file} is missing."

  # Check if video directory exists and has videos
  assert os.path.isdir(VIDEO_DIR), f"Video directory {VIDEO_DIR} does not exist."
  
  # Check if each video file is downloaded
  for video in VIDEOS:
    video_path = os.path.join(VIDEO_DIR, video)
    assert os.path.isfile(video_path), f"Video file {video} is not downloaded."
    # Check file is not empty
    assert os.path.getsize(video_path) > 1024, f"Video file {video} appears to be empty or corrupted."

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T10675")
def test_setup_kubernetes():
  """Verify that secrets and videos have been set up."""
  setup_functionality_check()

@pytest.mark.docker
@pytest.mark.zephyr_id("NEX-T9365")
def test_setup_docker():
  """Verify that secrets and videos have been set up."""
  setup_functionality_check()

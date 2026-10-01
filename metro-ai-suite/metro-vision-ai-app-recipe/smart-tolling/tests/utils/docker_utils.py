# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import json
from tests.utils.utils import run_command

def get_all_services():
  out, err, code = run_command(f"docker compose config --services")
  assert code == 0, f"Failed to list all services: {err}"
  return set(out.strip().splitlines())

def get_running_services():
  out, err, code = run_command(f"docker compose ps --services --filter 'status=running'")
  assert code == 0, f"Failed to list running services: {err}"
  return set(out.strip().splitlines())

// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// GENERATED FILE - do not edit.
// Written by Scripts/gen_catalog.py from utils/requirements.py. Edit there and re-run it.

// Only the thresholds the backend checks too. Disk space, driver versions and
// download URLs are the Setup screen's own; see setup-runner.cjs.

const MIN_MEMORY_GB = 32;
const REQUIRED_OS = 'Windows 11';
const MIN_WINDOWS_BUILD = 22000;
const PYTHON_TARGET = [3, 12];
const REQUIRED_DLSTREAMER = '2026.1.0';

module.exports = {
  MIN_MEMORY_GB,
  REQUIRED_OS,
  MIN_WINDOWS_BUILD,
  PYTHON_TARGET,
  REQUIRED_DLSTREAMER,
};

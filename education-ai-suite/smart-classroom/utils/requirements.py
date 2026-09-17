# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0

"""The platform Smart Classroom expects, declared once.

Checked by utils/system_checker.py on startup and by the app's first-run Setup
screen, which runs in the Electron main process and reads a generated copy
(`Scripts/gen_catalog.py`). Edit here, then re-run the generator.

Only thresholds both sides check belong here. Disk space, driver versions and
download URLs stay in setup-runner.cjs.
"""

#: Minimum system RAM, in GB.
MIN_MEMORY_GB = 32

REQUIRED_OS = "Windows 11"

#: What a check can actually test; REQUIRED_OS is what it reports.
MIN_WINDOWS_BUILD = 22000

#: Exact, not a floor: the wheels pinned in requirements.txt are built for it.
REQUIRED_PYTHON_MAJOR = 3
REQUIRED_PYTHON_MINOR = 12

#: For a from-source checkout. The packaged app bundles its own Node.
REQUIRED_NODE_MAJOR = 18

MIN_DLSTREAMER_VERSION = (2026, 1, 0)


def dlstreamer_version_str() -> str:
    return ".".join(str(v) for v in MIN_DLSTREAMER_VERSION)

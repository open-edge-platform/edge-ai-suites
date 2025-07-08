<!--
# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.
-->

# Testing with Pytest

- [Testing with Pytest](#testing-with-pytest)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Running tests](#running-tests)

## Prerequisites

- Python 3.12 or higher
- Newest Chrome browser installed
- Prepare your environment according to https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-intersection/docs/user-guide/get-started.md and https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/smart-intersection/docs/user-guide/how-to-deploy-docker.md guides.

## Installation

Create virtual environment on your system:

```bash
python3 -m venv venv
```

Activate virtual environment:

```bash
source venv/bin/activate
```

Install the required packages using pip.

```bash
python3 -m pip install -r requirements.txt
```

Now you are ready to run tests on your system. 

## Running tests

Use make file to run all tests or pytests to run the one you choose.

```bash
make test
```
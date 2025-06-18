# Copyright (C) 2025 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials,
# and your use of them is governed by the express license under which they
# were provided to you ("License"). Unless the License provides otherwise,
# you may not use, modify, copy, publish, distribute, disclose or transmit
# this software or the related documents without Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express
# or implied warranties, other than those that are expressly stated in the License.

import pytest
import time
from tests.utils.utils import run_command

DOCKER_COMPOSE_FILE = "compose.yml" 

@pytest.fixture(scope="session", autouse=True)
def build_and_deploy():
    # Build docker images
    out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} build")
    assert code == 0, f"Build failed: {err}"

    # Deploy (up) docker containers
    out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} up -d")
    assert code == 0, f"Deploy failed: {err}"

    # Wait for services to be healthy (adjust timeout as needed)
    time.sleep(120)

    yield

    # Teardown: stop and remove containers
    run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} down")
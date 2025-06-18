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

import subprocess
import time
import pytest
import json

from .conftest import DOCKER_COMPOSE_FILE
from tests.utils.docker_utils import get_all_services, get_running_services, check_service_health

def test_docker_build_and_deployment():
    """Test that all docker-compose services are running after build and deploy."""
    running = get_running_services()
    expected = get_all_services()
    assert expected == running, f"Not all services are running. Expected: {expected}, Running: {running}"

@pytest.mark.parametrize("service", list(get_all_services()))
def test_docker_services_healthy(service):
    """Test that each service is healthy (if healthcheck is defined)."""
    result, message = check_service_health(service)
    if result is None:
        pytest.skip(message)
    assert result, message
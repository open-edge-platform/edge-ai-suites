# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import logging
import pytest
from .utils.kubernetes_utils import (
  check_helm_deployment_status,
  check_namespace_exists,
  check_all_pods_running,
  get_services_in_namespace
)

logger = logging.getLogger(__name__)

@pytest.mark.kubernetes
@pytest.mark.zephyr_id("NEX-T10676")
def test_kubernetes_build_and_deployment():
  """Test that all Kubernetes services are running after deployment."""
  namespace = "smart-intersection"
  release_name = "smart-intersection"
  
  logger.info("Testing Kubernetes deployment status...")
  
  # 1. Check if namespace exists
  assert check_namespace_exists(namespace), f"Namespace '{namespace}' does not exist"
  
  # 2. Check if Helm deployment is successful
  assert check_helm_deployment_status(release_name, namespace), f"Helm release '{release_name}' is not deployed successfully"
  
  # 3. Check if all pods are running
  assert check_all_pods_running(namespace), f"Not all pods in namespace '{namespace}' are running"
  
  # 4. Get and log services information
  services = get_services_in_namespace(namespace)
  assert services is not None, f"Failed to get services in namespace '{namespace}'"
  assert len(services) > 0, f"No services found in namespace '{namespace}'"
  
  logger.info(f"Kubernetes deployment verification completed successfully:")
  logger.info(f"  - Namespace: {namespace} ✓")
  logger.info(f"  - Helm release: {release_name} ✓")
  logger.info(f"  - All pods running ✓")
  logger.info(f"  - Services: {len(services)} found ✓")

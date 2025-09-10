# SPDX-FileCopyrightText: (C) 2025 Intel Corporation
# SPDX-License-Identifier: LicenseRef-Intel-Edge-Software
# This file is licensed under the Limited Edge Software Distribution License Agreement.

import os
import time
import subprocess
import logging
from .utils import run_command

logger = logging.getLogger(__name__)

SCENESCAPE_URL = os.getenv("SCENESCAPE_URL", "https://localhost")
SCENESCAPE_KUBERNETES_URL = None

def get_node_port(service_name, namespace):
  """Get the NodePort for a given service."""
  logger.info(f"Attempting to get NodePort for service '{service_name}' in namespace '{namespace}'")
  result = subprocess.run(
    ["kubectl", "get", "service", service_name, "-n", namespace, "-o", "jsonpath={.spec.ports[0].nodePort}"],
    capture_output=True, text=True
  )
  if result.returncode != 0:
    logger.error(f"Failed to get NodePort: {result.stderr}")
    raise RuntimeError("Failed to get NodePort")
  node_port = result.stdout.strip()
  logger.info(f"NodePort for service '{service_name}' is '{node_port}'")
  return node_port

def wait_for_pods_ready(namespace, timeout=300, interval=10):
  """Wait for all pods in the specified namespace to be in 'Running' state."""
  start_time = time.time()
  while time.time() - start_time < timeout:
    out, err, code = run_command(f"kubectl get pods -n {namespace} --no-headers")
    if code != 0:
      logger.error(f"Failed to get pods: {err}")
      raise RuntimeError("Failed to get pods status")

    pods = out.strip().split("\n")
    all_running = all("Running" in pod for pod in pods)
    if all_running:
      logger.info("All pods are in 'Running' state.")
      return True

    logger.info("Waiting for pods to be ready...")
    time.sleep(interval)

  raise TimeoutError("Pods did not become ready in time.")

def get_scenescape_kubernetes_url():
  """Get the Kubernetes URL for Scenescape service."""
  global SCENESCAPE_KUBERNETES_URL
  if SCENESCAPE_KUBERNETES_URL is None:
    web_node_port = get_node_port("smart-intersection-web", "smart-intersection")
    SCENESCAPE_KUBERNETES_URL = f"{SCENESCAPE_URL}:{web_node_port}"
  return SCENESCAPE_KUBERNETES_URL

def get_pod_name(service_name, namespace="smart-intersection"):
  """Get the name of the first pod for a given service."""
  cmd = f"kubectl get pods -n {namespace} -l app={service_name} -o jsonpath='{{.items[0].metadata.name}}'"
  return subprocess.check_output(cmd, shell=True).decode().strip()

def start_port_forwarding(service_name, local_port, remote_port, namespace="smart-intersection"):
  """Start port forwarding for a service and return the process."""
  pod_name = get_pod_name(service_name, namespace)
  cmd = f"kubectl -n {namespace} port-forward {pod_name} {local_port}:{remote_port}"
  logger.info(f"Starting port forwarding for {service_name}: localhost:{local_port}")
  subprocess.Popen(cmd, shell=True)

def check_helm_deployment_status(release_name, namespace):
  """Check if Helm deployment is successful."""
  logger.info(f"Checking Helm deployment status for release '{release_name}' in namespace '{namespace}'")
  
  out, err, code = run_command(f"helm status {release_name} -n {namespace}")
  if code != 0:
    logger.error(f"Failed to get Helm release status: {err}")
    return False
  
  if "STATUS: deployed" in out:
    logger.info(f"Helm release '{release_name}' is successfully deployed")
    return True
  else:
    logger.error(f"Helm release '{release_name}' is not in deployed status")
    return False

def check_namespace_exists(namespace):
  """Check if Kubernetes namespace exists."""
  logger.info(f"Checking if namespace '{namespace}' exists")
  
  out, err, code = run_command(f"kubectl get namespace {namespace}")
  if code == 0:
    logger.info(f"Namespace '{namespace}' exists")
    return True
  else:
    logger.error(f"Namespace '{namespace}' does not exist: {err}")
    return False

def get_pods_in_namespace(namespace):
  """Get all pods in a namespace with their status."""
  logger.info(f"Getting pods in namespace '{namespace}'")
  
  out, err, code = run_command(f"kubectl get pods -n {namespace} --no-headers")
  if code != 0:
    logger.error(f"Failed to get pods: {err}")
    return None
  
  pods = []
  for line in out.strip().split('\n'):
    if line.strip():
      parts = line.split()
      pod_name = parts[0]
      ready = parts[1]
      status = parts[2]
      restarts = parts[3]
      age = parts[4]
      
      pods.append({
        'name': pod_name,
        'ready': ready,
        'status': status,
        'restarts': restarts,
        'age': age
      })
  
  logger.info(f"Found {len(pods)} pods in namespace '{namespace}'")
  return pods

def check_all_pods_running(namespace):
  """Check if all pods in namespace are in Running state."""
  pods = get_pods_in_namespace(namespace)
  if pods is None:
    return False
  
  running_pods = []
  failed_pods = []
  
  for pod in pods:
    if pod['status'] == 'Running':
      running_pods.append(pod['name'])
    else:
      failed_pods.append({'name': pod['name'], 'status': pod['status']})
  
  logger.info(f"Running pods ({len(running_pods)}): {', '.join(running_pods)}")
  
  if failed_pods:
    logger.error(f"Pods not running ({len(failed_pods)}):")
    for pod in failed_pods:
      logger.error(f"  - {pod['name']}: {pod['status']}")
    return False
  
  logger.info(f"All {len(running_pods)} pods are in Running state")
  return True

def get_services_in_namespace(namespace):
  """Get all services in a namespace."""
  logger.info(f"Getting services in namespace '{namespace}'")
  
  out, err, code = run_command(f"kubectl get services -n {namespace} --no-headers")
  if code != 0:
    logger.error(f"Failed to get services: {err}")
    return None
  
  services = []
  for line in out.strip().split('\n'):
    if line.strip():
      parts = line.split()
      service_name = parts[0]
      service_type = parts[1]
      cluster_ip = parts[2]
      external_ip = parts[3]
      ports = parts[4]
      age = parts[5]
      
      services.append({
        'name': service_name,
        'type': service_type,
        'cluster_ip': cluster_ip,
        'external_ip': external_ip,
        'ports': ports,
        'age': age
      })
  
  logger.info(f"Found {len(services)} services in namespace '{namespace}'")
  return services

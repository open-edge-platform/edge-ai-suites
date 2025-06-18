import json
from tests.utils.utils import run_command
from ..conftest import DOCKER_COMPOSE_FILE

def get_all_services():
    out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} config --services")
    assert code == 0, f"Failed to list all services: {err}"
    return set(out.strip().splitlines())

def get_running_services():
    out, err, code = run_command(f"docker compose -f {DOCKER_COMPOSE_FILE} ps --services --filter 'status=running'")
    assert code == 0, f"Failed to list running services: {err}"
    return set(out.strip().splitlines())

def check_service_health(service):
    """Check the health status of a Docker service."""
    out, err, code = run_command(f"docker inspect --format='{{{{json .State.Health}}}}' $(docker compose -f {DOCKER_COMPOSE_FILE} ps -q {service})")
    if code == 0 and "null" not in out:
        health = json.loads(out)
        if health["Status"] != "healthy":
            return False, f"Service {service} is not healthy: {health}"
        return True, None
    else:
        return None, f"No healthcheck defined for {service}"
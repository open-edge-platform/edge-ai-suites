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
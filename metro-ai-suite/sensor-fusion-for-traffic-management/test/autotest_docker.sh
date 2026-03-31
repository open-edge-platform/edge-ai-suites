#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(cd -- "$SCRIPT_DIR/.." && pwd)}"

IMAGE="${IMAGE:-intel/tfcc:latest}"
# Default matches docker/run_docker.sh and the image's built project directory.
CONTAINER_WORKDIR="${CONTAINER_WORKDIR:-/home/tfcc/metro}"
AUTOTEST_CMD_IN_CONTAINER="${AUTOTEST_CMD_IN_CONTAINER:-bash test/autotest.sh}"
CONTAINER_NAME="${CONTAINER_NAME:-tfcc-autotest-$(date +%Y%m%d_%H%M%S)}"

# Persist benchmark artifacts on the host.
HOST_LOG_DIR="${HOST_LOG_DIR:-$SCRIPT_DIR/autotest_logs}"

# Container-side log directory; will be copied back to HOST_LOG_DIR.
CONTAINER_LOG_DIR="${CONTAINER_LOG_DIR:-/tmp/autotest_logs}"

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

check_docker_env() {
  require_cmd docker
  require_cmd grep

  if ! docker info >/dev/null 2>&1; then
    die "Docker daemon is not reachable. Start Docker (e.g., 'sudo systemctl start docker') and ensure your user can access it (e.g., add user to 'docker' group and re-login)."
  fi
}

check_intel_gpu_driver() {
  if [[ ! -d /dev/dri ]]; then
    die "Intel GPU device nodes not found: /dev/dri is missing. Verify Intel GPU driver installation on the host."
  fi
  if ! ls /dev/dri/renderD* >/dev/null 2>&1; then
    die "No render nodes found under /dev/dri (expected /dev/dri/renderD*). Verify Intel GPU driver installation on the host."
  fi
}

docker_pull_image() {
  echo "[INFO] Pulling Docker image: $IMAGE"
  docker pull "$IMAGE"
}

CONTAINER_ID=""

cleanup() {
  if [[ -n "${CONTAINER_ID:-}" ]]; then
    docker rm -f "$CONTAINER_ID" >/dev/null 2>&1 || true
    CONTAINER_ID=""
  fi
}

trap cleanup EXIT INT TERM

start_container_via_run_docker() {
  local docker_dir="$PROJECT_DIR/docker"
  [[ -d "$docker_dir" ]] || die "Docker directory not found: $docker_dir"
  [[ -f "$docker_dir/run_docker.sh" ]] || die "run_docker.sh not found: $docker_dir/run_docker.sh"

  echo "[INFO] Starting container via docker/run_docker.sh"
  local out
  out=$(cd "$docker_dir" && bash ./run_docker.sh "$IMAGE" false)
  echo "$out"

  CONTAINER_ID=$(echo "$out" | tr -d '\r' | grep -Eo '[0-9a-f]{12,64}' | tail -n 1)
  [[ -n "$CONTAINER_ID" ]] || die "Failed to parse container id from run_docker.sh output"
  echo "[INFO] Container id: $CONTAINER_ID"
}

resolve_container_workdir() {
  local detected
  detected=$(docker exec -u root "$CONTAINER_ID" bash -lc 'if [[ -n "${PROJ_DIR:-}" && -d "$PROJ_DIR" ]]; then echo "$PROJ_DIR"; elif [[ -d /home/tfcc/metro ]]; then echo /home/tfcc/metro; else echo ""; fi')
  if [[ -z "$detected" ]]; then
    die "Failed to locate project directory inside container (expected PROJ_DIR or /home/tfcc/metro)."
  fi
  CONTAINER_WORKDIR="$detected"
  echo "[INFO] Container project dir: $CONTAINER_WORKDIR"
}

copy_scripts_into_container() {
  docker exec -u root "$CONTAINER_ID" bash -lc "mkdir -p '$CONTAINER_WORKDIR/test'"
  docker cp "$SCRIPT_DIR/autotest.sh" "$CONTAINER_ID:$CONTAINER_WORKDIR/test/autotest.sh"
  docker cp "$PROJECT_DIR/run_service_bare_log.sh" "$CONTAINER_ID:$CONTAINER_WORKDIR/run_service_bare_log.sh"
  docker exec -u root "$CONTAINER_ID" bash -lc "chmod +x '$CONTAINER_WORKDIR/test/autotest.sh' '$CONTAINER_WORKDIR/run_service_bare_log.sh' || true"
}

container_exec() {
  local cmd="$1"
  docker exec -u root -w "$CONTAINER_WORKDIR" \
    -e "LOG_DIR=$CONTAINER_LOG_DIR" \
    -e "no_proxy=localhost,127.0.0.1" \
    "$CONTAINER_ID" \
    bash -lc "$cmd"
}

copy_logs_from_container() {
  mkdir -p "$HOST_LOG_DIR" || die "Failed to create HOST_LOG_DIR: $HOST_LOG_DIR"
  local dest="$HOST_LOG_DIR/$CONTAINER_NAME"
  mkdir -p "$dest" || die "Failed to create log destination: $dest"
  docker cp "$CONTAINER_ID:$CONTAINER_LOG_DIR/." "$dest" >/dev/null 2>&1 || true
  echo "[INFO] Logs copied to: $dest"
}

run_autotest_in_container() {
  [[ -f "$SCRIPT_DIR/autotest.sh" ]] || die "Expected test/autotest.sh at: $SCRIPT_DIR/autotest.sh"
  [[ -f "$PROJECT_DIR/run_service_bare_log.sh" ]] || die "Expected run_service_bare_log.sh at: $PROJECT_DIR/run_service_bare_log.sh"

  echo "[INFO] Running docker-based autotest"
  echo "[INFO] Test command: $AUTOTEST_CMD_IN_CONTAINER"
  echo "[INFO] Container name: $CONTAINER_NAME"
  echo "[INFO] Host log dir: $HOST_LOG_DIR"

  start_container_via_run_docker
  resolve_container_workdir

  echo "[INFO] Preparing container log directory: $CONTAINER_LOG_DIR"
  container_exec "mkdir -p '$CONTAINER_LOG_DIR'"

  echo "[INFO] Copying latest autotest scripts into container"
  copy_scripts_into_container

  echo "[INFO] Verifying build artifacts"
  container_exec "ls -la build/bin >/dev/null; compgen -G 'build/bin/testGRPC*Pipeline' >/dev/null"

  echo "[INFO] Running autotest"
  set +e
  container_exec "$AUTOTEST_CMD_IN_CONTAINER"
  local test_rc=$?
  set -e

  copy_logs_from_container
  exit "$test_rc"
}

main() {
  check_docker_env
  check_intel_gpu_driver
  docker_pull_image
  run_autotest_in_container
}

main "$@"

#!/usr/bin/env bash

set -Eeuo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

log(){ echo "[autotest-docker] $*"; }
warn(){ echo "[autotest-docker][warn] $*" >&2; }
die(){ echo "[autotest-docker][error] $*" >&2; exit 1; }
require_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DOCKER_DIR="${SCRIPT_DIR}/docker"
RUN_DOCKER_SCRIPT="${DOCKER_DIR}/run_docker.sh"
BUILD_DOCKER_SCRIPT="${DOCKER_DIR}/build_docker.sh"

IMAGE="tfcc:bevfusion"
CUSTOM_OPENVINO_INSTALL_DIR="${CUSTOM_OPENVINO_INSTALL_DIR:-}"
DOCKERFILE="Dockerfile.dockerfile"
BASE="ubuntu"
BASE_VERSION="24.04"
HOST_LOGS_DIR="${SCRIPT_DIR}/docker_autotest_logs/$(date +%Y%m%d_%H%M%S)"
CONTAINER_LOGS_DIR="/tmp/bevfusion_autotest_logs"
DEFAULT_CONTAINER_DATASET_PATH="/home/tfcc/bevfusion/data/v2xfusion/dataset"
IMPORTED_CONTAINER_DATASET_PATH="/tmp/bevfusion_autotest_dataset"
HOST_DATASET_PATH=""
CONTAINER_DATASET_PATH="${DEFAULT_CONTAINER_DATASET_PATH}"
CONTAINER_DATASET_PATH_EXPLICIT=0
CONTAINER_NAME="bevfusion-autotest-$(date +%Y%m%d_%H%M%S)"
BUILD_IMAGE=0
KEEP_CONTAINER=0

CONTAINER_ID=""
CONTAINER_PROJECT_DIR=""
HOST_SUMMARY_FILE=""

declare -a INNER_AUTOTEST_ARGS=()

usage(){
  cat <<'EOF'
Usage: bash autotest_docker.sh [options] [-- autotest.sh args]

Options:
  --dataset-path PATH              Host dataset root to copy into the container
                                   before running tests.
  --image NAME                     Docker image to run.
                                   Default: tfcc:bevfusion
  --build-image                    Build the Docker image before running tests.
  --custom-openvino-install-dir P  Host custom OpenVINO install root used when
                                   building the image. Must contain setupvars.sh.
  --dockerfile NAME                Dockerfile name under docker/.
                                   Default: Dockerfile.dockerfile
  --base NAME                      Base image name forwarded to build_docker.sh.
                                   Default: ubuntu
  --base-version VER               Base image version forwarded to build_docker.sh.
                                   Default: 24.04
  --host-logs-dir PATH             Host directory for copied logs and captured
                                   docker stdout.
                                   Default: ./docker_autotest_logs/<timestamp>
  --container-logs-dir PATH        Log directory inside the container.
                                   Default: /tmp/bevfusion_autotest_logs
  --container-dataset-path PATH    Dataset path inside the container.
                                   Default: /home/tfcc/bevfusion/data/v2xfusion/dataset
                                   When --dataset-path is used and this option is
                                   omitted, the copied dataset is placed under
                                   /tmp/bevfusion_autotest_dataset.
  --container-name NAME            Docker container name.
                                   Default: bevfusion-autotest-<timestamp>
  --keep-container                 Do not remove the container after the run.
  -h, --help                       Show this message.

Behavior:
  - Uses docker/run_docker.sh so GPU, render, and display settings stay
    aligned with the documented container workflow.
  - If --build-image is set, or the requested image does not exist locally, the
    script builds it first through docker/build_docker.sh.
  - Runs autotest.sh inside the container against the container-visible
    dataset path and copies the generated logs back to the host.
  - When --dataset-path is provided, the script copies that host dataset into
    the container before running tests.
  - Additional arguments after -- are forwarded to autotest.sh.
EOF
}

canonicalize_existing(){
  realpath "$1"
}

canonicalize_maybe_missing(){
  realpath -m "$1"
}

require_dataset_layout(){
  local root="$1"
  local subdir

  [[ -d "${root}" ]] || die "Dataset path is not a directory: ${root}"
  for subdir in image_2 velodyne calib label_2; do
    [[ -d "${root}/${subdir}" ]] || die "Missing dataset subdirectory: ${root}/${subdir}"
  done
}

cleanup(){
  if [[ -n "${CONTAINER_ID}" && "${KEEP_CONTAINER}" != "1" ]]; then
    docker rm -f "${CONTAINER_ID}" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT

docker_exec(){
  local command="$1"
  docker exec -u tfcc -w "${CONTAINER_PROJECT_DIR}" "${CONTAINER_ID}" bash -lc "${command}"
}

docker_image_exists(){
  docker image inspect "${IMAGE}" >/dev/null 2>&1
}

check_docker_env(){
  require_cmd docker
  require_cmd realpath
  require_cmd grep
  require_cmd awk

  [[ -f "${RUN_DOCKER_SCRIPT}" ]] || die "run_docker.sh not found: ${RUN_DOCKER_SCRIPT}"
  [[ -f "${BUILD_DOCKER_SCRIPT}" ]] || die "build_docker.sh not found: ${BUILD_DOCKER_SCRIPT}"

  docker info >/dev/null 2>&1 || die "Docker daemon is not reachable"
  [[ -d /dev/dri ]] || die "Intel GPU device nodes not found: /dev/dri is missing"
}

build_image_if_needed(){
  if [[ "${BUILD_IMAGE}" != "1" ]] && docker_image_exists; then
    return 0
  fi

  [[ -n "${CUSTOM_OPENVINO_INSTALL_DIR}" ]] || die "A custom OpenVINO install directory is required to build the Docker image"
  CUSTOM_OPENVINO_INSTALL_DIR=$(canonicalize_existing "${CUSTOM_OPENVINO_INSTALL_DIR}")
  [[ -f "${CUSTOM_OPENVINO_INSTALL_DIR}/setupvars.sh" ]] || die "Custom OpenVINO install must contain setupvars.sh: ${CUSTOM_OPENVINO_INSTALL_DIR}"

  log "Building Docker image ${IMAGE}"
  (
    cd "${DOCKER_DIR}"
    bash "${BUILD_DOCKER_SCRIPT}" "${CUSTOM_OPENVINO_INSTALL_DIR}" "${IMAGE}" "${DOCKERFILE}" "${BASE}" "${BASE_VERSION}"
  )
}

start_container(){
  local output

  log "Starting Docker container from image ${IMAGE}"
  output=$(cd "${DOCKER_DIR}" && bash "${RUN_DOCKER_SCRIPT}" "${IMAGE}")
  echo "${output}"

  CONTAINER_ID=$(printf '%s\n' "${output}" | tr -d '\r' | grep -Eo '[0-9a-f]{12,64}' | tail -n 1 || true)
  [[ -n "${CONTAINER_ID}" ]] || die "Failed to determine container id from run_docker.sh output"

  docker rename "${CONTAINER_ID}" "${CONTAINER_NAME}" >/dev/null 2>&1 || die "Failed to rename container to ${CONTAINER_NAME}"
  CONTAINER_ID="${CONTAINER_NAME}"
}

resolve_container_project_dir(){
  CONTAINER_PROJECT_DIR=$(docker exec -u root "${CONTAINER_ID}" bash -lc 'if [[ -n "${PROJ_DIR:-}" && -d "${PROJ_DIR}" ]]; then printf "%s\n" "${PROJ_DIR}"; elif [[ -d /home/tfcc/bevfusion ]]; then printf "%s\n" /home/tfcc/bevfusion; else exit 1; fi') || \
    die "Failed to locate the project directory inside the container"
}

prepare_container(){
  log "Preparing container paths"
  docker exec -u root "${CONTAINER_ID}" bash -lc "mkdir -p '${CONTAINER_LOGS_DIR}' && chown tfcc:tfcc '${CONTAINER_LOGS_DIR}' && chmod 0775 '${CONTAINER_LOGS_DIR}'"
  docker cp "${SCRIPT_DIR}/autotest.sh" "${CONTAINER_ID}:${CONTAINER_PROJECT_DIR}/autotest.sh"
  docker exec -u root "${CONTAINER_ID}" bash -lc "chmod +x '${CONTAINER_PROJECT_DIR}/autotest.sh'"
}

copy_dataset_into_container(){
  [[ -n "${HOST_DATASET_PATH}" ]] || return 0

  log "Copying dataset into container: ${HOST_DATASET_PATH} -> ${CONTAINER_DATASET_PATH}"
  docker exec -u root "${CONTAINER_ID}" bash -lc "rm -rf '${CONTAINER_DATASET_PATH}' && mkdir -p '${CONTAINER_DATASET_PATH}'"
  docker cp "${HOST_DATASET_PATH}/." "${CONTAINER_ID}:${CONTAINER_DATASET_PATH}/"
}

copy_logs_from_container(){
  mkdir -p "${HOST_LOGS_DIR}"
  if docker cp "${CONTAINER_ID}:${CONTAINER_LOGS_DIR}/." "${HOST_LOGS_DIR}" >/dev/null 2>&1; then
    HOST_SUMMARY_FILE="${HOST_LOGS_DIR}/summary.txt"
    log "Copied container logs to ${HOST_LOGS_DIR}"
  else
    warn "Failed to copy ${CONTAINER_LOGS_DIR} from the container"
  fi
}

summary_value(){
  local key="$1"
  local summary_file="$2"

  awk -F': ' -v key="${key}" '$1 == key { print $2; exit }' "${summary_file}"
}

print_result_line(){
  local status="$1"
  local pass="$2"
  local fail="$3"
  local skipped="$4"

  echo "AUTOTEST_DOCKER_RESULT status=${status} pass=${pass} fail=${fail} skipped=${skipped} logs=${HOST_LOGS_DIR} summary=${HOST_SUMMARY_FILE:-missing} image=${IMAGE} container=${CONTAINER_ID}"
}

run_autotest_in_container(){
  local stdout_log="$1"
  local quoted_dataset=""
  local quoted_logs=""
  local quoted_inner_args=""
  local inner_command=""
  local inner_rc=0
  local status="FAIL"
  local pass="0"
  local fail="1"
  local skipped="0"

  printf -v quoted_dataset '%q' "${CONTAINER_DATASET_PATH}"
  printf -v quoted_logs '%q' "${CONTAINER_LOGS_DIR}"
  if [[ ${#INNER_AUTOTEST_ARGS[@]} -gt 0 ]]; then
    printf -v quoted_inner_args '%q ' "${INNER_AUTOTEST_ARGS[@]}"
    quoted_inner_args=${quoted_inner_args% }
  fi

  inner_command="source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1 || true; source /opt/intel/openvino/setupvars.sh >/dev/null 2>&1 || true; bash autotest.sh --dataset-path ${quoted_dataset} --logs-dir ${quoted_logs} --skip-env-setup"
  if [[ -n "${quoted_inner_args}" ]]; then
    inner_command+=" ${quoted_inner_args}"
  fi

  log "Running autotest.sh inside the container"
  set +e
  docker_exec "${inner_command}" 2>&1 | tee "${stdout_log}"
  inner_rc=${PIPESTATUS[0]}
  set -e

  copy_logs_from_container

  if [[ -f "${HOST_SUMMARY_FILE}" ]]; then
    pass=$(summary_value "Passed" "${HOST_SUMMARY_FILE}")
    fail=$(summary_value "Failed" "${HOST_SUMMARY_FILE}")
    skipped=$(summary_value "Skipped" "${HOST_SUMMARY_FILE}")
    if [[ -n "${fail}" && "${fail}" -gt 0 ]]; then
      status="FAIL"
    elif [[ -n "${skipped}" && "${skipped}" -gt 0 ]]; then
      status="WARN"
    else
      status="PASS"
    fi
  elif [[ "${inner_rc}" -eq 0 ]]; then
    status="PASS"
    fail="0"
  fi

  print_result_line "${status}" "${pass:-0}" "${fail:-0}" "${skipped:-0}"
  return "${inner_rc}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-path)
      [[ $# -ge 2 ]] || die "--dataset-path requires a path"
      HOST_DATASET_PATH="$2"
      shift 2
      ;;
    --image)
      [[ $# -ge 2 ]] || die "--image requires a value"
      IMAGE="$2"
      shift 2
      ;;
    --build-image)
      BUILD_IMAGE=1
      shift
      ;;
    --custom-openvino-install-dir)
      [[ $# -ge 2 ]] || die "--custom-openvino-install-dir requires a path"
      CUSTOM_OPENVINO_INSTALL_DIR="$2"
      shift 2
      ;;
    --dockerfile)
      [[ $# -ge 2 ]] || die "--dockerfile requires a value"
      DOCKERFILE="$2"
      shift 2
      ;;
    --base)
      [[ $# -ge 2 ]] || die "--base requires a value"
      BASE="$2"
      shift 2
      ;;
    --base-version)
      [[ $# -ge 2 ]] || die "--base-version requires a value"
      BASE_VERSION="$2"
      shift 2
      ;;
    --host-logs-dir)
      [[ $# -ge 2 ]] || die "--host-logs-dir requires a path"
      HOST_LOGS_DIR="$2"
      shift 2
      ;;
    --container-logs-dir)
      [[ $# -ge 2 ]] || die "--container-logs-dir requires a path"
      CONTAINER_LOGS_DIR="$2"
      shift 2
      ;;
    --container-dataset-path)
      [[ $# -ge 2 ]] || die "--container-dataset-path requires a path"
      CONTAINER_DATASET_PATH="$2"
      CONTAINER_DATASET_PATH_EXPLICIT=1
      shift 2
      ;;
    --container-name)
      [[ $# -ge 2 ]] || die "--container-name requires a value"
      CONTAINER_NAME="$2"
      shift 2
      ;;
    --keep-container)
      KEEP_CONTAINER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      INNER_AUTOTEST_ARGS+=("$@")
      break
      ;;
    *)
      INNER_AUTOTEST_ARGS+=("$1")
      shift
      ;;
  esac
done

HOST_LOGS_DIR=$(canonicalize_maybe_missing "${HOST_LOGS_DIR}")

if [[ -n "${HOST_DATASET_PATH}" ]]; then
  HOST_DATASET_PATH=$(canonicalize_existing "${HOST_DATASET_PATH}")
  require_dataset_layout "${HOST_DATASET_PATH}"
  if [[ "${CONTAINER_DATASET_PATH_EXPLICIT}" != "1" ]]; then
    CONTAINER_DATASET_PATH="${IMPORTED_CONTAINER_DATASET_PATH}"
  fi
fi

check_docker_env
build_image_if_needed
mkdir -p "${HOST_LOGS_DIR}"
start_container
resolve_container_project_dir
prepare_container
copy_dataset_into_container
run_autotest_in_container "${HOST_LOGS_DIR}/docker_stdout.log"
#!/usr/bin/env bash

set -Eeuo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

log(){ echo "[autotest] $*"; }
warn(){ echo "[autotest][warn] $*" >&2; }
die(){ echo "[autotest][error] $*" >&2; exit 1; }
require_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

RUNNING_CASE_PID=""

cleanup_active_case(){
  local pid="${RUNNING_CASE_PID:-}"
  RUNNING_CASE_PID=""
  if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
    kill -TERM -- "-${pid}" 2>/dev/null || kill -TERM "${pid}" 2>/dev/null || true
  fi
}

handle_interrupt(){ cleanup_active_case; exit 130; }
handle_terminate(){ cleanup_active_case; exit 143; }

trap cleanup_active_case EXIT
trap handle_interrupt INT
trap handle_terminate TERM

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_BUILD_DIR="${SCRIPT_DIR}/build"
DEFAULT_V2X_ROOT="${SCRIPT_DIR}/data/v2xfusion"
DEFAULT_KITTI_ROOT="${SCRIPT_DIR}/data/kitti"
DEFAULT_DATASET_SUBDIR="dataset"
DEFAULT_ONEAPI_SETVARS="/opt/intel/oneapi/setvars.sh"
DEFAULT_OPENVINO_SETUPVARS="/opt/intel/openvino/setupvars.sh"
DEFAULT_MODEL_ASSET_MODE_FILE="${SCRIPT_DIR}/data/model_asset_mode.txt"

BUILD_DIR="${DEFAULT_BUILD_DIR}"
V2X_ROOT="${DEFAULT_V2X_ROOT}"
KITTI_ROOT="${DEFAULT_KITTI_ROOT}"
DATASET_PATH=""
DATASET_PATH_EXPLICIT=0
LOGS_DIR=""
SMALL_SAMPLES=1
SHORT_WARMUP=1
SHORT_ITERS=5
CASE_TIMEOUT=120
BEVFUSION_REPEAT=1
UNIFIED_REPEAT=1
UNIFIED_NUM_SAMPLES=""
USE_FP32=0
KEEP_WORKDIR=0
SKIP_ENV_SETUP=0
QUIET=1
ONEAPI_SETVARS="${DEFAULT_ONEAPI_SETVARS}"
OPENVINO_SETUPVARS="${DEFAULT_OPENVINO_SETUPVARS}"
MODEL_ASSET_MODE_FILE="${DEFAULT_MODEL_ASSET_MODE_FILE}"
MODEL_ASSET_MODE="standard"
AUTOTEST_MODE="full-suite"
RUNTIME_SMOKE_ONLY=0

declare -a CASE_ORDER=()
declare -A CASE_STATUS=()
declare -A CASE_LOG=()
declare -A CASE_PERF=()

PASSED_COUNT=0
FAILED_COUNT=0
SKIPPED_COUNT=0

WORK_ROOT=""
MINI_ROOT=""
MINI_DATASET=""
APP_DATASET_PATH=""
SUMMARY_FILE=""
POINTPILLARS_MODEL_DIR=""
POINTPILLARS_PFE_MODEL=""
KITTI_DATASET_PATH=""
KITTI_POINTPILLARS_MODEL_DIR=""

usage(){
  cat <<'EOF'
Usage: bash autotest.sh [options]

Optional:
  --dataset-path PATH         KITTI-style dataset root for end-to-end runs.
                              If omitted, the script uses the bundled sample
                              dataset and runs the repeat-capable applications
                              on a single-frame mini dataset.
  --build-dir PATH            Deploy build directory.
                              Default: ./build
  --v2x-root PATH             DAIR-V2X data root that contains dump_bins/, pointpillars/, second/, dataset/.
                              Default: ./data/v2xfusion
  --kitti-root PATH           KITTI-360 data root that contains pointpillars/, second/, dataset/.
                              Default: ./data/kitti
  --logs-dir PATH             Directory for per-case logs and summary output.
                              Default: <build-dir>/autotest_logs/<timestamp>
  --small-samples N           Number of samples in the temporary mini dataset for test_* dataset runs.
                              Default: 1
  --short-warmup N            Warmup count for short-running module tests.
                              Default: 1
  --short-iters N             Iteration count for short-running module tests.
                              Default: 5
  --case-timeout SEC          Timeout for each test case. Use 0 to disable.
                              Default: 120
  --bevfusion-repeat N        Repeat count for bevfusion.
                              Default: 1
  --unified-repeat N          Repeat count for bevfusion_unified.
                              Default: 1
  --unified-num-samples N     Optional --num-samples override for bevfusion_unified.
                              Default: full dataset
  --fp32                      Run split-model binaries with FP32 models and unified binaries with FP16 models.
  --quiet                     Only print start/finish status lines for each case.
                              This is the default behavior.
  --verbose                   Stream each binary's output to the console while
                              still writing per-case log files.
  --oneapi-setvars PATH       oneAPI setvars.sh to source before testing.
                              Default: /opt/intel/oneapi/setvars.sh
  --openvino-setupvars PATH   OpenVINO setupvars.sh to source before testing.
                              Default: /opt/intel/openvino/setupvars.sh
  --skip-env-setup            Do not source oneAPI/OpenVINO environment scripts.
  --keep-workdir              Keep the temporary mini dataset under the logs directory.
  -h, --help                  Show this message.

Behavior:
  - Without --dataset-path, the script uses data/v2xfusion/dataset and
    runs bevfusion and bevfusion_unified on a one-frame mini dataset.
  - With --dataset-path, bevfusion and bevfusion_unified run on the provided
    dataset and ignore repeat counts.
  - If data/model_asset_mode.txt declares mode=dummy, the script switches to
    runtime smoke mode and only runs bevfusion/bevfusion_unified application
    checks, because the bundled dummy weights do not provide meaningful module
    outputs or detection results.
  - Dataset-based test_* binaries run on a temporary mini dataset built from the
    first --small-samples samples.
  - Module tests use short warmup/iteration counts.
  - Each binary writes a dedicated log file and the script prints a concise summary
    plus a final AUTOTEST_RESULT line with pass/fail/skipped counts and log paths.
EOF
}

canonicalize_existing(){
  realpath "$1"
}

canonicalize_maybe_missing(){
  realpath -m "$1"
}

cleanup(){
  if [[ -n "${WORK_ROOT}" && -d "${WORK_ROOT}" && "${KEEP_WORKDIR}" != "1" ]]; then
    rm -rf "${WORK_ROOT}"
  fi
}

trap cleanup EXIT

require_dataset_layout(){
  local root="$1"
  local subdir

  [[ -d "${root}" ]] || die "Dataset path is not a directory: ${root}"
  for subdir in image_2 velodyne calib label_2; do
    [[ -d "${root}/${subdir}" ]] || die "Missing dataset subdirectory: ${root}/${subdir}"
  done
}

source_setup_script(){
  local script_path="$1"
  local label="$2"

  if [[ "${label}" == "oneAPI" && "${SETVARS_COMPLETED:-0}" == "1" ]]; then
    log "oneAPI environment already initialized"
    return 0
  fi

  set +u
  # shellcheck disable=SC1090
  if ! source "${script_path}" >/dev/null 2>&1; then
    warn "${label} setup returned non-zero, continuing with the current shell environment"
  fi
  set -u
}

source_runtime_env(){
  if [[ "${SKIP_ENV_SETUP}" == "1" ]]; then
    log "Skipping oneAPI/OpenVINO environment setup"
    return 0
  fi

  [[ -f "${ONEAPI_SETVARS}" ]] || die "oneAPI setvars.sh not found: ${ONEAPI_SETVARS}"
  [[ -f "${OPENVINO_SETUPVARS}" ]] || die "OpenVINO setupvars.sh not found: ${OPENVINO_SETUPVARS}"

  source_setup_script "${ONEAPI_SETVARS}" "oneAPI"
  source_setup_script "${OPENVINO_SETUPVARS}" "OpenVINO"
}

detect_model_asset_mode(){
  MODEL_ASSET_MODE="standard"
  AUTOTEST_MODE="full-suite"
  RUNTIME_SMOKE_ONLY=0

  if [[ -f "${MODEL_ASSET_MODE_FILE}" ]] && grep -Eq '^[[:space:]]*mode=dummy[[:space:]]*$' "${MODEL_ASSET_MODE_FILE}"; then
    MODEL_ASSET_MODE="dummy"
    AUTOTEST_MODE="runtime-smoke"
    RUNTIME_SMOKE_ONLY=1
  fi
}

collect_sample_ids(){
  local dataset_root="$1"
  local limit="$2"
  local count=0
  local file
  local sample_id

  while IFS= read -r file; do
    sample_id=$(basename -- "${file}")
    sample_id=${sample_id%.*}
    printf '%s\n' "${sample_id}"
    count=$((count + 1))
    if [[ "${count}" -ge "${limit}" ]]; then
      break
    fi
  done < <(find "${dataset_root}/image_2" -maxdepth 1 -type f | sort)
}

link_sample_assets(){
  local source_root="$1"
  local target_root="$2"
  local sample_id="$3"
  local subdir
  local file
  local matches

  for subdir in image_2 velodyne calib label_2; do
    matches=0
    shopt -s nullglob
    for file in "${source_root}/${subdir}/${sample_id}".*; do
      ln -s "${file}" "${target_root}/${subdir}/$(basename -- "${file}")"
      matches=1
    done
    shopt -u nullglob

    if [[ "${matches}" != "1" ]]; then
      die "Missing ${subdir}/${sample_id}.* in ${source_root}"
    fi
  done
}

create_mini_dataset(){
  local source_dataset="$1"
  local limit="$2"
  local sample_ids=()
  local sample_id

  mapfile -t sample_ids < <(collect_sample_ids "${source_dataset}" "${limit}")
  [[ ${#sample_ids[@]} -gt 0 ]] || die "No samples found under ${source_dataset}/image_2"

  MINI_ROOT="${WORK_ROOT}/mini_v2xfusion"
  MINI_DATASET="${MINI_ROOT}/dataset"

  mkdir -p "${MINI_DATASET}/image_2" "${MINI_DATASET}/velodyne" "${MINI_DATASET}/calib" "${MINI_DATASET}/label_2"
  ln -s "${V2X_ROOT}/dump_bins" "${MINI_ROOT}/dump_bins"
  if [[ -d "${V2X_ROOT}/pointpillars" ]]; then
    ln -s "${V2X_ROOT}/pointpillars" "${MINI_ROOT}/pointpillars"
  fi
  if [[ -d "${V2X_ROOT}/second" ]]; then
    ln -s "${V2X_ROOT}/second" "${MINI_ROOT}/second"
  fi

  for sample_id in "${sample_ids[@]}"; do
    link_sample_assets "${source_dataset}" "${MINI_DATASET}" "${sample_id}"
  done
}

find_first_viewtransform_image(){
  local dataset_root="$1"
  local file

  while IFS= read -r file; do
    case "${file##*.}" in
      jpg|jpeg|png|JPG|JPEG|PNG)
        printf '%s\n' "${file}"
        return 0
        ;;
    esac
  done < <(find "${dataset_root}/image_2" -maxdepth 1 -type f | sort)

  return 1
}

extract_perf_line(){
  local case_name="$1"
  local log_file="$2"

  case "${case_name}" in
    bevfusion|bevfusion_unified)
      grep -E '\[perf\] frames=' "${log_file}" | tail -n 1 || true
      ;;
    *)
      grep -E '\[perf\]' "${log_file}" | tail -n 1 || true
      ;;
  esac
}

format_command(){
  local formatted=""

  printf -v formatted '%q ' "$@"
  printf '%s\n' "${formatted% }"
}

record_case(){
  local name="$1"
  local status="$2"
  local log_file="$3"

  CASE_ORDER+=("${name}")
  CASE_STATUS["${name}"]="${status}"
  CASE_LOG["${name}"]="${log_file}"

  case "${status}" in
    PASS)
      PASSED_COUNT=$((PASSED_COUNT + 1))
      ;;
    FAIL)
      FAILED_COUNT=$((FAILED_COUNT + 1))
      ;;
    SKIPPED)
      SKIPPED_COUNT=$((SKIPPED_COUNT + 1))
      ;;
  esac
}

run_case(){
  local name="$1"
  local collect_perf="$2"
  shift 2

  local binary_path="$1"
  local log_file="${LOGS_DIR}/${name}.log"
  local command_line

  command_line=$(format_command "$@")

  if [[ ! -x "${BUILD_DIR}/${binary_path#./}" ]]; then
    warn "Skipping ${name}: binary not found at ${BUILD_DIR}/${binary_path#./}"
    : > "${log_file}"
    record_case "${name}" "SKIPPED" "${log_file}"
    return 0
  fi

  printf '# cwd: %s\n# cmd: %s\n\n' "${BUILD_DIR}" "${command_line}" > "${log_file}"
  log "Executing ${name}: ${command_line}"
  echo "# timeout: ${CASE_TIMEOUT}s" >> "${log_file}"

  if [[ "${QUIET}" == "1" ]]; then
    if run_in_build_dir "$@" >>"${log_file}" 2>&1; then
      record_case "${name}" "PASS" "${log_file}"
      log "${name} succeeded"
    else
      local exit_code=$?
      if [[ "${exit_code}" == "124" || "${exit_code}" == "137" ]]; then
        echo "[autotest][error] ${name} timed out after ${CASE_TIMEOUT}s" >> "${log_file}"
        warn "${name} timed out after ${CASE_TIMEOUT}s (log: ${log_file})"
      else
        warn "${name} failed (log: ${log_file})"
      fi
      record_case "${name}" "FAIL" "${log_file}"
    fi
  elif run_in_build_dir "$@" > >(tee -a "${log_file}") 2>&1; then
    record_case "${name}" "PASS" "${log_file}"
    log "${name} succeeded"
  else
    record_case "${name}" "FAIL" "${log_file}"
    warn "${name} failed (log: ${log_file})"
  fi

  if [[ -n "${collect_perf}" ]]; then
    CASE_PERF["${name}"]=$(extract_perf_line "${name}" "${log_file}")
  fi
}

run_with_timeout(){
  local exit_code

  if [[ "${CASE_TIMEOUT}" == "0" ]]; then
    setsid "$@" &
  else
    setsid timeout --kill-after=10s "${CASE_TIMEOUT}s" "$@" &
  fi

  RUNNING_CASE_PID=$!
  if wait "${RUNNING_CASE_PID}"; then
    exit_code=0
  else
    exit_code=$?
  fi
  RUNNING_CASE_PID=""
  return "${exit_code}"
}

run_in_build_dir(){
  local previous_dir
  local exit_code

  previous_dir=$(pwd)
  cd "${BUILD_DIR}"
  if run_with_timeout "$@"; then
    exit_code=0
  else
    exit_code=$?
  fi
  cd "${previous_dir}"
  return "${exit_code}"
}

write_summary(){
  local name

  SUMMARY_FILE="${LOGS_DIR}/summary.txt"
  {
    echo "Autotest Summary"
    echo "Status: $(overall_status)"
    echo "Model asset mode: ${MODEL_ASSET_MODE}"
    echo "Autotest mode: ${AUTOTEST_MODE}"
    echo "Logs dir: ${LOGS_DIR}"
    echo "Dataset path: ${DATASET_PATH}"
    echo "Mini dataset: ${MINI_DATASET}"
    echo "Passed: ${PASSED_COUNT}"
    echo "Failed: ${FAILED_COUNT}"
    echo "Skipped: ${SKIPPED_COUNT}"
    echo
    for name in "${CASE_ORDER[@]}"; do
      printf '[%s] %s\n' "${CASE_STATUS[${name}]}" "${name}"
      if [[ -n "${CASE_PERF[${name}]:-}" ]]; then
        printf 'perf: %s\n' "${CASE_PERF[${name}]}"
      fi
      printf 'log: %s\n' "${CASE_LOG[${name}]}"
      echo
    done
  } > "${SUMMARY_FILE}"
}

overall_status(){
  if [[ "${FAILED_COUNT}" -gt 0 ]]; then
    printf 'FAIL\n'
  elif [[ "${SKIPPED_COUNT}" -gt 0 ]]; then
    printf 'WARN\n'
  else
    printf 'PASS\n'
  fi
}

print_summary(){
  local name

  echo
  echo "=== Autotest Summary ==="
  echo "Status : $(overall_status)"
  echo "Asset mode : ${MODEL_ASSET_MODE}"
  echo "Test mode  : ${AUTOTEST_MODE}"
  echo "Passed : ${PASSED_COUNT}"
  echo "Failed : ${FAILED_COUNT}"
  echo "Skipped: ${SKIPPED_COUNT}"
  echo "Logs   : ${LOGS_DIR}"
  echo "Summary: ${SUMMARY_FILE}"
  echo
  echo "BEVFusion perf        : ${CASE_PERF[bevfusion]:-(missing [perf] line)}"
  echo "BEVFusion unified perf: ${CASE_PERF[bevfusion_unified]:-(missing [perf] line)}"

  if [[ "${FAILED_COUNT}" -gt 0 || "${SKIPPED_COUNT}" -gt 0 ]]; then
    echo
    echo "Non-pass cases:"
    for name in "${CASE_ORDER[@]}"; do
      if [[ "${CASE_STATUS[${name}]}" == "PASS" ]]; then
        continue
      fi
      printf '[%s] %s\n' "${CASE_STATUS[${name}]}" "${name}"
      printf '  log : %s\n' "${CASE_LOG[${name}]}"
      if [[ -n "${CASE_PERF[${name}]:-}" ]]; then
        printf '  perf: %s\n' "${CASE_PERF[${name}]}"
      fi
    done
  fi
}

print_result_line(){
  echo "AUTOTEST_RESULT status=$(overall_status) pass=${PASSED_COUNT} fail=${FAILED_COUNT} skipped=${SKIPPED_COUNT} logs=${LOGS_DIR} summary=${SUMMARY_FILE}"
}

build_bevfusion_args(){
  local -a args=(./bevfusion "${APP_DATASET_PATH}" --model-dir "${POINTPILLARS_MODEL_DIR}")

  if [[ "${DATASET_PATH_EXPLICIT}" != "1" ]]; then
    args+=(--repeat "${BEVFUSION_REPEAT}")
  fi
  args+=("${FP32_FLAG[@]}")

  printf '%s\0' "${args[@]}"
}

build_unified_args(){
  local -a args=(./bevfusion_unified "${APP_DATASET_PATH}" --preset v2x)

  if [[ "${DATASET_PATH_EXPLICIT}" != "1" ]]; then
    args+=(--repeat "${UNIFIED_REPEAT}")
  fi
  args+=("${UNIFIED_ARGS[@]}")
  args+=("${UNIFIED_PRECISION_ARGS[@]}")

  printf '%s\0' "${args[@]}"
}

build_kitti_bevfusion_args(){
  local -a args=(./bevfusion "${KITTI_DATASET_PATH}" --preset kitti --model-dir "${KITTI_POINTPILLARS_MODEL_DIR}" --num-samples 1)
  args+=("${FP32_FLAG[@]}")

  printf '%s\0' "${args[@]}"
}

build_kitti_unified_args(){
  local -a args=(./bevfusion_unified "${KITTI_DATASET_PATH}" --preset kitti --num-samples 1)

  printf '%s\0' "${args[@]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dataset-path)
      [[ $# -ge 2 ]] || die "--dataset-path requires a path"
      DATASET_PATH="$2"
      DATASET_PATH_EXPLICIT=1
      shift 2
      ;;
    --build-dir)
      [[ $# -ge 2 ]] || die "--build-dir requires a path"
      BUILD_DIR="$2"
      shift 2
      ;;
    --v2x-root)
      [[ $# -ge 2 ]] || die "--v2x-root requires a path"
      V2X_ROOT="$2"
      shift 2
      ;;
    --kitti-root)
      [[ $# -ge 2 ]] || die "--kitti-root requires a path"
      KITTI_ROOT="$2"
      shift 2
      ;;
    --logs-dir)
      [[ $# -ge 2 ]] || die "--logs-dir requires a path"
      LOGS_DIR="$2"
      shift 2
      ;;
    --small-samples)
      [[ $# -ge 2 ]] || die "--small-samples requires a value"
      SMALL_SAMPLES="$2"
      shift 2
      ;;
    --short-warmup)
      [[ $# -ge 2 ]] || die "--short-warmup requires a value"
      SHORT_WARMUP="$2"
      shift 2
      ;;
    --short-iters)
      [[ $# -ge 2 ]] || die "--short-iters requires a value"
      SHORT_ITERS="$2"
      shift 2
      ;;
    --case-timeout)
      [[ $# -ge 2 ]] || die "--case-timeout requires a value"
      CASE_TIMEOUT="$2"
      shift 2
      ;;
    --bevfusion-repeat)
      [[ $# -ge 2 ]] || die "--bevfusion-repeat requires a value"
      BEVFUSION_REPEAT="$2"
      shift 2
      ;;
    --unified-repeat)
      [[ $# -ge 2 ]] || die "--unified-repeat requires a value"
      UNIFIED_REPEAT="$2"
      shift 2
      ;;
    --unified-num-samples)
      [[ $# -ge 2 ]] || die "--unified-num-samples requires a value"
      UNIFIED_NUM_SAMPLES="$2"
      shift 2
      ;;
    --fp32)
      USE_FP32=1
      shift
      ;;
    --verbose)
      QUIET=0
      shift
      ;;
    --quiet)
      QUIET=1
      shift
      ;;
    --keep-workdir)
      KEEP_WORKDIR=1
      shift
      ;;
    --skip-env-setup)
      SKIP_ENV_SETUP=1
      shift
      ;;
    --oneapi-setvars)
      [[ $# -ge 2 ]] || die "--oneapi-setvars requires a path"
      ONEAPI_SETVARS="$2"
      shift 2
      ;;
    --openvino-setupvars)
      [[ $# -ge 2 ]] || die "--openvino-setupvars requires a path"
      OPENVINO_SETUPVARS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

require_cmd realpath
require_cmd find
require_cmd sort
require_cmd mktemp
require_cmd ln
require_cmd grep
require_cmd setsid
if [[ "${CASE_TIMEOUT}" != "0" ]]; then
  require_cmd timeout
fi

BUILD_DIR=$(canonicalize_existing "${BUILD_DIR}")
V2X_ROOT=$(canonicalize_existing "${V2X_ROOT}")
KITTI_ROOT=$(canonicalize_maybe_missing "${KITTI_ROOT}")

if [[ -n "${DATASET_PATH}" ]]; then
  DATASET_PATH=$(canonicalize_existing "${DATASET_PATH}")
else
  DATASET_PATH=$(canonicalize_existing "${V2X_ROOT}/${DEFAULT_DATASET_SUBDIR}")
fi

require_dataset_layout "${DATASET_PATH}"

[[ -d "${BUILD_DIR}" ]] || die "Build directory not found: ${BUILD_DIR}"
[[ -d "${V2X_ROOT}" ]] || die "v2x root not found: ${V2X_ROOT}"
[[ -d "${V2X_ROOT}/dump_bins" ]] || die "Missing dump_bins under ${V2X_ROOT}"
[[ -d "${V2X_ROOT}/pointpillars" ]] || die "Missing pointpillars model directory under ${V2X_ROOT}"
[[ -d "${V2X_ROOT}/second" ]] || die "Missing second model directory under ${V2X_ROOT}"

POINTPILLARS_MODEL_DIR="${V2X_ROOT}/pointpillars"
if [[ "${USE_FP32}" == "0" && -f "${POINTPILLARS_MODEL_DIR}/quantized_lidar_pfe.xml" ]]; then
  POINTPILLARS_PFE_MODEL="${POINTPILLARS_MODEL_DIR}/quantized_lidar_pfe.xml"
elif [[ -f "${POINTPILLARS_MODEL_DIR}/lidar_pfe_v7000.onnx" ]]; then
  POINTPILLARS_PFE_MODEL="${POINTPILLARS_MODEL_DIR}/lidar_pfe_v7000.onnx"
elif [[ -f "${POINTPILLARS_MODEL_DIR}/lidar_pfe_v6000.onnx" ]]; then
  POINTPILLARS_PFE_MODEL="${POINTPILLARS_MODEL_DIR}/lidar_pfe_v6000.onnx"
else
  die "Missing lidar PFE model under ${POINTPILLARS_MODEL_DIR}"
fi

if [[ -d "${KITTI_ROOT}/dataset" && -d "${KITTI_ROOT}/pointpillars" && -d "${KITTI_ROOT}/second" ]]; then
  KITTI_DATASET_PATH="${KITTI_ROOT}/dataset"
  KITTI_POINTPILLARS_MODEL_DIR="${KITTI_ROOT}/pointpillars"
fi

if [[ -z "${LOGS_DIR}" ]]; then
  LOGS_DIR="${BUILD_DIR}/autotest_logs/$(date +%Y%m%d_%H%M%S)"
fi
LOGS_DIR=$(canonicalize_maybe_missing "${LOGS_DIR}")
mkdir -p "${LOGS_DIR}"

WORK_ROOT=$(mktemp -d "${LOGS_DIR}/work.XXXXXX")

source_runtime_env
detect_model_asset_mode
create_mini_dataset "${DATASET_PATH}" "${SMALL_SAMPLES}"

if [[ "${DATASET_PATH_EXPLICIT}" == "1" ]]; then
  APP_DATASET_PATH="${DATASET_PATH}"
else
  APP_DATASET_PATH="${MINI_DATASET}"
fi

VIEWTRANSFORM_IMAGE=""
if VIEWTRANSFORM_IMAGE=$(find_first_viewtransform_image "${DATASET_PATH}"); then
  :
elif VIEWTRANSFORM_IMAGE=$(find_first_viewtransform_image "${V2X_ROOT}/dataset"); then
  warn "No jpg/jpeg/png image found in --dataset-path; falling back to bundled sample image for test_viewtransform"
else
  die "Unable to find a jpg/jpeg/png image for test_viewtransform"
fi

CAMERA_MODEL="../data/v2xfusion/pointpillars/quantized_camera.xml"
FP32_FLAG=()
UNIFIED_ARGS=()
UNIFIED_PRECISION_ARGS=()

if [[ "${USE_FP32}" == "1" ]]; then
  CAMERA_MODEL="../data/v2xfusion/pointpillars/camera.backbone.onnx"
  FP32_FLAG=(--fp32)
  UNIFIED_PRECISION_ARGS=(--fp16)
fi

if [[ -n "${UNIFIED_NUM_SAMPLES}" ]]; then
  UNIFIED_ARGS+=(--num-samples "${UNIFIED_NUM_SAMPLES}")
fi

log "Build dir     : ${BUILD_DIR}"
log "Dataset path  : ${DATASET_PATH}"
log "Mini dataset  : ${MINI_DATASET}"
log "App dataset   : ${APP_DATASET_PATH}"
log "v2x root      : ${V2X_ROOT}"
log "PointPillars  : ${POINTPILLARS_MODEL_DIR}"
log "Asset mode    : ${MODEL_ASSET_MODE}"
log "Autotest mode : ${AUTOTEST_MODE}"
if [[ -n "${KITTI_DATASET_PATH}" ]]; then
  log "KITTI-360 data : ${KITTI_DATASET_PATH}"
fi
log "Logs dir      : ${LOGS_DIR}"

mapfile -d '' -t BEVFUSION_CMD < <(build_bevfusion_args)
mapfile -d '' -t UNIFIED_CMD < <(build_unified_args)
if [[ -n "${KITTI_DATASET_PATH}" ]]; then
  mapfile -d '' -t KITTI_BEVFUSION_CMD < <(build_kitti_bevfusion_args)
  mapfile -d '' -t KITTI_UNIFIED_CMD < <(build_kitti_unified_args)
fi

if [[ "${RUNTIME_SMOKE_ONLY}" != "1" ]]; then
  run_case "test_camera_geometry" "" ./test_camera_geometry
  run_case "test_bev_pool" "" ./test_bev_pool "${SHORT_WARMUP}" "${SHORT_ITERS}"
  run_case "test_viewtransform" "" ./test_viewtransform "${VIEWTRANSFORM_IMAGE}" "${CAMERA_MODEL}" "${SHORT_WARMUP}" "${SHORT_ITERS}" "${FP32_FLAG[@]}"
  run_case "test_camera_bev_pipeline" "" ./test_camera_bev_pipeline "${MINI_DATASET}" "${CAMERA_MODEL}" "${SHORT_WARMUP}" "${FP32_FLAG[@]}"
  run_case "test_pointpillars_voxelizer" "" ./test_pointpillars_voxelizer
  run_case "test_pointpillars" "" ./test_pointpillars --dataset "${MINI_DATASET}" --pfe "${POINTPILLARS_PFE_MODEL}" "${FP32_FLAG[@]}"
  run_case "test_lidar_pipeline" "" ./test_lidar_pipeline "${MINI_DATASET}" "${POINTPILLARS_PFE_MODEL}" "${SHORT_WARMUP}" --num-samples "${SMALL_SAMPLES}" "${FP32_FLAG[@]}"
  run_case "test_fuser" "" ./test_fuser "${SHORT_WARMUP}" "${SHORT_ITERS}" "${FP32_FLAG[@]}"
  run_case "test_head" "" ./test_head "${SHORT_WARMUP}" "${SHORT_ITERS}" "${FP32_FLAG[@]}"
  run_case "test_fusion_pipeline" "" ./test_fusion_pipeline "../data/v2xfusion" "${SHORT_WARMUP}" "${SHORT_ITERS}" usm "${FP32_FLAG[@]}"
  run_case "test_bevfusion_pipeline" "" ./test_bevfusion_pipeline "${MINI_DATASET}" --model-dir "${POINTPILLARS_MODEL_DIR}" --num-samples "${SMALL_SAMPLES}" --warmup "${SHORT_WARMUP}" "${FP32_FLAG[@]}"
else
  log "Dummy model assets detected; running bevfusion/bevfusion_unified runtime smoke tests only"
fi

run_case "bevfusion" "bevfusion" "${BEVFUSION_CMD[@]}"
run_case "bevfusion_unified" "bevfusion_unified" "${UNIFIED_CMD[@]}"
if [[ -n "${KITTI_DATASET_PATH}" ]]; then
  run_case "bevfusion_kitti" "bevfusion" "${KITTI_BEVFUSION_CMD[@]}"
  if [[ "${USE_FP32}" == "0" ]]; then
    run_case "bevfusion_unified_kitti" "bevfusion_unified" "${KITTI_UNIFIED_CMD[@]}"
  fi
fi

write_summary
print_summary
print_result_line

if [[ "${FAILED_COUNT}" -gt 0 ]]; then
  exit 1
fi

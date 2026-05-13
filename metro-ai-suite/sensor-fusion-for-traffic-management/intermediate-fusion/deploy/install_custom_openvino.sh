#!/usr/bin/env bash

set -Eeuo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

log(){ echo "[custom-openvino] $*"; }
warn(){ echo "[custom-openvino][warn] $*" >&2; }
die(){ echo "[custom-openvino][error] $*" >&2; exit 1; }
require_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

default_parallel_jobs(){
  if command -v nproc >/dev/null 2>&1; then
    echo $(( $(nproc) / 2 ))
  else
    echo 1
  fi
}

bootstrap_apt_packages(){
  local packages=("$@")

  require_cmd sudo
  command -v apt-get >/dev/null 2>&1 || die "Missing required command: apt-get"

  sudo -v
  sudo -E apt-get update -y
  sudo -E apt-get install -y --no-install-recommends "${packages[@]}"
}

ensure_bootstrap_tools(){
  local packages=()

  if ! command -v curl >/dev/null 2>&1; then
    packages+=(ca-certificates curl)
  fi
  if ! command -v gpg >/dev/null 2>&1; then
    packages+=(gpg)
  fi
  if ! command -v git >/dev/null 2>&1; then
    packages+=(git)
  fi
  if ! command -v cmake >/dev/null 2>&1; then
    packages+=(cmake)
  fi
  if ! command -v nproc >/dev/null 2>&1 || ! command -v realpath >/dev/null 2>&1; then
    packages+=(coreutils)
  fi

  if [[ ${#packages[@]} -gt 0 ]]; then
    log "Installing missing bootstrap packages: ${packages[*]}"
    bootstrap_apt_packages "${packages[@]}"
  fi
}

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
DEFAULT_PATCH_FILE="${SCRIPT_DIR}/custom_openvino_2026.1.0_sparse_ops.patch"
OPENVINO_GIT_URL="https://github.com/openvinotoolkit/openvino.git"
OPENVINO_GIT_BRANCH="2026.1.0"
OPENVINO_BASE_COMMIT="63e31528c62d3eee06733efa63915ce04bd86f47"
OPENVINO_ENABLE_TESTS="${OPENVINO_ENABLE_TESTS:-OFF}"
OPENCL_SDK_GIT_URL="https://github.com/KhronosGroup/OpenCL-SDK.git"
OPENCL_SDK_GIT_REF="${OPENCL_SDK_GIT_REF:-v2025.07.23}"

OV_DIR=""
PATCH_FILE="${DEFAULT_PATCH_FILE}"
BUILD_DIR=""
INSTALL_DIR=""
OPENCL_SDK_SOURCE_DIR="${OPENCL_SDK_SOURCE_DIR:-}"
OPENCL_SDK_BUILD_DIR="${OPENCL_SDK_BUILD_DIR:-}"
JOBS="$(default_parallel_jobs)"
ONEAPI_VERSION="${ONEAPI_VERSION:-2025.3}"
SKIP_ONEAPI_INSTALL="${SKIP_ONEAPI_INSTALL:-0}"

usage(){
  cat <<'EOF'
Usage: bash install_custom_openvino.sh --ov-dir /path/to/openvino [options]

Required:
  --ov-dir PATH           Target path for the OpenVINO 2026.1.0 source tree.
                          If the checkout does not exist yet, the script clones
                          upstream OpenVINO there automatically.

Optional:
  --patch PATH            Patch file to apply.
                          Default: <script-dir>/custom_openvino_2026.1.0_sparse_ops.patch
  --build-dir PATH        CMake build directory.
                          Default: <ov-dir>/build
  --install-dir PATH      Install prefix.
                          Default: <ov-dir>/install
  --jobs N                Parallel build jobs.
                          Default: nproc
  --oneapi-version VER    oneAPI apt package suffix.
                          Default: 2025.3
  --skip-oneapi-install   Reuse existing /opt/intel/oneapi instead of apt installing.
  -h, --help              Show this message.

Environment overrides:
  ONEAPI_VERSION          Same as --oneapi-version
  SKIP_ONEAPI_INSTALL=1   Same as --skip-oneapi-install
  TRACE=1                 Enable shell tracing

What the script does:
  1. Clones upstream OpenVINO 2026.1.0 into <ov-dir> if needed.
  2. Installs OpenVINO build dependencies from <ov-dir>/install_build_dependencies.sh.
  3. Installs Intel oneAPI Base Toolkit (icx/icpx) unless skipped.
  4. Installs OpenCL-SDK before configuring OpenVINO.
  5. Applies the custom sparse-op patch if it is not already applied.
  6. Configures, builds, and installs custom OpenVINO.

Example:
  bash install_custom_openvino.sh --ov-dir /work/openvino
EOF
}

canonicalize_existing(){
  realpath "$1"
}

canonicalize_maybe_missing(){
  realpath -m "$1"
}

opencl_sdk_config_present(){
  local candidate

  for candidate in \
    /usr/lib/cmake/OpenCL/OpenCLConfig.cmake \
    /usr/lib64/cmake/OpenCL/OpenCLConfig.cmake \
    /usr/local/lib/cmake/OpenCL/OpenCLConfig.cmake \
    /usr/local/lib64/cmake/OpenCL/OpenCLConfig.cmake \
    /usr/lib/x86_64-linux-gnu/cmake/OpenCL/OpenCLConfig.cmake; do
    if [[ -f "${candidate}" ]]; then
      return 0
    fi
  done

  return 1
}

ensure_openvino_checkout(){
  if [[ -d "${OV_DIR}/.git" ]]; then
    log "Reusing existing OpenVINO checkout at ${OV_DIR}"
    return 0
  fi

  if [[ -e "${OV_DIR}" && ! -d "${OV_DIR}" ]]; then
    die "${OV_DIR} exists but is not a directory"
  fi

  if [[ -d "${OV_DIR}" ]] && [[ -n "$(find "${OV_DIR}" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    die "${OV_DIR} exists but is not an OpenVINO git checkout"
  fi

  mkdir -p "$(dirname -- "${OV_DIR}")"

  log "Cloning upstream OpenVINO ${OPENVINO_GIT_BRANCH} into ${OV_DIR}"
  git clone --branch "${OPENVINO_GIT_BRANCH}" --single-branch "${OPENVINO_GIT_URL}" "${OV_DIR}"

  local cloned_head
  cloned_head=$(git -C "${OV_DIR}" rev-parse HEAD)

  if [[ "${cloned_head}" != "${OPENVINO_BASE_COMMIT}" ]]; then
    warn "Cloned branch head is ${cloned_head:0:12}; checking out patch base ${OPENVINO_BASE_COMMIT:0:12}"
    git -C "${OV_DIR}" checkout "${OPENVINO_BASE_COMMIT}"
  fi
}

source_oneapi(){
  [[ -f /opt/intel/oneapi/setvars.sh ]] || die "oneAPI setvars.sh not found at /opt/intel/oneapi/setvars.sh"

  set +u
  # shellcheck disable=SC1091
  source /opt/intel/oneapi/setvars.sh --force >/dev/null 2>&1
  set -u
}

install_openvino_build_deps(){
  local deps_script="${OV_DIR}/install_build_dependencies.sh"
  require_cmd sudo

  [[ -f "${deps_script}" ]] || die "OpenVINO dependency script not found: ${deps_script}"

  log "Installing OpenVINO build dependencies via ${deps_script}"
  sudo -E bash "${deps_script}"
}

install_oneapi(){
  if [[ "${SKIP_ONEAPI_INSTALL}" == "1" ]]; then
    log "SKIP_ONEAPI_INSTALL=1 set, skipping oneAPI apt installation"
    source_oneapi
    return 0
  fi

  if [[ -f /opt/intel/oneapi/setvars.sh ]]; then
    source_oneapi
    if command -v icx >/dev/null 2>&1 && command -v icpx >/dev/null 2>&1; then
      log "oneAPI compiler already available, skipping apt installation"
      return 0
    fi
  fi

  ensure_bootstrap_tools
  require_cmd sudo

  local keyring=/usr/share/keyrings/intel-oneapi-archive-keyring.gpg
  log "Installing Intel oneAPI Base Toolkit ${ONEAPI_VERSION}"

  sudo -E apt-get update -y
  sudo -E apt-get install -y ca-certificates curl gpg lsb-release

  if [[ ! -f "${keyring}" ]]; then
    curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | \
      sudo gpg --dearmor -o "${keyring}"
  fi

  if [[ ! -f /etc/apt/sources.list.d/oneAPI.list ]] || ! grep -q "apt.repos.intel.com/oneapi" /etc/apt/sources.list.d/oneAPI.list; then
    echo "deb [signed-by=${keyring}] https://apt.repos.intel.com/oneapi all main" | \
      sudo tee /etc/apt/sources.list.d/oneAPI.list >/dev/null
  fi

  sudo -E apt-get update -y
  sudo -E apt-get install -y "intel-oneapi-base-toolkit-${ONEAPI_VERSION}" lsb-release

  source_oneapi
  command -v icx >/dev/null 2>&1 || die "icx not found after oneAPI installation"
  command -v icpx >/dev/null 2>&1 || die "icpx not found after oneAPI installation"
}

install_opencl_sdk(){
  if [[ "${SKIP_OPENCL_SDK:-0}" == "1" || "${SKIP_OPENCL_SDK_INSTALL:-0}" == "1" ]]; then
    log "Skipping OpenCL-SDK installation."
    return 0
  fi

  require_cmd sudo

  if opencl_sdk_config_present; then
    log "OpenCL-SDK CMake package already present, skipping OpenCL-SDK build"
    return 0
  fi

  log "Installing OpenCL-SDK ${OPENCL_SDK_GIT_REF}"
  sudo -E apt-get install -y --no-install-recommends vulkan-tools libvulkan-dev

  mkdir -p "$(dirname -- "${OPENCL_SDK_SOURCE_DIR}")"

  if [[ -d "${OPENCL_SDK_SOURCE_DIR}/.git" ]]; then
    log "Updating existing OpenCL-SDK checkout at ${OPENCL_SDK_SOURCE_DIR}"
    git -C "${OPENCL_SDK_SOURCE_DIR}" fetch --depth 1 origin "${OPENCL_SDK_GIT_REF}"
    git -C "${OPENCL_SDK_SOURCE_DIR}" checkout --detach -q FETCH_HEAD
    git -C "${OPENCL_SDK_SOURCE_DIR}" submodule update --init --recursive --depth 1
  else
    log "Cloning OpenCL-SDK ${OPENCL_SDK_GIT_REF} into ${OPENCL_SDK_SOURCE_DIR}"
    git clone --depth 1 -b "${OPENCL_SDK_GIT_REF}" --recursive "${OPENCL_SDK_GIT_URL}" "${OPENCL_SDK_SOURCE_DIR}"
  fi

  cmake -S "${OPENCL_SDK_SOURCE_DIR}" -B "${OPENCL_SDK_BUILD_DIR}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr
  sudo cmake --build "${OPENCL_SDK_BUILD_DIR}" --target install --config Release --parallel "${JOBS}"
}

update_submodules(){
  log "Updating OpenVINO submodules"
  git -C "${OV_DIR}" submodule update --init --recursive
}

apply_patch_if_needed(){
  local current_head
  current_head=$(git -C "${OV_DIR}" rev-parse HEAD)

  if [[ "${current_head}" != "${OPENVINO_BASE_COMMIT}" ]]; then
    warn "OpenVINO HEAD is ${current_head:0:12}, expected ${OPENVINO_BASE_COMMIT:0:12}. The patch will still be checked before apply."
  fi

  if git -C "${OV_DIR}" apply --reverse --check "${PATCH_FILE}" >/dev/null 2>&1; then
    log "Patch already applied, skipping"
    return 0
  fi

  log "Checking patch applicability"
  if git -C "${OV_DIR}" apply --check "${PATCH_FILE}" >/dev/null 2>&1; then
    log "Applying patch ${PATCH_FILE}"
    git -C "${OV_DIR}" apply --binary "${PATCH_FILE}"
    return 0
  fi

  require_cmd patch
  log "Patch is partially applied, applying any remaining hunks from ${PATCH_FILE}"
  (cd "${OV_DIR}" && patch -p1 -N --forward --batch < "${PATCH_FILE}" >/dev/null) || true

  if git -C "${OV_DIR}" apply --reverse --check "${PATCH_FILE}" >/dev/null 2>&1; then
    log "Patch now fully applied"
    return 0
  fi

  die "Patch does not apply cleanly to ${OV_DIR}"
}

configure_build(){
  log "Configuring OpenVINO build in ${BUILD_DIR}"
  cmake -S "${OV_DIR}" -B "${BUILD_DIR}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DENABLE_TESTS="${OPENVINO_ENABLE_TESTS}" \
    -DCMAKE_C_COMPILER=icx \
    -DCMAKE_CXX_COMPILER=icpx \
    -DCMAKE_INSTALL_PREFIX="${INSTALL_DIR}"
}

build_openvino(){
  log "Building OpenVINO with ${JOBS} parallel jobs"
  cmake --build "${BUILD_DIR}" --parallel "${JOBS}"
}

install_openvino(){
  log "Installing custom OpenVINO to ${INSTALL_DIR}"
  if [[ -d "${INSTALL_DIR}" ]]; then
    if [[ -w "${INSTALL_DIR}" ]]; then
      cmake --install "${BUILD_DIR}" --prefix "${INSTALL_DIR}"
    else
      require_cmd sudo
      sudo -E cmake --install "${BUILD_DIR}" --prefix "${INSTALL_DIR}"
    fi
  else
    local parent_dir
    parent_dir=$(dirname -- "${INSTALL_DIR}")
    if [[ -d "${parent_dir}" && -w "${parent_dir}" ]]; then
      cmake --install "${BUILD_DIR}" --prefix "${INSTALL_DIR}"
    else
      require_cmd sudo
      sudo mkdir -p "${INSTALL_DIR}"
      sudo -E cmake --install "${BUILD_DIR}" --prefix "${INSTALL_DIR}"
    fi
  fi
  [[ -f "${INSTALL_DIR}/setupvars.sh" ]] || die "Expected install output missing: ${INSTALL_DIR}/setupvars.sh"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ov-dir)
      [[ $# -ge 2 ]] || die "--ov-dir requires a path"
      OV_DIR="$2"
      shift 2
      ;;
    --patch)
      [[ $# -ge 2 ]] || die "--patch requires a path"
      PATCH_FILE="$2"
      shift 2
      ;;
    --build-dir)
      [[ $# -ge 2 ]] || die "--build-dir requires a path"
      BUILD_DIR="$2"
      shift 2
      ;;
    --install-dir)
      [[ $# -ge 2 ]] || die "--install-dir requires a path"
      INSTALL_DIR="$2"
      shift 2
      ;;
    --jobs)
      [[ $# -ge 2 ]] || die "--jobs requires a value"
      JOBS="$2"
      shift 2
      ;;
    --oneapi-version)
      [[ $# -ge 2 ]] || die "--oneapi-version requires a value"
      ONEAPI_VERSION="$2"
      shift 2
      ;;
    --skip-oneapi-install)
      SKIP_ONEAPI_INSTALL=1
      shift
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

[[ -n "${OV_DIR}" ]] || die "--ov-dir is required"

ensure_bootstrap_tools
require_cmd git
require_cmd cmake
require_cmd nproc
require_cmd realpath

OV_DIR=$(canonicalize_maybe_missing "${OV_DIR}")
PATCH_FILE=$(canonicalize_existing "${PATCH_FILE}")
ensure_openvino_checkout
OV_DIR=$(canonicalize_existing "${OV_DIR}")
BUILD_DIR=$(canonicalize_maybe_missing "${BUILD_DIR:-${OV_DIR}/build}")
INSTALL_DIR=$(canonicalize_maybe_missing "${INSTALL_DIR:-${OV_DIR}/install}")
OPENCL_SDK_SOURCE_DIR=$(canonicalize_maybe_missing "${OPENCL_SDK_SOURCE_DIR:-$(dirname -- "${OV_DIR}")/OpenCL-SDK}")
OPENCL_SDK_BUILD_DIR=$(canonicalize_maybe_missing "${OPENCL_SDK_BUILD_DIR:-${OPENCL_SDK_SOURCE_DIR}/build}")

[[ -d "${OV_DIR}/.git" ]] || die "${OV_DIR} is not a git checkout"
[[ -f "${PATCH_FILE}" ]] || die "Patch file not found: ${PATCH_FILE}"

log "OpenVINO source dir : ${OV_DIR}"
log "Patch file          : ${PATCH_FILE}"
log "Build dir           : ${BUILD_DIR}"
log "Install dir         : ${INSTALL_DIR}"
log "oneAPI version      : ${ONEAPI_VERSION}"
log "ENABLE_TESTS        : ${OPENVINO_ENABLE_TESTS}"
log "OpenCL-SDK dir      : ${OPENCL_SDK_SOURCE_DIR}"

install_openvino_build_deps
install_oneapi
install_opencl_sdk
update_submodules
apply_patch_if_needed
configure_build
build_openvino
install_openvino

log "Done. Source the installed runtime with:"
log "  source ${INSTALL_DIR}/setupvars.sh"
log "For Docker builds, set CUSTOM_OPENVINO_INSTALL_DIR=${INSTALL_DIR}"
#!/bin/bash

<<Comment
Description: Install script of Intel(R) Metro AI Suite Sensor Fusion project dependencies.
Aligns the host environment with the versions and package families used by the Dockerfile.
Comment

set -Eeuo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

log(){ echo "[install] $*"; }
warn(){ echo "[install][warn] $*" >&2; }
die(){ echo "[install][error] $*" >&2; exit 1; }
require_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

default_parallel_jobs(){
  if command -v nproc >/dev/null 2>&1; then
    nproc
  else
    echo 1
  fi
}

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
THIRD_PARTY_BUILD_DIR=${THIRD_PARTY_BUILD_DIR:-"$HOME/3rd_build"}
export PROJ_DIR=${PROJ_DIR:-"${REPO_ROOT}"}

DOWNLOAD_RETRIES=${DOWNLOAD_RETRIES:-3}
DOWNLOAD_TIMEOUT=${DOWNLOAD_TIMEOUT:-30}
DOWNLOAD_USER_AGENT=${DOWNLOAD_USER_AGENT:-metro-ai-suite-installer/1.0}

BOOST_VERSION=${BOOST_VERSION:-1.83.0}
BOOST_TARBALL=${BOOST_TARBALL:-boost_1_83_0.tar.gz}
BOOST_DIR=${BOOST_DIR:-boost_1_83_0}
BOOST_URL=${BOOST_URL:-https://phoenixnap.dl.sourceforge.net/project/boost/boost/${BOOST_VERSION}/${BOOST_TARBALL}}

ONEAPI_VERSION=${ONEAPI_VERSION:-2025.3}
OPENCL_SDK_GIT_REF=${OPENCL_SDK_GIT_REF:-v2025.07.23}
INSTALL_CUSTOM_OPENVINO_SCRIPT=${INSTALL_CUSTOM_OPENVINO_SCRIPT:-${SCRIPT_DIR}/install_custom_openvino.sh}
CUSTOM_OPENVINO_PATCH=${CUSTOM_OPENVINO_PATCH:-${SCRIPT_DIR}/custom_openvino_2026.1.0_sparse_ops.patch}
CUSTOM_OPENVINO_SOURCE_DIR=${CUSTOM_OPENVINO_SOURCE_DIR:-${THIRD_PARTY_BUILD_DIR}/openvino_bevfusion}
CUSTOM_OPENVINO_INSTALL_DIR=${CUSTOM_OPENVINO_INSTALL_DIR:-/opt/intel/openvino}
CUSTOM_OPENVINO_JOBS=${CUSTOM_OPENVINO_JOBS:-$(default_parallel_jobs)}

mkdir -p "${THIRD_PARTY_BUILD_DIR}"

_try_download(){
  local url="$1"
  local out="${2:-${url##*/}}"
  local tmp="${out}.part"

  log "Downloading: ${url}"

  if command -v curl >/dev/null 2>&1; then
    rm -f "${tmp}"
    if curl -fL --retry "${DOWNLOAD_RETRIES}" --retry-delay 1 --connect-timeout "${DOWNLOAD_TIMEOUT}" \
      -A "${DOWNLOAD_USER_AGENT}" -o "${tmp}" "${url}"; then
      mv -f "${tmp}" "${out}"
      return 0
    fi
    rm -f "${tmp}"
  fi

  if command -v wget >/dev/null 2>&1; then
    rm -f "${tmp}"
    if wget --tries="${DOWNLOAD_RETRIES}" --timeout="${DOWNLOAD_TIMEOUT}" --user-agent="${DOWNLOAD_USER_AGENT}" \
      -O "${tmp}" -q --show-progress "${url}"; then
      mv -f "${tmp}" "${out}"
      return 0
    fi
    rm -f "${tmp}"
  fi

  return 1
}

download(){
  local url="$1"
  local out="${2:-${url##*/}}"
  _try_download "${url}" "${out}" || die "Failed to download: ${url} -> ${out}"
}

git_clone_or_update(){
  local repo_url="$1"
  local target_dir="$2"
  local git_ref="$3"
  local clone_extra=()

  if [[ $# -gt 3 ]]; then
    clone_extra=("${@:4}")
  fi

  if [[ -d "${target_dir}/.git" ]]; then
    log "Updating existing repository ${target_dir} to ${git_ref}"
    git -C "${target_dir}" fetch --depth 1 origin "${git_ref}"
    git -C "${target_dir}" checkout --detach -q FETCH_HEAD
    git -C "${target_dir}" submodule update --init --recursive --depth 1
  else
    git clone --depth 1 -b "${git_ref}" "${clone_extra[@]}" "${repo_url}" "${target_dir}"
  fi
}

safe_rm_rf_under_home(){
  local target="$1"
  if [[ -z "${target}" ]]; then
    die "safe_rm_rf_under_home: empty target"
  fi

  if [[ "${FORCE_RM_NOT_HOME:-0}" == "1" ]]; then
    sudo rm -rf "${target}"
    return 0
  fi

  if [[ "${target}" == "${HOME}/"* ]]; then
    sudo rm -rf "${target}"
  else
    log "Skip deleting path not under HOME: ${target}"
  fi
}

check_network(){
  PRC_NETWORK=false
  set +e
  local nw_loc
  nw_loc=$(curl -s --max-time 10 ipinfo.io/country 2>/dev/null)
  if [[ "${nw_loc}" == "CN" ]]; then
    PRC_NETWORK=true
  fi
  set -e
}

_install_base_libs(){
  require_cmd sudo
  sudo -v
  sudo -E apt-get update -y
  sudo -E apt-get install -y --no-install-recommends \
    autoconf automake libtool build-essential g++ \
    bison pkg-config flex curl git git-lfs vim dkms cmake make wget \
    debhelper devscripts mawk openssh-server \
    ca-certificates gpg lsb-release \
    libssl-dev libopencv-dev opencv-data \
    libeigen3-dev libuv1-dev libfmt-dev libdrm-dev \
    libtbb12 ocl-icd-libopencl1 \
    opencl-headers opencl-dev intel-gpu-tools va-driver-all \
    libmfx1 libmfxgen1 libvpl2 \
    libx11-dev libx11-xcb-dev libxcb-dri3-dev libxext-dev libxfixes-dev libwayland-dev \
    libgtk2.0-0 libgl1 libsm6 libxext6 x11-apps
}

_install_boost(){
  if [[ "${SKIP_BOOST:-0}" == "1" ]]; then
    log "SKIP_BOOST=1 set, skipping Boost build."
    return 0
  fi

  if [[ "${USE_SYSTEM_BOOST:-0}" == "1" ]]; then
    log "USE_SYSTEM_BOOST=1 set, installing libboost-all-dev from apt."
    sudo -E apt-get install -y libboost-all-dev
    return 0
  fi

  pushd "${THIRD_PARTY_BUILD_DIR}" >/dev/null
  if [[ ! -f "${BOOST_TARBALL}" ]]; then
    download "${BOOST_URL}" "${BOOST_TARBALL}"
  fi
  if [[ ! -d "${BOOST_DIR}" ]]; then
    tar -zxf "${BOOST_TARBALL}"
  fi
  cd "${BOOST_DIR}"
  ./bootstrap.sh --with-libraries=all --with-toolset=gcc
  ./b2 toolset=gcc -j"$(nproc)"
  sudo ./b2 install
  sudo ldconfig
  popd >/dev/null
}

_install_oneapi(){
  if [[ "${SKIP_ONEAPI:-0}" == "1" ]]; then
    log "SKIP_ONEAPI=1 set, skipping oneAPI install."
    return 0
  fi

  pushd "${THIRD_PARTY_BUILD_DIR}" >/dev/null
  local keyring=/usr/share/keyrings/intel-oneapi.gpg

  sudo -E apt-get install -y ca-certificates curl gpg lsb-release

  if [[ ! -f "${keyring}" ]]; then
    download https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
    sudo gpg --dearmor -o "${keyring}" GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
    rm -f GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
  fi

  echo "deb [signed-by=${keyring}] https://apt.repos.intel.com/oneapi all main" | \
    sudo tee /etc/apt/sources.list.d/oneAPI.list >/dev/null

  sudo -E apt-get update -y
  sudo -E apt-get install -y "intel-oneapi-base-toolkit-${ONEAPI_VERSION}" lsb-release
  popd >/dev/null
}

_install_custom_openvino(){
  if [[ "${SKIP_OPENVINO:-0}" == "1" || "${SKIP_CUSTOM_OPENVINO:-0}" == "1" ]]; then
    log "Skipping custom OpenVINO install."
    return 0
  fi

  [[ -f "${INSTALL_CUSTOM_OPENVINO_SCRIPT}" ]] || die "Custom OpenVINO installer not found: ${INSTALL_CUSTOM_OPENVINO_SCRIPT}"
  [[ -f "${CUSTOM_OPENVINO_PATCH}" ]] || die "Custom OpenVINO patch not found: ${CUSTOM_OPENVINO_PATCH}"

  bash "${INSTALL_CUSTOM_OPENVINO_SCRIPT}" \
    --ov-dir "${CUSTOM_OPENVINO_SOURCE_DIR}" \
    --install-dir "${CUSTOM_OPENVINO_INSTALL_DIR}" \
    --patch "${CUSTOM_OPENVINO_PATCH}" \
    --jobs "${CUSTOM_OPENVINO_JOBS}" \
    --oneapi-version "${ONEAPI_VERSION}" \
    --skip-oneapi-install
}

_install_opencl_sdk(){
  if [[ "${SKIP_OPENCL_SDK:-0}" == "1" ]]; then
    log "SKIP_OPENCL_SDK=1 set, skipping OpenCL-SDK build."
    return 0
  fi

  pushd "${THIRD_PARTY_BUILD_DIR}" >/dev/null
  sudo -E apt-get install -y --no-install-recommends vulkan-tools libvulkan-dev

  git_clone_or_update https://github.com/KhronosGroup/OpenCL-SDK.git OpenCL-SDK "${OPENCL_SDK_GIT_REF}" --recursive
  cd OpenCL-SDK
  mkdir -p build
  cd build
  cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
  sudo cmake --build . --target install --config Release -j"$(nproc)"
  popd >/dev/null
}

install_3rd_libs(){
  require_cmd bash
  require_cmd sudo
  require_cmd dpkg

  if [[ "${CLEAN_BUILD_DIR:-1}" == "1" ]]; then
    safe_rm_rf_under_home "${THIRD_PARTY_BUILD_DIR}"
  fi
  mkdir -p "${THIRD_PARTY_BUILD_DIR}"

  _install_base_libs

  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    die "Neither curl nor wget is available after installing base packages"
  fi
  require_cmd git
  require_cmd cmake
  require_cmd nproc

  check_network
  _install_boost
  _install_oneapi
  if [[ "${SKIP_OPENVINO:-0}" == "1" || "${SKIP_CUSTOM_OPENVINO:-0}" == "1" ]]; then
    _install_opencl_sdk
  fi
  _install_custom_openvino

  log "Done. You may need to run 'newgrp render' or re-login to refresh supplementary groups."
  log "For build/runtime env, source:"
  log "  source /opt/intel/oneapi/setvars.sh"
  log "  source ${CUSTOM_OPENVINO_INSTALL_DIR}/setupvars.sh"
}

install_3rd_libs


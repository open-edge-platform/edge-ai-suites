#!/bin/bash

<<Comment
Description: Install script of Intel(R) Metro AI Suite Sensor Fusion driver dependencies.
Aligns host GPU, NPU and xpu-smi packages with the Dockerfile versions.
Comment

set -Eeuo pipefail

if [[ "${TRACE:-0}" == "1" ]]; then
  set -x
fi

log(){ echo "[install] $*"; }
warn(){ echo "[install][warn] $*" >&2; }
die(){ echo "[install][error] $*" >&2; exit 1; }
require_cmd(){ command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"; }

DOWNLOAD_RETRIES=${DOWNLOAD_RETRIES:-3}
DOWNLOAD_TIMEOUT=${DOWNLOAD_TIMEOUT:-30}
DOWNLOAD_USER_AGENT=${DOWNLOAD_USER_AGENT:-metro-ai-suite-installer/1.0}

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd -- "${SCRIPT_DIR}/.." && pwd)
THIRD_PARTY_BUILD_DIR=${THIRD_PARTY_BUILD_DIR:-"$HOME/3rd_build"}
export PROJ_DIR=${PROJ_DIR:-"${REPO_ROOT}"}

NEO_VERSION=${NEO_VERSION:-26.14.37833.4}
NEO_PACKAGE_REVISION=${NEO_PACKAGE_REVISION:-0}
NEO_IGC_VERSION=${NEO_IGC_VERSION:-2.32.7}
NEO_IGC_BUILD=${NEO_IGC_BUILD:-21184}
NEO_GMM_VERSION=${NEO_GMM_VERSION:-22.9.0}
NEO_SUM_URL=${NEO_SUM_URL:-https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/ww14.sum}
NEO_RELEASE_BASE_URL=${NEO_RELEASE_BASE_URL:-https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}}
IGC_RELEASE_BASE_URL=${IGC_RELEASE_BASE_URL:-https://github.com/intel/intel-graphics-compiler/releases/download/v${NEO_IGC_VERSION}}

LEVEL_ZERO_VERSION=${LEVEL_ZERO_VERSION:-1.28.2}
LEVEL_ZERO_DEB=${LEVEL_ZERO_DEB:-level-zero_${LEVEL_ZERO_VERSION}+u24.04_amd64.deb}
LEVEL_ZERO_PKG_VERSION=${LEVEL_ZERO_PKG_VERSION:-${LEVEL_ZERO_VERSION}+u24.04}
LEVEL_ZERO_DEB_URL=${LEVEL_ZERO_DEB_URL:-https://github.com/oneapi-src/level-zero/releases/download/v${LEVEL_ZERO_VERSION}/${LEVEL_ZERO_DEB}}

XPU_SMI_URL=${XPU_SMI_URL:-https://github.com/intel/xpumanager/releases/download/v1.3.6/xpu-smi_1.3.6_20260206.143628.1004f6cb.u24.04_amd64.deb}
NPU_DRIVER_URL=${NPU_DRIVER_URL:-https://github.com/intel/linux-npu-driver/releases/download/v1.32.1/linux-npu-driver-v1.32.1.20260422-24767473183-ubuntu2404.tar.gz}

INTEL_GPU_APT_KEY_URL=${INTEL_GPU_APT_KEY_URL:-https://repositories.intel.com/gpu/intel-graphics.key}
INTEL_GPU_APT_KEYRING=${INTEL_GPU_APT_KEYRING:-/usr/share/keyrings/intel-graphics.gpg}
INTEL_GPU_APT_LIST=${INTEL_GPU_APT_LIST:-/etc/apt/sources.list.d/intel-gpu-noble.list}
INTEL_GPU_APT_ENTRY=${INTEL_GPU_APT_ENTRY:-deb [arch=amd64 signed-by=${INTEL_GPU_APT_KEYRING}] https://repositories.intel.com/gpu/ubuntu noble unified}

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

download_optional(){
  local url="$1"
  local out="${2:-${url##*/}}"
  if ! _try_download "${url}" "${out}"; then
    warn "Optional download failed: ${url}"
    return 1
  fi
  return 0
}

pkg_version_installed(){
  dpkg-query -W -f='${Version}' "$1" 2>/dev/null || true
}

version_ge(){
  dpkg --compare-versions "$1" ge "$2"
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
    automake libtool build-essential bison pkg-config flex \
    curl git git-lfs vim dkms cmake make wget \
    ca-certificates gpg lsb-release software-properties-common \
    pciutils clinfo hwinfo vainfo
}

_upgrade_kernel(){
  if [[ "${SKIP_KERNEL_UPGRADE:-0}" == "1" ]]; then
    log "SKIP_KERNEL_UPGRADE=1 set, skipping kernel upgrade."
    return 0
  fi

  mkdir -p "${THIRD_PARTY_BUILD_DIR}/6.17.0_kernel"
  pushd "${THIRD_PARTY_BUILD_DIR}/6.17.0_kernel" >/dev/null
  local cur_kernel
  local cur_kernel_ver
  cur_kernel=$(uname -r)
  cur_kernel_ver=$(echo "${cur_kernel}" | sed -E 's/^([0-9]+\.[0-9]+\.[0-9]+).*/\1/')

  if dpkg --compare-versions "${cur_kernel_ver}" ge "6.17.0"; then
    log "Current kernel (${cur_kernel}) is >= 6.17.0, skipping kernel upgrade."
    popd >/dev/null
    return 0
  fi

  if [[ "${cur_kernel}" != *"6.17.0-061700-generic"* ]]; then
    sudo -E apt-get update -y
    download https://kernel.ubuntu.com/mainline/v6.17/amd64/linux-headers-6.17.0-061700_6.17.0-061700.202509282239_all.deb
    download https://kernel.ubuntu.com/mainline/v6.17/amd64/linux-headers-6.17.0-061700-generic_6.17.0-061700.202509282239_amd64.deb
    download https://kernel.ubuntu.com/mainline/v6.17/amd64/linux-image-unsigned-6.17.0-061700-generic_6.17.0-061700.202509282239_amd64.deb
    download https://kernel.ubuntu.com/mainline/v6.17/amd64/linux-modules-6.17.0-061700-generic_6.17.0-061700.202509282239_amd64.deb

    sudo dpkg -i ./*.deb || sudo -E apt-get -f install -y

    local grub_default_value="Advanced options for Ubuntu>Ubuntu, with Linux 6.17.0-061700-generic"
    if sudo grep -q '^GRUB_DEFAULT=' /etc/default/grub; then
      sudo sed -i "s#^GRUB_DEFAULT=.*#GRUB_DEFAULT=\"${grub_default_value}\"#" /etc/default/grub
    else
      echo "GRUB_DEFAULT=\"${grub_default_value}\"" | sudo tee -a /etc/default/grub >/dev/null
    fi

    sudo update-grub

    if [[ "${SKIP_REBOOT:-0}" == "1" ]]; then
      log "Kernel packages installed. SKIP_REBOOT=1 set; please reboot manually then re-run the script."
      popd >/dev/null
      return 0
    fi

    log "The system will reboot shortly, please re-run the script after reboot..."
    sleep 1
    sudo reboot
  fi

  popd >/dev/null
}

_configure_intel_gpu_repo(){
  local key_tmp="${THIRD_PARTY_BUILD_DIR}/intel-graphics.key"

  if [[ ! -f "${INTEL_GPU_APT_KEYRING}" || "${FORCE_UPDATE_INTEL_GPU_REPO_KEY:-0}" == "1" ]]; then
    download "${INTEL_GPU_APT_KEY_URL}" "${key_tmp}"
    sudo mkdir -p "$(dirname -- "${INTEL_GPU_APT_KEYRING}")"
    sudo gpg --dearmor -o "${INTEL_GPU_APT_KEYRING}" "${key_tmp}"
    rm -f "${key_tmp}"
  fi

  echo "${INTEL_GPU_APT_ENTRY}" | sudo tee "${INTEL_GPU_APT_LIST}" >/dev/null
  sudo -E apt-get update -y
}

_install_gpu_driver(){
  _configure_intel_gpu_repo

  sudo -E apt-get install -y --no-install-recommends \
    intel-media-va-driver-non-free intel-gsc intel-gpu-tools \
    ocl-icd-libopencl1 clinfo hwinfo vainfo \
    libtbb12 libmfx1 libmfxgen1 libvpl2 libva-glx2 va-driver-all

  sudo gpasswd -a "${USER}" render || true

  local target_pkg_ver="${NEO_VERSION}-${NEO_PACKAGE_REVISION}"
  local installed_opencl_ver installed_ocloc_ver installed_ze_ver installed_loader_ver
  installed_opencl_ver=$(pkg_version_installed intel-opencl-icd)
  installed_ocloc_ver=$(pkg_version_installed intel-ocloc)
  installed_ze_ver=$(pkg_version_installed libze-intel-gpu1)
  installed_loader_ver=$(pkg_version_installed libze1)

  if [[ "${FORCE_MANUAL_NEO_INSTALL:-0}" != "1" ]] && \
     [[ -n "${installed_opencl_ver}" && -n "${installed_ocloc_ver}" && -n "${installed_ze_ver}" && -n "${installed_loader_ver}" ]] && \
     version_ge "${installed_opencl_ver}" "${target_pkg_ver}" && \
     version_ge "${installed_ocloc_ver}" "${target_pkg_ver}" && \
     version_ge "${installed_ze_ver}" "${target_pkg_ver}" && \
     version_ge "${installed_loader_ver}" "${LEVEL_ZERO_PKG_VERSION}"; then
    log "Pinned GPU runtime is already installed; skipping manual compute runtime packages."
    return 0
  fi

  pushd "${THIRD_PARTY_BUILD_DIR}" >/dev/null
  mkdir -p neo
  cd neo

  local sum_file="${NEO_SUM_URL##*/}"
  local igc_pkg_ver="${NEO_IGC_VERSION}+${NEO_IGC_BUILD}"
  local artifacts=(
    "${LEVEL_ZERO_DEB}"
    "intel-igc-core-2_${igc_pkg_ver}_amd64.deb"
    "intel-igc-opencl-2_${igc_pkg_ver}_amd64.deb"
    "intel-ocloc-dbgsym_${target_pkg_ver}_amd64.ddeb"
    "intel-ocloc_${target_pkg_ver}_amd64.deb"
    "intel-opencl-icd-dbgsym_${target_pkg_ver}_amd64.ddeb"
    "intel-opencl-icd_${target_pkg_ver}_amd64.deb"
    "libigdgmm12_${NEO_GMM_VERSION}_amd64.deb"
    "libze-intel-gpu1-dbgsym_${target_pkg_ver}_amd64.ddeb"
    "libze-intel-gpu1_${target_pkg_ver}_amd64.deb"
  )
  local artifact

  rm -f ./*.deb ./*.ddeb ./*.sum
  download "${NEO_SUM_URL}" "${sum_file}"

  for artifact in "${artifacts[@]}"; do
    case "${artifact}" in
      ${LEVEL_ZERO_DEB})
        download "${LEVEL_ZERO_DEB_URL}" "${artifact}"
        ;;
      intel-igc-*)
        download "${IGC_RELEASE_BASE_URL}/${artifact}" "${artifact}"
        ;;
      *)
        download "${NEO_RELEASE_BASE_URL}/${artifact}" "${artifact}"
        ;;
    esac
  done

  if [[ "${SKIP_NEO_CHECKSUM:-0}" != "1" ]]; then
    local filtered_sum="selected-${sum_file}"
    : > "${filtered_sum}"
    for artifact in "${artifacts[@]}"; do
      if ! grep -F " ${artifact}" "${sum_file}" >> "${filtered_sum}"; then
        warn "Checksum entry not found for ${artifact}; continuing without it."
      fi
    done
    if [[ -s "${filtered_sum}" ]]; then
      sha256sum -c "${filtered_sum}"
    else
      warn "No matching checksum entries were found in ${sum_file}; skipping checksum verification."
    fi
  else
    warn "SKIP_NEO_CHECKSUM=1 set; skipping checksum verification for downloaded GPU packages."
  fi

  sudo dpkg -i "${artifacts[@]}" || sudo -E apt-get -f install -y
  sudo ldconfig
  popd >/dev/null
}

_install_npu_driver(){
  if [[ "${SKIP_NPU_DRIVER:-0}" == "1" ]]; then
    log "SKIP_NPU_DRIVER=1 set, skipping NPU driver install."
    return 0
  fi

  mkdir -p "${THIRD_PARTY_BUILD_DIR}/npu_drivers"
  pushd "${THIRD_PARTY_BUILD_DIR}/npu_drivers" >/dev/null

  if dpkg -l | grep -q "^ii  intel-driver-compiler-npu " && \
     dpkg -l | grep -q "^ii  intel-fw-npu " && \
     dpkg -l | grep -q "^ii  intel-level-zero-npu "; then
    log "NPU driver already installed."
    popd >/dev/null
    return 0
  fi

  local npu_archive="${NPU_DRIVER_URL##*/}"
  if ! download_optional "${NPU_DRIVER_URL}" "${npu_archive}"; then
    warn "Skipping NPU driver installation because the driver archive is unavailable. Override NPU_DRIVER_URL or set SKIP_NPU_DRIVER=1."
    popd >/dev/null
    return 0
  fi

  rm -rf linux-npu-driver-*
  tar -xf "${npu_archive}"

  local npu_dir
  npu_dir=$(find . -maxdepth 1 -mindepth 1 -type d -name 'linux-npu-driver-*' | head -n 1)
  [[ -n "${npu_dir}" ]] || die "Failed to extract NPU driver archive ${npu_archive}"

  cd "${npu_dir}"
  sudo -E apt-get install -y libtbb12
  sudo -E apt-get install -y ./intel-*.deb || sudo -E apt-get -f install -y

  log "NPU driver installed. A reboot is recommended before running NPU workloads."
  popd >/dev/null
}

_install_xpu_smi(){
  if [[ "${SKIP_XPU_SMI:-0}" == "1" ]]; then
    log "SKIP_XPU_SMI=1 set, skipping xpu-smi install."
    return 0
  fi

  pushd "${THIRD_PARTY_BUILD_DIR}" >/dev/null
  rm -f xpu-smi_*.deb
  local xpu_smi_deb="${XPU_SMI_URL##*/}"
  if ! download_optional "${XPU_SMI_URL}" "${xpu_smi_deb}"; then
    warn "xpu-smi download failed; skipping xpu-smi install. Override XPU_SMI_URL or set SKIP_XPU_SMI=1."
    popd >/dev/null
    return 0
  fi

  sudo dpkg -i "${xpu_smi_deb}" || sudo -E apt-get -f install -y
  popd >/dev/null
}

install_3rd_libs(){
  require_cmd sudo
  require_cmd dpkg

  mkdir -p "${THIRD_PARTY_BUILD_DIR}"
  _install_base_libs

  if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
    die "Neither curl nor wget is available after installing base packages"
  fi
  require_cmd sha256sum
  require_cmd sed
  require_cmd lspci

  check_network
  _upgrade_kernel
  _install_gpu_driver
  _install_xpu_smi

  if lspci | grep -iq "npu\|neural\|ai"; then
    log "NPU detected, installing NPU driver..."
    _install_npu_driver
  else
    log "No NPU detected, skipping NPU driver installation."
  fi

  if [[ "${KEEP_BUILD_DIR:-0}" == "1" ]]; then
    log "KEEP_BUILD_DIR=1 set; keeping ${THIRD_PARTY_BUILD_DIR}"
  else
    safe_rm_rf_under_home "${THIRD_PARTY_BUILD_DIR}"
  fi

  log "All driver libs installed successfully."
}

install_3rd_libs


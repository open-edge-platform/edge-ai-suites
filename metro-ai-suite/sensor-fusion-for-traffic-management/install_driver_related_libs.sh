#!/bin/bash

<<Comment
Description: Install script of Intel® Metro AI Suite Sensor Fusion for Traffic Management.
Will download and install all driver libs. 
Comment

set -x
set -e

#Set Proxy for help component src download. 
#_PROXY=
#export http_proxy=http://${_PROXY}
#export https_proxy=http://${_PROXY}

THIRD_PARTY_BUILD_DIR=~/3rd_build
export PROJ_DIR=$PWD 

mkdir -p ${THIRD_PARTY_BUILD_DIR}

PRC_NETWORK=false

check_network()
{
  set +e
  nw_loc=$(curl -s --max-time 10 ipinfo.io/country)
  if [ "${nw_loc}" = "CN" ]; then
    PRC_NETWORK=true
  else
    PRC_NETWORK=false
  fi
  set -e
}

#[1] base libs
_install_base_libs()
{  
  sudo -E apt update -y
  sudo -E apt install -y automake libtool build-essential bison pkg-config flex curl git git-lfs vim dkms cmake make wget
}

_upgrade_kernel()
{
  mkdir -p ${THIRD_PARTY_BUILD_DIR}/6.16.0_kernel
  pushd ${THIRD_PARTY_BUILD_DIR}/6.16.0_kernel
  cur_kernel=$(uname -r)
  # Extract numeric version prefix from uname (e.g. 6.8.0-xx -> 6.8.0)
  cur_kernel_ver=$(echo "${cur_kernel}" | sed -E 's/^([0-9]+\.[0-9]+\.[0-9]+).*/\1/')

  # If current kernel is already >= 6.16.0, skip upgrading.
  if dpkg --compare-versions "${cur_kernel_ver}" ge "6.16.0"; then
    echo "Current kernel (${cur_kernel}) is >= 6.16.0, skipping kernel upgrade."
    popd
    return 0
  fi

  if [[ "$cur_kernel" != *"6.16.0-061600-generic"* ]]; then
    sudo -E apt update
    wget https://kernel.ubuntu.com/mainline/v6.16/amd64/linux-headers-6.16.0-061600_6.16.0-061600.202507272138_all.deb
    wget https://kernel.ubuntu.com/mainline/v6.16/amd64/linux-headers-6.16.0-061600-generic_6.16.0-061600.202507272138_amd64.deb
    wget https://kernel.ubuntu.com/mainline/v6.16/amd64/linux-image-unsigned-6.16.0-061600-generic_6.16.0-061600.202507272138_amd64.deb
    wget https://kernel.ubuntu.com/mainline/v6.16/amd64/linux-modules-6.16.0-061600-generic_6.16.0-061600.202507272138_amd64.deb

    sudo dpkg -i *.deb

    grub_default_value="Advanced options for Ubuntu>Ubuntu, with Linux 6.16.0-061600-generic"
    if sudo grep -q '^GRUB_DEFAULT=' /etc/default/grub; then
      sudo sed -i "s#^GRUB_DEFAULT=.*#GRUB_DEFAULT=\"${grub_default_value}\"#" /etc/default/grub
    else
      echo "GRUB_DEFAULT=\"${grub_default_value}\"" | sudo tee -a /etc/default/grub > /dev/null
    fi

    sudo update-grub

    echo "The system will reboot shortly, please re-run the script after reboot..."
    sleep 1
    sudo reboot
  fi

  popd
}

_install_gpu_driver()
{
  set +e
  sudo -E apt-get update

  sudo -E apt install -y software-properties-common
  # Add the intel-graphics PPA
  sudo -E add-apt-repository -y ppa:kobuk-team/intel-graphics
  # Install the compute-related packages
  sudo -E apt install -y libze-intel-gpu1 libze1 intel-ocloc intel-opencl-icd clinfo intel-gsc hwinfo
  # Install the media-related packages
  sudo -E apt install -y intel-media-va-driver-non-free libmfx1 libmfx-gen1 libvpl2 libvpl-tools libva-glx2 va-driver-all vainfo

  sudo gpasswd -a ${USER} render

  sudo -E apt install -y ocl-icd-libopencl1 libigdgmm12
  pushd ${THIRD_PARTY_BUILD_DIR}
  neo_download_url=https://github.com
  mkdir -p neo && cd neo
  rm -f ww35.sum && wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/ww35.sum
  sha256sum -c ww35.sum
  if [ $? -ne 0 ] ; then
      rm -rf *.deb *.ddeb
      wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/v2.18.5/intel-igc-core-2_2.18.5+19820_amd64.deb
      wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/v2.18.5/intel-igc-opencl-2_2.18.5+19820_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/intel-ocloc-dbgsym_25.35.35096.9-0_amd64.ddeb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/intel-ocloc_25.35.35096.9-0_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/intel-opencl-icd-dbgsym_25.35.35096.9-0_amd64.ddeb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/intel-opencl-icd_25.35.35096.9-0_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/libigdgmm12_22.8.1_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/libze-intel-gpu1-dbgsym_25.35.35096.9-0_amd64.ddeb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/25.35.35096.9/libze-intel-gpu1_25.35.35096.9-0_amd64.deb

      sha256sum -c ww35.sum
  fi
  set -e
  # Install all packages as root
  rm -rf libigdgmm12_22.8.1_amd64.deb
  sudo dpkg -i *deb

  popd
}

_install_npu_driver()
{
  echo "install npu driver"
  # sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu
  mkdir -p ${THIRD_PARTY_BUILD_DIR}/npu_drivers
  pushd ${THIRD_PARTY_BUILD_DIR}/npu_drivers
  if dpkg -l | grep -q "^ii  intel-driver-compiler-npu " && \
      dpkg -l | grep -q "^ii  intel-fw-npu " && \
      dpkg -l | grep -q "^ii  intel-level-zero-npu "; then
      echo "NPU driver already installed."
  else
      wget https://github.com/intel/linux-npu-driver/releases/download/v1.22.0/linux-npu-driver-v1.22.0.20250813-16938856004-ubuntu2404.tar.gz
      tar -xf linux-npu-driver-v1.22.0.20250813-16938856004-ubuntu2404.tar.gz

      sudo -E apt install -y libtbb12 && sudo dpkg -i *.deb

      wget https://github.com/oneapi-src/level-zero/releases/download/v1.22.4/level-zero_1.22.4+u24.04_amd64.deb
      sudo dpkg -i level-zero*.deb

      read -n 1 -s -r -p "Press any key to reboot..."
      sudo reboot
  fi
  popd
}

_install_xpu_smi()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  wget https://github.com/intel/xpumanager/releases/download/v1.3.3/xpu-smi_1.3.3_20250926.101214.8a6b6526.u24.04_amd64.deb

  # Install all packages as root
  sudo dpkg -i xpu-smi_*.deb

  popd
}

install_3rd_libs(){
  mkdir -p ${THIRD_PARTY_BUILD_DIR}
  _install_base_libs
  check_network #in case that some components download may failed in PRC network, we provide a proxy to help, comment this line if no needed.
  _upgrade_kernel
  _install_gpu_driver
  _install_xpu_smi
  if lspci | grep -iq "npu\|neural\|ai"; then
    echo "NPU detected, installing NPU driver..."
    _install_npu_driver
  else
    echo "No NPU detected, skipping NPU driver installation."
  fi
  sudo rm -rf ${THIRD_PARTY_BUILD_DIR}

  echo "All driver libs installed successfully."
}

install_3rd_libs


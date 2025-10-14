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
  mkdir -p ${THIRD_PARTY_BUILD_DIR}/6.8.0-51_kernel
  pushd ${THIRD_PARTY_BUILD_DIR}/6.8.0-51_kernel
  cur_kernel=$(uname -r)
  if [[ "$cur_kernel" != *"6.8.0-51-generic"* ]]; then
    sudo -E apt update
    sudo -E apt install -y linux-image-6.8.0-51-generic
    sudo -E apt install -y linux-headers-6.8.0-51-generic
    sudo -E apt install -y linux-modules-6.8.0-51-generic
    sudo -E apt install -y linux-modules-extra-6.8.0-51-generic

    sudo sed -i 's#^GRUB_DEFAULT=0$#GRUB_DEFAULT="Advanced options for Ubuntu>Ubuntu, with Linux 6.8.0-51-generic"#' /etc/default/grub

    sudo update-grub

    echo "The system will reboot shortly, please re-run the script after reboot..."
    sleep 1
    sudo reboot
  fi

  popd
}

_install_arc770_gpu_driver()
{
  # Install the Intel graphics GPG public key
  wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
    sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg

  # Configure the repositories.intel.com package repository
  echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | \
    sudo tee /etc/apt/sources.list.d/intel-gpu-jammy.list

  # Update the package repository metadata
  sudo -E apt update


  # Install the compute-related packages
  sudo -E apt install -y intel-opencl-icd=23.22.26516.25-682~22.04 \
    debhelper devscripts mawk openssh-server opencl-headers opencl-dev intel-gpu-tools clinfo \
    intel-fw-gpu libtbb12 intel-level-zero-gpu libigc1 libigdfcl1 libigfxcmrt7 libmfx1
  
  sudo apt-mark hold intel-opencl-icd
}

_upgrade_i915_driver()
{
  pushd ${THIRD_PARTY_BUILD_DIR}

  git clone https://github.com/intel-gpu/intel-gpu-i915-backports.git
  cd intel-gpu-i915-backports/
  git checkout backport/RELEASE_2405_23.10
  make i915dkmsdeb-pkg
  sudo dpkg -i ../intel-i915-dkms_*_all.deb

  popd
}

_install_mtl_gpu_driver()
{
  set +e
  pushd ${THIRD_PARTY_BUILD_DIR}

  # Install the Intel graphics GPG public key
  wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
    sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg

  # Configure the repositories.intel.com package repository
  echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | \
    sudo tee /etc/apt/sources.list.d/intel-gpu-jammy.list

  # Update the package repository metadata
  sudo -E apt update


  # Install the compute-related packages
  sudo -E apt install -y debhelper devscripts mawk openssh-server opencl-headers opencl-dev intel-gpu-tools clinfo \
    intel-fw-gpu libtbb12 intel-level-zero-gpu libigc1 libigdfcl1 libigfxcmrt7 libmfx1
  
  # Install header files to allow compilation of new code
  sudo -E apt install -y ocl-icd-libopencl1

  neo_download_url=https://github.com
  # if $PRC_NETWORK; then
  #   neo_download_url=https://hub.mirror.com/github.com
  # fi
  mkdir -p neo && cd neo
  # 25.13.33276.16 version cause some unexpected iGPU issues, so we use 24.39.31294.12 version
  # rm -f ww13.sum && wget ${neo_download_url}/intel/compute-runtime/releases/download/25.13.33276.16/ww13.sum
  # sha256sum -c ww13.sum
  # if [ $? -ne 0 ] ; then
  #     rm -rf *.deb *.ddeb
  #     wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/v2.10.8/intel-igc-core-2_2.10.8+18926_amd64.deb
  #     wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/v2.10.8/intel-igc-opencl-2_2.10.8+18926_amd64.deb
  #     wget ${neo_download_url}/intel/compute-runtime/releases/download/25.13.33276.16/intel-level-zero-gpu-dbgsym_1.6.33276.16_amd64.ddeb
  #     wget ${neo_download_url}/intel/compute-runtime/releases/download/25.13.33276.16/intel-level-zero-gpu_1.6.33276.16_amd64.deb
  #     wget ${neo_download_url}/intel/compute-runtime/releases/download/25.13.33276.16/intel-opencl-icd-dbgsym_25.13.33276.16_amd64.ddeb
  #     wget ${neo_download_url}/intel/compute-runtime/releases/download/25.13.33276.16/intel-opencl-icd_25.13.33276.16_amd64.deb
  #     wget ${neo_download_url}/intel/compute-runtime/releases/download/25.13.33276.16/libigdgmm12_22.7.0_amd64.deb

  #     set -e
  #     sha256sum -c ww13.sum
  # fi

  # # Install all packages as root
  # sudo dpkg -i *deb

  sudo -E apt install libigdgmm12

  rm -f ww39.sum && wget ${neo_download_url}/intel/compute-runtime/releases/download/24.39.31294.12/ww39.sum
  sha256sum -c ww39.sum
  if [ $? -ne 0 ] ; then
      rm -rf *.deb *.ddeb
      wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/igc-1.0.17791.9/intel-igc-core_1.0.17791.9_amd64.deb
      wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/igc-1.0.17791.9/intel-igc-opencl_1.0.17791.9_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/24.39.31294.12/intel-level-zero-gpu-dbgsym_1.6.31294.12_amd64.ddeb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/24.39.31294.12/intel-level-zero-gpu_1.6.31294.12_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/24.39.31294.12/intel-opencl-icd-dbgsym_24.39.31294.12_amd64.ddeb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/24.39.31294.12/intel-opencl-icd_24.39.31294.12_amd64.deb

      set -e
      sha256sum -c ww39.sum
  fi

  # Install all packages as root
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
      wget https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-driver-compiler-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb
      wget https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-fw-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb
      wget https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-level-zero-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb

      sudo -E apt install -y libtbb12 && sudo dpkg -i *.deb

      wget https://github.com/oneapi-src/level-zero/releases/download/v1.20.2/level-zero_1.20.2+u22.04_amd64.deb
      sudo dpkg -i level-zero*.deb

      read -n 1 -s -r -p "Press any key to reboot, after reboot please set the udev rules for permissions access of NPU ..."
      sudo reboot
  fi
  popd
}

_set_rule_after_npu()
{
  if [ -e "/dev/accel/accel0" ]; then
    ls -lah /dev/accel/accel0
  else
    sudo chown root:render /dev/accel/accel0
    sudo chmod g+rw /dev/accel/accel0
    sudo usermod -a -G render $USER

    sudo bash -c "echo 'SUBSYSTEM==\"accel\", KERNEL==\"accel*\", GROUP=\"render\", MODE=\"0660\"' > /etc/udev/rules.d/10-intel-vpu.rules"
    sudo udevadm control --reload-rules
    sudo udevadm trigger --subsystem-match=accel

    ls -lah /dev/accel/accel0

    echo "The system will reboot shortly..."
    sleep 1
    sudo reboot
  fi
}

install_3rd_libs(){
  mkdir -p ${THIRD_PARTY_BUILD_DIR}
  _install_base_libs
  check_network #in case that some components download may failed in PRC network, we provide a proxy to help, comment this line if no needed.
  _upgrade_kernel
  
  if lscpu | grep "Model name" | grep -q i7-13700; then
    echo "Install i7-13700 driver"
    _install_arc770_gpu_driver
    _upgrade_i915_driver
  fi
  if lscpu | grep "Model name" | grep -q Ultra; then
    echo "Install Ultra driver"
    _install_mtl_gpu_driver
    _install_npu_driver
    _set_rule_after_npu
  fi
  if lscpu | grep "Model name" | grep -q 7305E; then
    echo "Install 7305E driver"
    _install_mtl_gpu_driver
  fi
  sudo rm -rf ${THIRD_PARTY_BUILD_DIR}

  echo "All driver libs installed successfully."
}

install_3rd_libs


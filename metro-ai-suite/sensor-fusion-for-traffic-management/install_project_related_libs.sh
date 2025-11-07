#!/bin/bash

<<Comment
Description: Install script of Intel® Metro AI Suite Sensor Fusion for Traffic Management.
Will download and install all 3rd parties libs and then build the project. 
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
  sudo -E apt-get update -y
  sudo -E apt install -y --only-upgrade systemd
  sudo -E apt install -y libssl-dev libuv1-dev libeigen3-dev git-lfs libfmt-dev zlib1g-dev libicu-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev intel-gpu-tools libopencv-dev libeigen3-dev
  sudo -E apt install -y intel-media-va-driver-non-free va-driver-all libmfx1 libvpl2
}

#[2] boost
_install_boost()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  curl -k -o boost_1_83_0.tar.gz https://phoenixnap.dl.sourceforge.net/project/boost/boost/1.83.0/boost_1_83_0.tar.gz -L
  tar -zxf boost_1_83_0.tar.gz && cd boost_1_83_0
  ./bootstrap.sh --with-libraries=all --with-toolset=gcc
  ./b2 toolset=gcc && sudo ./b2 install && sudo ldconfig
  popd
}

#[3] spdlog
_install_spdlog()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  curl -k -o v1.11.0.tar.gz https://github.com/gabime/spdlog/archive/refs/tags/v1.11.0.tar.gz -L
  tar -zxf v1.11.0.tar.gz && cd spdlog-1.11.0
  sudo rm -rf /usr/local/include/spdlog && sudo mv include/spdlog /usr/local/include
  popd
}

#[4] thrift
_install_thrift()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  curl -k -o thrift_v0.21.0.tar.gz https://github.com/apache/thrift/archive/refs/tags/v0.21.0.tar.gz -L
  tar -zxf thrift_v0.21.0.tar.gz && cd thrift-0.21.0
  ./bootstrap.sh && ./configure --with-qt4=no --with-qt5=no --with-python=no
  make -j8 && sudo make install
  popd
}

#[5] oneapi
_install_oneapi()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  curl -k -o GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -L
  sudo -E apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && sudo rm GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB

  echo "deb https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list

  sudo -E apt-get update -y
  sudo -E apt-get install -y intel-oneapi-base-toolkit lsb-release
  popd
}

#[6] openvino
_install_openvino()
{
  set +e
  pushd ${THIRD_PARTY_BUILD_DIR}

  if [ ! -f openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz ];then
      wget https://storage.openvinotoolkit.org/repositories/openvino/packages/2025.2/linux/openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz
  fi
  tar -xvf openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz
  sudo mkdir -p /opt/intel && sudo mv openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64 /opt/intel/openvino_2025
  sudo -E apt install -y libgdal-dev libpugixml-dev libopencv-dev
  sudo -E apt install -y opencl-headers ocl-icd-opencl-dev
  sudo usermod -a -G render $USER
  popd
  set -e
}


#[7] gRPC
_install_grpc()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  git config --global http.postBuffer 524288000
  # Sometimes below git command may failed in PRC network, try add: git config --global url."https://mirror.ghproxy.com/https://github.com".insteadOf "https://github.com"  
  git clone --recurse-submodules -b v1.58.1 --depth 1 --shallow-submodules https://github.com/grpc/grpc grpc-v1.58.1
  pushd grpc-v1.58.1/third_party && rm -rf zlib
  # git clone -b develop https://github.com/madler/zlib.git zlib
  git clone -b v1.3.1 https://github.com/madler/zlib.git zlib
  pushd zlib ## && git reset 73331a6a0481067628f065ffe87bb1d8f787d10c --hard 
  sed -i 's/PUBLIC ${CMAKE_CURRENT_BINARY_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}> $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>/g' CMakeLists.txt
  popd && popd
  pushd grpc-v1.58.1
  mkdir -p cmake/build
  cd cmake/build
  cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DCMAKE_INSTALL_PREFIX=/opt/grpc ../..
  make -j8
  sudo make install

  # git config --global http.postBuffer 524288000
  # git clone --recurse-submodules -b v1.72.0 --depth 1 --shallow-submodules https://github.com/grpc/grpc grpc-v1.72.0
  # cd grpc-v1.72.0 && mkdir -p cmake/build
  # cd cmake/build
  # cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/grpc ../..
  # make -j8 && \
  # sudo make install
  popd
}

#[8] level_zero
_install_level_zero()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  # git clone https://github.com/oneapi-src/level-zero.git
  # cd level-zero
  # git checkout v1.17.19
  # mkdir build && cd build
  # cmake .. -DCMAKE_INSTALL_PREFIX=/opt/intel/level-zero
  # sudo cmake --build . --config Release --target install

  git clone https://github.com/oneapi-src/level-zero.git
  cd level-zero
  git checkout v1.22.4
  mkdir build && cd build
  cmake .. -DCMAKE_INSTALL_PREFIX=/opt/intel/level-zero
  sudo cmake --build . --config Release --target install
  popd
}

#[9] onevpl
_install_onevpl()
{
  pushd ${THIRD_PARTY_BUILD_DIR}

  curl -k -o MediaStack.tar.gz https://github.com/intel/vpl-gpu-rt/releases/download/intel-onevpl-25.2.6/MediaStack.tar.gz -L

  tar -xvf MediaStack.tar.gz

  cd MediaStack

  sudo bash install_media.sh

  # sudo usermod -aG $(stat --format %G /dev/dri/renderD128) $(whoami)
  # sudo usermod -aG $(stat --format %G /dev/dri/card0) $(whoami)

  popd
}

#[10] opencl-sdk
_install_opencl_sdk()
{
  pushd ${THIRD_PARTY_BUILD_DIR}

  sudo -E apt install -y vulkan-tools libvulkan-dev vulkan-utility-libraries-dev

  git clone --recursive -b v2025.07.23 https://github.com/KhronosGroup/OpenCL-SDK.git
  cd OpenCL-SDK
  mkdir build
  cd build
  cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr
  sudo cmake --build . --target install --config Release

  popd
}

#[11] libradar
_install_libradar()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  
  # Add the Intel SED repository key
  sudo -E wget -O- https://eci.intel.com/sed-repos/gpg-keys/GPG-PUB-KEY-INTEL-SED.gpg | sudo tee /usr/share/keyrings/sed-archive-keyring.gpg > /dev/null

  # Add the repository to the sources list
  echo "deb [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | sudo tee /etc/apt/sources.list.d/sed.list
  echo "deb-src [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | sudo tee -a /etc/apt/sources.list.d/sed.list

  # Set package pinning preferences
  sudo bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/sed'

  # Update package list and install libradar
  sudo -E apt update
  sudo -E apt-get install libradar

  popd
}

install_3rd_libs(){
  sudo rm -rf ${THIRD_PARTY_BUILD_DIR} && mkdir -p ${THIRD_PARTY_BUILD_DIR}
  _install_base_libs
  check_network #in case that some components download may failed in PRC network, we provide a proxy to help, comment this line if no needed.
  _install_boost
  _install_spdlog
  _install_thrift
  _install_oneapi
  _install_openvino
  _install_grpc
  _install_level_zero
  _install_onevpl
  _install_opencl_sdk
  _install_libradar
}

install_3rd_libs


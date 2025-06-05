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
  sudo -E apt-get install -y libuv1-dev libeigen3-dev git-lfs libfmt-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev intel-gpu-tools libopencv-dev

}

#[2] cmake
_install_cmake()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  curl -k -o cmake-3.21.2.tar.gz https://github.com/Kitware/CMake/releases/download/v3.21.2/cmake-3.21.2.tar.gz -L
  tar -zxf cmake-3.21.2.tar.gz && cd cmake-3.21.2
  ./bootstrap --prefix=/usr && make -j8 && sudo make install
  popd
}

#[3] boost
_install_boost()
{
  sudo -E apt-get install -y libboost-dev libboost-filesystem-dev libboost-program-options-dev
}

#[4] spdlog
_install_spdlog()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  curl -k -o v1.8.2.tar.gz https://github.com/gabime/spdlog/archive/refs/tags/v1.8.2.tar.gz -L
  tar -zxf v1.8.2.tar.gz && cd spdlog-1.8.2
  sudo rm -rf /usr/local/include/spdlog && sudo mv include/spdlog /usr/local/include
  popd
}

#[5] thrift
_install_thrift()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  curl -k -o thrift_v0.18.1.tar.gz https://github.com/apache/thrift/archive/refs/tags/v0.18.1.tar.gz -L
  tar -zxf thrift_v0.18.1.tar.gz && cd thrift-0.18.1
  ./bootstrap.sh && ./configure --with-qt4=no --with-qt5=no --with-python=no
  make -j8 && sudo make install
  popd
}

#[6] openvino

_install_openvino()
{
  set +e
  pushd ${THIRD_PARTY_BUILD_DIR}
  if [ ! -f l_openvino_toolkit_ubuntu24_2024.5.0.17288.7975fa5da0c_x86_64.tgz ];then
      wget https://storage.openvinotoolkit.org/repositories/openvino/packages/2024.5/linux/l_openvino_toolkit_ubuntu24_2024.5.0.17288.7975fa5da0c_x86_64.tgz
  fi
  tar -xvf l_openvino_toolkit_ubuntu24_2024.5.0.17288.7975fa5da0c_x86_64.tgz
  sudo mkdir -p /opt/intel && sudo mv l_openvino_toolkit_ubuntu24_2024.5.0.17288.7975fa5da0c_x86_64 /opt/intel/openvino_2024
  sudo apt-get install -y libgdal-dev libpugixml-dev libopencv-dev
  sudo usermod -a -G render $USER
  popd
  set -e
}

#[] neo
_install_neo_0()
{
  set +e
  pushd ${THIRD_PARTY_BUILD_DIR}
  neo_download_url=https://github.com
  if $PRC_NETWORK; then
    neo_download_url=https://hub.mirror.com/github.com
  fi
  mkdir -p neo && cd neo
  rm -f ww22.sum && wget ${neo_download_url}/intel/compute-runtime/releases/download/23.22.26516.18/ww22.sum 
  sha256sum -c ww22.sum
  if [ $? -ne 0 ] ; then
      rm -rf *.deb *.ddeb
      wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/igc-1.0.14062.11/intel-igc-core_1.0.14062.11_amd64.deb
      wget ${neo_download_url}/intel/intel-graphics-compiler/releases/download/igc-1.0.14062.11/intel-igc-opencl_1.0.14062.11_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/23.22.26516.18/intel-level-zero-gpu-dbgsym_1.3.26516.18_amd64.ddeb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/23.22.26516.18/intel-level-zero-gpu_1.3.26516.18_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/23.22.26516.18/intel-opencl-icd-dbgsym_23.22.26516.18_amd64.ddeb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/23.22.26516.18/intel-opencl-icd_23.22.26516.18_amd64.deb
      wget ${neo_download_url}/intel/compute-runtime/releases/download/23.22.26516.18/libigdgmm12_22.3.0_amd64.deb
      set -e
      sha256sum -c ww22.sum
  fi

  # Install all packages as root
  sudo dpkg -i *deb

  # Install header files to allow compilation of new code
  sudo -E apt install -y opencl-headers
  popd
}

_install_neo()
{
  set +e
  pushd ${THIRD_PARTY_BUILD_DIR}
  neo_download_url=https://github.com
  # if $PRC_NETWORK; then
  #   neo_download_url=https://hub.mirror.com/github.com
  # fi
  mkdir -p neo && cd neo
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
      wget ${neo_download_url}/intel/compute-runtime/releases/download/24.39.31294.12/libigdgmm12_22.5.2_amd64.deb
      set -e
      sha256sum -c ww39.sum
  fi

  # Install all packages as root
  sudo dpkg -i *deb

  # Install header files to allow compilation of new code
  sudo -E apt install -y ocl-icd-libopencl1
  popd
}

#[7] oneapi-mkl
_install_mkl()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  # curl -k -o GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -L
  # sudo -E apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && sudo rm GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB

  # echo "deb https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list
  sudo -E apt-get update -y
  sudo -E apt-get install -y intel-oneapi-mkl-devel lsb-release
  popd
}

#[8] gRPC
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
  popd
}

#[9] oneAPI Level Zero
_install_level_zero0()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  if ! $PRC_NETWORK; then
    git clone https://github.com/oneapi-src/level-zero.git
    cd level-zero
    git checkout v1.16.15
  else
    curl -k -o level-zero.tar.gz https://hub.gitmirror.com/github.com/oneapi-src/level-zero/archive/refs/tags/v1.16.15.tar.gz -L
    tar zxvf level-zero.tar.gz && cd level-zero-1.16.15
  fi

  mkdir build && cd build
  cmake .. -DCMAKE_INSTALL_PREFIX=/opt/intel/level-zero
  sudo cmake --build . --config Release --target install
  popd
}

_install_level_zero()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  # if ! $PRC_NETWORK; then
  #   git clone https://github.com/oneapi-src/level-zero.git
  #   cd level-zero
  #   git checkout v1.17.19
  # else
  #   curl -k -o level-zero.tar.gz https://hub.gitmirror.com/github.com/oneapi-src/level-zero/archive/refs/tags/v1.17.19.tar.gz -L
  #   tar zxvf level-zero.tar.gz && cd level-zero-1.17.19
  # fi
  git clone https://github.com/oneapi-src/level-zero.git
  cd level-zero
  git checkout v1.17.19
  mkdir build && cd build
  cmake .. -DCMAKE_INSTALL_PREFIX=/opt/intel/level-zero
  sudo cmake --build . --config Release --target install
  popd
}

#[10] HDF5
_install_hdf5()
{
  pushd ${THIRD_PARTY_BUILD_DIR}
  if ! $PRC_NETWORK; then
    curl -k -o hdf5-1.14.3.tar.gz https://github.com/HDFGroup/hdf5/releases/download/hdf5-1_14_3/hdf5-1_14_3.tar.gz -L
  else
    curl -k -o hdf5-1.14.3.tar.gz https://hub.gitmirror.com/github.com/HDFGroup/hdf5/releases/download/hdf5-1_14_3/hdf5-1_14_3.tar.gz -L
  fi

  tar -xvf hdf5-1.14.3.tar.gz
  cd hdfsrc
  ./configure --prefix=/opt/hdf5
  make -j8
  sudo make install

  popd
}

_install_onevpl()
{
  pushd ${THIRD_PARTY_BUILD_DIR}

  MFX_HOME="/opt/intel/media"
  LIBVA_INSTALL_PATH="/opt/intel/media/lib64"
  LIBVA_DRIVERS_PATH="/opt/intel/media/lib64"
  LIBVA_DRIVER_NAME="iHD"
  LIBVA_INSTALL_PREFIX="/opt/intel/media"
  export LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LIBRARY_PATH}
  export C_INCLUDE_PATH=${LIBVA_INSTALL_PREFIX}/include:${C_INCLUDE_PATH}
  export CPLUS_INCLUDE_PATH=${LIBVA_INSTALL_PREFIX}/include:${CPLUS_INCLUDE_PATH}
  export PKG_CONFIG_PATH=${LIBVA_INSTALL_PATH}/pkgconfig:${PKG_CONFIG_PATH}

  sudo mkdir -p $MFX_HOME
  sudo mkdir -p $LIBVA_INSTALL_PATH
  sudo mkdir -p $LIBVA_DRIVERS_PATH

  sudo apt-get -y install libdrm-dev libegl1-mesa-dev libgl1-mesa-dev libx11-dev libx11-xcb-dev libxcb-dri3-dev libxext-dev libxfixes-dev libwayland-dev

  mkdir -p onevpl_dependencies
  pushd onevpl_dependencies

  curl -k -o libva-2.22.0.tar.gz https://github.com/intel/libva/archive/refs/tags/2.22.0.tar.gz -L
  tar -xvf libva-2.22.0.tar.gz
  pushd libva-2.22.0
  ./autogen.sh --prefix=${LIBVA_INSTALL_PREFIX} --libdir=${LIBVA_INSTALL_PATH} --enable-x11
  make -j8 && sudo make install
  popd
 
  curl -k -o libva-utils-2.22.0.tar.gz https://github.com/intel/libva-utils/archive/refs/tags/2.22.0.tar.gz -L
  tar -xvf libva-utils-2.22.0.tar.gz
  pushd libva-utils-2.22.0
  ./autogen.sh --prefix=${LIBVA_INSTALL_PREFIX} --libdir=${LIBVA_INSTALL_PATH}
  make -j8 && sudo make install
  popd

  curl -k -o gmmlib-22.5.3.tar.gz https://github.com/intel/gmmlib/archive/refs/tags/intel-gmmlib-22.5.3.tar.gz -L
  tar -xvf gmmlib-22.5.3.tar.gz
  pushd  gmmlib-intel-gmmlib-22.5.3
  mkdir -p build && pushd build
  cmake .. -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release
  make -j8 && sudo make install && popd
  popd

  curl -k -o intel-media-24.3.4.tar.gz https://github.com/intel/media-driver/archive/refs/tags/intel-media-24.3.4.tar.gz -L
  tar -xvf intel-media-24.3.4.tar.gz
  mkdir -p build_media && pushd build_media
  cmake ../media-driver-intel-media-24.3.4 -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DLIBVA_INSTALL_PATH=${LIBVA_INSTALL_PATH} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release -DENABLE_PRODUCTION_KMD=ON
  make -j8 && sudo make install
  env LD_LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LD_LIBRARY_PATH} LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LIBRARY_PATH}  && sudo make install
  sudo mv /opt/intel/media/lib64/dri/* /opt/intel/media/lib64/
  sudo rm -rf /opt/intel/media/lib64/dri
  popd

  curl -k -o intel-onevpl-24.3.4.tar.gz https://github.com/oneapi-src/oneVPL-intel-gpu/archive/refs/tags/intel-onevpl-24.3.4.tar.gz -L
  tar -xvf intel-onevpl-24.3.4.tar.gz
  pushd vpl-gpu-rt-intel-onevpl-24.3.4
  mkdir -p build && pushd build
  cmake .. -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release
  make -j8 && sudo make install && popd
  popd

  curl -k -o oneVPL_v2.13.0.tar.gz https://github.com/intel/libvpl/archive/refs/tags/v2.13.0.tar.gz -L
  tar -xvf oneVPL_v2.13.0.tar.gz
  pushd libvpl-2.13.0
  mkdir -p build && pushd build
  cmake .. -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release -DENABLE_X11=ON
  cmake --build . --config Release
  sudo cmake --build . --config Release --target install
  popd && popd

  popd
  popd
}

_install_gpu_driver()
{
  wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
  sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg
  echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu noble client" | \
  sudo tee /etc/apt/sources.list.d/intel-gpu-noble.list
  sudo apt update

  sudo apt install -y \
  intel-opencl-icd intel-level-zero-gpu \
  intel-media-va-driver-non-free libmfx1 libvpl2 \
  libegl-mesa0 libegl1-mesa-dev libgbm1 libgl1-mesa-dev libgl1-mesa-dri \
  libglapi-mesa libgles2-mesa-dev libglx-mesa0 libigdgmm12 libxatracker2 mesa-va-drivers \
  mesa-vdpau-drivers mesa-vulkan-drivers va-driver-all vainfo hwinfo clinfo


  sudo apt install -y \
  libigc-dev intel-igc-cm libigdfcl-dev libigfxcmrt-dev 
}

_upgrade_kernel()
{
  mkdir -p ${THIRD_PARTY_BUILD_DIR}/6.8.1_kernel
  pushd ${THIRD_PARTY_BUILD_DIR}/6.8.1_kernel
  cur_kernel=$(uname -r)
  if [[ "$cur_kernel" != *"6.8.1-060801-generic"* ]]; then
    kernel_url="https://kernel.ubuntu.com/mainline/v6.8.1/amd64/linux-image-unsigned-6.8.1-060801-generic_6.8.1-060801.202403151937_amd64.deb"
    modules_url="https://kernel.ubuntu.com/mainline/v6.8.1/amd64/linux-modules-6.8.1-060801-generic_6.8.1-060801.202403151937_amd64.deb"

    rm -rf *.deb
    wget -c ${kernel_url} && wget -c ${modules_url} && sudo dpkg -i *.deb 
    #sudo reboot
  fi

  popd
}

_install_npu_driver()
{
  echo "install npu driver"
  sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu
  mkdir -p ${THIRD_PARTY_BUILD_DIR}/npu_drivers
  pushd ${THIRD_PARTY_BUILD_DIR}/npu_drivers
    wget -c https://github.com/intel/linux-npu-driver/releases/download/v1.8.0/intel-driver-compiler-npu_1.8.0.20240916-10885588273_ubuntu24.04_amd64.deb
    wget -c https://github.com/intel/linux-npu-driver/releases/download/v1.8.0/intel-fw-npu_1.8.0.20240916-10885588273_ubuntu24.04_amd64.deb
    wget -c https://github.com/intel/linux-npu-driver/releases/download/v1.8.0/intel-level-zero-npu_1.8.0.20240916-10885588273_ubuntu24.04_amd64.deb

    sudo apt install -y libtbb12 && sudo dpkg -i *.deb

    #wget https://github.com/oneapi-src/level-zero/releases/download/v1.16.1/level-zero_1.16.1+u22.04_amd64.deb
    #sudo dpkg -i level-zero*.deb
  popd

  read -n 1 -s -r -p "Press any key to reboot, after reboot please set the udev rules for permissions access of NPU ..."
  sudo reboot

}

_set_rule_after_npu()
{
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
}

# Build Project
build()
{
  # Specify PROJ_DIR
  # PROJ_DIR=~/applications.iot.video-edge-device.holographic-sensor-fusion
  pushd ${PROJ_DIR}
  [ ! -L /opt/datasets ] && sudo ln -s $(realpath ${PROJ_DIR})/ai_inference/deployment/datasets /opt/datasets
  [ ! -L /opt/models ] && sudo ln -s $(realpath ${PROJ_DIR})/ai_inference/deployment/models /opt/models
  [ ! -L /opt/radarResults.csv] && sudo ln -s $(realpath ${PROJ_DIR})/ai_inference/deployment/datasets/radarResults.csv /opt
  mkdir -p $PROJ_DIR/output_logs
  sudo mkdir -p /opt/hce-core
  [ ! -L /opt/hce-core/output_logs ] && sudo ln -s $(realpath ${PROJ_DIR})/output_logs /opt/hce-core/output_logs

  bash -x build.sh
  popd
}

install_3rd_libs(){
  sudo rm -rf ${THIRD_PARTY_BUILD_DIR} && mkdir -p ${THIRD_PARTY_BUILD_DIR}
  _install_base_libs
  check_network #in case that some components download may failed in PRC network, we provide a proxy to help, comment this line if no needed.
  # _install_cmake
  _install_boost
  # _install_level_zero
  _install_spdlog
  _install_thrift
  # _install_openvino
  # _install_neo
  _install_mkl
  # _install_grpc
  ###_install_hdf5 ###
  # _install_onevpl
  # _install_gpu_driver
  # if lscpu |grep "Model name" |grep -q Ultra; then
  #   _upgrade_kernel
  #   _install_npu_driver
  #   _set_rule_after_npu
  # fi

}

install_3rd_libs


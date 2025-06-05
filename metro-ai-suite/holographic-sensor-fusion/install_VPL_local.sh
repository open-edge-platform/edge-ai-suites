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

# base libs
_install_base_libs()
{  
  sudo -E apt update -y
  sudo -E apt install -y automake libtool build-essential bison pkg-config flex curl git git-lfs vim dkms cmake make wget
}

# onevpl
_install_onevpl()
{
  pushd ${THIRD_PARTY_BUILD_DIR}

  mkdir -p onevpl_dependencies
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

  curl -k -o gmmlib-22.7.1.tar.gz https://github.com/intel/gmmlib/archive/refs/tags/intel-gmmlib-22.7.1.tar.gz -L
  tar -xvf gmmlib-22.7.1.tar.gz
  pushd  gmmlib-intel-gmmlib-22.7.1
  mkdir -p build && pushd build
  cmake .. -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release
  make -j8 && sudo make install && popd
  popd

  curl -k -o intel-media-25.1.4.tar.gz https://github.com/intel/media-driver/archive/refs/tags/intel-media-25.1.4.tar.gz -L
  tar -xvf intel-media-25.1.4.tar.gz
  mkdir -p build_media && pushd build_media
  cmake ../media-driver-intel-media-25.1.4 -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DLIBVA_INSTALL_PATH=${LIBVA_INSTALL_PATH} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release -DENABLE_PRODUCTION_KMD=ON
  make -j8 && sudo make install
  env LD_LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LD_LIBRARY_PATH} LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LIBRARY_PATH}  && sudo make install
  sudo mv /opt/intel/media/lib64/dri/* /opt/intel/media/lib64/
  sudo rm -rf /opt/intel/media/lib64/dri
  popd

  curl -k -o intel-onevpl-25.1.4.tar.gz https://github.com/intel/vpl-gpu-rt/archive/refs/tags/intel-onevpl-25.1.4.tar.gz -L
  tar -xvf intel-onevpl-25.1.4.tar.gz
  pushd vpl-gpu-rt-intel-onevpl-25.1.4
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

_install_base_libs
check_network #in case that some components download may failed in PRC network, we provide a proxy to help, comment this line if no needed.
_install_onevpl

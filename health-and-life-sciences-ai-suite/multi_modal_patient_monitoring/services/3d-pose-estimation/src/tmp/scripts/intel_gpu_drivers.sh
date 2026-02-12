#!/bin/bash -x

if [ -z "$INSTALL_DRIVER_VERSION" ]; then
    echo "Error: INSTALL_DRIVER_VERSION cannot be empty."
    exit 1
fi

apt-get update && apt-get install -y libnuma1 ocl-icd-libopencl1 --no-install-recommends && rm -rf /var/lib/apt/lists/*

case $INSTALL_DRIVER_VERSION in
"25.31.34666")
    mkdir /tmp/gpu_deps && cd /tmp/gpu_deps
    curl -L -O https://github.com/intel/compute-runtime/releases/download/25.31.34666.3/libze-intel-gpu1_25.31.34666.3-0_amd64.deb
    curl -L -O https://github.com/intel/compute-runtime/releases/download/25.31.34666.3/intel-opencl-icd_25.31.34666.3-0_amd64.deb
    curl -L -O https://github.com/intel/compute-runtime/releases/download/25.31.34666.3/libigdgmm12_22.8.1_amd64.deb
    curl -L -O https://github.com/intel/compute-runtime/releases/download/25.31.34666.3/intel-ocloc_25.31.34666.3-0_amd64.deb
    curl -L -O https://github.com/intel/intel-graphics-compiler/releases/download/v2.16.0/intel-igc-core-2_2.16.0+19683_amd64.deb
    curl -L -O https://github.com/intel/intel-graphics-compiler/releases/download/v2.16.0/intel-igc-opencl-2_2.16.0+19683_amd64.deb
    dpkg -i *.deb && rm -Rf /tmp/gpu_deps
    ;;
*)
    echo "Unsupported driver version: $INSTALL_DRIVER_VERSION"
    exit 1
    ;;
esac

apt-get clean && rm -rf /var/lib/apt/lists/* && rm -rf /tmp/*
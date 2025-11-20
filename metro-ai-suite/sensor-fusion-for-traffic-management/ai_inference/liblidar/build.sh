#! /bin/bash

# Optional: Whether to build samples, default OFF
BUILD_EXAMPLES=${1:-OFF}
echo "BUILD_EXAMPLES: ${BUILD_EXAMPLES}"

source /opt/intel/oneapi/setvars.sh
source /opt/intel/openvino_2025/setupvars.sh

mkdir -p build
cd build

cmake .. -DCMAKE_BUILD_TYPE=Release -DBUILD_EXAMPLES=${BUILD_EXAMPLES}
make -j8
cp liblidar.so ../liblidar.so

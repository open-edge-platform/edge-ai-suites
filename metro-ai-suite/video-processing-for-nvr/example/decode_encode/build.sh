#!/usr/bin/env bash
set -e

source /opt/intel/vppsdk/env.sh

MODE="${1:-normal}"

sudo mkdir -p build
cd build

if [ "$MODE" = "asan" ]; then
    echo "[BUILD] Configure ASan/UBSan debug build"
    sudo cmake -DCMAKE_PREFIX_PATH=/opt/intel/vppsdk -DENABLE_SANITIZERS=ON -DCMAKE_BUILD_TYPE=Debug ..
    sudo -E cmake -DENABLE_SANITIZERS=ON -DCMAKE_BUILD_TYPE=Debug ..
else
    echo "[BUILD] Configure normal build"
    sudo cmake -DCMAKE_PREFIX_PATH=/opt/intel/vppsdk ..
    sudo -E cmake ..
fi

sudo make -j4
sudo cp decode_encode ..

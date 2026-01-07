source /opt/intel/openvino_2025/setupvars.sh
source /opt/intel/vppsdk/env.sh

sudo mkdir build
cd build
sudo -E cmake .. -DCMAKE_BUILD_TYPE=Debug
sudo make -j4
sudo cp dec_det ..

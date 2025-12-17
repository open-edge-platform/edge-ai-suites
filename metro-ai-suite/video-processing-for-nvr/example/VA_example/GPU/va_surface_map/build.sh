source /opt/intel/openvino_2024/setupvars.sh
source /opt/intel/vppsdk/env.sh

sudo mkdir build
cd build
sudo -E cmake ..
sudo make -j4
sudo cp va_surface_map_264 ..
sudo cp va_surface_map_265 ..
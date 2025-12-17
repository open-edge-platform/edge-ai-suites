source /opt/intel/vppsdk/env.sh

sudo mkdir build
cd build
sudo cmake -DCMAKE_PREFIX_PATH=/opt/intel/vppsdk ..
sudo -E cmake ..
sudo make -j4
sudo cp decode_pp_encode ..

source /opt/intel/vppsdk/env.sh

sudo mkdir build
cd build
sudo -E cmake ..
sudo make -j4
sudo cp decode_pp_display ..
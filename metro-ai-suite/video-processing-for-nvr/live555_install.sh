#!/bin/bash
sudo apt install -y wget libssl-dev

wget -c https://github.com/k0zmo/live555/archive/refs/heads/master.zip
unzip master.zip
cd live555-master
mkdir build
cd build
cmake ../ -DBUILD_SHARED_LIBS=true
make 
sudo make install

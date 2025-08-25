#!/bin/bash

source /opt/intel/vppsdk/env.sh
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
cd /home/vpp/vppsample
/home/vpp/vppsample/build/svet_app load /home/vpp/vppsample/sample_config/basic/1dec1disp.txt

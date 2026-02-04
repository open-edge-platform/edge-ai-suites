#!/bin/bash

if [ -f /opt/intel/vppsdk/env.sh ]; then
    source /opt/intel/vppsdk/env.sh >/dev/null 2>&1
fi

cd /home/vpp/vppsample/example/VA_example/decode_detection/surface_map
echo "$@"

exec ./dec_det "$@"

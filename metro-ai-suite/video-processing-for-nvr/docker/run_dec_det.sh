#!/bin/bash

# 加载 VPP SDK 环境
if [ -f /opt/intel/vppsdk/env.sh ]; then
    source /opt/intel/vppsdk/env.sh >/dev/null 2>&1
fi

# 切换到 dec_det 所在目录
cd /home/vpp/vppsample/example/VA_example/decode_detection/surface_map
echo "$@"

# 执行二进制（传递所有参数）
exec ./dec_det "$@"

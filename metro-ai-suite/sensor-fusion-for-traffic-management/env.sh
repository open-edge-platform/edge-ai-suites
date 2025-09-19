#!/bin/bash
if [ -d "/opt/intel/media" ]; then
    source /opt/intel/openvino_2025/setupvars.sh
    source /opt/intel/oneapi/setvars.sh
    source /opt/intel/media/etc/vpl/vars.sh

    MEDIA_DIR=/opt/intel/media
    export PATH=$MEDIA_DIR/bin:$PATH
    export PKG_CONFIG_PATH=$MEDIA_DIR/lib64/pkgconfig/:$PKG_CONFIG_PATH
    export LIBRARY_PATH=$MEDIA_DIR/lib64:$LIBRARY_PATH
    export LIBVA_DRIVERS_PATH=$MEDIA_DIR/lib64
    export LD_LIBRARY_PATH=$MEDIA_DIR/lib64:$LD_LIBRARY_PATH
    export LIBVA_DRIVER_NAME=iHD
    export MFX_HOME=$MEDIA_DIR
    export VPPLOG_LEVEL=info
    export VPL_DIR=/opt/intel/media/lib64/cmake

    export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
else
    source /opt/intel/openvino_2025/setupvars.sh
    source /opt/intel/oneapi/setvars.sh
    source /usr/local/etc/vpl/vars.sh

    export PATH=/usr/local/lib:$PATH
    export PATH=$MEDIA_DIR:$PATH
    export PKG_CONFIG_PATH=$MEDIA_DIR/pkgconfig/:$PKG_CONFIG_PATH
    export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig/:$PKG_CONFIG_PATH
    export LIBRARY_PATH=$MEDIA_DIR:$LIBRARY_PATH
    export LIBVA_DRIVERS_PATH=$MEDIA_DIR/dri
    export LD_LIBRARY_PATH=$MEDIA_DIR:$LD_LIBRARY_PATH
    export LIBVA_DRIVER_NAME=iHD
    export MFX_HOME=$MEDIA_DIR
    export VPPLOG_LEVEL=info
    export VPL_DIR=/usr/local/lib/cmake

    export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu:$LD_LIBRARY_PATH
    export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

    # export OpenCV_DIR=/usr/local/lib/cmake/opencv4
    export OpenCV_DIR=/usr/lib/x86_64-linux-gnu/cmake/opencv4
fi

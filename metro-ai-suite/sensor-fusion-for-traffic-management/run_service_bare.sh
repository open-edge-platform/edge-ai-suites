#! /bin/bash
set -x

PROJ_DIR=$PWD

if [ -d "/opt/intel/media" ]; then
    source /opt/intel/openvino_2025/setupvars.sh
    source /opt/intel/oneapi/setvars.sh
    # source /opt/intel/oneVPL_v2023.3.0/etc/vpl/vars.sh
    source /opt/intel/media/etc/vpl/vars.sh
    # source /opt/intel/oneVPL-2022.2.2/etc/vpl/vars.sh


    MEDIA_DIR=/opt/intel/media
    export PATH=$MEDIA_DIR/bin:$PATH
    export PKG_CONFIG_PATH=$MEDIA_DIR/lib64/pkgconfig/:$PKG_CONFIG_PATH
    export CMAKE_PREFIX_PATH=$MEDIA_DIR/lib64:$CMAKE_PREFIX_PATH
    export LIBRARY_PATH=$MEDIA_DIR/lib64:$LIBRARY_PATH
    export CPATH=$MEDIA_DIR/include/:$CPATH
    export LIBVA_DRIVERS_PATH=$MEDIA_DIR/lib64
    export VPL_DIR=$MEDIA_DIR/lib64/cmake
    export LD_LIBRARY_PATH=$MEDIA_DIR/lib64:$LD_LIBRARY_PATH
    export LIBVA_DRIVER_NAME=iHD
    export MFX_HOME=$MEDIA_DIR



    export HVA_NODE_DIR=$PROJ_DIR/build/lib
    # export LD_LIBRARY_PATH=/opt/hdf5/lib:$LD_LIBRARY_PATH

    unset http_proxy
    unset https_proxy
    unset HTTP_PROXY
    unset HTTPS_PROXY

    cd $PROJ_DIR/build/
    # gdb --args ./bin/HceAILLInfServer -C ../ai_inference/source/low_latency_server/AiInference.config
    ./bin/HceAILLInfServer -C ../ai_inference/source/low_latency_server/AiInference.config
else
    source /opt/intel/openvino_2025/setupvars.sh
    source /opt/intel/oneapi/setvars.sh
    source /usr/local/etc/vpl/vars.sh

    MEDIA_DIR=/usr/lib/x86_64-linux-gnu
    export PATH=/usr/local/lib:$PATH
    export PATH=$MEDIA_DIR:$PATH
    export PKG_CONFIG_PATH=$MEDIA_DIR/pkgconfig/:$PKG_CONFIG_PATH
    export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig/:$PKG_CONFIG_PATH

    export CMAKE_PREFIX_PATH=$MEDIA_DIR:$CMAKE_PREFIX_PATH
    export LIBRARY_PATH=$MEDIA_DIR:$LIBRARY_PATH
    export CPATH=/usr/include/:$CPATH
    export LIBVA_DRIVERS_PATH=$MEDIA_DIR/dri
    export VPL_DIR=/usr/local/lib/cmake
    export LD_LIBRARY_PATH=/opt/intel/mediasdk/lib:$LD_LIBRARY_PATH
    export LD_LIBRARY_PATH=$MEDIA_DIR:$LD_LIBRARY_PATH
    export LIBVA_DRIVER_NAME=iHD
    export MFX_HOME=$MEDIA_DIR

    export HVA_NODE_DIR=$PROJ_DIR/build/lib

    export OpenCV_DIR=/usr/lib/x86_64-linux-gnu/cmake/opencv4

    unset http_proxy
    unset https_proxy
    unset HTTP_PROXY
    unset HTTPS_PROXY

    cd $PROJ_DIR/build/
    ./bin/HceAILLInfServer -C ../ai_inference/source/low_latency_server/AiInference.config
fi

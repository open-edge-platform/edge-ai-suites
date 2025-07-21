#!/bin/bash
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
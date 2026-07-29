#!/bin/bash
#MEDIA_DIR=/opt/intel/media
#export PATH=$MEDIA_DIR/bin:$PATH
#export PKG_CONFIG_PATH=$MEDIA_DIR/lib64/pkgconfig/:$PKG_CONFIG_PATH
#export LIBRARY_PATH=$MEDIA_DIR/lib64:$LIBRARY_PATH
#export LIBVA_DRIVERS_PATH=$MEDIA_DIR/lib64
#export LD_LIBRARY_PATH=$MEDIA_DIR/lib64:$LD_LIBRARY_PATH
#export LIBVA_DRIVER_NAME=iHD
#export MFX_HOME=$MEDIA_DIR
#export VPPLOG_LEVEL=info

#export VPPSDK_DIR=/opt/intel/vppsdk
#export LD_LIBRARY_PATH=$VPPSDK_DIR/lib:$LD_LIBRARY_PATH
#export MULTI_DISPLAY_PATCH=1
#export DISPLAY_NEW_PLATFORM=1

sudo init 3
source /opt/intel/vppsdk/env.sh
export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
export MULTI_DISPLAY_PATCH=1
export DISPLAY_NEW_PLATFORM=1

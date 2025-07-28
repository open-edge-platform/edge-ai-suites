#!/bin/bash

topdir=`pwd`
if [ ! -d "/opt/intel/vppsdk" ]
then
	echo "Foler /opt/intel/vppsdk doesn't exist."
	echo "Please check if your vppsdk installed correctly."
	exit 0
fi

if [ ! -f "1080p.h265" ]
then
	if [ ! -f "/opt/video/1080p.h265" ]
	then
		echo "/opt/video/1080p.h265 does not exist. It shall be installed by vppsdk install script."
		echo "Please check if your vppsdk installed correctly."
        else	
		echo "Copy test video clips from /opt/video/ to current folder"
		cp /opt/video/* .
	fi
fi


if [ ! -d "svet_app/thirdparty/spdlog" ]
then
	mkdir -p svet_app/thirdparty
	echo "wget https://github.com/gabime/spdlog/archive/refs/tags/v1.10.0.tar.gz  -O svet_app/thirdparty/v1.10.0.tar.gz"
	wget https://github.com/gabime/spdlog/archive/refs/tags/v1.10.0.tar.gz  -O svet_app/thirdparty/v1.10.0.tar.gz
	cd svet_app/thirdparty/
	tar zxvf v1.10.0.tar.gz
	mv spdlog-1.10.0 spdlog
fi
cd $topdir

source /opt/intel/vppsdk/env.sh
mkdir -p build
cd build
cmake ../svet_app
make -j8
cd ../

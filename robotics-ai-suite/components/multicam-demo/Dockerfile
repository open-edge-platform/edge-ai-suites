
# SPDX-License-Identifier: Apache-2.0
# Copyright (C) 2025 Intel Corporation
FROM openvino/ubuntu20_dev
ARG DEBIAN_FRONTEND=noninteractive

# Add environment variable for pyrealsense2
ENV PATH=$PATH:/usr/local/lib/
ENV PYTHONPATH=$PYTHONPATH:/usr/local/lib/

USER root
RUN apt update -y
RUN apt-get install -y git wget make cmake build-essential
RUN apt install -y  libgl1 libglib2.0-0  libx11-dev  python3-tk libcanberra-gtk-module libcanberra-gtk3-module python3-opencv 
RUN apt install -y openssl libusb-1.0-0-dev wget gnupg2

RUN apt install -y python3-pip python3-dev python-dev-is-python3

# Install intel-basekit.
RUN echo "deb [trusted=yes] https://apt.repos.intel.com/oneapi all main" | \
    tee /etc/apt/sources.list.d/oneAPI.list

RUN apt update -y
RUN apt install -y intel-basekit intel-oneapi-python

RUN source /opt/intel/oneapi/setvars.sh && \
        pip3 install imutils protobuf==3.20.3 Pillow psutil cython  \
        screeninfo dpnp onnx ultralytics==8.0.43 openvino-dev

# Build and Install librealsense from source
# Branch: development; because the pyrealsense2 for adl-p is not yet in main branch
WORKDIR /tmp
RUN git clone https://github.com/IntelRealSense/librealsense
RUN cd librealsense && git checkout development && \
	mkdir build && cd build && \
	source /opt/intel/oneapi/setvars.sh && \
	cmake ../ -DBUILD_EXAMPLES=false -DBUILD_GRAPHICAL_EXAMPLES=false -DBUILD_TOOLS=true \
	-DPYTHON_EXECUTABLE=`which python` -DBUILD_PYTHON_BINDINGS:bool=true && \
	make -j`nproc` && make install && \
	cp -aL Release/pyrealsense2* /usr/local/lib/
RUN	rm -rf /tmp/librealsense/

WORKDIR /workspace/
COPY src /workspace/src/
COPY scripts /workspace/scripts/
COPY config /workspace/config/
COPY videos /workspace/videos/
RUN cd ./src/ && source /opt/intel/oneapi/setvars.sh && python3 ./setup.py build_ext --inplace

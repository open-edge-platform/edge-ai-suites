ARG BASE=ubuntu
ARG BASE_VERSION=22.04

# ---------- Build Stage ----------
FROM $BASE:${BASE_VERSION} AS builder
USER root
WORKDIR /home/openvino
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# install all build dependencies and tools
RUN apt update && \
	apt install -y automake libtool build-essential bison pkg-config flex curl git git-lfs vim dkms cmake make wget \
	debhelper devscripts mawk openssh-server libssl-dev && \
	apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/*

# download 3rd libs
WORKDIR /home/openvino/3rd_build
RUN curl -k -o boost_1_83_0.tar.gz https://phoenixnap.dl.sourceforge.net/project/boost/boost/1.83.0/boost_1_83_0.tar.gz -L && \
    tar -zxf boost_1_83_0.tar.gz && \
    curl -k -o v1.11.0.tar.gz https://github.com/gabime/spdlog/archive/refs/tags/v1.11.0.tar.gz -L && \
    tar -zxf v1.11.0.tar.gz && \
    curl -k -o thrift_v0.21.0.tar.gz https://github.com/apache/thrift/archive/refs/tags/v0.21.0.tar.gz -L && \
    tar -zxf thrift_v0.21.0.tar.gz

# boost 1.83.0
WORKDIR /home/openvino/3rd_build/boost_1_83_0
RUN ./bootstrap.sh --with-libraries=all --with-toolset=gcc && \
    ./b2 toolset=gcc && ./b2 install && ldconfig

# spdlog 1.11.0
WORKDIR /home/openvino/3rd_build/spdlog-1.11.0
RUN mv include/spdlog /usr/local/include

# thrift 0.21.0
WORKDIR /home/openvino/3rd_build/thrift-0.21.0
RUN ./bootstrap.sh && ./configure --with-qt4=no --with-qt5=no --with-python=no && \
    make -j8 && make install && \
    rm -rf /home/openvino/3rd_build

# mkl
RUN curl -k -o GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -L && \
	apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && rm GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && \
	echo "deb https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
	apt update -y && \
	apt install -y intel-oneapi-mkl-devel lsb-release

# Install oneVPL dependencies
WORKDIR /home/openvino/3rd_build/
RUN curl -k -o MediaStack.tar.gz https://github.com/intel/vpl-gpu-rt/releases/download/intel-onevpl-25.3.4/MediaStack.tar.gz -L&& \
    tar -xvf MediaStack.tar.gz
WORKDIR /home/openvino/3rd_build/MediaStack
RUN sudo bash install_media.sh

# openvino
WORKDIR /home/openvino/3rd_build
RUN curl -k -o openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz https://storage.openvinotoolkit.org/repositories/openvino/packages/2025.2/linux/openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz -L && \
	tar -xvf openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz && \
	mkdir -p /opt/intel/openvino_2025 && \
	mv openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64/* /opt/intel/openvino_2025

# grpc 1.58.1
WORKDIR /home/openvino/3rd_build
RUN git config --global http.postBuffer 524288000 && \
    git clone --recurse-submodules -b v1.58.1 --depth 1 --shallow-submodules https://github.com/grpc/grpc grpc-v1.58.1
WORKDIR /home/openvino/3rd_build/grpc-v1.58.1/third_party
RUN rm -rf zlib && \
    git clone -b v1.3.1 https://github.com/madler/zlib.git zlib
WORKDIR /home/openvino/3rd_build/grpc-v1.58.1/third_party/zlib
RUN sed -i 's/PUBLIC ${CMAKE_CURRENT_BINARY_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}> $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>/g' CMakeLists.txt
WORKDIR /home/openvino/3rd_build/grpc-v1.58.1/cmake/build
RUN cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DCMAKE_INSTALL_PREFIX=/opt/grpc ../.. && \
    make -j8 && \
    make install

# level-zero 1.20.2
WORKDIR /home/openvino/3rd_build
RUN git clone https://github.com/oneapi-src/level-zero.git
WORKDIR /home/openvino/3rd_build/level-zero
RUN git checkout v1.20.2 && \
    mkdir build
WORKDIR /home/openvino/3rd_build/level-zero/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=/opt/intel/level-zero && \
    cmake --build . --config Release --target install 

# clean build files
RUN rm -rf /home/openvino/3rd_build /tmp/*

# ---------- Runtime Stage ----------
FROM $BASE:${BASE_VERSION} AS runtime
USER root
WORKDIR /home/openvino
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

# install all build dependencies and tools
RUN apt update && \
	apt install -y automake libtool build-essential bison pkg-config flex curl git git-lfs vim dkms cmake make wget \
	debhelper devscripts mawk openssh-server ocl-icd-libopencl1 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Install GPU driver
### Install the Intel graphics GPG public key
RUN curl -sSL https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg

### Configure the repositories.intel.com package repository
RUN echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | \
    tee /etc/apt/sources.list.d/intel-gpu-jammy.list

# GPU/NPU drivers and runtimes
WORKDIR /tmp/gpu_deps
RUN apt update && \
    apt install -y libigdgmm12 && \
	curl -L -O https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.17791.9/intel-igc-core_1.0.17791.9_amd64.deb && \
	curl -L -O https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.17791.9/intel-igc-opencl_1.0.17791.9_amd64.deb && \
	curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-level-zero-gpu-dbgsym_1.6.31294.12_amd64.ddeb && \
	curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-level-zero-gpu_1.6.31294.12_amd64.deb && \
	curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-opencl-icd-dbgsym_24.39.31294.12_amd64.ddeb && \
	curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-opencl-icd_24.39.31294.12_amd64.deb && \
	dpkg -i ./*.deb && rm -rf /tmp/gpu_deps

WORKDIR /tmp/npu_deps
RUN curl -L -O https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-driver-compiler-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb && \
	curl -L -O https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-fw-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb && \
	curl -L -O https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-level-zero-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb && \
	apt install -y ./*.deb && \
	curl -L -O https://github.com/oneapi-src/level-zero/releases/download/v1.20.2/level-zero_1.20.2+u22.04_amd64.deb && \
	dpkg -i level-zero*.deb && rm -rf /tmp/npu_deps

RUN apt update && \
    apt install -y opencl-headers opencl-dev intel-gpu-tools clinfo \
	intel-fw-gpu libtbb12 intel-level-zero-gpu libigc1 libigdfcl1 libigfxcmrt7 libmfx1 libigdgmm12 \
	libssl-dev libuv1-dev libeigen3-dev libfmt-dev zlib1g-dev libicu-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libopencv-dev \
	intel-media-va-driver-non-free va-driver-all libmfxgen1 libvpl2 libgdal-dev libpugixml-dev \
	libdrm-dev libegl1-mesa-dev libgl1-mesa-dev libx11-dev libx11-xcb-dev libxcb-dri3-dev libxext-dev libxfixes-dev libwayland-dev \
	libgtk2.0-0 libgl1 libsm6 libxext6 x11-apps --no-install-recommends && \
	apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/*

# create user and set permissions
RUN useradd -ms /bin/bash -G video,users,sudo openvino && \
	echo 'openvino:intel' | chpasswd && \
	chown openvino -R /home/openvino

# copy build artifacts and project files
COPY --from=builder /opt/intel /opt/intel
COPY --from=builder /opt/grpc /opt/grpc
COPY --from=builder /usr/local /usr/local
COPY --from=builder /usr/include /usr/include
COPY --from=builder /usr/lib /usr/lib
COPY --from=builder /lib /lib

COPY . /home/openvino/metro-2.0

# environment variables and bashrc configuration
RUN echo "source /opt/intel/openvino_2025/setupvars.sh" >> /home/openvino/.bashrc && \
	echo "source /opt/intel/media/etc/vpl/vars.sh" >> /home/openvino/.bashrc && \
	echo "source /opt/intel/oneapi/setvars.sh" >> /home/openvino/.bashrc
ENV PROJ_DIR=/home/openvino/metro-2.0
RUN ln -s $PROJ_DIR/ai_inference/deployment/datasets /opt/datasets && \
	ln -s $PROJ_DIR/ai_inference/deployment/models /opt/models && \
	cp $PROJ_DIR/ai_inference/deployment/datasets/radarResults.csv /opt

RUN chown openvino -R /home/openvino
USER openvino
WORKDIR /home/openvino

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD (test -d /home/openvino/metro-2.0) || exit 1

ENTRYPOINT ["/bin/bash", "-c", "source /home/openvino/.bashrc && bash"]

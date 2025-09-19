ARG BASE=ubuntu
ARG BASE_VERSION=22.04
FROM $BASE:${BASE_VERSION} AS base

USER root
WORKDIR /

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive


# Creating user openvino and adding it to groups "video" and "users" to use GPU and VPU
RUN sed -ri -e 's@^UMASK[[:space:]]+[[:digit:]]+@UMASK 000@g' /etc/login.defs && \
	grep -E "^UMASK" /etc/login.defs && useradd -ms /bin/bash -G video,users openvino && \
    chown openvino -R /home/openvino

# Change password & Add sudo privileges
### Sets up user openvino with default password.
RUN echo 'openvino:intel' | chpasswd

### Sets up user openvino with sudo privileges.
RUN usermod -aG sudo openvino

# Install base lib
RUN apt update && \
    apt install -y automake libtool build-essential bison pkg-config flex curl git git-lfs vim dkms cmake make wget


# Install GPU driver
### Install the Intel graphics GPG public key
RUN curl -sSL https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg

### Configure the repositories.intel.com package repository
RUN echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | \
    tee /etc/apt/sources.list.d/intel-gpu-jammy.list

### Update the package repository metadata and Install the compute-related packages
RUN apt update && \
    apt install -y debhelper devscripts mawk openssh-server opencl-headers opencl-dev intel-gpu-tools clinfo  && \
    apt install -y intel-fw-gpu libtbb12 intel-level-zero-gpu libigc1 libigdfcl1 libigfxcmrt7 libmfx1

### Install the compute-related packages
RUN apt update && \
    apt install -y --no-install-recommends ocl-icd-libopencl1 && \
    apt-get clean && \
    rm -rf /tmp/*

WORKDIR /tmp/gpu_deps
RUN curl -L -O https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.17791.9/intel-igc-core_1.0.17791.9_amd64.deb && \
    curl -L -O https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.17791.9/intel-igc-opencl_1.0.17791.9_amd64.deb && \
    curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-level-zero-gpu-dbgsym_1.6.31294.12_amd64.ddeb && \
    curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-level-zero-gpu_1.6.31294.12_amd64.deb && \
    curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-opencl-icd-dbgsym_24.39.31294.12_amd64.ddeb && \
    curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/intel-opencl-icd_24.39.31294.12_amd64.deb && \
    curl -L -O https://github.com/intel/compute-runtime/releases/download/24.39.31294.12/libigdgmm12_22.5.2_amd64.deb && \
    dpkg -i ./*.deb && rm -rf /tmp/gpu_deps && \
    apt install -y libigdgmm12=22.7.1-1120~22.04

## Install Linux NPU Driver v1.16.0 on Ubuntu 22.04
WORKDIR /tmp/npu_deps
RUN dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu && \
    apt install -y libtbb12 && \
    curl -L -O https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-driver-compiler-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb && \
    curl -L -O https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-fw-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb && \
    curl -L -O https://github.com/intel/linux-npu-driver/releases/download/v1.16.0/intel-level-zero-npu_1.16.0.20250328-14132024782_ubuntu22.04_amd64.deb && \
    apt install -y ./*.deb && \
    curl -L -O https://github.com/oneapi-src/level-zero/releases/download/v1.20.2/level-zero_1.20.2+u22.04_amd64.deb && \
    dpkg -i level-zero*.deb && rm -rf /tmp/npu_deps

RUN apt-mark hold intel-opencl-icd


# TFCC related
WORKDIR /home/openvino/3rd_build
### base libs
RUN apt update -y && \
    apt install --only-upgrade systemd && \
    apt install -y libssl-dev libuv1-dev libeigen3-dev git-lfs libfmt-dev zlib1g-dev libicu-dev libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev intel-gpu-tools libopencv-dev && \
    apt install -y intel-media-va-driver-non-free va-driver-all libmfx1 libmfxgen1 libvpl2

### download 3rd libs
WORKDIR /home/openvino/3rd_build
RUN curl -k -o boost_1_83_0.tar.gz https://phoenixnap.dl.sourceforge.net/project/boost/boost/1.83.0/boost_1_83_0.tar.gz -L && \
    tar -zxf boost_1_83_0.tar.gz && \
    curl -k -o v1.11.0.tar.gz https://github.com/gabime/spdlog/archive/refs/tags/v1.11.0.tar.gz -L && \
    tar -zxf v1.11.0.tar.gz && \
    curl -k -o thrift_v0.21.0.tar.gz https://github.com/apache/thrift/archive/refs/tags/v0.21.0.tar.gz -L && \
    tar -zxf thrift_v0.21.0.tar.gz

### boost 1.83.0
WORKDIR /home/openvino/3rd_build/boost_1_83_0
RUN ./bootstrap.sh --with-libraries=all --with-toolset=gcc && \
    ./b2 toolset=gcc && ./b2 install && ldconfig

### spdlog 1.11.0
WORKDIR /home/openvino/3rd_build/spdlog-1.11.0
RUN mv include/spdlog /usr/local/include

### thrift 0.21.0
WORKDIR /home/openvino/3rd_build/thrift-0.21.0
RUN ./bootstrap.sh && ./configure --with-qt4=no --with-qt5=no --with-python=no && \
    make -j8 && make install && \
    rm -rf /home/openvino/3rd_build

### mkl
RUN curl -k -o GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -L && \
    apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && rm GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && \
    echo "deb https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
    apt update -y && \
    apt install -y intel-oneapi-mkl-devel lsb-release

### Install oneVPL dependencies
WORKDIR /home/openvino/3rd_build/onevpl_dependencies

RUN apt install -y libdrm-dev libegl1-mesa-dev libgl1-mesa-dev libx11-dev libx11-xcb-dev libxcb-dri3-dev libxext-dev libxfixes-dev libwayland-dev

ENV MFX_HOME=/opt/intel/media
ENV LIBVA_INSTALL_PATH=/opt/intel/media/lib64
ENV LIBVA_DRIVERS_PATH=/opt/intel/media/lib64
ENV LIBVA_DRIVER_NAME=iHD
ENV LIBVA_INSTALL_PREFIX=/opt/intel/media

ENV LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LIBRARY_PATH}
ENV C_INCLUDE_PATH=${LIBVA_INSTALL_PREFIX}/include:${C_INCLUDE_PATH}
ENV CPLUS_INCLUDE_PATH=${LIBVA_INSTALL_PREFIX}/include:${CPLUS_INCLUDE_PATH}
ENV PKG_CONFIG_PATH=${LIBVA_INSTALL_PATH}/pkgconfig:${PKG_CONFIG_PATH}

RUN mkdir -p $MFX_HOME && mkdir -p $LIBVA_INSTALL_PATH && mkdir -p $LIBVA_DRIVERS_PATH && \
    apt install -y libdrm-dev libegl1-mesa-dev libgl1-mesa-dev libx11-dev libx11-xcb-dev libxcb-dri3-dev libxext-dev libxfixes-dev libwayland-dev

##### Download oneVPL dependencies
WORKDIR /home/openvino/3rd_build/onevpl_dependencies
RUN curl -k -o libva-2.22.0.tar.gz https://github.com/intel/libva/archive/refs/tags/2.22.0.tar.gz -L && \
    tar -xvf libva-2.22.0.tar.gz && \
    curl -k -o libva-utils-2.22.0.tar.gz https://github.com/intel/libva-utils/archive/refs/tags/2.22.0.tar.gz -L && \
    tar -xvf libva-utils-2.22.0.tar.gz && \
    curl -k -o gmmlib-22.7.1.tar.gz https://github.com/intel/gmmlib/archive/refs/tags/intel-gmmlib-22.7.1.tar.gz -L && \
    tar -xvf gmmlib-22.7.1.tar.gz && \
    curl -k -o intel-media-25.1.4.tar.gz https://github.com/intel/media-driver/archive/refs/tags/intel-media-25.1.4.tar.gz -L && \
    tar -xvf intel-media-25.1.4.tar.gz && \
    curl -k -o intel-onevpl-25.1.4.tar.gz https://github.com/intel/vpl-gpu-rt/archive/refs/tags/intel-onevpl-25.1.4.tar.gz -L && \
    tar -xvf intel-onevpl-25.1.4.tar.gz && \
    curl -k -o oneVPL_v2.13.0.tar.gz https://github.com/intel/libvpl/archive/refs/tags/v2.13.0.tar.gz -L && \
    tar -xvf oneVPL_v2.13.0.tar.gz

##### Install libva
WORKDIR /home/openvino/3rd_build/onevpl_dependencies/libva-2.22.0
RUN ./autogen.sh --prefix=${LIBVA_INSTALL_PREFIX} --libdir=${LIBVA_INSTALL_PATH} --enable-x11 && \
    make -j8 && \
    make install

##### Install libva-utils
WORKDIR /home/openvino/3rd_build/onevpl_dependencies/libva-utils-2.22.0
RUN ./autogen.sh --prefix=${LIBVA_INSTALL_PREFIX} --libdir=${LIBVA_INSTALL_PATH} && \
    make -j8 && \
    make install

##### Install gmmlib
WORKDIR /home/openvino/3rd_build/onevpl_dependencies/gmmlib-intel-gmmlib-22.7.1/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release && \
    make -j8 && \
    make install

##### Install media-driver
WORKDIR /home/openvino/3rd_build/onevpl_dependencies/build_media
RUN cmake ../media-driver-intel-media-25.1.4 -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DLIBVA_INSTALL_PATH=${LIBVA_INSTALL_PATH} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release -DENABLE_PRODUCTION_KMD=ON && \
    make -j8 && \
    make install && \
    env LD_LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LD_LIBRARY_PATH} LIBRARY_PATH=${LIBVA_INSTALL_PATH}:${LIBRARY_PATH} && \
    make install && \
    mv /opt/intel/media/lib64/dri/* /opt/intel/media/lib64/ && \
    rm -rf /opt/intel/media/lib64/dri

##### Install oneVPL-intel-gpu
WORKDIR /home/openvino/3rd_build/onevpl_dependencies/vpl-gpu-rt-intel-onevpl-25.1.4/build
RUN sed -i 's|set( MFX_API_HOME ${MFX_API_HOME}/vpl)|set( MFX_API_HOME "/home/openvino/3rd_build/onevpl_dependencies/vpl-gpu-rt-intel-onevpl-25.1.4/api/vpl")|' /home/openvino/3rd_build/onevpl_dependencies/vpl-gpu-rt-intel-onevpl-25.1.4/builder/FindMFX.cmake && \
    sed -i '/PATH_SUFFIXES include/s/^/#/' /home/openvino/3rd_build/onevpl_dependencies/vpl-gpu-rt-intel-onevpl-25.1.4/builder/FindMFX.cmake && \
    cmake .. -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release && \
    make -j8 && \
    make install

##### Install oneVPL-dispatcher
WORKDIR /home/openvino/3rd_build/onevpl_dependencies/libvpl-2.13.0/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=${LIBVA_INSTALL_PREFIX} -DCMAKE_INSTALL_LIBDIR=${LIBVA_INSTALL_PATH} -DCMAKE_BUILD_TYPE=Release -DENABLE_X11=ON && \
    cmake --build . --config Release && \
    cmake --build . --config Release --target install

### Install openvino 2025.2
WORKDIR /home/openvino/3rd_build
RUN curl -k -o openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz https://storage.openvinotoolkit.org/repositories/openvino/packages/2025.2/linux/openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz -L && \
    tar -xvf openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64.tgz && \
    mkdir -p /opt/intel/openvino_2025 && \
    mv openvino_toolkit_ubuntu22_2025.2.0.19140.c01cd93e24d_x86_64/* /opt/intel/openvino_2025
RUN apt install -y libgdal-dev libpugixml-dev libopencv-dev

# ### Install grpc 1.72.0
# RUN git config --global http.postBuffer 524288000 && \
#     git clone --recurse-submodules -b v1.72.0 --depth 1 --shallow-submodules https://github.com/grpc/grpc grpc-v1.72.0 && \
#     cd grpc-v1.72.0 && mkdir -p cmake/build && \
#     cd cmake/build && \
#     cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/grpc ../.. && \
#     make -j8 && \
#     make install

### Install grpc 1.58.1
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

### Install level-zero 1.20.2
WORKDIR /home/openvino/3rd_build
RUN git clone https://github.com/oneapi-src/level-zero.git
WORKDIR /home/openvino/3rd_build/level-zero
RUN git checkout v1.20.2 && \
    mkdir build
WORKDIR /home/openvino/3rd_build/level-zero/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=/opt/intel/level-zero && \
    cmake --build . --config Release --target install 

### Install libradar
WORKDIR /home/openvino/3rd_build
RUN curl -s https://eci.intel.com/sed-repos/gpg-keys/GPG-PUB-KEY-INTEL-SED.gpg | tee /usr/share/keyrings/sed-archive-keyring.gpg > /dev/null
RUN echo "deb [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | tee /etc/apt/sources.list.d/sed.list
RUN echo "deb-src [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | tee -a /etc/apt/sources.list.d/sed.list
RUN bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/sed'
RUN apt update -y && \
    apt install libradar

# Install display related libs
RUN apt install -y libgtk2.0-0 libgl1 libsm6 libxext6 x11-apps

WORKDIR /home/openvino
RUN rm -rf /home/openvino/3rd_build && \
    echo "source /opt/intel/openvino_2025/setupvars.sh" >> /home/openvino/.bashrc && \
    echo "source /opt/intel/media/etc/vpl/vars.sh" >> /home/openvino/.bashrc && \
    echo "source /opt/intel/oneapi/setvars.sh" >> /home/openvino/.bashrc
ENV DEBIAN_FRONTEND=noninteractive

COPY . /home/openvino/metro-2.0

ENV PROJ_DIR=/home/openvino/metro-2.0
RUN ln -s $PROJ_DIR/ai_inference/deployment/datasets /opt/datasets && \
    ln -s $PROJ_DIR/ai_inference/deployment/models /opt/models && \
    cp $PROJ_DIR/ai_inference/deployment/datasets/radarResults.csv /opt

RUN chown openvino -R /home/openvino
USER openvino
WORKDIR /home/openvino

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD (test -d /home/openvino/metro-2.0) || exit 1

# CMD ["/bin/bash"]
ENTRYPOINT ["/bin/bash", "-c", "source /home/openvino/.bashrc && bash"]

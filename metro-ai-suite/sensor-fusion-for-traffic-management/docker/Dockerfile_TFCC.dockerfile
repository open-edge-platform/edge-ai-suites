ARG BASE=ubuntu
ARG BASE_VERSION=24.04

# ==============================================================================
# base builder stage
# ==============================================================================
FROM $BASE:${BASE_VERSION} AS builder

ARG DEBIAN_FRONTEND=noninteractive
ARG BUILD_ARG=release

ARG GST_VERSION=1.26.7
ARG VORBIS_VERSION=1.3.7
ENV GSTREAMER_DIR=/opt/gstreamer
ENV GSTREAMER_SRC_DIR=/opt/gstreamer/src
ENV LIBVA_DRIVER_NAME=iHD
ENV GST_VA_ALL_DRIVERS=1

ARG PACKAGE_ORIGIN="https://gstreamer.freedesktop.org"
ARG GST_REPO="${PACKAGE_ORIGIN}"/src
ARG VORBIS_URL=https://downloads.xiph.org/releases/vorbis/libvorbis-${VORBIS_VERSION}.tar.xz

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN apt update && \
    apt install -y -q --no-install-recommends libtbb12 curl gpg ca-certificates ocl-icd-libopencl1 && \
    rm -rf /var/lib/apt/lists/*

# Intel GPU client drivers and prerequisites installation
RUN curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu noble unified" |\
    tee /etc/apt/sources.list.d/intel-gpu-noble.list

RUN apt update && \
    apt install --allow-downgrades -y -q --no-install-recommends libze-intel-gpu1 libze1 \
    intel-media-va-driver-non-free intel-gsc intel-opencl-icd && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Intel NPU drivers and prerequisites installation
WORKDIR /tmp/npu_deps
RUN curl -LO https://github.com/oneapi-src/level-zero/releases/download/v1.24.2/level-zero_1.24.2+u24.04_amd64.deb && \
    dpkg -i level-zero_1.24.2+u24.04_amd64.deb && \
    curl -LO https://github.com/intel/linux-npu-driver/releases/download/v1.24.0/linux-npu-driver-v1.24.0.20251003-18218973328-ubuntu2404.tar.gz && \
    tar -xf linux-npu-driver-v1.24.0.20251003-18218973328-ubuntu2404.tar.gz && \
    dpkg -i ./*.deb && \
    rm -rf /var/lib/apt/lists/* /tmp/npu_deps

USER root
WORKDIR /

# create user and set permissions
RUN useradd -ms /bin/bash -G video,users,sudo tfcc && \
	echo 'tfcc:intel' | chpasswd && \
	chown tfcc -R /home/tfcc && \
	mkdir /python3venv && \
    chown tfcc -R /python3venv && \
    chmod u+w /python3venv

RUN apt update && \
	apt install -y -q --no-install-recommends autoconf automake libtool build-essential g++ \
	bison pkg-config flex curl git git-lfs vim dkms cmake make wget \
	debhelper devscripts mawk openssh-server libssl-dev libopencv-dev opencv-data \
	python3-pip python3-gi python-gi-dev python3-dev python3-venv && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

RUN apt update && \
	apt install -y --no-install-recommends libcairo2-dev libgirepository1.0-dev && \
	apt clean && \
	rm -rf /var/lib/apt/lists/*

USER tfcc
RUN python3 -m venv /python3venv && \
    /python3venv/bin/pip3 install --no-cache-dir --upgrade pip && \
    /python3venv/bin/pip3 install --no-cache-dir --no-dependencies \
    meson==1.4.1 \
    ninja==1.11.1.1 \
    numpy==2.2.0 \
    tabulate==0.9.0 \
    tqdm==4.67.1 \
    junit-xml==1.9 \
    opencv-python==4.11.0.86 \
    XlsxWriter==3.2.0 \
    zxing-cpp==2.2.0 \
    pyzbar==0.1.9 \
    six==1.16.0 \
    pycairo==1.26.0 \
    PyGObject==3.50.0 \
    setuptools==78.1.1 \
    pytest==8.3.3 \
    pluggy==1.5.0 \
    exceptiongroup==1.2.2 \
    iniconfig==2.0.0

USER root

# download 3rd libs
WORKDIR /home/tfcc/3rd_build
RUN curl -k -o boost_1_83_0.tar.gz https://phoenixnap.dl.sourceforge.net/project/boost/boost/1.83.0/boost_1_83_0.tar.gz -L && \
    tar -zxf boost_1_83_0.tar.gz && \
    curl -k -o v1.11.0.tar.gz https://github.com/gabime/spdlog/archive/refs/tags/v1.11.0.tar.gz -L && \
    tar -zxf v1.11.0.tar.gz && \
    curl -k -o thrift_v0.21.0.tar.gz https://github.com/apache/thrift/archive/refs/tags/v0.21.0.tar.gz -L && \
    tar -zxf thrift_v0.21.0.tar.gz

# boost 1.83.0
WORKDIR /home/tfcc/3rd_build/boost_1_83_0
RUN ./bootstrap.sh --with-libraries=all --with-toolset=gcc && \
    ./b2 toolset=gcc && ./b2 install && ldconfig

# spdlog 1.11.0
WORKDIR /home/tfcc/3rd_build/spdlog-1.11.0
RUN mv include/spdlog /usr/local/include

# thrift 0.21.0
WORKDIR /home/tfcc/3rd_build/thrift-0.21.0
RUN ./bootstrap.sh && ./configure --with-qt4=no --with-qt5=no --with-python=no && \
    make -j8 && make install && \
    rm -rf /home/tfcc/3rd_build

# oneapi
RUN curl -k -o GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -L && \
	apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && rm GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && \
	echo "deb https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
	apt update -y && \
	apt install -y intel-oneapi-base-toolkit lsb-release

# Install oneVPL dependencies
WORKDIR /home/tfcc/3rd_build/
RUN curl -k -o MediaStack.tar.gz https://github.com/intel/vpl-gpu-rt/releases/download/intel-onevpl-25.3.4/MediaStack.tar.gz -L&& \
    tar -xvf MediaStack.tar.gz
WORKDIR /home/tfcc/3rd_build/MediaStack
RUN bash install_media.sh

# openvino
WORKDIR /home/tfcc/3rd_build
RUN curl -k -o openvino_toolkit_ubuntu24_2025.3.0.19807.44526285f24_x86_64.tgz https://storage.openvinotoolkit.org/repositories/openvino/packages/2025.3/linux/openvino_toolkit_ubuntu24_2025.3.0.19807.44526285f24_x86_64.tgz -L && \
	tar -xvf openvino_toolkit_ubuntu24_2025.3.0.19807.44526285f24_x86_64.tgz && \
	mkdir -p /opt/intel/openvino_2025 && \
	mv openvino_toolkit_ubuntu24_2025.3.0.19807.44526285f24_x86_64/* /opt/intel/openvino_2025

# grpc 1.58.1
WORKDIR /home/tfcc/3rd_build
RUN git config --global http.postBuffer 524288000 && \
    git clone --recurse-submodules -b v1.58.1 --depth 1 --shallow-submodules https://github.com/grpc/grpc grpc-v1.58.1
WORKDIR /home/tfcc/3rd_build/grpc-v1.58.1/third_party
RUN rm -rf zlib && \
    git clone -b v1.3.1 https://github.com/madler/zlib.git zlib
WORKDIR /home/tfcc/3rd_build/grpc-v1.58.1/third_party/zlib
RUN sed -i 's/PUBLIC ${CMAKE_CURRENT_BINARY_DIR} ${CMAKE_CURRENT_SOURCE_DIR}/PUBLIC $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}> $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>/g' CMakeLists.txt
WORKDIR /home/tfcc/3rd_build/grpc-v1.58.1/cmake/build
RUN cmake -DgRPC_INSTALL=ON -DgRPC_BUILD_TESTS=OFF -DCMAKE_INSTALL_PREFIX=/opt/grpc ../.. && \
    make -j8 && \
    make install

# level-zero 1.24.2
WORKDIR /home/tfcc/3rd_build
RUN git clone https://github.com/oneapi-src/level-zero.git
WORKDIR /home/tfcc/3rd_build/level-zero
RUN git checkout v1.24.2 && \
    mkdir build
WORKDIR /home/tfcc/3rd_build/level-zero/build
RUN cmake .. -DCMAKE_INSTALL_PREFIX=/opt/intel/level-zero && \
    cmake --build . --config Release --target install 

### Install libradar
WORKDIR /home/tfcc/3rd_build
RUN curl -s https://eci.intel.com/sed-repos/gpg-keys/GPG-PUB-KEY-INTEL-SED.gpg | tee /usr/share/keyrings/sed-archive-keyring.gpg > /dev/null
RUN echo "deb [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | tee /etc/apt/sources.list.d/sed.list
RUN echo "deb-src [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | tee -a /etc/apt/sources.list.d/sed.list
RUN bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/sed'
RUN apt update -y && \
    apt install libradar && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# openclsdk
WORKDIR /home/tfcc/3rd_build
RUN apt update && \
	apt install -y -q --no-install-recommends vulkan-tools libvulkan-dev && \
	git clone --recursive -b v2025.07.23 https://github.com/KhronosGroup/OpenCL-SDK.git
WORKDIR /home/tfcc/3rd_build/OpenCL-SDK/build
RUN cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr && \
	cmake --build . --target install --config Release

# clean build files
RUN rm -rf /home/tfcc/3rd_build /tmp/*

ENV PATH="/python3venv/bin:${PATH}"

# ==============================================================================
# gstreamer builder stage
# ==============================================================================
FROM builder AS gstreamer-builder
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

# Build GStreamer
WORKDIR /home/tfcc

RUN git clone https://gitlab.freedesktop.org/gstreamer/gstreamer.git

ENV PKG_CONFIG_PATH=/usr/lib/x86_64-linux-gnu/pkgconfig/:/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH

RUN ldconfig

RUN apt update && \
    apt install -y -q --no-install-recommends libogg-dev libxv-dev && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# GStreamer core
RUN \
    mkdir -p "$GSTREAMER_SRC_DIR" && \
    wget --quiet --no-check-certificate ${GST_REPO}/gstreamer/gstreamer-${GST_VERSION}.tar.xz -O "$GSTREAMER_SRC_DIR"/gstreamer-${GST_VERSION}.tar.xz && \
    tar -xf "$GSTREAMER_SRC_DIR"/gstreamer-${GST_VERSION}.tar.xz -C "$GSTREAMER_SRC_DIR" && \
    rm "$GSTREAMER_SRC_DIR"/gstreamer-${GST_VERSION}.tar.xz

WORKDIR "$GSTREAMER_SRC_DIR"/gstreamer-${GST_VERSION}

RUN \
    meson setup \
    -Dexamples=disabled \
    -Dtests=disabled \
    -Dbenchmarks=disabled \
    -Dpackage-origin="${PACKAGE_ORIGIN}" \
    --buildtype="${BUILD_ARG}" \
    --prefix=/ \
    --libdir=lib/ \
    --libexecdir=bin/ \
    build/ && \
    ninja -C build && \
    meson install -C build/ && \
    DESTDIR=/opt/gstreamer meson install -C build/

ENV PKG_CONFIG_PATH="${GSTREAMER_DIR}/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH"
ENV LD_LIBRARY_PATH="${GSTREAMER_DIR}/lib:/usr/lib:/usr/local/lib"

#Build vorbis
RUN \
    mkdir -p /src/vorbis && \
    wget -q --no-check-certificate ${VORBIS_URL} -O /src/vorbis/libvorbis-${VORBIS_VERSION}.tar.xz && \
    tar -xf /src/vorbis/libvorbis-${VORBIS_VERSION}.tar.xz -C /src/vorbis && \
    rm /src/vorbis/libvorbis-${VORBIS_VERSION}.tar.xz

WORKDIR /src/vorbis/libvorbis-${VORBIS_VERSION}

RUN \
    ./autogen.sh && \
    ./configure --disable-dependency-tracking && \
    make -j "$(nproc)" && \
    make install

# Build the gstreamer plugin base
RUN \
    wget --quiet --no-check-certificate ${GST_REPO}/gst-plugins-base/gst-plugins-base-${GST_VERSION}.tar.xz -O "$GSTREAMER_SRC_DIR"/gst-plugins-base-${GST_VERSION}.tar.xz && \
    tar -xf "$GSTREAMER_SRC_DIR"/gst-plugins-base-${GST_VERSION}.tar.xz -C "$GSTREAMER_SRC_DIR" && \
    rm "$GSTREAMER_SRC_DIR"/gst-plugins-base-${GST_VERSION}.tar.xz

WORKDIR "$GSTREAMER_SRC_DIR"/gst-plugins-base-${GST_VERSION}

RUN \
    meson setup \
    -Dexamples=disabled \
    -Dtests=disabled \
    -Dnls=disabled \
    -Dgl=disabled \
    -Dxvideo=enabled \
    -Dpackage-origin="${PACKAGE_ORIGIN}" \
    --buildtype="${BUILD_ARG}" \
    --prefix=/ \
    --libdir=lib/ \
    --libexecdir=bin/ \
    build/ && \
    ninja -C build && \
    meson install -C build/ && \
    DESTDIR=/opt/gstreamer meson install -C build/

ENV PKG_CONFIG_PATH="${GSTREAMER_DIR}/lib/pkgconfig:/usr/lib/x86_64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH"
ENV LD_LIBRARY_PATH="${GSTREAMER_DIR}/lib:/usr/lib:/usr/local/lib"

# ==============================================================================
# project builder stage
# ==============================================================================
FROM gstreamer-builder AS project-builder
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN apt update && \
    apt install -y -q --no-install-recommends libeigen3-dev libuv1-dev libfmt-dev libdrm-dev && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Build Project
COPY . /home/tfcc/metro
WORKDIR /home/tfcc/metro
RUN rm -rf build
WORKDIR /home/tfcc/metro/ai_inference/liblidar
RUN rm -rf build liblidar.so
RUN /bin/bash -c "bash build.sh"
WORKDIR /home/tfcc/metro
RUN /bin/bash -c "bash build.sh"
RUN rm -rf /home/tfcc/metro/ai_inference/liblidar/build

# ---------- Runtime Stage ----------
FROM $BASE:${BASE_VERSION} AS runtime
USER root
WORKDIR /
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive

RUN apt update && \
    apt install -y -q --no-install-recommends libtbb12 curl gpg ca-certificates ocl-icd-libopencl1 sudo && \
    rm -rf /var/lib/apt/lists/*

# Intel GPU client drivers and prerequisites installation
RUN curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu noble unified" |\
    tee /etc/apt/sources.list.d/intel-gpu-noble.list

RUN apt update && \
    apt install --allow-downgrades -y -q --no-install-recommends libze-intel-gpu1 libze1 \
    intel-media-va-driver-non-free intel-gsc intel-opencl-icd && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# Intel NPU drivers and prerequisites installation
WORKDIR /tmp/npu_deps
RUN curl -LO https://github.com/oneapi-src/level-zero/releases/download/v1.24.2/level-zero_1.24.2+u24.04_amd64.deb && \
    dpkg -i level-zero_1.24.2+u24.04_amd64.deb && \
    curl -LO https://github.com/intel/linux-npu-driver/releases/download/v1.24.0/linux-npu-driver-v1.24.0.20251003-18218973328-ubuntu2404.tar.gz && \
    tar -xf linux-npu-driver-v1.24.0.20251003-18218973328-ubuntu2404.tar.gz && \
    dpkg -i ./*.deb && \
    rm -rf /var/lib/apt/lists/* /tmp/npu_deps

# create user and set permissions
RUN useradd -ms /bin/bash -G video,users,sudo tfcc && \
	echo 'tfcc:intel' | chpasswd && \
	chown tfcc -R /home/tfcc

RUN apt update && \
	apt install -y -q --no-install-recommends autoconf automake libtool build-essential g++ \
	bison pkg-config flex curl git git-lfs vim dkms cmake make wget \
	debhelper devscripts mawk openssh-server libssl-dev libeigen3-dev libopencv-dev opencv-data \
	opencl-headers opencl-dev intel-gpu-tools va-driver-all libmfxgen1 libvpl2 \
	libx11-dev libx11-xcb-dev libxcb-dri3-dev libxext-dev libxfixes-dev libwayland-dev \
	libgtk2.0-0 libgl1 libsm6 libxext6 x11-apps && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

RUN curl -k -o GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB -L && \
	apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && rm GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB && \
	echo "deb https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
	apt update -y && \
	apt install -y intel-oneapi-runtime-mkl intel-oneapi-compiler-dpcpp-cpp-runtime lsb-release && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# xpu_smi
WORKDIR /tmp/
RUN apt update && \
	apt install -y -q --no-install-recommends intel-gsc && \
	curl -k -o xpu-smi_1.3.3_20250926.101214.8a6b6526.u24.04_amd64.deb https://github.com/intel/xpumanager/releases/download/v1.3.3/xpu-smi_1.3.3_20250926.101214.8a6b6526.u24.04_amd64.deb -L && \
	dpkg -i xpu-smi_*.deb && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* /tmp/*

RUN apt autoremove -y

# copy build artifacts and project files
COPY --from=project-builder /opt/intel/openvino_2025 /opt/intel/openvino_2025
COPY --from=project-builder /opt/intel/media /opt/intel/media
COPY --from=project-builder /opt/intel/level-zero /opt/intel/level-zero
COPY --from=project-builder /opt/grpc /opt/grpc
COPY --from=project-builder /opt/gstreamer /opt/gstreamer
COPY --from=project-builder /usr/local /usr/local
COPY --from=project-builder /usr/include /usr/include
COPY --from=project-builder /usr/lib /usr/lib
COPY --from=project-builder /lib/x86_64-linux-gnu /lib/x86_64-linux-gnu

COPY --from=project-builder /home/tfcc/metro /home/tfcc/metro

# environment variables and bashrc configuration
RUN echo "source /opt/intel/openvino_2025/setupvars.sh" >> /home/tfcc/.bashrc && \
	echo "source /opt/intel/media/etc/vpl/vars.sh" >> /home/tfcc/.bashrc && \
	echo "source /opt/intel/oneapi/setvars.sh" >> /home/tfcc/.bashrc
ENV PROJ_DIR=/home/tfcc/metro
RUN ln -s $PROJ_DIR/ai_inference/deployment/datasets /opt/datasets && \
	ln -s $PROJ_DIR/ai_inference/deployment/models /opt/models && \
	cp $PROJ_DIR/ai_inference/deployment/datasets/radarResults.csv /opt

RUN chown tfcc -R /home/tfcc
USER tfcc
WORKDIR /home/tfcc

ENV GST_PLUGIN_PATH=/opt/gstreamer/lib/gstreamer-1.0:/opt/gstreamer/lib/
ENV LD_LIBRARY_PATH=/opt/gstreamer/lib:/usr/lib:/usr/local/lib/gstreamer-1.0:/usr/local/lib

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD (test -d /home/tfcc/metro) || exit 1

ENTRYPOINT ["/bin/bash", "-c", "source /home/tfcc/.bashrc && bash"]

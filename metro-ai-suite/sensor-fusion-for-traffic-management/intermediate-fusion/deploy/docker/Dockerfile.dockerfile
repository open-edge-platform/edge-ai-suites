# syntax=docker/dockerfile:1.4
ARG BASE=ubuntu
ARG BASE_VERSION=24.04
ARG ONEAPI_VERSION=2025.3
ARG CUSTOM_OPENVINO_INSTALL_DIR

# ==============================================================================
# base builder stage
# ==============================================================================
FROM $BASE:${BASE_VERSION} AS builder

ARG DEBIAN_FRONTEND=noninteractive
ARG ONEAPI_VERSION
ARG CUSTOM_OPENVINO_INSTALL_DIR

SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN apt update && \
    apt install -y -q --no-install-recommends libtbb12 curl gpg ca-certificates ocl-icd-libopencl1

# Intel GPU client drivers and prerequisites installation
RUN curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu noble unified" |\
    tee /etc/apt/sources.list.d/intel-gpu-noble.list

RUN apt update && \
    apt install -y -q --no-install-recommends intel-media-va-driver-non-free intel-gsc

# Intel GPU drivers and prerequisites installation
WORKDIR /tmp/neo_deps
RUN IGC_VERSION=2.32.7 && \
    IGC_BUILD=21184 && \
    NEO_VERSION=26.14.37833.4 && \
    GMM_VERSION=22.9.0 && \
    LEVEL_ZERO_PKG=level-zero_1.28.2+u24.04_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/oneapi-src/level-zero/releases/download/v1.28.2/${LEVEL_ZERO_PKG} && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/intel-graphics-compiler/releases/download/v${IGC_VERSION}/intel-igc-core-2_${IGC_VERSION}+${IGC_BUILD}_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/intel-graphics-compiler/releases/download/v${IGC_VERSION}/intel-igc-opencl-2_${IGC_VERSION}+${IGC_BUILD}_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-ocloc-dbgsym_${NEO_VERSION}-0_amd64.ddeb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-ocloc_${NEO_VERSION}-0_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-opencl-icd-dbgsym_${NEO_VERSION}-0_amd64.ddeb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-opencl-icd_${NEO_VERSION}-0_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/libigdgmm12_${GMM_VERSION}_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/libze-intel-gpu1-dbgsym_${NEO_VERSION}-0_amd64.ddeb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/libze-intel-gpu1_${NEO_VERSION}-0_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/ww14.sum && \
    sha256sum -c ww14.sum && \
    dpkg -i ./*.deb || apt-get -f install -y && \
    rm -rf /tmp/neo_deps

# Intel NPU drivers and prerequisites installation
WORKDIR /tmp/npu_deps
RUN apt update && \
    curl -LO https://github.com/intel/linux-npu-driver/releases/download/v1.32.1/linux-npu-driver-v1.32.1.20260422-24767473183-ubuntu2404.tar.gz && \
    tar -xf linux-npu-driver-v1.32.1.20260422-24767473183-ubuntu2404.tar.gz && \
    apt install ./intel-*.deb && \
    rm -rf /tmp/npu_deps

USER root
WORKDIR /

# create user and set permissions
RUN useradd -ms /bin/bash -G video,users,sudo tfcc && \
	echo 'tfcc:intel' | chpasswd && \
	chown tfcc -R /home/tfcc

RUN apt update && \
	apt install -y -q --no-install-recommends autoconf automake libtool build-essential g++ \
	bison pkg-config flex curl git git-lfs vim dkms cmake make wget \
	debhelper devscripts mawk openssh-server libssl-dev libopencv-dev opencv-data \
    && apt clean && \
    rm -rf /var/lib/apt/lists/*

USER root

# download 3rd libs
WORKDIR /home/tfcc/3rd_build
RUN curl -fL --retry 5 --retry-delay 2 --retry-connrefused \
	-o boost_1_83_0.tar.gz \
	https://phoenixnap.dl.sourceforge.net/project/boost/boost/1.83.0/boost_1_83_0.tar.gz && \
    tar -zxf boost_1_83_0.tar.gz && \
    rm -f boost_1_83_0.tar.gz

# boost 1.83.0
WORKDIR /home/tfcc/3rd_build/boost_1_83_0
RUN ./bootstrap.sh --with-libraries=all --with-toolset=gcc && \
    ./b2 toolset=gcc && ./b2 install && ldconfig

# oneapi
RUN curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | \
    gpg --dearmor -o /usr/share/keyrings/intel-oneapi.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/intel-oneapi.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
    apt update -y && \
    apt install -y intel-oneapi-base-toolkit-${ONEAPI_VERSION} lsb-release && \
    apt clean && \
    rm -rf /var/lib/apt/lists/*

# custom OpenVINO install
RUN rm -rf /opt/intel/openvino /opt/intel/openvino_2026 && \
    mkdir -p /opt/intel/openvino
COPY --from=custom_openvino . /opt/intel/openvino
RUN test -n "${CUSTOM_OPENVINO_INSTALL_DIR}" && \
    test -f /opt/intel/openvino/setupvars.sh && \
    test -d /opt/intel/openvino/runtime && \
    source /opt/intel/openvino/setupvars.sh >/dev/null 2>&1

# openclsdk
WORKDIR /home/tfcc/3rd_build
RUN apt update && \
	apt install -y -q --no-install-recommends vulkan-tools libvulkan-dev && \
	git clone --recursive -b v2025.07.23 https://github.com/KhronosGroup/OpenCL-SDK.git
WORKDIR /home/tfcc/3rd_build/OpenCL-SDK/build
RUN cmake .. -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr && \
	cmake --build . --target install --config Release

# clean build files
RUN rm -rf /home/tfcc/3rd_build /tmp/* /var/lib/apt/lists/*

# ==============================================================================
# project builder stage
# ==============================================================================
FROM builder AS project-builder
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]

RUN apt update && \
    apt install -y -q --no-install-recommends libeigen3-dev libuv1-dev libfmt-dev libdrm-dev && \
    apt clean

# Build Project
COPY . /home/tfcc/bevfusion
WORKDIR /home/tfcc/bevfusion
RUN rm -rf build
WORKDIR /home/tfcc/bevfusion
RUN /bin/bash -c "bash build.sh"

# ---------- Runtime Stage ----------
FROM $BASE:${BASE_VERSION} AS runtime
USER root
WORKDIR /
SHELL ["/bin/bash", "-xo", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
ARG ONEAPI_VERSION

RUN apt update && \
    apt install -y -q --no-install-recommends libtbb12 curl gpg ca-certificates ocl-icd-libopencl1 sudo

# Intel GPU client drivers and prerequisites installation
RUN curl -fsSL https://repositories.intel.com/gpu/intel-graphics.key | \
    gpg --dearmor -o /usr/share/keyrings/intel-graphics.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu noble unified" |\
    tee /etc/apt/sources.list.d/intel-gpu-noble.list

RUN apt update && \
    apt install -y -q --no-install-recommends intel-media-va-driver-non-free intel-gsc && \
    apt clean

# Intel GPU drivers and prerequisites installation
WORKDIR /tmp/neo_deps
RUN IGC_VERSION=2.32.7 && \
    IGC_BUILD=21184 && \
    NEO_VERSION=26.14.37833.4 && \
    GMM_VERSION=22.9.0 && \
    LEVEL_ZERO_PKG=level-zero_1.28.2+u24.04_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/oneapi-src/level-zero/releases/download/v1.28.2/${LEVEL_ZERO_PKG} && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/intel-graphics-compiler/releases/download/v${IGC_VERSION}/intel-igc-core-2_${IGC_VERSION}+${IGC_BUILD}_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/intel-graphics-compiler/releases/download/v${IGC_VERSION}/intel-igc-opencl-2_${IGC_VERSION}+${IGC_BUILD}_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-ocloc-dbgsym_${NEO_VERSION}-0_amd64.ddeb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-ocloc_${NEO_VERSION}-0_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-opencl-icd-dbgsym_${NEO_VERSION}-0_amd64.ddeb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/intel-opencl-icd_${NEO_VERSION}-0_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/libigdgmm12_${GMM_VERSION}_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/libze-intel-gpu1-dbgsym_${NEO_VERSION}-0_amd64.ddeb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/libze-intel-gpu1_${NEO_VERSION}-0_amd64.deb && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused -O https://github.com/intel/compute-runtime/releases/download/${NEO_VERSION}/ww14.sum && \
    sha256sum -c ww14.sum && \
    dpkg -i ./*.deb || apt-get -f install -y && \
    rm -rf /tmp/neo_deps

# Intel NPU drivers and prerequisites installation
WORKDIR /tmp/npu_deps
RUN apt update && \
    curl -LO https://github.com/intel/linux-npu-driver/releases/download/v1.32.1/linux-npu-driver-v1.32.1.20260422-24767473183-ubuntu2404.tar.gz && \
    tar -xf linux-npu-driver-v1.32.1.20260422-24767473183-ubuntu2404.tar.gz && \
    apt install ./intel-*.deb && \
    rm -rf /tmp/npu_deps

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
    apt clean

RUN curl -fsSL https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | \
    gpg --dearmor -o /usr/share/keyrings/intel-oneapi.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/intel-oneapi.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list && \
    apt update -y && \
    apt install -y intel-oneapi-base-toolkit-runtime-${ONEAPI_VERSION} lsb-release && \
    apt clean

# xpu_smi
WORKDIR /tmp/
RUN apt update && \
	apt install -y -q --no-install-recommends intel-gsc && \
    curl -fL --retry 5 --retry-delay 2 --retry-connrefused \
        -o xpu-smi_1.3.6_20260206.143628.1004f6cb.u24.04_amd64.deb \
        https://github.com/intel/xpumanager/releases/download/v1.3.6/xpu-smi_1.3.6_20260206.143628.1004f6cb.u24.04_amd64.deb && \
    dpkg -i xpu-smi_*.deb || true && \
    apt-get update && apt-get -f install -y && \
    apt clean && \
    rm -rf /var/lib/apt/lists/* /tmp/*

RUN apt autoremove -y

# copy build artifacts and project files
COPY --from=project-builder /opt/intel/openvino /opt/intel/openvino
COPY --from=project-builder /usr/local /usr/local

COPY --from=project-builder /home/tfcc/bevfusion /home/tfcc/bevfusion

# environment variables and bashrc configuration
RUN echo "source /opt/intel/openvino/setupvars.sh" >> /home/tfcc/.bashrc && \
	echo "source /opt/intel/oneapi/setvars.sh" >> /home/tfcc/.bashrc
ENV PROJ_DIR=/home/tfcc/bevfusion
RUN ln -sfn $PROJ_DIR/deploy/data/v2xfusion/second /opt/models

RUN chown tfcc -R /home/tfcc
USER tfcc
WORKDIR /home/tfcc

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD (test -d /home/tfcc/bevfusion) || exit 1

ENTRYPOINT ["/bin/bash", "-c", "source /home/tfcc/.bashrc && bash"]

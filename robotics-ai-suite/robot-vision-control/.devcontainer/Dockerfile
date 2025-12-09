###########################################
# Base image
###########################################
ARG ROS_DISTRO=humble
ARG UBUNTU_VERSION=22.04
FROM ubuntu:${UBUNTU_VERSION} AS rvc-base

ARG ROS_DISTRO
ARG PYTHON_VERSION=3.10

ENV DEBIAN_FRONTEND=noninteractive

# Install language
RUN apt-get update && apt-get install -y \
  locales \
  && locale-gen en_US.UTF-8 \
  && update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8 \
  && rm -rf /var/lib/apt/lists/*
ENV LANG en_US.UTF-8

# Install timezone
RUN ln -fs /usr/share/zoneinfo/UTC /etc/localtime \
  && export DEBIAN_FRONTEND=noninteractive \
  && apt-get update \
  && apt-get install -y tzdata \
  && dpkg-reconfigure --frontend noninteractive tzdata \
  && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get -y upgrade \
  && rm -rf /var/lib/apt/lists/*

# Install common programs
RUN apt-get update && apt-get install -y --no-install-recommends \
  curl \
  gnupg2 \
  lsb-release \
  sudo \
  software-properties-common \
  wget \
  python3-venv \
  && rm -rf /var/lib/apt/lists/*

# Install ROS2
RUN sudo add-apt-repository universe \
  && curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null \
  && apt-get update && apt-get install -y --no-install-recommends \
  ros-${ROS_DISTRO}-ros-base \
  python3-argcomplete \
  && rm -rf /var/lib/apt/lists/*

RUN bash -c 'wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/intel-repo-keyring.gpg > /dev/null' \
  && bash -c 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/intel-repo-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list' \
  && bash -c 'echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/intel-repo-keyring.gpg] https://apt.repos.intel.com/openvino/2024 ubuntu22 main" | tee /etc/apt/sources.list.d/intel-openvino-2024.list' \
  && apt-get update && apt-get install -y --no-install-recommends \
  ros-${ROS_DISTRO}-controller-manager \
  ros-${ROS_DISTRO}-control-toolbox \
  ros-${ROS_DISTRO}-xacro \
  ros-${ROS_DISTRO}-librealsense2 \
  ros-${ROS_DISTRO}-realsense2-camera \
  ros-${ROS_DISTRO}-realsense2-description \
  ros-${ROS_DISTRO}-pcl-conversions \
  ros-${ROS_DISTRO}-diagnostic-updater \
  ros-${ROS_DISTRO}-joint-state-broadcaster \
  ros-${ROS_DISTRO}-joint-trajectory-controller \
  ros-${ROS_DISTRO}-joint-state-publisher \
  ros-${ROS_DISTRO}-forward-command-controller \
  ros-${ROS_DISTRO}-moveit-ros-planning \
  ros-${ROS_DISTRO}-moveit-ros-planning-interface \
  ros-${ROS_DISTRO}-moveit-ros-visualization \
  ros-${ROS_DISTRO}-moveit-servo \
  ros-${ROS_DISTRO}-velocity-controllers \
  ros-${ROS_DISTRO}-position-controllers \
  ros-${ROS_DISTRO}-forward-command-controller \
  ros-${ROS_DISTRO}-moveit-ros-visualization \
  ros-${ROS_DISTRO}-compressed-depth-image-transport \
  ros-${ROS_DISTRO}-compressed-image-transport \
  ros-${ROS_DISTRO}-image-transport-plugins \
  openvino-libraries-dev \
  nlohmann-json3-dev \
  libnlopt-cxx-dev \
  && rm -rf /var/lib/apt/lists/*

# Add Intel GPU repo key / Add Intel GPU repo / Install GPU runtime packages
RUN wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg \
  && echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | tee /etc/apt/sources.list.d/intel-gpu-jammy.list \
  && apt update \
  && apt-get install -y libze-intel-gpu1=24.52.32224.14-1077~22.04 libze1=1.19.2.0-1077~22.04 intel-opencl-icd=24.52.32224.14-1077~22.04 clinfo xpu-smi

# Add Intel ECI repo key / Pinning preferences
RUN wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null \
  && echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/jammy isar main" | tee /etc/apt/sources.list.d/eci.list \
  && echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/jammy isar main" | tee -a /etc/apt/sources.list.d/eci.list \
  && echo "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/isar 
RUN cat /etc/apt/preferences.d/isar 

# Install the NPU Libraries
RUN apt-get update && apt-get install -y level-zero* intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu

ENV ROS_DISTRO=${ROS_DISTRO}
ENV PYTHON_VERSION=${PYTHON_VERSION}
ENV AMENT_PREFIX_PATH=/opt/ros/${ROS_DISTRO}
ENV COLCON_PREFIX_PATH=/opt/ros/${ROS_DISTRO}
ENV LD_LIBRARY_PATH=/opt/ros/${ROS_DISTRO}/lib
ENV PATH=/opt/ros/${ROS_DISTRO}/bin:$PATH
ENV PYTHONPATH=/opt/ros/${ROS_DISTRO}/lib/python${PYTHON_VERSION}/site-packages
ENV ROS_PYTHON_VERSION=3
ENV ROS_VERSION=2
ENV DEBIAN_FRONTEND=

###########################################
#  Development image
###########################################
ARG ROS_DISTRO=humble
ARG USER_UID=1000
FROM rvc-base AS rvc-dev

ARG ROS_DISTRO
ARG USER_UID

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
  bash-completion \
  build-essential \
  cmake \
  gdb \
  git \
  openssh-client \
  python3-argcomplete \
  python3-pip \
  ros-dev-tools \
  ros-${ROS_DISTRO}-ament-* \
  vim \
  && rm -rf /var/lib/apt/lists/*

RUN rosdep init || echo "rosdep already initialized"

ARG USERNAME=ros
ARG USER_GID=$USER_UID

# Create a non-root user
RUN groupadd --gid $USER_GID $USERNAME \
  && useradd -s /bin/bash --uid $USER_UID --gid $USER_GID -m $USERNAME \
  # Add sudo support for the non-root user
  && apt-get update \
  && apt-get install -y sudo \
  && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME\
  && chmod 0440 /etc/sudoers.d/$USERNAME \
  && rm -rf /var/lib/apt/lists/*

# Set up autocompletion for user
RUN apt-get update && apt-get install -y git-core bash-completion \
  && echo "if [ -f /opt/ros/${ROS_DISTRO}/setup.bash ]; then source /opt/ros/${ROS_DISTRO}/setup.bash; fi" >> /home/$USERNAME/.bashrc \
  && echo "if [ -f /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash ]; then source /usr/share/colcon_argcomplete/hook/colcon-argcomplete.bash; fi" >> /home/$USERNAME/.bashrc \
  && rm -rf /var/lib/apt/lists/* 

ENV DEBIAN_FRONTEND=
ENV AMENT_CPPCHECK_ALLOW_SLOW_VERSIONS=1

# Set up auto-source of workspace for ros user
ARG WORKSPACE=/rvc
RUN echo "if [ -f ${WORKSPACE}/install/setup.bash ]; then source ${WORKSPACE}/install/setup.bash; fi" >> /home/$USERNAME/.bashrc

FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive
# example build command: docker build --build-arg HTTP_PROXY=$http_proxy --build-arg https_proxy=$https_proxy --build-arg no_proxy=$no_proxy -t my-rvc-container .
# example run command: docker run --env http_proxy=$http_proxy  --env https_proxy=$https_proxy --env no_proxy=$no_proxy -it --rm my-rvc-container /bin/bash

# 1. and 2. Update system, set up additional repos and install dependencies
RUN apt-get update && apt-get upgrade -y && apt-get install -y git wget curl gpg sudo ocl-icd-libopencl1 \
  && wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/intel-repo-keyring.gpg > /dev/null \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/intel-repo-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/intel-repo-keyring.gpg] https://apt.repos.intel.com/openvino/2023 ubuntu22 main" | tee /etc/apt/sources.list.d/intel-openvino-2023.list \
  && apt-get update

# 3. Install OpenCL support for intel graphics
RUN wget https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.15136.4/intel-igc-core_1.0.15136.4_amd64.deb \
  && wget https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.15136.4/intel-igc-opencl_1.0.15136.4_amd64.deb \
  && wget https://github.com/intel/compute-runtime/releases/download/23.35.27191.9/intel-level-zero-gpu_1.3.27191.9_amd64.deb \
  && wget https://github.com/intel/compute-runtime/releases/download/23.35.27191.9/intel-opencl-icd_23.35.27191.9_amd64.deb \
  && wget https://github.com/intel/compute-runtime/releases/download/23.35.27191.9/libigdgmm12_22.3.11.ci17747749_amd64.deb \
  && dpkg -i intel-igc-core_1.0.15136.4_amd64.deb intel-igc-opencl_1.0.15136.4_amd64.deb intel-level-zero-gpu_1.3.27191.9_amd64.deb libigdgmm12_22.3.11.ci17747749_amd64.deb intel-opencl-icd_23.35.27191.9_amd64.deb

# 4. Install Real time kernel from ECI
RUN wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null \
  && echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(. /etc/os-release && echo $VERSION_CODENAME) isar main" | tee /etc/apt/sources.list.d/eci.list \
  && echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(. /etc/os-release && echo $VERSION_CODENAME) isar main" | tee -a /etc/apt/sources.list.d/eci.list \
  && bash -c echo -e "Package: *\nPin: origin archive.ubuntu.com\nPin-Priority: 1000" | tee /etc/apt/preferences.d/isar \
  && apt-get update && apt-get upgrade -y && apt-get install -y customizations-grub customizations-system linux-intel-rt && apt-get reinstall -y '(firmware-linux-nonfree|linux-firmware$)'

# oneapi repo has a bug, install specific version
RUN apt-get install -y intel-oneapi-runtime-dpcpp-cpp=2023.2.3-20 intel-oneapi-runtime-compilers=2023.2.3-20 intel-oneapi-runtime-openmp=2023.2.3-20 intel-oneapi-runtime-dpcpp-cpp=2023.2.3-20 \
      intel-oneapi-runtime-compilers-common=2023.2.3-20 intel-oneapi-runtime-dpcpp-cpp-common=2023.2.3-20 intel-oneapi-runtime-opencl=2023.2.3-20

# Install ros
RUN wget -O- https://raw.githubusercontent.com/ros/rosdistro/master/ros.key | tee /usr/share/keyrings/ros-archive-keyring.gpg > /dev/null \
  && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) main" | tee /etc/apt/sources.list.d/ros2.list \
  && wget -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor | tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null \
  && echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | tee /etc/apt/sources.list.d/oneAPI.list \
  && apt-get update \
  && apt-get install -y libopen62541-osadl-dev python3-colcon-common-extensions python3-rosdep ros-humble-desktop ros-humble-controller-manager ros-humble-xacro ros-humble-control-toolbox \
      ros-humble-librealsense2 ros-humble-diagnostic-updater ros-humble-joint-state-broadcaster ros-humble-joint-trajectory-controller ros-humble-joint-state-publisher ros-humble-forward-command-controller \
      libnlopt-dev libnlopt-cxx-dev ros-humble-moveit-msgs libyaml-cpp-dev ros-humble-realsense2-camera ros-humble-realsense2-description ros-humble-realsense2-camera-msgs \
      libpugixml1v5 python3-pip ros-humble-moveit-ros-planning ros-humble-moveit-ros-planning-interface ros-humble-velocity-controllers ros-humble-position-controllers \ 
      ros-humble-forward-command-controller ros-humble-moveit-ros-visualization ros-humble-compressed-depth-image-transport ros-humble-compressed-image-transport ros-humble-image-transport-plugins \
      ros-humble-image-transport ros-humble-theora-image-transport ros-humble-moveit-servo intel-gpu-tools nlohmann-json3-dev openvino openvino-libraries-dev python3-vcstool ros-humble-ur-bringup \
      ros-humble-ur-robot-driver ros-humble-urdf ros-humble-ur-calibration ros-humble-pick-ik unzip

# 5. Configure user
RUN useradd ros -m -d /rvc \
  && passwd -d ros \
  && rosdep init \
  && usermod -aG video,render,adm,sudo ros \
  && echo "ros soft rtprio   98" | sudo tee -a /etc/security/limits.conf \
  && echo "ros soft priority 99" | sudo tee -a /etc/security/limits.conf  \
  && echo "ros hard priority 99" | sudo tee -a /etc/security/limits.conf  \
  && echo "ros soft memlock  102400" | sudo tee -a /etc/security/limits.conf  \
  && echo "ros hard memlock  102400" | sudo tee -a /etc/security/limits.conf  \
  && echo "ros - memlock     51200" | sudo tee -a /etc/security/limits.conf  \
  && echo "ros - rtprio      99" | sudo tee -a /etc/security/limits.conf 

# Set up RVC repo and install
COPY --chown=ros . root
#base=$(basename -- $(find . -name "Robot_Vision_and_Control*.zip" | sort | tail -n 1  ))
RUN bash -c 'cd ~  && filename=$(find . -name "Robot_Vision_and_Control*.zip" | sort | tail -n 1  ) && base=${filename%.*} \
  && unzip "$base.zip" && tar zxvf "$base.tar.gz" \
  && gpg --full-gen-key --batch <(echo "Key-Type: 1"; \
                             echo "Key-Length: 4096"; \
                             echo "Subkey-Type: 1"; \
                             echo "Subkey-Length: 4096"; \
                             echo "Expire-Date: 0"; \
                             echo "Name-Real: ros user"; \
                             echo "Name-Email: ros@intel.com"; \
                             echo "%no-protection"; ) \
  && echo 'deb [trusted=yes] file:/rvc/ubuntu-jammy isar main' | sudo tee -a /etc/apt/sources.list \
  && gpg --export --armor `gpg --keyid-format short --list-keys | grep 'pub\ ' | awk -F '/' '{print $2 }' | awk -F ' ' '{ print $1}'` | sudo apt-key add --  \
  && apt-get -o Acquire::GzipIndexes=false update \
  && apt install ros-humble-ur-pendant-motion-controller'

USER ros
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc

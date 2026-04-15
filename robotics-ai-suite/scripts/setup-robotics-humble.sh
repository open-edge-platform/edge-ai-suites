#!/bin/bash

set -e
export DEBIAN_FRONTEND=noninteractive

DEBUG=${DEBUG:-0}
if [ "$DEBUG" = "1" ]; then
    WGET_QUIET=""
    CURL_QUIET="-L"
else
    WGET_QUIET="-q"
    CURL_QUIET="-sSL"
fi

USE_PROXY=${USE_PROXY:-0}
if [ "$USE_PROXY" = "1" ]; then
    OPENVINO_PROXY_SELECT="true"
else
    OPENVINO_PROXY_SELECT="false"
fi

run() {
    if [ "$DEBUG" = "1" ]; then
        "$@"
    else
        "$@" > /dev/null 2>&1
    fi
}

STEP=0
TOTAL=25
step() {
    STEP=$((STEP + 1))
    echo "${STEP}/${TOTAL} ==> $1"
}

# Function to handle the Ctrl+C event
cleanup_handler() {
    printf "\\n** Ctrl+C detected. Performing cleanup...\\n" >&2

    # Reset the trap to its default behavior and re-send the signal to terminate
    # This is a robust way to ensure the script properly exits
    trap - INT
    kill -INT "$$"
}

# Trap the SIGINT signal and call the cleanup_handler function
trap 'cleanup_handler' INT

step "Removing previously installed packages..."
run sudo apt remove -y --purge "*oneapi*" "ros-*" "*openvino*" "*gazebo*" "*realsense*" || :
run sudo apt remove -y --purge "intel-igc*" || :
run sudo apt remove -y --purge "*level-zero*" || :
run sudo apt remove -y --purge "libze1" || :
sudo rm -f "/etc/apt/sources.list.d/*" || :

step "Updating package lists and cleaning up..."
run sudo apt update
run sudo apt autoremove -y

step "Installing GCC 12..."
run sudo apt install -y gcc-12 g++-12
run sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 60 --slave /usr/bin/g++ g++ /usr/bin/g++-12

step "Installing prerequisites..."
run sudo apt install -y software-properties-common
run sudo add-apt-repository -y universe

step "Installing curl and fetching ROS 2 apt source..."
run sudo apt update
run sudo apt install curl -y
export ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F "tag_name" | awk -F\" '{print $4}')
echo "    ROS apt source version: ${ROS_APT_SOURCE_VERSION}"
curl $CURL_QUIET -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.$(. /etc/os-release && echo ${UBUNTU_CODENAME:-${VERSION_CODENAME}})_all.deb"
run sudo dpkg -i /tmp/ros2-apt-source.deb

step "Upgrading system packages..."
run sudo apt update
run sudo apt upgrade -y

step "Installing ROS 2 Humble Desktop (this may take a while)..."
run sudo apt install -y ros-humble-desktop

step "Configuring ROS 2 environment in ~/.bashrc..."
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
echo "export ROS_DOMAIN_ID=42" >> ~/.bashrc

step "Adding Intel ECI and AMR apt repositories..."
sudo -E wget $WGET_QUIET -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null 2>&1
echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list > /dev/null
echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee -a /etc/apt/sources.list.d/eci.list > /dev/null
echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) amr main" | sudo tee /etc/apt/sources.list.d/amr.list > /dev/null
echo "deb-src [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://amrdocs.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) amr main" | sudo tee -a /etc/apt/sources.list.d/amr.list > /dev/null
echo -e "Package: *\nPin: origin amrdocs.intel.com\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/amr > /dev/null

step "Configuring Intel ECI apt pinning..."
echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" | sudo tee /etc/apt/preferences.d/isar > /dev/null
echo -e "\nPackage: libflann*\nPin: version 1.19.*\nPin-Priority: -1\n\nPackage: flann*\nPin: version 1.19.*\nPin-Priority: -1" | sudo tee -a /etc/apt/preferences.d/isar > /dev/null

step "Adding Intel oneAPI apt repository..."
wget $WGET_QUIET -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor 2>/dev/null | sudo tee /usr/share/keyrings/oneapi-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/oneapi-archive-keyring.gpg] https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list > /dev/null
echo -e "Package: intel-oneapi-runtime-*\nPin: version 2025.3.*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/oneapi > /dev/null

step "Adding Intel OpenVINO apt repository..."
wget $WGET_QUIET -O- https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB | gpg --dearmor 2>/dev/null | sudo tee /usr/share/keyrings/openvino-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/openvino-archive-keyring.gpg] https://apt.repos.intel.com/openvino/2025 ubuntu22 main" | sudo tee /etc/apt/sources.list.d/intel-openvino-2025.list > /dev/null
echo -e "\nPackage: openvino-libraries-dev\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee /etc/apt/preferences.d/intel-openvino > /dev/null
echo -e "\nPackage: openvino\nPin: version 2025.3.0*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/intel-openvino > /dev/null
echo -e "\nPackage: ros-humble-openvino-wrapper-lib\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino > /dev/null
echo -e "\nPackage: ros-humble-openvino-node\nPin: version 2025.3.0*\nPin-Priority: 1002" | sudo tee -a /etc/apt/preferences.d/intel-openvino > /dev/null

step "Updating package lists with new repositories..."
run sudo apt update

step "Installing Level Zero GPU drivers..."
run sudo apt install -y libze1 libze-intel-gpu1

step "Preparing OpenVINO installation (purging old config)..."
run sudo apt install -y debconf-utils
run sudo apt purge -y ros-humble-openvino-node || :
run sudo apt autoremove -y || :
echo PURGE | sudo debconf-communicate ros-humble-openvino-node > /dev/null 2>&1 || true

step "Installing OpenVINO base package..."
run sudo apt install -y openvino

step "Installing ROS 2 OpenVINO node..."
echo "ros-humble-openvino-node openvino-node/pip-proxy select ${OPENVINO_PROXY_SELECT}" | sudo debconf-set-selections
echo "ros-humble-openvino-node openvino-node/models select true" | sudo debconf-set-selections
run sudo -E apt install -y ros-humble-openvino-node

step "Adding Intel RealSense apt repository..."
sudo mkdir -p /etc/apt/keyrings
curl -sSf https://librealsense.realsenseai.com/Debian/librealsenseai.asc | gpg --dearmor | sudo tee /etc/apt/keyrings/librealsenseai.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/librealsenseai.gpg] https://librealsense.realsenseai.com/Debian/apt-repo `lsb_release -cs` main" | sudo tee /etc/apt/sources.list.d/librealsense.list > /dev/null
run sudo apt update
echo -e "Package: librealsense2*\nPin: version 2.55.1-0~realsense.12474\nPin-Priority: 1001\n" | sudo tee /etc/apt/preferences.d/librealsense > /dev/null
echo -e "Package: ros-humble-librealsense2*\nPin: version 2.56.4*\nPin-Priority: 1001\n" | sudo tee -a /etc/apt/preferences.d/librealsense > /dev/null
echo -e "Package: ros-humble-realsense2*\nPin: version 4.56.4*\nPin-Priority: 1001" | sudo tee -a /etc/apt/preferences.d/librealsense > /dev/null

step "Installing Intel RealSense SDK..."
run sudo apt install -y librealsense2-dkms
run sudo apt install -y librealsense2

step "Adding Gazebo apt repository..."
run sudo apt-get update
run sudo apt-get install -y curl lsb-release gnupg
run sudo -E add-apt-repository ppa:openrobotics/gazebo11-gz-cli -y
sudo -E curl -sS https://packages.osrfoundation.org/gazebo.gpg --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] https://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/gazebo-stable.list > /dev/null

step "Installing ROS 2 Robotics SDK..."
run sudo apt-get update
run sudo apt install -y ros-humble-robotics-sdk

step "Installing Collaborative SLAM (requires Intel Xe/UHD Graphics)..."
run sudo apt-get install -y ros-humble-collab-slam-lze

step "Installing Linux firmware..."
run sudo apt install -y linux-firmware

step "Installing Intel NPU drivers and configuring permissions..."
run sudo apt-get install -y intel-level-zero-npu intel-driver-compiler-npu
sudo usermod -a -G render "$USER" || :
sudo chown root:render /dev/accel/accel0 || :
sudo chmod g+rw /dev/accel/accel0 || :
sudo bash -c "echo 'SUBSYSTEM==\"accel\", KERNEL==\"accel*\", GROUP=\"render\", MODE=\"0660\"' > /etc/udev/rules.d/10-intel-vpu.rules"
run sudo udevadm control --reload-rules || :
run sudo udevadm trigger --subsystem-match=accel || :

step "Setup complete."
echo ""
echo "###########################################"
echo " Source ROS setup script to use this shell:"
echo " $ source /opt/ros/humble/setup.bash"
echo " $ export ROS_DOMAIN_ID=42"
echo "###########################################"

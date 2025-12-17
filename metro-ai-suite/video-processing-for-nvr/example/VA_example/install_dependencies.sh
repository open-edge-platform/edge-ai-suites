#!/bin/bash
echo ""
echo "************************************************************************"
echo "Install required tools and create build environment."
echo "************************************************************************"

# Install the necessary tools
echo "Please input the sudo password to proceed"
sudo apt update
sudo apt install -y ocl-icd-libopencl1 intel-opencl-icd ocl-icd-opencl-dev opencl-headers opencl-clhpp-headers
echo ""
echo "************************************************************************"
echo "Pull all the source code."
echo "************************************************************************"
CURRENT_DIR=`pwd`
WORKING_DIR="${CURRENT_DIR}/dependencies_build"
echo ${WORKING_DIR}
if [ ! -d "${WORKING_DIR}" ]
then
	sudo mkdir -p ${WORKING_DIR}
	echo "Create working directory:$WORKING_DIR"
else
	echo "Working directory exists: ${WORKING_DIR}"
fi

if [ ! -d ${WORKING_DIR}"/openvino" ]
then
	echo "************************************************************************"
	echo "Downloading openvino"
	echo "************************************************************************"

	cd $WORKING_DIR;
	sudo rm -f openvino_2024.2.0.tgz
	sudo curl -L https://storage.openvinotoolkit.org/repositories/openvino/packages/2024.2/linux/l_openvino_toolkit_ubuntu22_2024.2.0.15519.5c0f38f83f6_x86_64.tgz --output openvino_2024.2.0.tgz
	sudo tar zxf openvino_2024.2.0.tgz --one-top-level=openvino --strip-components 1
fi

if [ ! -d ${WORKING_DIR}"/neo" ]
then
	echo "************************************************************************"
	echo "Downloading neo"
	echo "************************************************************************"

	cd $WORKING_DIR;
	sudo mkdir neo
	cd neo
	sudo wget --no-check-certificate https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.17384.11/intel-igc-core_1.0.17384.11_amd64.deb
	sudo wget --no-check-certificate https://github.com/intel/intel-graphics-compiler/releases/download/igc-1.0.17384.11/intel-igc-opencl_1.0.17384.11_amd64.deb
	sudo wget --no-check-certificate https://github.com/intel/compute-runtime/releases/download/24.31.30508.7/intel-level-zero-gpu-dbgsym_1.3.30508.7_amd64.ddeb
	sudo wget --no-check-certificate https://github.com/intel/compute-runtime/releases/download/24.31.30508.7/intel-level-zero-gpu_1.3.30508.7_amd64.deb
	sudo wget --no-check-certificate https://github.com/intel/compute-runtime/releases/download/24.31.30508.7/intel-opencl-icd-dbgsym_24.31.30508.7_amd64.ddeb
	sudo wget --no-check-certificate https://github.com/intel/compute-runtime/releases/download/24.31.30508.7/intel-opencl-icd_24.31.30508.7_amd64.deb
	sudo wget --no-check-certificate https://github.com/intel/compute-runtime/releases/download/24.31.30508.7/libigdgmm12_22.4.1_amd64.deb
fi

# Install openvino
echo ""
echo "************************************************************************"
echo "Install openvino dependency"
echo "************************************************************************"

cd ${WORKING_DIR}
sudo cp -r openvino  /opt/intel/openvino_2024
cd /opt/intel/openvino_2024
sudo -E ./install_dependencies/install_openvino_dependencies.sh


# Install neo
echo ""
echo "************************************************************************"
echo "Install neo"
echo "************************************************************************"

cd ${WORKING_DIR}/neo
sudo dpkg -i *.deb

echo ""
echo "************************************************************************"
echo "Check and Install NPU drivers for Ubuntu 24.04"
echo "************************************************************************"

# Check if NPU is already installed
if [ -e "/dev/accel/accel0" ] && dpkg -l intel-driver-compiler-npu >/dev/null 2>&1; then
    echo "NPU driver is already installed, skipping installation..."
else
    # Create NPU installation directory
    cd ${WORKING_DIR}
    if [ ! -d "${WORKING_DIR}/npu" ]
    then
        sudo mkdir -p npu
        echo "Create NPU installation directory: ${WORKING_DIR}/npu"
    fi

    cd npu

    # Remove old packages if exist
    echo "Removing old NPU packages if any..."
    sudo dpkg --purge --force-remove-reinstreq intel-driver-compiler-npu intel-fw-npu intel-level-zero-npu 2>/dev/null || true

    # Download NPU packages for Ubuntu 24.04
    echo "Downloading NPU packages for Ubuntu 24.04..."
    sudo wget https://github.com/intel/linux-npu-driver/releases/download/v1.13.0/intel-driver-compiler-npu_1.13.0.20250131-13074932693_ubuntu24.04_amd64.deb
    sudo wget https://github.com/intel/linux-npu-driver/releases/download/v1.13.0/intel-fw-npu_1.13.0.20250131-13074932693_ubuntu24.04_amd64.deb
    sudo wget https://github.com/intel/linux-npu-driver/releases/download/v1.13.0/intel-level-zero-npu_1.13.0.20250131-13074932693_ubuntu24.04_amd64.deb

    # Install dependency
    echo "Installing libtbb12 dependency..."
    sudo apt update
    sudo apt install -y libtbb12

    # Check if Level Zero is installed
    if ! dpkg -l level-zero >/dev/null 2>&1; then
        echo "Level Zero not found, installing..."
        sudo wget https://github.com/oneapi-src/level-zero/releases/download/v1.18.5/level-zero_1.18.5+u24.04_amd64.deb
        sudo dpkg -i level-zero*.deb
    fi

    # Install NPU packages
    echo "Installing NPU packages..."
    sudo dpkg -i *.deb
fi

echo ""
if [ -e "/dev/accel/accel0" ]; then
    echo "[SUCCESS] NPU is ready (found /dev/accel/accel0)"
else
    echo "[WARNING] NPU device not detected. Please reboot and check:"
    echo "ls /dev/accel/accel0"
    echo "dmesg | grep intel_vpu"
fi

# Install imagenet labels
echo ""
echo "************************************************************************"
echo "Download and copy imagenet_2012.txt to VA_EXAMPLE_DIR"
echo "************************************************************************"
 
# Download imagenet_2012.txt from Open Model Zoo
IMAGENET_FILE="imagenet_2012.txt"
IMAGENET_URL="https://raw.githubusercontent.com/openvinotoolkit/open_model_zoo/master/data/dataset_classes/imagenet_2012.txt"
VA_EXAMPLE_DIR="/opt/intel/vppsdk/example/VA_example"
 
# Download the file to the script's directory
echo "Downloading $IMAGENET_FILE to script directory..."
wget -q "$IMAGENET_URL" -O "$CURRENT_DIR/$IMAGENET_FILE"
 
# Check if VA_EXAMPLE_DIR exists, create if not
if [ ! -d "$VA_EXAMPLE_DIR" ]; then
    echo "Creating directory: $VA_EXAMPLE_DIR"
    sudo mkdir -p "$VA_EXAMPLE_DIR"
fi
 
# Copy the file to VA_EXAMPLE_DIR
echo "Copying $IMAGENET_FILE to $VA_EXAMPLE_DIR..."
sudo cp "$CURRENT_DIR/$IMAGENET_FILE" "$VA_EXAMPLE_DIR/"
 
# Verify the copy was successful
if [ -f "$VA_EXAMPLE_DIR/$IMAGENET_FILE" ]; then
    echo "[SUCCESS] $IMAGENET_FILE successfully copied to $VA_EXAMPLE_DIR"
else
    echo "[ERROR] Failed to copy $IMAGENET_FILE to $VA_EXAMPLE_DIR"
fi
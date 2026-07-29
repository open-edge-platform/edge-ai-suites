# Install Client GPUs driver

<!--hide_directive::::{tab-set}hide_directive-->
<!--hide_directive:::{tab-item}hide_directive--> **Ubuntu 22.04**
<!--hide_directive:sync: humblehide_directive-->

## Installation

The Ubuntu 22.04 repositories do not contain compute packages for various Intel graphics products. To install these packages, you can use Intel's dedicated package repository.

```bash
# Install the Intel graphics GPG public key
wget -qO - https://repositories.intel.com/gpu/intel-graphics.key | \
sudo gpg --yes --dearmor --output /usr/share/keyrings/intel-graphics.gpg

# Configure the repositories.intel.com package repository
echo "deb [arch=amd64,i386 signed-by=/usr/share/keyrings/intel-graphics.gpg] https://repositories.intel.com/gpu/ubuntu jammy unified" | \
sudo tee /etc/apt/sources.list.d/intel-gpu-jammy.list

# Update the package repository metadata
sudo apt update

# Install the compute-related packages
sudo apt-get install -y libze-intel-gpu1=24.52.32224.14-1077~22.04 libze1=1.19.2.0-1077~22.04 intel-opencl-icd=24.52.32224.14-1077~22.04 clinfo xpu-smi
```

The commands listed above install all the essential packages needed for most users, aiming to minimize the installation of unnecessary packages. However, certain scenarios may require you to install additional packages. If you plan to use PyTorch, install `libze-dev` and `intel-ocloc` additionally:

```bash
sudo apt-get install -y libze-dev intel-ocloc
```

## Verifying Installation

To verify that the kernel and compute drivers are installed and functional, run `clinfo`:

```bash
clinfo | grep "Device Name"
```

You should see the Intel graphics product device names listed. If they do not appear, ensure you have permissions to access `/dev/dri/renderD*`. This typically requires your user to be in the render group:

```bash
sudo gpasswd -a ${USER} render
newgrp render
```

To verify that the client GPUs drivers version (24.52.32224.14-1077~22.04):

```bash
sudo apt-cache policy intel-opencl-icd
```

Alternatively, you can run the `clinfo` command as root.

<!--hide_directive:::hide_directive-->
<!--hide_directive:::{tab-item}hide_directive-->  **Ubuntu 24.04**
<!--hide_directive:sync: jazzyhide_directive-->

## Installation

The Ubuntu 24.04 repositories do not contain compute packages for various Intel graphics products. To install these packages, you can use Intel's dedicated package repository.

Visit the following GitHub repositories release pages and download all the Debian packages:

- https://github.com/intel/intel-graphics-compiler/releases
- https://github.com/intel/compute-runtime/releases

Install all packages as root:
```bash
sudo dpkg -i *.deb
```

For reference, this software release was validated on the following package versions:

```bash
# Download all *.deb packages
wget https://github.com/intel/intel-graphics-compiler/releases/download/v2.30.1/intel-igc-core-2_2.30.1+20950_amd64.deb --no-check-certificate
wget https://github.com/intel/intel-graphics-compiler/releases/download/v2.30.1/intel-igc-opencl-2_2.30.1+20950_amd64.deb --no-check-certificate
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/intel-ocloc-dbgsym_26.09.37435.1-0_amd64.ddeb --no-check-certificate
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/intel-ocloc_26.09.37435.1-0_amd64.deb --no-check-certificate
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/intel-opencl-icd-dbgsym_26.09.37435.1-0_amd64.ddeb --no-check-certificate
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/intel-opencl-icd_26.09.37435.1-0_amd64.deb --no-check-certificate
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/libigdgmm12_22.9.0_amd64.deb --no-check-certificate
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/libze-intel-gpu1-dbgsym_26.09.37435.1-0_amd64.ddeb --no-check-certificate
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/libze-intel-gpu1_26.09.37435.1-0_amd64.deb --no-check-certificate

# Verify sha256 sums for packages
wget https://github.com/intel/compute-runtime/releases/download/26.09.37435.1/ww09.sum --no-check-certificate
sha256sum -c ww09.sum

# Install all packages as root
sudo dpkg -i *.deb
```

## Verifying Installation

To verify that the kernel and compute drivers are installed and functional, run `clinfo`:

```bash
clinfo | grep "Device Name"
```

You should see the Intel graphics product device names listed. If they do not appear, ensure you have permissions to access `/dev/dri/renderD*`. This typically requires your user to be in the render group:

```bash
sudo gpasswd -a ${USER} render
newgrp render
```

To verify that the client GPUs drivers version (26.09.37435.1-0):

```bash
sudo apt-cache policy intel-opencl-icd
```

Alternatively, you can run the `clinfo` command as root.

<!--hide_directive:::hide_directive-->
<!--hide_directive::::hide_directive-->

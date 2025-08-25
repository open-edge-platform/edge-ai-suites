# VSLAM: ORB-SLAM3

SLAM(Simultaneous localization and mapping) is a major research problem in the robotics community, where a great deal of effort has been devoted to developing new methods to maximize their robustness and reliability.

VSLAM (visual SLAM) utilizes camera(s) as the primary source of sensor input to sense the surrounding environment. This can be done either with a single camera, multiple cameras, and with or without an inertial measurement unit (IMU) that measure translational and rotational movements.

Feature-based tracking algorithm is main-stream implementation for VSLAM, according to its real-time and simplified SLAM process.

ORB-SLAM3 is one of popular real-time feature-based SLAM libraries able to perform Visual, Visual-Inertial and Multi-Map SLAM with monocular, stereo and RGB-D cameras, using pin-hole and fisheye lens models. In all sensor configurations, ORB-SLAM3 is as robust as the best systems available in the literature, and significantly more accurate.

![architecture](README.assets/ORB-SLAM3-Architecture.png)

## Component Documentation

Comprehensive documentation on this component is available here: [Link](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/ORB_VSLAM.html)

## Changes to 3rd party source

This work is based off of the open-source [ORB_SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3.git) repository.

The following patches are provided to enhance the ORB_SLAM3 source:

| Directory          | Enhancement                  |
| ------------------ | ---------------------------- |
| [patches](patches) | Build Debian package         |

## Prerequisites

> [!IMPORTANT]
> Please make sure you have all the prerequisites and installation in [Installation & Setup](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/installation_setup.html) before proceeding.
> And follow the guide [Install Realsense SDK](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/installation_setup/installation/realsense.html) to install Realsense SDK.

## Installation

1. Make sure Realsense SDK installed. If not, follow [Install Realsense SDK](
https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/installation_setup/installation/realsense.html) to install Realsense packages.

Here is a minimal installation:

```
$ sudo apt install librealsense2
```

2. Install the ORB-SLAM3 packages by following the below command:

```
$ sudo apt install orb-slam3
```

After installation, the VSLAM example programs are installed under folder ``/opt/intel/orb-slam3``.

## VSLAM Demos

### Demo-1: Monocular Camera with Mono-Dataset

This Demo uses EUROC dataset to test ORB-SLAM3 monocular mode.

![orb-slam3-mono](README.assets/orb-slam3-mono.gif)

1. Download the EUROC MAV Dataset files

```
$ mkdir -p ~/orb-slam3/dataset
$ cd ~/orb-slam3/dataset
$ wget http://robotics.ethz.ch/~asl-datasets/ijrr_euroc_mav_dataset/machine_hall/MH_04_difficult/MH_04_difficult.zip
$ unzip MH_04_difficult.zip -d MH04
```

> [!NOTE]
> This demo uses `MH_04_difficult dataset`. If you want to try other dataset, you may download them from the link: https://projects.asl.ethz.ch/datasets/doku.php?id=kmavvisualinertialdatasets.

2. Launch ORB-SLAM3 Demo pipeline

Run the below commands in a bash terminal:

```
$ mkdir -p ~/orb-slam3/log
$ cd ~/orb-slam3/
$ /opt/intel/orb-slam3/Examples/Monocular/mono_euroc /opt/intel/orb-slam3/Vocabulary/ORBvoc.txt /opt/intel/orb-slam3/Examples/Monocular/EuRoC.yaml ~/orb-slam3/dataset/MH04/ /opt/intel/orb-slam3/Examples/Monocular/EuRoC_TimeStamps/MH04.txt  ~/orb-slam3/log/MH04_mono.txt
```

> [!NOTE]
> If you use other datasets other than `MH_04_difficult`, you should make sure you update the command above with the correct name of dataset you use.

### Demo-2: VSLAM Demo with Intel Realsense Camera

This Demo uses Intel Realsense Camera as stereo inputs.

![orb-slam3-realsense](README.assets/orb-slam3-realsense.gif)

1. Connect a Realsense D435 or D435i Camera to the test machine

2. Launch ORB-SLAM3 Demo pipeline

Run the below command in a bash terminal:

```
$ /opt/intel/orb-slam3/Examples/Stereo/stereo_realsense_D435i /opt/intel/orb-slam3/Vocabulary/ORBvoc.txt /opt/intel/orb-slam3/Examples/Stereo/RealSense_D435i.yaml
```

## Building ORB-SLAM3 Debian package

This step-by-step guide will detail how to build ORB-SLAM3 into a Debian package. Execute the following steps on an Ubuntu-based Linux development system:

1. Install prerequiste development tools:

```
$ apt update
$ apt install build-essential make cmake git wget debhelper devscripts equivs
```

2. Add the ECI APT repository to your APT sources:

```
$ sudo -E wget -O- https://eci.intel.com/repos/gpg-keys/GPG-PUB-KEY-INTEL-ECI.gpg | sudo tee /usr/share/keyrings/eci-archive-keyring.gpg > /dev/null
$ echo "deb [signed-by=/usr/share/keyrings/eci-archive-keyring.gpg] https://eci.intel.com/repos/$(source /etc/os-release && echo $VERSION_CODENAME) isar main" | sudo tee /etc/apt/sources.list.d/eci.list
```

3. Add the Intel RealSense APT repository to your APT sources:

```
$ sudo -E wget -O- https://librealsense.intel.com/Debian/librealsense.pgp | sudo tee /usr/share/keyrings/librealsense.pgp > /dev/null
$ sudo echo "deb [signed-by=/usr/share/keyrings/librealsense.pgp] https://librealsense.intel.com/Debian/apt-repo `lsb_release -cs` main" | sudo tee /etc/apt/sources.list.d/librealsense.list
```

4. Update your APT sources:

```
$ sudo apt update
```

5. Clone the Robotics AI Suite source:

```
$ git clone https://github.com/open-edge-platform/edge-ai-suites.git --recurse-submodules
```

6. Copy the Robotics AI Suite ORB-SLAM3 patches:

```
$ cd edge-ai-suites/robotics-ai-suite/components/orb-slam3-sample
$ cp ./patches/* ./ORB_SLAM3
```

7. Apply the patches:

```
$ cd ORB_SLAM3
$ git apply *.patch
$ rm *.patch
```

8. Install the package build dependencies:

```
$ sudo mk-build-deps -i --host-arch amd64 --build-arch amd64 -t "apt-get -y -q -o Debug::pkgProblemResolver=yes --no-install-recommends --allow-downgrades" debian/control
```

9. Build the Debian package:

```
dpkg-buildpackage
```

The Debian package will reside in the parent directory of `ORB_SLAM3`.

```
$ ls ../ -1
ORB_SLAM3
liborb-slam3-dbgsym_1.0-1_amd64.ddeb
liborb-slam3-dev_1.0-1_amd64.deb
liborb-slam3_1.0-1_amd64.deb
orb-slam3-dbgsym_1.0-1_amd64.ddeb
orb-slam3_1.0-1.dsc
orb-slam3_1.0-1.tar.gz
orb-slam3_1.0-1_amd64.buildinfo
orb-slam3_1.0-1_amd64.changes
orb-slam3_1.0-1_amd64.deb
```


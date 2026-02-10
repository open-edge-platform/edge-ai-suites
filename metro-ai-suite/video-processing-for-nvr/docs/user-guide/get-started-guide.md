# Get Started Guide
  
-   **Time to Complete:** 20min
-   **Programming Language:** c++

## Get Started
The sample application is based on Intel VPP SDK. It can run typical video processing workflows like video analytics and video transcoding. It can also be configured to run typical video composition workloads. You can use it for performance evaluation and implementation reference.  
  
### Prerequisites

**Operating System:**
* Ubuntu 24.04

**Software:**
* VPP SDK

## Installation Guide

### 1	System Installation
Install Ubuntu* 24.04 and set up the network correctly and run the sudo apt update.  

### 2 Install Software Dependencies
The sample application depends on Intel VPP SDK for video decode, encoding, and post-processing functionalities. It also depends on OpenVINO for video analytics and live555 library for RTSP streaming.  

#### 2.1 Install Intel VPP SDK
Install VPP SDK first. 
```
sudo -E wget -O- https://eci.intel.com/sed-repos/gpg-keys/GPG-PUB-KEY-INTEL-SED.gpg | sudo tee /usr/share/keyrings/sed-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | sudo tee /etc/apt/sources.list.d/sed.list
echo "deb-src [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | sudo tee -a /etc/apt/sources.list.d/sed.list
sudo bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/sed'
sudo apt update
sudo apt install intel-vppsdk

sudo bash /opt/intel/vppsdk/install_vppsdk_dependencies.sh
source /opt/intel/vppsdk/env.sh
```
Assume the VPP SDK package directory is vppsdk and the default install path is /opt/intel/. Run command `vainfo` to verify the media stack is installed successfully:  
  
```
# sudo su
# export LIBVA_DRIVER_NAME="iHD"
# export LIBVA_DRIVERS_PATH="/opt/intel/media/lib64"
# /opt/intel/media/bin/vainfo
```
  
In the terminal, you will see the output below:  
  
```
Trying display: drm
libva info: VA-API version 1.22.0
libva info: User environment variable requested driver 'iHD'
libva info: Trying to open /opt/intel/media/lib64/iHD_drv_video.so
libva info: Found init function __vaDriverInit_1_22
libva info: va_openDriver() returns 0
vainfo: VA-API version: 1.22 (libva 2.22.0.1)
vainfo: Driver version: Intel iHD driver for Intel(R) Gen Graphics - 24.2.5 (12561f6)
vainfo: Supported profile and entrypoints
      VAProfileNone                   : VAEntrypointVideoProc
      VAProfileNone                   : VAEntrypointStats
      VAProfileMPEG2Simple            : VAEntrypointVLD
      VAProfileMPEG2Simple            : VAEntrypointEncSlice
```
  
Then you can try to run one VPP SDK API test.  
  
Note:	Make sure to switch to `root` and `init 3` before running the command below:  
  
```
# sudo init 3
# sudo su

# cd /opt/intel/vppsdk/bin
# source /opt/intel/vppsdk/env.sh
# ./api_test --gtest_filter=*MainAPI*
```
  
It will start to run a decode pipeline. You will see below message if the test can run successfully.  
  
```
[       OK ] TestDecodeAPI.MainAPI (23877 ms)
[----------] 1 test from TestDecodeAPI (23877 ms total)
[----------] Global test environment tear-down
[==========] 1 test from 1 test suite ran. (23877 ms total)
[  PASSED  ] 1 test.
```
  
#### 2.2	Install the OpenVINO library
There is a `example/VA_example/install_dependencies.sh` under VA example folder. Make sure the network connection is good on your system, then run this script, and it will download, build, and install OpenVINO libraries. The libraries will be installed to /opt/intel/openvino.  

#### 2.3	Install the live555 library
There is a `svet2/live555_install.sh` under the root directory of svet_app source code package. Make sure the network connection is good on your system, then run this script, and it will download, build, and install live555 libraries. The libraries will be installed to /usr/local/lib/.  
  
### 3	Build sample application
If you have not run the commands below in the current terminal, run them first to set up the correct environment variables:  
  
```
$ source /opt/intel/vppsdk/env.sh
$ export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
```
  
Then run build.sh to build the video analytic application binary:  
  
```
$ cd example/VA_example/decode_detection/surface_map
$ ./build.sh
```
  
If the build.sh runs successfully, you can find `dec_det` binary under the build directory.  
  
## Run Sample Application
### 1	Download and convert model
You can download and convert yolo model with [openvino notebook](https://github.com/openvinotoolkit/openvino_notebooks/blob/latest/notebooks/yolov8-optimization/yolov8-object-detection.ipynb), you will get `yolov8n_with_preprocess.xml` after the model successfully downloaded and converted  
```
https://github.com/openvinotoolkit/openvino_notebooks/blob/latest/notebooks/yolov8-optimization/yolov8-object-detection.ipynb  
```
  
### 2	Switch to root and set environment variables
Before running the sample application, make sure the environment variables are set correctly in the current bash:  
  
```
# sudo init 3
# sudo su
# source /opt/intel/vppsdk/env.sh
# export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
```
  
Note:	VPP SDK uses drm display, which requires that there is no X server running and with root privileges.  
  
### 3	Run basic video analytic pipeline
Run video decode + detection with yolo detection model
```
./dec_det yolov8n_with_preprocess.xml
```

## Uninstall 

### Uninstall application
`sudo rm -rf build`

### Uninstall live555
`xargs sudo rm < live555-master/build/install_manifest.txt`  
`sudo rm -rf live555-master`

### Uninstall VPP SDK
`sudo apt remove intel-vppsdk`  
`sudo rm -rf /opt/intel/vppsdk`  
`sudo rm -rf /opt/intel/media`

## Run Sample Application in docker
Build docker image and Run in docker container, [guide](../../docker/README.md)
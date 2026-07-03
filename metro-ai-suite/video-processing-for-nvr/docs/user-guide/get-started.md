# Get Started

The sample application is based on the Video Processing Platform SDK. It can run typical video processing workflows
 like video analytics and video transcoding. It can also be configured to run typical video
 composition workloads. You can use it for performance evaluation and implementation reference.

- **Time to Complete:** 20min
- **Programming Language:** C++

> **Note:** This guide covers the Video Analytic and Transcoding example applications in the
> `example` folder.

## Prerequisites

**Operating System:**

- Ubuntu 24.04

**Software:**

- Video Processing Platform SDK

## Installation Guide

### 1 System Installation

Install Ubuntu\* 24.04, set up the network correctly, and run the sudo apt update.

### 2 Install Software Dependencies

The sample application depends on the Video Processing Platform SDK for video decode, encoding, and post-processing
functionalities. It also depends on OpenVINO™ for video analytics and the live555 library for RTSP
streaming.

#### 2.1 Install the Video Processing Platform SDK

Install the Video Processing Platform SDK first.

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

Assume the Video Processing Platform SDK package directory is `vppsdk` and the default install path is `/opt/intel/`.
Run `vainfo` to verify the media stack is installed successfully:

```
# sudo su
# export LIBVA_DRIVER_NAME="iHD"
# export LIBVA_DRIVERS_PATH="/opt/intel/media/lib64"
# /opt/intel/media/bin/vainfo
```

In the terminal, you should see the output similar to what is shown below:

```text
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

Then, run a Video Processing Platform SDK API test.

Switch to `root` and `init 3` before running the command below:

```
sudo init 3
sudo su

cd /opt/intel/vppsdk/bin
source /opt/intel/vppsdk/env.sh
./api_test --gtest_filter=*MainAPI*
```

It will start a decode pipeline. On a successful test run, you should see a message similar
to the one below:

```text
[       OK ] TestDecodeAPI.MainAPI (23877 ms)
[----------] 1 test from TestDecodeAPI (23877 ms total)
[----------] Global test environment tear-down
[==========] 1 test from 1 test suite ran. (23877 ms total)
[  PASSED  ] 1 test.
```

#### 2.2 Install the OpenVINO™ library

There is an `example/VA_example/install_dependencies.sh` under VA example folder. With a working
network connection on your system, run this script: it will download, build, and install
OpenVINO™ libraries. The libraries will be installed to `/opt/intel/openvino`.

#### 2.3 Install the live555 library

There is a `svet2/live555_install.sh` under the root directory of svet_app source code package.
With a working network connection on your system, run this script: it will download, build, and
install live555 libraries. The libraries will be installed to `/usr/local/lib/`.

### 3 Build the sample application

If you have not run the commands below in the current terminal, run them first to set up the
correct environment variables:

```
$ source /opt/intel/vppsdk/env.sh
$ export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
```

Then run `build.sh` to build the Video Analytic application binary:

```
$ cd example/VA_example/decode_detection/surface_map
$ ./build.sh
```

If the `build.sh` runs successfully, you can find the `dec_det` binary under the build directory.

## Run the Sample Application

### 1 Download and convert the model

You can download and convert the YOLO model with [OpenVINO™ notebook](https://github.com/openvinotoolkit/openvino_notebooks/blob/2026.0/notebooks/yolov8-optimization/yolov8-object-detection.ipynb), you will get `yolov8n_with_preprocess.xml` after successful model download and conversion.

```
https://github.com/openvinotoolkit/openvino_notebooks/blob/2026.0/notebooks/yolov8-optimization/yolov8-object-detection.ipynb
```

### 2 Switch to root and set environment variables

Before running the sample application, make sure the environment variables are set correctly in the current bash:

```
# sudo init 3
# sudo su
# source /opt/intel/vppsdk/env.sh
# export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
```

> **Note:** the Video Processing Platform SDK uses drm display, which requires that there is no X server running and with root privileges.

### 3 Run a basic Video Analytic pipeline

Run video decode + detection with YOLO detection model:

```
./dec_det yolov8n_with_preprocess.xml
```

Logs will be displayed upon successful execution. Sample output is shown below:

```text
[FPS counter] Tue Jun  2 06:27:28 2026

Decode node stream 4, fps is 60.000000
Decode node stream 3, fps is 56.000000
Decode node stream 11, fps is 67.000000
Decode node stream 12, fps is 60.000000
Decode node stream 6, fps is 60.000000
Decode node stream 1, fps is 55.000000
Decode node stream 14, fps is 63.000000
Decode node stream 15, fps is 56.000000
Decode node stream 2, fps is 59.000000
Decode node stream 0, fps is 62.000000
Decode node stream 13, fps is 59.000000
Decode node stream 10, fps is 60.000000
Decode node stream 8, fps is 57.000000
Decode node stream 9, fps is 60.000000
Decode node stream 5, fps is 59.000000
Decode node stream 7, fps is 59.000000
Decode node total fps is 952.000000, total stream number is 16, average stream fps is 59.500000
[2026-06-02 06:27:28.494] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.503] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.513] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.522] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.531] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.541] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.551] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.559] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.568] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.577] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.586] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
[2026-06-02 06:27:28.594] [thread 134686] [info]: [decode.cpp:destroy@Line110] decode destroy
Decode and detection finished.
```

## Uninstall

### Uninstall the sample application

`sudo rm -rf build`

### Uninstall live555

`xargs sudo rm < live555-master/build/install_manifest.txt`
`sudo rm -rf live555-master`

### Uninstall the Video Processing Platform SDK

`sudo apt remove intel-vppsdk`
`sudo rm -rf /opt/intel/vppsdk`
`sudo rm -rf /opt/intel/media`

## Run the Sample Application in Docker

Build Docker image and Run in Docker container, for information see the [Docker README](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/video-processing-for-nvr/docker/README.md).

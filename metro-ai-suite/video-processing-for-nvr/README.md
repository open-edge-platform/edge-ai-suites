# Video Processing for NVR

This sample application allows users to evaluate and optimize video processing workflows for Network Video Recorders (NVRs). Users can run video processing workflows like video analytic and transcoding with example applications based on the **Video Processing Platform SDK**. User can also configure concurrent video processing, including video decode, post-processing, and concurrent display, utilizing the integrated GPUs and utilize application multiview to evaluate runtime performance or debug core video processing workload with **Smart Video Evaluation Tool 2 (SVET2)**.

## Overview

This sample application is built on the Video Processing Platform SDK and can serve as a reference for various video processing use cases.

- Several reference applications are in example folder, built with APIs from the Video Processing Platform SDK to construct video analytic and transcoding workflows.
- SVET2 is a subcomponent designed for the NVR scenario. With SVET2, users can configure NVR workloads (such as decode, composition, and display) through a configuration file. The application reads this file and executes the user-defined workload accordingly.
- Programming Language: C++

## Dependencies

The sample application depends on the Video Processing Platform SDK, OpenVINO™ and live555

## Table of Contents

- [System requirements](#system-requirements)
- [How to Run in Docker Container](#how-to-run-in-docker-container)
- [How to Install the Video Processing Platform SDK on Bare Metal](#how-to-install-the-video-processing-platform-sdk-on-bare-metal)
- [Known limitations](#known-limitations)
- [Learn More](#learn-more)
- [License](#license)

## System requirements

**Operating System:**

- Ubuntu 24.04

**Software:**

- Video Processing Platform SDK

**Hardware:**

- Intel® platforms with iGPU and dGPU

## How to Run in Docker Container

Please refer to [docker guide](./docker/README.md) to run the video analytic workflow

## How to Install the Video Processing Platform SDK on Bare Metal

1. Install the Video Processing Platform SDK and dependencies

```
sudo -E wget -O- https://eci.intel.com/sed-repos/gpg-keys/GPG-PUB-KEY-INTEL-SED.gpg | sudo tee /usr/share/keyrings/sed-archive-keyring.gpg > /dev/null
echo "deb [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | sudo tee /etc/apt/sources.list.d/sed.list
echo "deb-src [signed-by=/usr/share/keyrings/sed-archive-keyring.gpg] https://eci.intel.com/sed-repos/$(source /etc/os-release && echo $VERSION_CODENAME) sed main" | sudo tee -a /etc/apt/sources.list.d/sed.list
sudo bash -c 'echo -e "Package: *\nPin: origin eci.intel.com\nPin-Priority: 1000" > /etc/apt/preferences.d/sed'
sudo apt update
sudo apt -y install intel-vppsdk

sudo bash /opt/intel/vppsdk/install_vppsdk_dependencies.sh
source /opt/intel/vppsdk/env.sh
```

2. Run `example/VA_example/install_dependencies.sh` to install OpenVINO™

3. Run `svet2/live555_install.sh` to install live555

4. Run `build.sh` in sub-folders to build specific components depending on the use case

## Known limitations

The sample application has been validated on Intel® platforms Arrow Lake, Meteor Lake, Raptor Lake, Adler Lake, Tiger Lake and Panther Lake

## Learn More

- [Overview](./docs/user-guide/index.md) - Overview and SVET2 concepts
- [Get Started](./docs/user-guide/get-started.md) - Get started with basic workloads
- [SVET2 Guide](./docs/user-guide/svet-guide.md) - Configure and run NVR workloads with SVET2
- [How It Works](./docs/user-guide/how-it-works.md) - Architecture and how it works
- [Release Notes](./docs/user-guide/release-notes.md)

## License

The sample application is licensed under [APACHE 2.0](https://github.com/open-edge-platform/edge-ai-suites/blob/main/LICENSE).

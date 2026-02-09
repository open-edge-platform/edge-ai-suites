# Video Processing for NVR
This sample application allows users to evaluate and optimize video processing workflows for NVR. Users can run video processing workflows  like video analytic and transcoding with example applications based on VPP SDK. User can also configure concurrent video processing, including video decode, post-processing, and concurrent display, utilizing the integrated GPUs and utilize application multiview to evaluate runtime performance or debug core video processing workload with `SVET2` (Smart Video Evaluation Tool 2).

# Overview
This sample application is built on the VPP SDK and can serve as a reference for various video processing use cases.  
* Sveral reference applications are in example folder, built with APIs from VPP SDK to construct video analytic and transcoding workflows.
* `SVET2` is a subcomponent designed for the NVR scenario. With `SVET2`, users can configure NVR workloads (such as decode, composition, and display) through a configuration file. The application reads this file and executes the user-defined workload accordingly.  
* Programming Language: C++  

## Dependencies
The sample application depends on VPP SDK, OpenVINO and live555

## Table of contents

  * [License](#license)
  * [System requirements](#system-requirements)
  * [How to build](#how-to-build)
  * [Known limitations](#known-limitations)

## License
The sample application is licensed under [APACHE 2.0](https://github.com/open-edge-platform/edge-ai-suites/blob/main/LICENSE).

## System requirements

**Operating System:**
* Ubuntu 24.04

**Software:**
* VPP SDK

**Hardware:** 
* Intel® platforms with iGPU and dGPU

## How to install

1. Install VPPSDK and dependencies
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

2. Run `example/VA_example/install_dependencies.sh` to install OpenVINO  

3. Run `svet2/live555_install.sh` to install live555  

4. Run `build.sh` in sub-folerds to build each component  

## How to run
Please refer to [docker guide](./docker/README.md) to run the video analytic workflow  

## Known limitations

The sample application has been validated on Intel® platforms Arrow Lake, Meteor Lake, Raptor Lake, Adler Lake, Tiger Lake and Panther Lake


# Learn More  
- Get started with basic workloads [Get Started Guide](./docs/user-guide/get-started-guide.md)
- VPP SDK Overview [VPP SDK Overview](./docs/user-guide/Overview.md)
- [Release Notes](./docs/user-guide/release-notes.md)
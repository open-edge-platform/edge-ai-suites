# Video Processing for NVR
This sample application allows users to evaluate and optimize video processing workflows for NVR. Users can configure concurrent video processing, including video decode, post-processing, and concurrent display, utilizing the integrated GPUs. Users can also utilize application multiview to evaluate runtime performance or debug core video processing workload.

# Overview
This sample application based on VPP SDK, user can configure workload with config file, svet will read the config file and run the user defined workload.  
Programming Language: C++  

# How it works
## Typical workloads
Sample config files can be found in ./sample_config directory.
* 16 1080p local H264/H265 clip decoding, compositon, and render on one 4K display
* 16 1080p RTSP H264/H265 stream decoding, composition, and render on one 4K display
* Dynamic remove one input stream in runtime 
* Dynamic add one input stream in runtime 

## Dependencies
The sample application depends on VPP SDK and [live555](http://www.live555.com/)

## Table of contents

  * [License](#license)
  * [System requirements](#system-requirements)
  * [How to build](#how-to-build)
  * [Known limitations](#know-limitations)

## License
The sample application is licensed under LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE. See [LICENSE](./LICENSE.txt) for details.

## System requirements

**Operating System:**
* Ubuntu 24.04

**Software:**
* VPP SDK

**Hardware:** 
* Intel® platforms supported by the OneVPL GPU 24.2.5 
* For OneVPL GPU, the major platform dependency comes from the back-end media driver. https://github.com/intel/media-driver

## How to build

1. Run live555_install.sh to install live555
2. Install VPPSDK and dependencies  
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
3. Run build.sh
4. Add /usr/local/lib to $LD_LIBRARY_PATH: export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
   You shall add this export command to your .bashrc or need to run it before running svet_app 
5. Basic test: 
```
./build/svet_app load sample_config/basic/1dec1disp.txt
```


## Known limitations

The sample application has been validated on Intel® platforms Meteor Lake, Raptor Lake, Adler Lake and Tiger Lake 


# Learn More  
- Get started with basic workloads [Get Started Guide](./docs/user-guide/get-started-guide.md)
- VPP SDK Overview [VPP SDK Overview](./docs/user-guide/Overview.md)
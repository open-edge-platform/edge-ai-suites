# Video Processing for NVR
This sample application allows users to evaluate and optimize video processing workflows for NVR. Users can configure concurrent video processing, including video decode, post-processing, and concurrent display, utilizing the integrated GPUs. Users can also utilize application multiview to evaluate runtime performance or debug core video processing workload.

## Typical workloads
Sample config files can be found in ./sample_config directory.
* 16 1080p local H264/H265 clip decoding, compositon, and render on one 4K display
* 16 1080p RTSP H264/H265 stream decoding, composition, and render on one 4K display
* Dynamic remove one input stream in runtime 
* Dynamic add one input stream in runtime 

# Dependencies
The sample application depends on VPP SDK and [live555](http://www.live555.com/)

# Table of contents

  * [License](#license)
  * [Documentation](#documentation)
  * [System requirements](#system-requirements)
  * [How to build](#how-to-build)
    * [Build steps](#build-steps)
  * [Known limitations](#know-limitations)

# License
The sample application is licensed under LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE. See [LICENSE](./LICENSE.txt) for details.


# Documentation
See [VPP SDK Overview](./docs/user-guide/Overview.md)

# System requirements

**Operating System:**
* Ubuntu 24.04

**Software:**
* VPP SDK

**Hardware:** 
* Intel® platforms supported by the OneVPL GPU 24.2.5 
* For OneVPL GPU, the major platform dependency comes from the back-end media driver. https://github.com/intel/media-driver

# How to build

1. Run live555_install.sh to install live555
2. Install VPPSDK and run env.sh 
3. Run build.sh
4. Add /usr/local/lib to $LD_LIBRARY_PATH: export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH
   You shall add this export command to your .bashrc or need to run it before running svet_app 
5. Basic test: ./build/svet_app load sample_config/basic/1dec1disp.txt



# Known limitations

The sample application has been validated on Intel® platforms Meteor Lake, Raptor Lake, Adler Lake and Tiger Lake 



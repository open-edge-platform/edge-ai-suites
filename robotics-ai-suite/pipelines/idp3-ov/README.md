# Improved 3D Diffusion Policy (OpenVINO)

This document provides setup instructions for the Improved 3D Diffusion Policy implementation optimized with Intel OpenVINO toolkit.

## Prerequisites

- Git installed on your system
- Robotics AI Suite environment set up
- Intel OpenVINO toolkit installed

## Setup Instructions

### 1. Clone the Source Code

```bash
git clone https://github.com/YanjieZe/Improved-3D-Diffusion-Policy.git
cd Improved-3D-Diffusion-Policy
git checkout f5b27faabbb8952672dd3d6a21d0ba762d5dfabb
```

### 2. Apply OpenVINO Optimization Patches

Apply the following patches in order to enable OpenVINO-specific optimizations:

```bash
git am ../patches/0001-Replace-diffusion_pointcloud_policy.py-with-cleaned-.patch
git am ../patches/0002-Update-idp3_workspace.py-and-add-convert_idp3.py.patch
git am ../patches/0003-update-convert_idp3.py.patch
git am ../patches/0001-Fix-unsafe-PyTorch-load-issue.patch
```

## Next Steps

After completing the source code setup, please refer to the [Robotics AI Suite documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_idp3.html) to build and run the sample pipeline.

## Support

For issues related to the OpenVINO optimizations, please consult the [Robotics AI Suite documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/developer_tools_tutorials/model_tutorials/model_idp3.html) or contact the development team.

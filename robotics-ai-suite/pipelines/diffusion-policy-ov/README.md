# Diffusion Policy (OpenVINO)

This document provides setup instructions for the Diffusion Policy implementation optimized with Intel OpenVINO toolkit.

## Prerequisites

- Git installed on your system
- Robotics AI Suite environment set up
- Intel OpenVINO toolkit installed

## Setup Instructions

### 1. Clone the Source Code

```bash
git clone https://github.com/real-stanford/diffusion_policy.git
cd diffusion_policy
git checkout 5ba07ac6661db573af695b419a7947ecb704690f
```

### 2. Apply OpenVINO Optimization Patches

Apply the following patches in order to enable OpenVINO-specific optimizations:

```bash
git am ../patches/0001-Enable-pipeline-with-OV-2024.6.patch
git am ../patches/0002-Add-test-script.patch
git am ../patches/0003-Add-core-affinity.patch
git am ../patches/0004-Fix-OV-inference-performance.patch
git am ../patches/0005-Add-OpenVINO-conversion-scripts.patch
git am ../patches/0001-Fix-unsafe-PyTorch-load-issue.patch
git am ../patches/0001-Modify-README.md-for-OpenVINO-model-conversion.patch
```

## Next Steps

After completing the source code setup, please refer to the [Robotics AI Suite documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/diffusion_policy.html) to build and run the sample pipeline.

## Support

For issues related to the OpenVINO optimizations, please consult the [Robotics AI Suite documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/diffusion_policy.html) or contact the development team.

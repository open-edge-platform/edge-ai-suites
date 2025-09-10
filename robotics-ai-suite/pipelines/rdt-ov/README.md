# RDT: Robotics Diffusion Transformer (OpenVINO)

This document provides setup instructions for the Robotics Diffusion Transformer implementation optimized with Intel OpenVINO toolkit.

## Prerequisites

- Git installed on your system
- Robotics AI Suite environment set up
- Intel OpenVINO toolkit installed

## Setup Instructions

### 1. Clone the Source Code

```bash
git clone https://github.com/thu-ml/RoboticsDiffusionTransformer.git
cd RoboticsDiffusionTransformer
git checkout 9af5241cb4456836ddf852b5a0286441f7b5d1d6
```

### 2. Apply OpenVINO Optimization Patches

Apply the following patches in order to enable OpenVINO-specific optimizations:

```bash
git am ../patches/0001-add-language-convert-script.patch
git am ../patches/0002-add-MUJOCO-pipeline-for-cuda.patch
git am ../patches/0003-add-MUJOCO-OpenVINO-pipeline.patch
git am ../patches/0004-add-OpenVINO-convert-script.patch
git am ../patches/0005-Add-jupyter-notebook-guide-and-enable-t5-model-conve.patch
git am ../patches/0006-add-dockerfile-5.patch
git am ../patches/0001-Fix-unsafe-PyTorch-load-issue.patch
```

## Next Steps

After completing the source code setup, please refer to the [Robotics AI Suite documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/robotics_diffusion_transformer.html) to build and run the sample pipeline.

## Support

For issues related to the OpenVINO optimizations, please consult the [Robotics AI Suite documentation](https://docs.openedgeplatform.intel.com/edge-ai-suites/robotics-ai-suite/main/embodied/sample_pipelines/robotics_diffusion_transformer.html) or contact the development team.

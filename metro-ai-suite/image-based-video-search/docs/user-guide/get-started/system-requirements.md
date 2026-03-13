# System Requirements

This page provides detailed hardware, software, and platform requirements to
help you set up and run the application efficiently.

## Supported Platforms

**Operating Systems**

- Ubuntu 22.04 LTS
- Windows 10/11 with WSL 2

**Hardware Platforms**
- 12th Generation Intel® Core™ processor or above with Intel® HD Graphics or , or Intel® Xeon® processor

## Minimum Requirements
| **Component**      | **Minimum Requirement**   | **Recommended**         |
|---------------------|---------------------------|--------------------------|
| **Processor**       | 12th Generation Intel® Core™ processor and above with Intel® HD Graphics   | Intel® Core™ Ultra Processors (Series 2) also known as Arrow Lake |
| **Memory**          | 16 GB                     | 16 GB                   |
| **Disk Space**      | 64 GB                | 128 GB               |

### Validated Platforms
The pallet defect detection model for this sample app has been tested to work on the following platforms/XPU(s)

| Product / Family     | CPU |  iGPU |  NPU | dGPU |
|----------------------|-----------|------------|-----------|----------|
| Intel® Core™ Ultra Processors (Series 3, 2, 1), Intel® Core™ Processors Series 2, Intel® Core™ Processors (14th/13th/12th Gen)  | ✓         | ✓          | ✓         |  Intel(R) Arc(TM) A770, B580        |
| 4th Gen Intel® Xeon® Scalable Processors                 | ✓         |            |           | Intel(R) Arc(TM) A770, B580        |

> **Note:** Users can also create apps tailored to their use case using models supported by DLStreamer.
Check [the list of supported models](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-libraries/dlstreamer/supported_models.html) for the latest information.

## Software Requirements

**Required Software**:

- Docker 27.3.1 or higher
- Python 3.10+
- Git

<!--
## Compatibility Notes
**Known Limitations**:
- GPU optimizations require Intel® integrated graphics or compatible accelerators.
-->

## Validation

- Ensure all dependencies are installed and configured before proceeding to
  [Get Started](../get-started.md).
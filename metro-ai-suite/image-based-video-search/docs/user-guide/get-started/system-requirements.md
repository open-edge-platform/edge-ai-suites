# System Requirements

This page provides detailed hardware, software, and platform requirements to
help you set up and run the application efficiently.

## Supported Platforms

**Operating Systems**

- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS
- Windows 10/11 with WSL 2

## Minimum Requirements
| **Component**       | **Minimum Requirement**   |
|---------------------|---------------------------|
| **Processor**       | 12th Generation Intel® Core™ processor and above with Intel® HD Graphics, 4th Gen Intel® Xeon® Scalable Processors   |
| **Memory**          | 16 GB                     |
| **Disk Space**      | 64 GB                     |

### Validated Platforms

| Product / Family     | CPU |  iGPU |  NPU |
|----------------------|-----------|------------|-----------|
| Intel® Core™ Ultra Processors (Series 3, 2, 1) | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 3 | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 2 | ✓         | ✓          |    NA      |
| Intel® Core™ Processors (14th/13th/12th Gen) | ✓         | ✓          | NA         |
| 4th Gen Intel® Xeon® Scalable Processors | ✓         |      NA      |      NA     |

**Validated on Intel® Arc™ dGPU models:** A770, B580, B60, and B50.

> **Note:** Users can also create apps tailored to their use case using models supported by DLStreamer.
Check [the list of supported models](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/dlstreamer/supported_models.html) for the latest information.

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

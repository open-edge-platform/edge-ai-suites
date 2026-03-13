# System Requirements

This section provides detailed hardware, software, and platform requirements to help you set up and run the application efficiently.

## Supported Platforms

**Operating Systems**
- Ubuntu 24.04 LTS

**Hardware Platforms**
- Intel® Core™ processors (i5 or higher)
- Intel® Xeon® processors (recommended for large deployments)

## Minimum Requirements
| **Component**      | **Minimum Requirement**   | **Recommended**         |
|---------------------|---------------------------|--------------------------|
| **Processor**       | Intel® Core™ processor   | Intel® Core™ Ultra 7    |
| **Memory**          | 8 GB                     | 16 GB                   |
| **Disk Space**      | 128 GB SSD               | 256 GB SSD              |
| **GPU/Accelerator** | Integrated GPU           | Integrated/Discrete GPU  |

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
- Docker 24.0 or higher
- Python 3.10+
- Git, jq, unzip

## Compatibility Notes

**Known Limitations**:
- GPU optimizations require Intel® Integrated/Discrete graphics or compatible accelerators.

## Validation
- Ensure all dependencies are installed and configured before proceeding to [Get Started](../get-started.md).

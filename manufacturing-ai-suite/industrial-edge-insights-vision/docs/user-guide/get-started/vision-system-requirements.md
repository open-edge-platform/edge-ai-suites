# Industrial Edge Insights - Vision System Requirements

This section shows detailed hardware, software, and platform requirements for Industrial Edge Insights - Vision applications, which comprises the Pallet Defect Detection and PCB Anomaly Detection use cases.

See the specific system requirements for **HMI Augmented Worker** and **Win Vision AI** in their respective sections.

## System Requirements

| Requirement | Industrial Edge Insights - Vision |
|---|---|
| Processor | 12th Generation Intel® Core™ processor and above with Intel® HD Graphics, 4th Gen Intel® Xeon® Scalable Processors |
| RAM (minimum) | 16 GB |
| Storage (minimum) | 64 GB |
| Operating system | Ubuntu 22.04 LTS or Ubuntu 24.04 LTS |
| Python Programming Language Version | 3.10 or higher |
| Docker Engine | Docker Engine 27.3.1 or higher |
| Other required software or tools | Git, jq, unzip |

## Validated Platforms

| Product / Family     | CPU |  iGPU |  NPU |
|----------------------|-----------|------------|-----------|
| Intel® Core™ Ultra Processors (Series 3, 2, 1) | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 3 | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 2 | ✓         | ✓          |    NA      |
| Intel® Core™ Processors (14th/13th/12th Gen) | ✓         | ✓          | NA         |
| 4th Gen Intel® Xeon® Scalable Processors | ✓         |      NA      |      NA     |

**Validated on Intel® Arc™ dGPU models:** A770, B580, B60, and B50.

> **Note:** Users can also create apps tailored to their use case using models supported by DL Streamer.
> Check [the list of supported models](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer/supported_models.html) for the latest information.

## Validation

Ensure all required software are installed and configured before proceeding to [Get Started](../get-started.md).

## Supporting Resources

- [Get Started Guide](../get-started.md)


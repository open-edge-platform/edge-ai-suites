# System Requirements

This section shows detailed hardware, software, and platform requirements for Industrial Edge Insights - Vision applications, which comprises the Pallet Defect Detection and PCB Anomaly Detection use cases.

See the specific system requirements for **HMI Augmented Worker** and **Win Vision AI** in their respective sections.

## Minimum Requirements

| Component | Specification |
|---|---|
| Processor | 12th Generation Intel® Core™ processor and above with Intel® HD Graphics, 4th Gen Intel® Xeon® Scalable Processors |
| RAM (minimum) | 16 GB |
| Storage (minimum) | 64 GB |

## Software Requirements

| Software | Version |
|---|---|
| Operating system | Ubuntu 22.04 LTS or Ubuntu 24.04 LTS |
| Python Programming Language Version | 3.10 or higher |
| Docker Engine | Docker Engine 27.3.1 or higher |

Other required software or tools: Git, jq, and unzip.

## Validated Platforms

| Product / Family     | CPU |  iGPU |  NPU |
|----------------------|-----------|------------|-----------|
| Intel® Core™ Ultra Processors (Series 3, 2, 1) | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 3 | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 2 | ✓         | ✓          |    N/A      |
| Intel® Core™ Processors (14th/13th/12th Gen) | ✓         | ✓          | N/A         |
| 4th Gen Intel® Xeon® Scalable Processors | ✓         |      N/A      |      N/A     |

**Validated on Intel® Arc™ dGPU models:** A770, B580, B60, and B50.

See the list of certified edge AI systems as enabled through the  Intel® Edge System Qualification (Intel® ESQ) through the [catalog](https://builders.intel.com/ecosystem-engagement/solution-hub/edge-ai-catalog/partner-spotlight). On the left menu, you can filter by **Verticals > Manufacturing** or by **Intel Open Software Platform** > **Manufacturing AI Suite**.

> **Note:** Only a subset of sample applications are represented by the Intel® ESQ package. See [Test Suites](https://open-edge-platform.github.io/edge-system-qualification/main/getting-started/suites/) for more information.

> **Note:** You can also create apps tailored to your use case using models supported by DL Streamer.
> Check [the list of supported models](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer/supported_models.html) for the latest information.

## Validation

Ensure all required software are installed and configured before proceeding to [Get Started](../get-started.md).

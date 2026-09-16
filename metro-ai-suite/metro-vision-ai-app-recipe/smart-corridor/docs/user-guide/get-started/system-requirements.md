# System Requirements
This page provides detailed hardware, software, and platform requirements to help you set up and run the application efficiently.


<!--
## User Stories Addressed
- **US-2: Evaluating System Requirements**
  - **As a developer**, I want to review the hardware and software requirements, so that I can determine if my environment supports the application.

### Acceptance Criteria
1. A detailed table of hardware requirements (e.g., processor type, memory).
2. A list of software dependencies and supported operating systems.
3. Clear guidance on compatibility issues.
-->

## Supported Platforms
<!--
**Guidelines**:
- Include supported operating systems, versions, and platform-specific notes.
-->
**Operating Systems**
- Ubuntu 22.04 LTS
- Ubuntu 24.04 LTS


## Minimum Requirements
<!--
**Guidelines**:
- Use a table to clearly outline minimum and recommended configurations.
-->

| **Component**      | **Minimum Requirement**   |
|---------------------|--------------------------|
| **Processor**       | 12th Generation Intel® Core™ processor and above with Intel® HD Graphics, 4th Gen Intel® Xeon® Scalable Processors   |
| **Memory**          | 16 GB                    |
| **Disk Space**      | 128 GB SSD               |

### Validated Platforms

| Product / Family     | CPU |  iGPU |  NPU |
|----------------------|-----------|------------|-----------|
| Intel® Core™ Ultra Processors (Series 3, 2, 1) | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 3 | ✓         | ✓          | ✓         |
| Intel® Core™ Processors Series 2 | ✓         | ✓          |    NA      |
| Intel® Core™ Processors (14th/13th/12th Gen) | ✓         | ✓          | NA         |
| 4th Gen Intel® Xeon® Scalable Processors | ✓         |      NA      |      NA     |

**Validated on Intel® Arc™ dGPU models:** A770, B580, B60, and B50.

## Software Requirements
<!--
**Guidelines**:
- List software dependencies, libraries, and tools.
-->
**Required Software**:
- Docker 24.0 or higher
- Git, jq, unzip

## Compatibility Notes
<!--
**Guidelines**:
- Include any limitations or known issues with supported platforms.
-->
**Known Limitations**:
- GPU optimizations require Intel® integrated graphics or compatible accelerators.

## Validation

- Follow instructions at [Get Started](../get-started.md).

# System Requirements

This page lists the hardware, software, and platform requirements for running the Agentic
Predictive Maintenance (APM) blueprint.

## Hardware Platforms Used for Validation

- 4th and 5th Gen Intel® Xeon® processors
- Intel® Arc™ GPU (A-series and B-series) with compatible Intel® Xeon® processor or Intel® Core™ processor
- Intel® Core™ Ultra processors with integrated GPU (suitable for smaller pipelines and fallback
  mode)

**Large Language Model (LLM) mode** requires GPU support. The **fallback mode** (rule-based) runs on CPU alone.

## Operating Systems Used for Validation

- Ubuntu OS version 22.04 LTS for CPU-only configurations
- Ubuntu OS version 24.04 LTS when using discrete GPU hardware
- See the
  [Intel GPU driver documentation](https://dgpu-docs.intel.com/devices/hardware-table.html) for
  specific kernel requirements per GPU model.

## Minimum Hardware Configuration

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 16 GB | 32 GB |
| Storage | 50 GB | 100 GB |
| CPU | Any Intel® Xeon® processor or Intel® Core™ processor | 4th Gen Intel® Xeon® processor or later |
| GPU | Not required (fallback mode) | Intel® Arc™ GPU for LLM mode |

## Software Requirements

| Software | Version |
|----------|---------|
| Docker Engine | 24.0 or higher |
| Docker Compose tool | 2.20 or higher |
| Python programming language | 3.10 or higher (for data preparation only) |

## Compatibility Notes

**Known Limitations**:

- The LLM service offers Neural Processing Unit (NPU) inference as an experimental option,
but the option is not validated for all model and configuration combinations.
- Intel® Core™ Ultra processors Series 2 and 3 with integrated GPU can run the application but model
  selection significantly affects performance.

## Validation

Ensure Docker Engine and Docker Compose tool are installed and are running before following the
[Get Started](../get-started.md) section.

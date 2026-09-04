# Benchmarks

The Handheld Multi-Modal application ships with the `2026.2-20260813` version of
[Visual Pipeline and Platform Evaluation Tool (ViPPET)](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).
ViPPET is included in the application package and starts automatically as part of the deployment.

## Using ViPPET for Benchmarking

ViPPET allows you to compare the performance of AI pipelines across different combinations of
supported hardware (CPU, GPU, NPU, NPU+GPU) to determine the best device configuration for a
specific workload.

To access the benchmarking functionality:

1. Open ViPPET at `https://localhost:1443`.
2. Navigate to the **Benchmarks** section.
3. Select the pipeline and hardware combinations to evaluate.
4. Run the benchmark and review the results, including throughput and resource utilization metrics.

## Edge Workloads and Benchmarks Guide

For platform-level benchmarking beyond ViPPET — vision AI inference, hardware-accelerated
media processing, end-to-end video analytics pipelines, and generative AI — see the
[Edge Workloads and Benchmarks Guide](./infrastructure/run-edge-benchmarks.md).

<!--hide_directive
:::{toctree}
:hidden:

Edge Workloads and Benchmarks Guide <./infrastructure/run-edge-benchmarks.md>
:::
hide_directive-->

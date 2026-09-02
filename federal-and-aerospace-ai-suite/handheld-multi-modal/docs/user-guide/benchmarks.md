# Benchmarks

The Handheld Multi-Modal application ships with the `2026.2-20260813` version of
[Visual Pipeline and Platform Evaluation Tool (ViPPET)](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html).
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

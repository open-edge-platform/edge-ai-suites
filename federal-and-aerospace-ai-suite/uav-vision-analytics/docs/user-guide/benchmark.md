# Benchmark — UAV Vision Analytics

This section explains how to measure the performance of the UAV Vision Analytics
application. The blueprint offers two options, using the UAV-specific `calc_stream_density.sh`
benchmarking script and the Edge Workloads and Benchmarks approach.

The [UAV-specific benchmarking Guide](./benchmarking/run-uav-benchmarks.md) explains how to
determine the maximum number of concurrent drone-camera video streams the system can process
(**stream density**) while sustaining a target frame rate, and simultaneously collects hardware
utilization and power metrics from `metrics-manager`.

[Edge Workloads and Benchmarks Guide](./benchmarking//run-edge-benchmarks.md) describes
the more general, platform-level benchmarking process, a solution for end-to-end video
analytics pipelines, vision AI inference, hardware-accelerated media processing, and
generative AI.


<!--hide_directive
:::{toctree}
:hidden:

UAV-specific Benchmarks Guide<./benchmarking/run-uav-benchmarks.md>
Edge Workloads and Benchmarks Guide <./benchmarking/run-edge-benchmarks.md>
:::
hide_directive-->
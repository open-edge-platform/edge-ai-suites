# How to Benchmark PCB Anomaly Detection
This guide demonstrates how to benchmark the PCB anomaly detection pipeline to determine optimal stream density and performance characteristics.

## Contents

### Prerequisites
> Ensure the application is set up and running. Refer to the [Setup Guide](../setup-guide.md) for complete installation and configuration steps.

- DL Streamer Pipeline Server (DLSPS) running and accessible
- `curl`, `jq`, `gawk` and `bc` utilities installed

### Benchmark Script Usage

Navigate to the `[WORKDIR]/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision` directory and use the benchmark script:

```bash
./benchmark_start.sh -p <pipeline_name> -l <lower_bound> -u <upper_bound> [-t <target_fps>] [-i <interval>]
```

**Arguments:**
- `-p <pipeline_name>` : **(Required)** The name of the pipeline to benchmark (e.g., pcb_anomaly_classification)
- `-l <lower_bound>` : **(Required)** Starting lower bound for number of streams
- `-u <upper_bound>` : **(Required)** Starting upper bound for number of streams  
- `-t <target_fps>` : Target FPS threshold (default: 14.95)
- `-i <interval>` : Monitoring duration in seconds per test run (default: 60)

### Configuration

The benchmark script automatically uses the configured sample application and its payload file:

1. **Application Selection**: The script reads `SAMPLE_APP` from the `.env` file to determine which application to benchmark
2. **Payload Configuration**: Uses the standard `payload.json` file from the selected application directory (`apps/${SAMPLE_APP}/payload.json`)
3. **Pipeline Selection**: Choose from available pipelines in the payload file (e.g., `pcb_anomaly_classification`, `pcb_anomaly_classification_gpu`)

Available pipelines for PCB anomaly detection:
- **`pcb_anomaly_classification`**: CPU-based anomaly classification pipeline
- **`pcb_anomaly_classification_gpu`**: GPU-accelerated anomaly classification pipeline with optimized settings

### Recommended Pipeline Parameters

These are the recommended parameters by Edge Benchmarking and Workloads team for workload with similar characteristics. These are configurable parameters that can be adjusted based on your specific requirements:

```
inference-region=full-frame inference-interval=1 batch-size=8 nireq=2 ie-config="GPU_THROUGHPUT_STREAMS=2"
```

**Parameter Descriptions:**
- `inference-region=full-frame`: Process the entire frame for detection
- `inference-interval=1`: Run inference on every frame
- `batch-size=8`: Process 8 frames in a single batch for better GPU utilization
- `nireq=2`: Number of inference requests to run in parallel
- `ie-config="GPU_THROUGHPUT_STREAMS=2"`: Intel OpenVINO engine streams configuration

### Steps to run benchmarks

1. **Set up the environment**: Ensure `SAMPLE_APP=pcb-anomaly-detection` is set in your `.env` file

2. **Test CPU performance**:
   ```bash
   ./benchmark_start.sh -p pcb_anomaly_classification -l 1 -u 10 -t 25.0 -i 30
   ```

3. **Test GPU performance** (if available):
   ```bash
   ./benchmark_start.sh -p pcb_anomaly_classification_gpu -l 1 -u 20 -t 28.5 -i 60
   ```

   > NOTE: The script automatically uses the payload.json file from the configured sample application directory.

### Understanding Results

The benchmark uses binary search to find optimal stream density. Key metrics include:

- **Stream Density**: Maximum concurrent streams achieving target FPS
- **Throughput Median**: Median FPS across all streams  
- **Throughput Cumulative**: Total FPS sum of all streams

**Sample Output:**
```
streams: 6 throughput: 28.8 range: [5,7]
======================================================
✅ FINAL RESULT: Stream-Density Benchmark Completed!
stream density: 6
======================================================
throughput median: 29.0
throughput cumulative: 173.8
```

### Troubleshooting

**Common Issues:**

1. **DL Streamer Pipeline Server Not Accessible**
   ```
   Error: DL Streamer Pipeline Server is not running or not reachable
   ```
   - Verify DL Streamer Pipeline Server is running: `docker ps | grep dlstreamer`
   - Check network connectivity to localhost

2. **Pipeline Startup Failures**
   - Check model file paths in payload.json
   - Verify video file accessibility  
   - Monitor system resources (CPU, memory, GPU)
   - Ensure the correct SAMPLE_APP is set in .env file

3. **Pipeline Not Found**
   ```
   Error: Pipeline 'pipeline_name' not found in payload.json
   ```
   - Verify the pipeline name exists in `apps/${SAMPLE_APP}/payload.json`
   - Check available pipelines: `jq '.[].pipeline' apps/${SAMPLE_APP}/payload.json`

4. **Debug Mode**
   Add `--trace` to see detailed execution steps:
   ```bash
   ./benchmark_start.sh -p pcb_anomaly_classification_gpu -l 1 -u 10 --trace
   ```

# Benchmark Performance

This document provides instructions on how to run performance benchmarks for the Vision AI
applications using the provided benchmarking scripts. The script determines the maximum number
of concurrent video streams a system can process (stream density) while maintaining a target
performance level.

## Prerequisites

- The `edge-ai-suites` repository must be cloned to your system.
- `curl`, `jq`, `gawk`, `ffmpeg`, and `bc` utilities installed

## Step 1: Understand the Benchmarking Script

The core of the benchmarking process is the `calc_stream_density.sh` script, located in the
`metro-vision-ai-app-recipe/` directory. This script automates the process of starting video
streams, monitoring their performance (Frames Per Second - FPS), and calculating key
performance indicators (KPIs) to find the maximum sustainable stream density.

### Stream Density Logic

The script determines the maximum stream density automatically: you supply only the pipeline
name and the FPS target, and the script discovers the search range itself using an exponential
ramp-up followed by a bisect. Here is a summary of the logic from the
`calc_stream_density.sh` script:

1. **Initialization:** The script starts at 1 stream. It tracks the highest stream count that
met the target (`lo`, also reported as `tns`) and the lowest stream count that failed it
(`hi`). No user-provided bounds are needed.

2. **Phase 1 - Exponential ramp-up:** The script measures 1, 2, 4, 8, 16, ... streams. In each
iteration:
    -   It runs a workload with the current number of streams (`ns`).
    -   It measures the `throughput min` (the lowest FPS achieved among all streams) and
    compares it to the `target_fps`.
    -   If the target is met, the stream count is doubled and the search continues.
    -   The first stream count that fails the target becomes the upper edge (`hi`) and ends
    this phase.

3. **Phase 2 - Bisect:** The script binary-searches between the last passing count (`lo`) and
the first failing count (`hi`), testing the midpoint each time and narrowing the interval,
until the two are adjacent.

4. **Convergence:** The final value of `lo` is the highest number of streams that met the
performance target, reported as the final stream density. If even a single stream fails the
target, the script reports that the target is not achievable. A safety ceiling (default 64
streams, override with the `MAX_STREAMS` environment variable) bounds the ramp-up on very
capable hardware.

### Average FPS Calculation

During each test run, the script logs the `avg_fps` for every active pipeline instance at
regular intervals. At the end of the run, an `awk` script processes these logs to calculate
several KPIs for the collection of FPS samples from each stream:

-   **Percentile Throughput:** Calculates a specific percentile (e.g., 90th) of the FPS values
to ignore outliers.
-   **Average Throughput:** The mean FPS across all streams.
-   **Median Throughput:** The median FPS value.
-   **Cumulative Throughput:** The sum of the FPS from all streams.
-   **Min Throughput:** The lowest (worst-case) FPS achieved among all streams. This value is
critical for the stream density calculation.

### NStreams Mode

The script also supports an **NStreams mode** for testing fixed stream counts without binary search. This mode allows you to run multiple pipeline types in parallel simultaneously with predefined stream counts for each pipeline.

**When to use NStreams Mode:**
- When you want to test specific stream count combinations across different pipelines (e.g., CPU and GPU simultaneously).
- To measure combined workload performance of heterogeneous pipelines on the same system.
- When you already know the desired stream counts and want to verify their performance.

**How NStreams Mode Works:**
- The script starts all specified pipelines with their respective fixed stream counts concurrently.
- Monitoring continues for the specified duration (default 60 seconds).
- KPIs are computed for the combined workload across all pipelines.
- No binary search is performed; results are based on the exact stream counts provided.

### Recommended Pipeline Parameters

These are the recommended parameters by Edge Benchmarking and Workloads team for workload with
similar characteristics. These are configurable parameters that can be adjusted based on your
specific requirements:

```
inference-region=1 inference-interval=3 batch-size=8 nireq=2 ie-config="GPU_THROUGHPUT_STREAMS=2" threshold=0.7
```

**Parameter Descriptions:**
- `inference-region=1`: Use the region-of-interest (ROI) set by the `gvaattachroi` element for
detection.
- `inference-interval=3`: Run inference on every 3rd frame.
- `batch-size=8`: Process 8 frames in a single batch for better GPU utilization.
- `nireq=2`: Number of inference requests to run in parallel.
- `ie-config="GPU_THROUGHPUT_STREAMS=2"`: OpenVINO™ engine streams configuration.
- `threshold=0.7`: Detection confidence threshold (70%).

## Step 2: Prepare for Benchmarking

1.  **Set Up and Start the Application:** Before running the benchmark, you must set up and
start the desired application (e.g., Loitering Detection). This ensures all services,
including the DL Streamer Pipeline Server, are running and available. For setup instructions,
please refer to the `get-started.md` guide located in the specific application's documentation
folder (e.g., [Get Started for Loitering Detection](../get-started.md)).

2.  **Navigate to Script Directory:** Open a terminal and navigate to the `metro-vision-ai-app-recipe` directory.

    ```bash
    cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
    ```

3.  **Stop Existing Pipelines:** Ensure no other pipelines are running before you start the
benchmark. You can stop any running pipelines with the `sample_stop.sh` script.

    ```bash
    ./sample_stop.sh
    ```

## Step 3: Run the Benchmark

> [!NOTE]
> The default parameters are set based on best know methods recommended by Edge
> Workloads and Benchamarks group for workload with similar characteristics. These parameters
> can be modified when starting the pipelines.

The `calc_stream_density.sh` script requires only a pipeline name; the stream count range is
determined automatically. The available pipelines are defined in the
`benchmark_app_payload.json` file located within each application's directory (e.g.,
`loitering-detection/`).

<details>
<summary>Example Payload with Detection and Classification</summary>

The `benchmark_app_payload.json` file contains an array of pipeline configurations. Each
configuration specifies the pipeline name and a payload with parameters for source, destination,
and AI models. The script uses the pipeline name to select the corresponding payload for
benchmarking.

Here is an example of a GPU pipeline configuration that includes both `detection-properties`
and `classification-properties` with additional parameters:

```json
{
    "pipeline": "object_tracking_gpu",
    "payload": {
        "source": {
            "uri": "file:///home/pipeline-server/videos/VIRAT_S_000101_looped.mp4",
            "type": "uri"
        },
        "destination": {
            "metadata": {
                "type": "mqtt",
                "topic": "object_detection_$x",
                "publish_frame": false
            },
            "frame": {
                "type": "webrtc",
                "peer-id": "object_detection_$x",
                "overlay-properties": {
                    "font-scale": 1.0,
                    "draw-txt-bg": false
                }
            }
        },
        "parameters": {
            "detection-properties": {
                "model": "/home/pipeline-server/models/intel/pedestrian-and-vehicle-detector-adas-0001/FP16/pedestrian-and-vehicle-detector-adas-0001.xml",
                "device": "GPU",
                "inference-interval": 3,
                "inference-region": 0,
                "batch-size": 8,
                "nireq": 2,
                "ie-config": "GPU_THROUGHPUT_STREAMS=2",
                "pre-process-backend": "va-surface-sharing",
                "threshold": 0.7
            }
        }
    }
}
```
</details>

### Example: Running Stream Density Benchmark for Loitering Detection

This example will find the maximum number of loitering detection streams that can run on the
CPU while maintaining at least 15 FPS.

1.  Execute the `calc_stream_density.sh` script, providing the desired pipeline name (`object_tracking_cpu` in this case). The script finds the stream count on its own.

    ```bash
    # Usage: ./calc_stream_density.sh -p <pipeline_name> -t <target_fps>

    ./calc_stream_density.sh -p object_tracking_cpu -t 15
    ```

2.  The script will output its progress as it tests different stream counts. The final output
will show the optimal stream density found.

    ```text
    ✅ FINAL RESULT: Stream-Density Benchmark Completed!
    stream density: 8
    ======================================================

    KPIs for the optimal configuration (8 streams):
    throughput #1: 29.98
    throughput #2: 29.98
    ...
    throughput #8: 29.98
    throughput median: 29.98
    throughput average: 29.98
    throughput stdev: 0
    throughput cumulative: 239.84
    throughput min: 29.98
    ```

### Example: Running Multiple Pipelines with Fixed Stream Counts

To test multiple pipelines in parallel with predefined stream counts (NStreams mode), use the `-nstreams` flag. This example runs 8 GPU streams and 6 NPU streams for loitering detection concurrently:

```bash
# Usage: ./calc_stream_density.sh -p <pipeline1> <pipeline2> ... -nstreams <count1> <count2> ...

./calc_stream_density.sh -p object_tracking_gpu object_tracking_npu -nstreams 8 6 -t 15 -i 60
```

**Parameters:**
- `-p object_tracking_gpu object_tracking_npu`: Two pipeline names to run in parallel.
- `-nstreams 8 6`: 8 streams for object_tracking_gpu, 6 streams for object_tracking_npu (order must match pipeline order).
- `-t 15`: Target FPS threshold (optional, default 14.95).
- `-i 60`: Monitoring duration in seconds (optional, default 60).

The script will start all specified pipelines and monitor their combined performance. Final output shows aggregated KPIs:

```text
✅ FINAL RESULT: Nstreams-mode Pipeline Run Completed!
   Pipelines : object_tracking_gpu object_tracking_npu
   Streams   : 8 6
   Total     : 14 streams
======================================================

KPIs (all 14 streams combined):
throughput median: 28.5
throughput average: 28.8
...
throughput min: 27.2
```

## Step 4: Stop the Benchmark

After the benchmark is complete, or if you need to stop it manually, use the `sample_stop.sh`
script. This will delete all running pipeline instances.

```bash
./sample_stop.sh
```

---
> *Intel, the Intel logo, OpenVINO, and the OpenVINO logo are trademarks of Intel Corporation or its subsidiaries.*

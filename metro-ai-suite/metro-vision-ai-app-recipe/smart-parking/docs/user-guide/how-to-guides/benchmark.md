# Benchmark Performance

This document provides instructions on how to run performance benchmarks for the Vision AI applications using the provided benchmarking scripts. The script determines the maximum number of concurrent video streams a system can process (stream density) while maintaining a target performance level.

## Prerequisites

- The `edge-ai-suites` repository must be cloned to your system.
- `curl`, `jq`, `gawk`, `ffmpeg`, and `bc` utilities installed

## Step 1: Understand the Benchmarking Script

The core of the benchmarking process is the `calc_stream_density.sh` script, located in the `metro-vision-ai-app-recipe/` directory. This script automates the process of starting video streams, monitoring their performance (Frames Per Second - FPS), and calculating key performance indicators (KPIs) to find the maximum sustainable stream density.

### Stream Density Logic

The script uses a binary search algorithm to efficiently find the optimal stream count within a given range (`lower_bound` and `upper_bound`). Here is a summary of the logic from the `calc_stream_density.sh` script:

1.  **Initialization:** The script starts with a lower bound (`lns`) and an upper bound (`uns`) for the number of streams. The current number of streams to test (`ns`) is initialized to the lower bound. A variable (`tns`) tracks the highest successful stream count found so far.

2.  **Binary Search Loop:** The script iterates until the range between the lower and upper bounds is 1, and both bounds have been tested. In each iteration:
    -   It runs a workload with the current number of streams (`ns`).
    -   It measures the `throughput min` (the lowest FPS achieved among all streams) and compares it to the `target_fps`.

3.  **Adjusting the Range:**
    -   **If Performance Target is NOT Met** (`throughput min` < `target_fps`): The current stream count (`ns`) is too high. It becomes the new upper bound (`uns = ns`). The next stream count to test is calculated as the midpoint between the old lower bound and this new upper bound.
    -   **If Performance Target is Met** (`throughput min` >= `target_fps`): The system can handle this workload. The current stream count (`ns`) becomes the new lower bound (`lns = ns`), and the highest successful stream count (`tns`) is updated. The next stream count to test is calculated as the midpoint between this new lower bound and the old upper bound.

4.  **Convergence:** This process of testing midpoints and narrowing the search range continues until the loop condition is met. The final value of `tns` represents the highest number of streams that successfully met the performance target, which is reported as the final stream density.

### Average FPS Calculation

During each test run, the script logs the `avg_fps` for every active pipeline instance at regular intervals. At the end of the run, an `awk` script processes these logs to calculate several KPIs for the collection of FPS samples from each stream:

-   **Percentile Throughput:** Calculates a specific percentile (e.g., 90th) of the FPS values to ignore outliers.
-   **Average Throughput:** The mean FPS across all streams.
-   **Median Throughput:** The median FPS value.
-   **Cumulative Throughput:** The sum of the FPS from all streams.
-   **Min Throughput:** The lowest (worst-case) FPS achieved among all streams. This value is critical for the stream density calculation.

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

These are the recommended parameters by Edge Benchmarking and Workloads team for a workload with similar characteristics. These are configurable parameters that can be adjusted based on your specific requirements:

```
inference-region=1 inference-interval=3 batch-size=8 nireq=2 ie-config="GPU_THROUGHPUT_STREAMS=2" threshold=0.7
```

**Parameter Descriptions:**
- `inference-region=1`: Use the region-of-interest (ROI) set by the `gvaattachroi` element for detection.
- `inference-interval=3`: Run inference on every 3rd frame.
- `batch-size=8`: Process 8 frames in a single batch for better GPU utilization.
- `nireq=2`: Number of inference requests to run in parallel.
- `ie-config="GPU_THROUGHPUT_STREAMS=2"`: Intel OpenVINO engine streams configuration.
- `threshold=0.7`: Detection confidence threshold (70%).

## Step 2: Prepare for Benchmarking

1.  **Set Up and Start the Application:** Before running the benchmark, you must set up and start the desired application (e.g., Smart Parking). This ensures all services, including the DL Streamer Pipeline Server, are running and available. For setup instructions, please refer to the `get-started.md` guide located in the specific application's documentation folder (e.g., `smart-parking/docs/user-guide/`).

2.  **Navigate to Script Directory:** Open a terminal and navigate to the `metro-vision-ai-app-recipe` directory.

    ```bash
    cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
    ```

3.  **Stop Existing Pipelines:** Ensure no other pipelines are running before you start the benchmark. You can stop any running pipelines with the `sample_stop.sh` script.

    ```bash
    ./sample_stop.sh
    ```

## Step 3: Run the Benchmark

> **Note:** The default parameters are set based on best know methods recommended by Edge Workloads and Benchamarks group for a workload with similar characteristics. These parameters can be modified when starting the pipelines.

The `calc_stream_density.sh` script requires a pipeline name and stream count boundaries to run. The available pipelines are defined in the `benchmark_app_payload.json` file located within each application's directory (e.g., `smart-parking/`).

<details>
<summary>Example Payload with Detection and Classification</summary>

The `benchmark_app_payload.json` file contains an array of pipeline configurations. Each configuration specifies the pipeline name and a payload with parameters for source, destination, and AI models. The script uses the pipeline name to select the corresponding payload for benchmarking.

Here is an example of a GPU pipeline configuration that includes both `detection-properties` and `classification-properties` with additional parameters:

```json
{
    "pipeline": "yolov11s_gpu",
    "payload": {
        "source": {
            "uri": "file:///home/pipeline-server/videos/new_video_1_looped.mp4",
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
                "model": "/home/pipeline-server/models/public/yolo11s/INT8/yolo11s.xml",
                "device": "GPU",
                "inference-interval": 3,
                "inference-region": 0,
                "batch-size": 8,
                "nireq": 2,
                "ie-config": "GPU_THROUGHPUT_STREAMS=2",
                "pre-process-backend": "va-surface-sharing",
                "threshold": 0.7
            },
            "classification-properties": {
                "model": "/home/pipeline-server/models/colorcls2/colorcls2.xml",
                "device": "GPU",
                "inference-interval": 3,
                "batch-size": 8,
                "nireq": 2,
                "ie-config": "GPU_THROUGHPUT_STREAMS=2",
                "pre-process-backend": "va-surface-sharing"
            }
        }
    }
}
```
</details>

### Example: Running Stream Density Benchmark for Smart Parking

This example will find the maximum number of smart parking streams that can run on the CPU while maintaining at least 15 FPS.

1.  Execute the `calc_stream_density.sh` script, providing the desired pipeline name (`yolov11s_gpu` in this case). Here, we test a range of 1 to 16 streams.

    ```bash
    # Usage: ./calc_stream_density.sh -p <pipeline_name> -l <lower_bound> -u <upper_bound> -t <target_fps>

    ./calc_stream_density.sh -p yolov11s_gpu -l 1 -u 16 -t 15
    ```

2.  The script will output its progress as it tests different stream counts. The final output will show the optimal stream density found.

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

To test multiple pipelines in parallel with predefined stream counts (NStreams mode), use the `-nstreams` flag. This example runs 9 GPU streams and 7 NPU streams concurrently:

```bash
# Usage: ./calc_stream_density.sh -p <pipeline1> <pipeline2> ... -nstreams <count1> <count2> ...

./calc_stream_density.sh -p yolov11s_gpu yolov11s_npu -nstreams 9 7 -t 15 -i 60
```

**Parameters:**
- `-p yolov11s_gpu yolov11s_npu`: Two pipeline names to run in parallel.
- `-nstreams 9 7`: 9 streams for yolov11s_gpu, 7 streams for yolov11s_npu (order must match pipeline order).
- `-t 15`: Target FPS threshold (optional, default 14.95).
- `-i 60`: Monitoring duration in seconds (optional, default 60).

The script will start all specified pipelines and monitor their combined performance. Final output shows aggregated KPIs:

```text
✅ FINAL RESULT: Nstreams-mode Pipeline Run Completed!
   Pipelines : yolov11s_gpu yolov11s_npu
   Streams   : 9 7
   Total     : 16 streams
======================================================

KPIs (all 16 streams combined):
throughput median: 28.5
throughput average: 28.8
...
throughput min: 27.2
```

## Step 4: Stop the Benchmark

After the benchmark is complete, or if you need to stop it manually, use the `sample_stop.sh` script. This will delete all running pipeline instances.

```bash
./sample_stop.sh
```

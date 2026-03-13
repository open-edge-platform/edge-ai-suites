# Optimization

The system achieves high-throughput processing on Edge hardware through specific
optimizations defined in `config.json`. The [`docker-compose.yml`](../_assets/docker-compose.yml)
file mentions all the services and the pipelines are configured in `config.json` file.

## Zero-Copy Video Pipeline

Unlike standard OpenCV pipelines that copy frames to CPU RAM, this solution utilizes **VASurface Sharing plugin**.

- **Mechanism:** Decoded video frames remain in GPU memory (`video/x-raw(memory:VAMemory)`).
- **Benefit:** Zero-copy inference eliminates PCIe bandwidth bottlenecks, reducing end-to-end latency by ~40%.
- **Config Evidence:** `pre-process-backend=va-surface-sharing` used in all `gvadetect` elements.

## Dynamic ROI Inference (Hierarchical Execution)

To maximize efficiency, heavy neural networks (like Axle Counting) do not run on the full 4K frame.

- **Logic:** The "Vehicle Type" model runs first to find the bounding box.
- **Optimization:** The Axle model is configured with `inference-region=roi-list`,
  forcing it to execute *only* within the coordinates of the detected vehicle.
- **Impact:** Reduces pixel processing load by >80% for sparse traffic scenes.

## Hybrid Workload Distribution

The pipeline intelligently maps models to available accelerators to prevent resource contention:

- **GPU (Flex Series):** Handles heavy convolution tasks (Vehicle Detection, LPR, Axle Counting).
- **CPU (Xeon):** Handles lighter classification tasks (Vehicle Color) and post-processing adapters (`gvapython`).

## Learn More

- [Perception Layer](./perception-layer.md)
- [Analytics Pipeline](./analytics-pipeline.md)
- [Support and Troubleshooting](../troubleshooting.md)

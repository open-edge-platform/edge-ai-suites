# How to use GPU for inference

## Pre-requisites
In order to benefit from hardware acceleration, pipelines can be constructed in a manner that different stages such as decoding, inference etc., can make use of these devices.
For containerized applications built using the DL Streamer Pipeline Server, first we need to provide GPU device(s) access to the container user.

### Provide GPU access to the container
This can be done by making the following changes to the docker compose file.

```yaml
services:
  dlstreamer-pipeline-server:
    group_add:
      # render group ID for ubuntu 22.04 host OS
      - "110"
      # render group ID for ubuntu 24.04 host OS
      - "992"
    devices:
      # you can add specific devices in case you don't want to provide access to all like below.
      - "/dev:/dev"
```
The changes above adds the container user to the `render` group and provides access to the GPU devices.

### Hardware specific encoder/decoders
Unlike the changes done for the container above, the following requires a modification to the media pipeline itself.

Gstreamer has a variety of hardware specific encoders and decoders elements such as Intel specific VA-API elements that you can benefit from by adding them into your media pipeline. Examples of such elements are `vah264dec`, `vah264enc`, `vajpegdec`, `vajpegdec`, etc.

Additionally, one can also enforce zero-copy of buffers using GStreamer caps (capabilities) to the pipeline by adding `video/x-raw(memory: VAMemory)` for Intel GPUs (integrated and discrete).

Read DL Streamer [docs](https://dlstreamer.github.io/dev_guide/gpu_device_selection.html) for more details.

### GPU specific element properties
DL Streamer inference elements also provides property such as `device=GPU` and `pre-process-backend=va-surface-sharing` to infer and pre-process on GPU. Read DL Streamer [docs](https://dlstreamer.github.io/dev_guide/model_preparation.html#model-pre-and-post-processing) for more.

### Selecting the GPU render device of your choice if there is more than one GPU device on the system
If you have multiple GPUs (integrated/discrete), please follow [this](https://dlstreamer.github.io/dev_guide/gpu_device_selection.html) DL Streamer document for selecting the GPU render device of your choice for VA codecs plugins.

## Tutorial on how to use GPU specific pipelines

> Note - This sample application already provides a default `docker-compose.yml` file that includes the necessary GPU access to the containers.

The pipeline `pallet_defect_detection_gpu` contains GPU specific elements and uses GPU backend for inferencing. We can start the pipeline as follows:

```sh
./sample_start.sh -p pallet_defect_detection_gpu
```

Go to grafana as explained in [get-started](./get-started.md) to view the dashboard.
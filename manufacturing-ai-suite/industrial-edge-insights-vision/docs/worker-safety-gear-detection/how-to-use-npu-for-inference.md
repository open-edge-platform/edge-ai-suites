# How to use NPU for inference

## Pre-requisites
In order to benefit from hardware acceleration, pipelines can be constructed in a manner that different stages such as decoding, inference etc., can make use of these devices.
For containerized applications built using the DL Streamer Pipeline Server, first we need to provide NPU device(s) access to the container user.

### Provide NPU access to the container
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
The changes above adds the container user to the `render` group and provides access to the NPU devices.

### Hardware specific encoder/decoders
Unlike the changes done for the container above, the following requires a modification to the media pipeline itself.

Gstreamer has a variety of hardware specific encoders and decoders elements such as Intel specific VA-API elements that you can benefit from by adding them into your media pipeline. Examples of such elements are `vah264dec`, `vah264enc`, `vajpegdec`, `vajpegdec`, etc.

Additionally, one can also enforce zero-copy of buffers using GStreamer caps (capabilities) to the pipeline by adding `video/x-raw(memory: VAMemory)` for Intel NPUs.

Read DL Streamer [docs](https://dlstreamer.github.io/dev_guide/gpu_device_selection.html) for more details.

### NPU specific element properties
DL Streamer inference elements also provides property such as `device=NPU` and `pre-process-backend=va` which should be used in pipelines with NPU memory. It performs mapping to the system memory and uses VA pre-processor. Read DL Streamer [docs](https://dlstreamer.github.io/dev_guide/model_preparation.html#model-pre-and-post-processing) for more.

## Tutorial on how to use NPU specific pipelines

> Note - This sample application already provides a default `docker-compose.yml` file that includes the necessary NPU access to the containers.

The pipeline `worker_safety_gear_detection_npu` in [pipeline-server-config](../../configs/pipeline-server-config.json) contains NPU specific elements and uses NPU backend for inferencing. We will now start the pipeline with a curl request.

```sh
curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/worker_safety_gear_detection_npu -X POST -H 'Content-Type: application/json' -d '{
    "source": {
        "uri": "file:///home/pipeline-server/resources/videos/Safety_Full_Hat_and_Vest.avi",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "file",
            "path": "/tmp/results.jsonl",
            "format": "json-lines"
        }
    },
    "parameters": {
        "detection-properties": {
            "model": "/home/pipeline-server/resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml"
        }
    }
}'
```

We should see the metadata results in `/tmp/results.jsonl` file.
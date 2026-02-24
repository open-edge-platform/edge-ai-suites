# How to use NPU for inference

## Pre-requisites

To take full advantage of hardware acceleration, pipelines can be designed so that different stages—such as decoding and inference—are executed on the most suitable hardware devices.

Low-power accelerators like a Neural Processing Unit (NPU) can offload neural network computation from the CPU or GPU, enabling more efficient resource utilization and improved overall system performance.

DLStreamer and the DLStreamer Pipeline Server support inference on NPU devices, allowing applications built on these frameworks to leverage NPU acceleration for improved efficiency and performance.

Before running inference on an NPU, ensure that:
- The host system includes a supported NPU device
- The required NPU drivers are installed and properly configured

For detailed setup instructions, refer to the [documentation](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer/dev_guide/advanced_install/advanced_install_guide_prerequisites.html#optional-prerequisite-2-install-intel-npu-drivers).

 For containerized application, following additional changes are required.

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

The pipeline `weld_porosity_classification_npu` in pipeline-server-config contains NPU specific elements and uses NPU backend for inferencing. We will now start the pipeline with a curl request(ensure the application is up and running).
>Note: If you're running multiple instances of app, ensure to provide `NGINX_HTTPS_PORT` number in the url for the app instance i.e. replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`

>If you're running a single instance and using an `NGINX_HTTPS_PORT` other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.
```sh
curl http://<HOST_IP>/api/pipelines/user_defined_pipelines/weld_porosity_classification_npu -X POST -H 'Content-Type: application/json' -d '{
    "source": {
        "uri": "file:///home/pipeline-server/resources/videos/welding.avi",
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
        "classification-properties": {
            "model": "/home/pipeline-server/resources/models/weld-porosity/deployment/Classification/model/model.xml"
        }
    }
}'
```

We should see the metadata results in `/tmp/results.jsonl` file.
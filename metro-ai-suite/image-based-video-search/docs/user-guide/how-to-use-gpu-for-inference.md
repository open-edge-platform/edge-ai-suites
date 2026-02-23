# How to use GPU for inference

## Docker deployment

Follow steps 1 and 2 mentioned in [Get Started](./get-started.md#set-up-and-first-use) guide
if not already done.

### Volume mount GPU config

Comment out CPU and NPU config and uncomment the GPU config present in [compose.yml](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/image-based-video-search/compose.yml)
file under `volumes` section as shown below:

```sh
    volumes:
      # - "./src/dlstreamer-pipeline-server/configs/filter-pipeline/config.cpu.json:/home/pipeline-server/config.json"
      - "./src/dlstreamer-pipeline-server/configs/filter-pipeline/config.gpu.json:/home/pipeline-server/config.json"
      # - "./src/dlstreamer-pipeline-server/configs/filter-pipeline/config.npu.json:/home/pipeline-server/config.json"
```

### Start and run the application

After the above changes to docker compose file, follow from step 3 as mentioned in the
[Get Started](./get-started.md#set-up-and-first-use) guide.

## Helm deployment

Follow step 1 mentioned in this [document](./get-started/deploy-with-helm.md#steps-to-deploy) if not already done.

### Update values.yaml

In `values.yaml` file, change value of `pipeline` config present under
`dlstreamerpipelineserver` section as shown below:

```sh
dlstreamerpipelineserver:
  # key: dlstreamerpipelineserver.repository
  repository:
    # key: dlstreamerpipelineserver.repository.image
    image: docker.io/intel/dlstreamer-pipeline-server
    # key: dlstreamerpipelineserver.repository.tag
    tag: 2025.2.0-ubuntu24
  # key: dlstreamerpipelineserver.replicas
  replicas: 1
  # key: dlstreamerpipelineserver.nodeSelector
  nodeSelector: {}
  # key: dlstreamerpipelineserver.pipeline
  pipeline: config.gpu.json       #### Changed value from config.cpu.json to config.gpu.json
```

### Start the application

After above changes to `values.yaml` file, follow from step 2 as mentioned in the
[Helm Deployment Guide](./get-started/deploy-with-helm.md#steps-to-deploy).

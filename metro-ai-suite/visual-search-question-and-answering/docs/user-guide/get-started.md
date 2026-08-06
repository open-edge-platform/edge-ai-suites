# Get Started Guide

- **Time to Complete:** 30 mins
- **Programming Language:** Python

## Get Started

### Prerequisites

- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
- Install Docker Compose: [Installation Guide](https://docs.docker.com/compose/install/).
- Install Intel Client GPU driver: [Installation Guide](https://dgpu-docs.intel.com/driver/client/overview.html).

### Step 1: Get the docker images

#### Option 1: Build from source

Go to the target directory of your choice and clone the suite.
If you want to clone a specific release branch, replace `main` with the desired tag.
To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

```bash
git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites
git sparse-checkout set metro-ai-suite
cd metro-ai-suite
```

Run the commands to build images for the microservices:

```bash
git clone https://github.com/open-edge-platform/edge-ai-libraries.git -b main
cd edge-ai-libraries/microservices

cd visual-data-preparation-for-retrieval/multimodal-dataprep
./build.sh
cd ../../

docker build -t vector-retriever-milvus:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f vector-retriever/milvus/src/Dockerfile .

cd multimodal-embedding-serving
docker build -t multimodal-embedding-serving:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f docker/Dockerfile .

cd ../../..
```

VLM OpenVINO Serving is not built from source. Pull the published image instead:

```bash
docker pull intel/vlm-openvino-serving:latest
docker tag intel/vlm-openvino-serving:latest vlm-openvino-serving:latest
```

Run the command to build image for the application:

```bash
docker build -t visual-search-qa-app:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f visual-search-question-and-answering/src/Dockerfile .
```

#### Option 2: use remote prebuilt images

Set a remote registry by exporting environment variables:

```bash
export REGISTRY="intel/"
export TAG="latest"
```

### Step 2: Prepare host directories for models and data

```sh
mkdir -p $HOME/data
```

If you would like to test the application with a demo dataset, please continue and follow the instructions in the [Try with a demo dataset](#try-with-a-demo-dataset) section later in this guide.

Otherwise, if you would like to use your own data (images and video), make sure to put them all in the created data directory (`$HOME/data` in the example commands above) and make sure the created path matches with the `HOST_DATA_PATH` variable in `deployment/docker-compose/env.sh` BEFORE deploying the services.

> **Note:** Supported media types are jpg, png, and mp4.

### Step 3: Deploy

#### Option1 (**Recommended**): Deploy with docker compose

1. Go to the deployment files

    ``` bash
    cd visual-search-question-and-answering/
    cd deployment/docker-compose/
    ```

2. Set up environment variables.

   > **Note:** You need to set models first.

   - **Ubuntu**:

     ``` bash
     export EMBEDDING_MODEL_NAME="CLIP/clip-vit-h-14" # Replace with other models if needed
     export VLM_MODEL_NAME="Qwen/Qwen2.5-VL-7B-Instruct" # Replace with other models if needed
     source env.sh
     ```

     > **Important:** You must set `EMBEDDING_MODEL_NAME` and `VLM_MODEL_NAME` before running `env.sh`. See
     > [Supported models](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/multimodal-embedding-serving/supported-models.html) for Multimodal Embedding Serving for available embedding models, and
     > [Supported models](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/vlm-openvino-serving/docs/user-guide/Overview.md#models-supported) for VLM OpenVINO for available VLM models.

     You might want to pay some attention to `VLM_DEVICE`, `EMBEDDING_DEVICE`,
     `MM_DATAPREP_EMBEDDING_DEVICE` and `MM_DATAPREP_DETECTION_DEVICE` in `env.sh`.
     By default, they are `GPU.1`, which applies to a standard hardware platform
     with an integrated GPU as `GPU.0` and a discrete GPU as `GPU.1`. You can
     refer to [OpenVINO's query device sample](https://docs.openvino.ai/2024/learn-openvino/openvino-samples/hello-query-device.html)
     to learn more about how to identify which GPU index should be set.

     Milvus/MinIO/etcd state now uses Docker named volumes by default. For cleanup/reset,
     use `source env.sh --clean-data` (this preserves `ov-models` and
     `dataprep-yolox-models`).

     Object detection is disabled by default, so only full frames are indexed. To
     also embed detected object crops, set `DATA_INGEST_WITH_DETECT=true` before
     running `env.sh`.

   - **EMT-S**:

     If you are on an EMT-S platform, set up the variables correspondingly by running:

     ``` bash
      cd emt-s   # go to emt-s specific files
      export EMBEDDING_MODEL_NAME="CLIP/clip-vit-h-14" # Replace with other models if needed
      export VLM_MODEL_NAME="Qwen/Qwen2.5-VL-7B-Instruct" # Replace with other models if needed
      source env.sh
     ```

3. Deploy with docker compose

   ``` bash
   docker compose -f compose_milvus.yaml up -d
   ```

   It might take a while to start the services for the first time, as there are some models to be prepared.

   Check if all microservices are up and runnning with

   ```sh
   docker compose -f compose_milvus.yaml ps
   ```

   Output:

   ```text
   NAME                         COMMAND                  SERVICE                      STATUS              PORTS
   multimodal-dataprep          "uvicorn src.main:ap…"   multimodal-dataprep          running (healthy)   0.0.0.0:9990->8000/tcp, :::9990->8000/tcp
   milvus-etcd                  "etcd -advertise-cli…"   milvus-etcd                  running (healthy)   2379-2380/tcp
   milvus-minio                 "/usr/bin/docker-ent…"   milvus-minio                 running (healthy)   0.0.0.0:9000-9001->9000-9001/tcp, :::9000-9001->9000-9001/tcp
   milvus-standalone            "/tini -- milvus run…"   milvus-standalone            running (healthy)   0.0.0.0:9091->9091/tcp, 0.0.0.0:19530->19530/tcp, :::9091->9091/tcp, :::19530->19530/tcp
   multimodal-embedding         gunicorn -b 0.0.0.0:8000 - ...   Up (unhealthy)   0.0.0.0:9777->8000/tcp,:::9777->8000/tcp
   retriever-milvus             "uvicorn retriever_s…"   retriever-milvus             running (healthy)   0.0.0.0:7770->7770/tcp, :::7770->7770/tcp
   visual-search-qa-app         "streamlit run app.p…"   visual-search-qa-app         running (healthy)   0.0.0.0:17580->17580/tcp, :::17580->17580/tcp
   vlm-openvino-serving         "/bin/bash -c '/app/…"   vlm-openvino-serving         running (healthy)   0.0.0.0:9764->8000/tcp, :::9764->8000/tcp
   ```

#### Option2: Deploy in Kubernetes

Refer to [Deploy with helm](./get-started/deploy-with-helm.md) for details.

## Try with a demo dataset

*Applicable to deployment with Option 1 (docker compose deployment).

### Prepare demo dataset [DAVIS](https://davischallenge.org/davis2017/code.html)

Use the `prepare_demo_dataset.sh` script shipped in `tests/`. It runs on the host
(it needs `curl`, `unzip` and `ffmpeg`) and writes the dataset into the directory
shared with the dataprep microservice:

```bash
bash tests/prepare_demo_dataset.sh
```

Check your host data directory `$HOME/data` (or `$HOST_DATA_PATH`) and see if
`DAVIS` is there. To save time, only a subset of the dataset is prepared: it is
stored in `$HOME/data/DAVIS/subset`, half as videos and half as sampled images.
Use this path in the next step.

The script also writes a `meta/<basename>.json` sidecar per item with a `camera`
and a `capture_date` field, so the `camera` and date filters in the UI have
values to filter on.

### Use it on Web UI

Go to `http://{host_ip}:17580` with a browser. Put the exact path to the subset of demo dataset (usually`/home/user/data/DAVIS/subset`, may vary according to your local username) into `file directory on host`. Click `UpdataDB` and wait for the uploading done.

Try searching with query text `tractor`, see if the results are correct.

Expected valid inputs are "car-race", "deer", "guitar-violin", "gym", "helicopter", "carousel", "monkeys-trees", "golf", "rollercoaster", "horsejump-stick", "planes-crossing", "tractor"

Try ticking a search result, and ask a question in the leftside chatbox about the selected media.

Note: for each chat request, you may select either a single image, or multiple images, or a single video. Multiple videos or a collection of images+videos are not supported yet.

## Performance

You can check the end-to-end response time for each round of question-and-answering in the chat history.

## Summary

In this get started guide, you learned how to:

- Build the microservice images
- Deploy the application with the microservices
- Try the application with a demo dataset

## Learn More

- Check [System requirements](./get-started/system-requirements.md).
- Learn how to deploy the application with [Helm](./get-started/deploy-with-helm.md).
- Explore more functionalities in [Tutorials](./tutorials.md).
- Understand the components, services, architecture, and data flow, in [Overview](./index.md).
- Check [Troubleshooting](./troubleshooting.md).

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements
./get-started/deploy-with-helm

:::
hide_directive-->

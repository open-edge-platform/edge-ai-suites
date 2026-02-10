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

Clone the source code repository if you don't have it

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
```

Start from `metro-ai-suite`

```bash
cd edge-ai-suites/metro-ai-suite
```

Run the commands to build images for the microservices:

```bash
git clone https://github.com/open-edge-platform/edge-ai-libraries.git
cd edge-ai-libraries/microservices

docker build -t dataprep-visualdata-milvus:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f visual-data-preparation-for-retrieval/milvus/src/Dockerfile .

docker build -t retriever-milvus:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f vector-retriever/milvus/src/Dockerfile .

cd vlm-openvino-serving
docker build -t vlm-openvino-serving:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f docker/Dockerfile .

cd ../multimodal-embedding-serving
docker build -t multimodal-embedding-serving:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f docker/Dockerfile .

cd ../../..
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
     > [multimodal-embedding-serving's supported models](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/multimodal-embedding-serving/docs/user-guide/supported-models.md) for available embedding models, and
     > [vlm-openvino-serving's supported models](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/vlm-openvino-serving/docs/user-guide/Overview.md#models-supported) for available vlm models.

     You might want to pay some attention to `DEVICE`, `VLM_DEVICE` and `EMBEDDING_DEVICE` in `env.sh`. By default, they are `GPU.1`, which applies to a standard hardware platform with an integrated GPU as `GPU.0` and a discrete GPU as `GPU.1`. You can refer to [OpenVINO's query device sample](https://docs.openvino.ai/2024/learn-openvino/openvino-samples/hello-query-device.html) to learn more about how to identify which GPU index should be set.

     Note that the default volume directory for Milvus (the vector DB) data is under `/opt/volumes`.
     If this directory is under constraint or you simply would like to store the data in a
     different location, please set the environment variable via `export DOCKER_VOLUME_DIRECTORY=<your_data_directory>`.
     The Milvus data will be stored at `${DOCKER_VOLUME_DIRECTORY}/volumes` in such case.

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
   dataprep-visualdata-milvus   "uvicorn dataprep_vi…"   dataprep-visualdata-milvus   running (healthy)   0.0.0.0:9990->9990/tcp, :::9990->9990/tcp
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

Create a `prepare_demo_dataset.sh` script as following

```text
CONTAINER_IDS=$(docker ps -a --filter "status=running" -q | xargs -r docker inspect --format '{{.Config.Image}} {{.Id}}' | grep "dataprep-visualdata-milvus" | awk '{print $2}')

# Check if any containers were found
if [ -z "$CONTAINER_IDS" ]; then
  echo "No containers found"
  exit 0
fi

CONTAINER_IDS=($CONTAINER_IDS)
NUM_CONTAINERS=${#CONTAINER_IDS[@]}

docker exec -it ${CONTAINER_IDS[0]} bash -c "python example/example_utils.py -d DAVIS"
exit 0
```

Run the script and check your host data directory `$HOME/data`, see if `DAVIS` is there.

```bash
bash prepare_demo_dataset.sh
```

In order to save time, only a subset of the dataset would be processed. They are stored in `$HOME/data/DAVIS/subset`, use this path to do the next step.

This script only works when the `dataprep-visualdata-milvus` service is available.

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

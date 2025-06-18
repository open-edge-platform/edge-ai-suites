# Get Started Guide

-   **Time to Complete:** 30 mins
-   **Programming Language:** Python

## Get Started

### Prerequisites
-    Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
-    Install Docker Compose: [Installation Guide](https://docs.docker.com/compose/install/).
-    Install Intel Client GPU driver: [Installation Guide](https://dgpu-docs.intel.com/driver/client/overview.html).

### Step 1: Build
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

cd ../../..
```

Run the command to build image for the application:

```bash
docker build -t visual-search-qa-app:latest --build-arg https_proxy=$https_proxy --build-arg http_proxy=$http_proxy --build-arg no_proxy=$no_proxy -f visual-search-question-and-answering/src/Dockerfile .
```

### Step 2: Prepare host directories for models and data

```
mkdir -p $HOME/.cache/huggingface
mkdir -p $HOME/models
mkdir -p $HOME/data
```

Make sure to put all your data (images and video) in the created data directory (`$HOME/data` in the example commands) BEFORE deploying the services.

Note: supported media types: jpg, png, mp4

### Step 3: Deploy

#### Option1 (**Recommended**): Deploy the application together with the Milvus Server

1. Go to the deployment files

    ``` bash
    cd visual-search-question-and-answering/
    cd deployment/docker-compose/
    ```

2.  Set up environment variables

    ``` bash
    source env.sh
    ```

When prompting `Please enter the LOCAL_EMBED_MODEL_ID`, choose one model name from table below and input

##### Supported Local Embedding Models

| Model Name                          | Search in English | Search in Chinese | Remarks|
|-------------------------------------|----------------------|---------------------|---------------|
| CLIP-ViT-H-14                        | Yes                  | No                 |            |
| CN-CLIP-ViT-H-14              | Yes                  | Yes                  | Supports search text query in Chinese       | 

When prompting `Please enter the VLM_MODEL_NAME`, choose one model name from table below and input

##### Supported VLM Models

| Model Name                          | Single Image Support | Multi-Image Support | Video Support | Hardware Support                |
|-------------------------------------|----------------------|---------------------|---------------|---------------------------------|
| Qwen/Qwen2.5-VL-7B-Instruct         | Yes                  | Yes                 | Yes           | GPU                       |


You might want to pay some attention to `DEVICE` and `VLM_DEVICE` in `env.sh`. By default, they are both `GPU.1`, which applies to a standard hardware platform with an integrated GPU as `GPU.0` and the discrete GPU would be `GPU.1`. You can refer to [OpenVINO's query device sample](https://docs.openvino.ai/2024/learn-openvino/openvino-samples/hello-query-device.html) to learn more about how to identify which GPU index should be set.

3.  Deploy with docker compose

    ``` bash
    docker compose -f compose_milvus.yaml up -d
    ```

It might take a while to start the services for the first time, as there are some models to be prepared.

Check if all microservices are up and runnning
    ```bash
    docker compose -f compose_milvus.yaml ps
    ```

Output 
```
NAME                         COMMAND                  SERVICE                      STATUS              PORTS
dataprep-visualdata-milvus   "uvicorn dataprep_vi…"   dataprep-visualdata-milvus   running (healthy)   0.0.0.0:9990->9990/tcp, :::9990->9990/tcp
milvus-etcd                  "etcd -advertise-cli…"   milvus-etcd                  running (healthy)   2379-2380/tcp
milvus-minio                 "/usr/bin/docker-ent…"   milvus-minio                 running (healthy)   0.0.0.0:9000-9001->9000-9001/tcp, :::9000-9001->9000-9001/tcp
milvus-standalone            "/tini -- milvus run…"   milvus-standalone            running (healthy)   0.0.0.0:9091->9091/tcp, 0.0.0.0:19530->19530/tcp, :::9091->9091/tcp, :::19530->19530/tcp
retriever-milvus             "uvicorn retriever_s…"   retriever-milvus             running (healthy)   0.0.0.0:7770->7770/tcp, :::7770->7770/tcp
visual-search-qa-app         "streamlit run app.p…"   visual-search-qa-app         running (healthy)   0.0.0.0:17580->17580/tcp, :::17580->17580/tcp
vlm-openvino-serving         "/bin/bash -c '/app/…"   vlm-openvino-serving         running (healthy)   0.0.0.0:9764->8000/tcp, :::9764->8000/tcp
```

#### Option2: Deploy the application with the Milvus Server deployed separately
If you have customized requirements for the Milvus Server, you may start the Milvus Server separately and run the commands for visual search and QA services only

``` bash
cd visual-search-question-and-answering/
cd deployment/docker-compose/

source env.sh # refer to Option 1 for model selection

docker compose -f compose.yaml up -d
```

## Try with a demo dataset
### Prepare demo dataset [DAVIS](https://davischallenge.org/davis2017/code.html)

Create a `prepare_demo_dataset.sh` script as following
```
CONTAINER_IDS=$(docker ps -a --filter "ancestor=dataprep-visualdata-milvus" -q)

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
Go to `http://{host_ip}:17580` with a browser. Put the exact path to the subset of demo dataset (usually`/home/user/data/DAVIS/subset`, may vary according to your local username) into `file directory on host`. Click `UpdataDB`. Wait for a while and click `showInfo`. You should see that the number of processed files is 25.

Try searching with prompt `tractor`, see if the results are correct.

Expected valid inputs are "car-race", "deer", "guitar-violin", "gym", "helicopter", "carousel", "monkeys-trees", "golf", "rollercoaster", "horsejump-stick", "planes-crossing", "tractor"

Try ticking a search result, and ask a question in the leftside chatbox about the selected media.

Note: for each chat request, you may select either a single image, or multiple images, or a single video. Multiple videos or a collection of images+videos are not supported yet.

## Performance

You can check the end-to-end response time for each round of question-and-answering in the chat history.

## Summary

In this get started guide, you learned how to: 
-    Build the microservice images 
-    Deploy the application with the microservices
-    Try the application with a demo dataset

## Learn More

-    Check the [System requirements](./system-requirements.md)
-    Explore more functionalities in [Tutorials](./tutorials.md).
-    Understand the components, services, architecture, and data flow, in the [Overview](./Overview.md).


## Troubleshooting

### Error Logs

-   Check the container log if a microservice shows mal-functional behaviours 
```bash
docker logs <container_id>
```

-   Click `showInfo` button on the web UI to get essential information about microservices

## Known Issues

-   Sometimes downloading the demo dataset can be slow. Try manually downloading it from [the source website](https://data.vision.ee.ethz.ch/csergi/share/davis/DAVIS-2017-test-dev-480p.zip), and put the zip file under your host `$HOME/data` folder.


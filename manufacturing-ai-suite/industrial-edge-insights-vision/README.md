# Overview
The industrial edge insights for vision is a template for users to create sample applications intended for industrial use cases on the edge.
Users can refer to one of many samples built from the template as a reference.

By adding minimal application specific pre-requisites, the boiler plate code this template provides can help you successfully deploy your application on the edge. 

Both compose based as well as helm based deployments are supported by this application template.

## Description

### Architecture
It consists of the following microservices: 
- DL Streamer Pipeline Server
- Model Registry Microservice(MRaaS)
- MediaMTX server, Coturn server
- Open Telemetry Collector
- Prometheus
- Postgres
- Minio.


<div style="text-align: center;">
    <img src=industrial-edge-insights-vision-architecture.drawio.svg width=800>
</div>

### Directory structure

Following directory structure consisting of generic deployment code as well as pre-baked sample applications are provided.


<br>

    apps/
        application_name/            
            configs/                
                pipeline-server-config.json
            setup.sh
            payload.json
    helm/
        apps/
            application_name/
                setup.sh
                payload.json
                pipeline-server-config.json
        templates/
        values.yaml

    resources/
        application_name/
            models/
            videos/
    
    .env_app_name
    docker-compose.yml
    
    setup.sh
    sample_list.sh
    sample_start.sh
    sample_status.sh
    sample_stop.sh

 - **apps**: containing application specific pre-requisite installers, configurations and runtime data. Users can follow the same structure to create their own application. The data from here is used for docker based deployments.

    - *configs/*: 
            associated container configurations such as DLStreamer Pipeline Server configuration, etc.
    - *setup.sh*: 
            pre-requisite installer to setup envs, download artificats such as models/videos to `resources/` directory. It also sets executable permissions for scripts.
    - *payload.json*: 
            A JSON array file containing one or more request(s) to be sent to DLStreamer Pipeline Server to launch GStreamer pipeline(s). The payload data is associated with the *configs/pipeline-server-config.json* provided for that application. Each JSON inside the array has two keys- `pipeline` and `payload` that refers to the pipeline it belongs to and the payload used to launch an instance of the pipeline.
            
 - **helm**: contains helm charts and application specific pre-requisite installers, configurations and runtime data. The configs and data within it are similar to **apps** but are kept here for easy packaging.

 - **resources**: This directory and its subdirs are created only after installation is done by running `setup.sh` for that application. It contains artificacts such as models, videos etc. Users can modify their application's `setup.sh` script to download artifacts as per their usecase requirements.

 - **.env_app_name**: Environment file containing application specific variables. Before starting the application, Users should rename it to `.env` for compose file to source it automatically.

 - **docker-compose.yml**: A generic, parameterized compose file that can launch a particular sample application defined in the environment variable `SAMPLE_APP`.

 ### Script description
 
 | Shell Command         | Description                              | Parameters                    |
|-----------------------|----------------------------------------|-------------------------------|
| `./setup.sh`     | Runs pre-requisites and app specific installer                   | *(none)*                      |
| `./sample_start.sh`    | Runs all or specific pipeline from the config.json. <br> Optionally, run copies of payload (default 1)| `--all` (default) <br> `--pipeline` or `-p` <br> `--payload-copies` or `-n` |
| `./sample_stop.sh`     | Stops all/specific instance by id      | `--all` (default) <br> `--id` or `-i` |
| `./sample_list.sh`     | List loaded pipelines                   | *(none)*                      |
| `./sample_status.sh –i 89ab898e090a90b0c897d3ea7` | Get pipeline status of all/specific instance | `--all` (default) <br> `--id` or `-i`    |

The shell scripts starting with `sample_*.sh` eases interaction with DLStreamer Pipeline Server REST APIs.

## Prerequisites

Please ensure that you have the correct version of the DL Streamer Pipeline Server image as specified in the [compose](./docker-compose.yml) and [helm](./helm/templates/dlstreamer-pipeline-server.yaml) deployment files. Instructions to build DL Streamer Pipeline Server can be found [here](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/dlstreamer-pipeline-server#build-from-source)

## Getting Started

### Docker based deployment 

General instructions for docker based deployment is as follows.

1. Prepare the `.env` file for compose to source during deployment. This chosen env file defines the application you would be running.
2. Run `setup.sh` to setup pre-requisites, download artifacts, etc.
3. Bring the services up with `docker compose up`.
4. Run `sample_start.sh` to start pipeline. This sends curl request with pre-defined payload to the running DLStreamer Pipeline Server.
5. Run `sample_status.sh` or `sample_list.sh` to monitor pipeline status or list available pipelines.
6. Run `sample_stop.sh` to abort any running pipeline(s).
7. Bring the services down by `docker compose down`.


Using the template above, several industrial recipies have been provided for users to deploy using docker compose.
Click on the applications below to get started.

* [Pallet Defect Detection](apps/pallet-defect-detection/docs/user-guide/get-started.md)
* [PCB Anomaly Detection](apps/pcb-anomaly-detection/docs/user-guide/get-started.md)
* [Weld Porosity Classfication](apps/weld-porosity/docs/user-guide/get-started.md)
* [Worker Safety Gear Detection](apps/worker-safety-gear-detection/docs/user-guide/get-started.md)

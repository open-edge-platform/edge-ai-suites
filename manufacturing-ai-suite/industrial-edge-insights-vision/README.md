# Industrial Edge Insights Vision
Industrial Edge Insights Vision is a template for users to create sample applications intended for industrial use cases on the edge.
Users can refer to one of many samples built from the template as a reference.

By adding minimal application specific pre-requisites, the boiler plate code this template provides can help you successfully deploy your application on the edge. 

Both compose based as well as helm based deployments are supported by this application template.

## Description

### Architecture
It consists of the following microservices: DL Streamer Pipeline Server, Model Registry Microservice(MRaaS), MediaMTX server, Coturn server, Open Telemetry Collector, Prometheus, Postgres and Minio.


<div style="text-align: center;">
    <img src=defect-detection-arch-diagram.png width=800>
</div>
More details to be added..

### Directory structure

Following directory structure consisting of generic deployment code as well as pre-baked sample applications are provided.


<br>

    apps/
        application_name/            
            configs/                
                pipeline-server-config.json
            install.sh
            payload.json
    helm/
        apps/
            application_name/
                install.sh
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
    
    install.sh
    sample_list.sh
    sample_start.sh
    sample_status.sh
    sample_stop.sh

 - **apps**: containing application specific pre-requisite installers, configurations and runtime data. Users can follow the same structure to create their own application. The data from here is used for docker based deployments.

 - **helm**: contains helm charts and application specific pre-requisite installers, configurations and runtime data. The configs and data within it are similar to **apps** but are kept here for easy packaging.

 - **resources**: This directory and its subdirs are created only after installation is done by running `install.sh` for that application. It contains artificacts such as models, videos etc. Users can modify their application's `install.sh` script to download artifacts as per their usecase requriements.

 
    - *configs/*: 
            associated container configurations suchas DLStreamer Pipeline Server configuration, etc.
    - *install.sh*: 
            pre-requisite installer to setup envs, download artificats such as models/videos to `resources/` directory. It also sets executable permissions for scripts.
    - *payload.json*: 
            A JSON array file containing one or more request(s) to be sent to DLStreamer Pipeline Server to launch GStreamer pipeline(s). The payload data is associated with the *configs/pipeline-server-config.json* provided for that application. Each JSON inside the array has two keys- `pipeline` and `payload` that refers to the pipeline it belongs to and the payload used to launch an instance of the pipeline. 

 - **.env_app_name**: Environment file containing application specific variables. Before starting the application, Users should rename it to `.env` for compose file to source it automatically.

 - **docker-compose.yml**: A generic, parameterized compose file that can launch a particular sample application defined in the environment variable `SAMPLE_APP`.

 ### Script description
 
 | Shell Command         | Description                              | Parameters                    |
|-----------------------|----------------------------------------|-------------------------------|
| `./install.sh`     | Runs pre-requisites and app specific installer                   | *(none)*                      |
| `./sample_start.sh`    | Runs all or specific pipeline from the config.json. <br> Optionally, run copies of payload (default 1)| `--all` (default) <br> `--pipeline` or `-p` <br> `--payload-copies` or `-n` |
| `./sample_stop.sh`     | Stops all/specific instance by id      | `--all` (default) <br> `--id` or `-i` |
| `./sample_list.sh`     | List loaded pipelines                   | *(none)*                      |
| `./sample_status.sh –i 89ab898e090a90b0c897d3ea7` | Get pipeline status of all/specific instance | `--all` (default) <br> `--id` or `-i`    |

The shell scripts starting with `sample_*.sh` eases interaction with DLStreamer Pipeline Server REST APIs.

## Prerequisites

Please ensure that you have the correct version of the DL Streamer Pipeline Server image as specified in the [compose](./docker-compose.yml) and [helm](./helm/templates/dlstreamer-pipeline-server.yaml) deployment files. Instructions to build DL Streamer Pipeline Server can be found [here](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/dlstreamer-pipeline-server#build-from-source)

## Getting Started

### 1. Docker based deployment 

General instructions for docker based deployment is as follows.

1. Prepare the `.env` file for compose to source during deployment. This chosen env file defines the application you would be running.
2. Run `install.sh` to setup pre-requisites, download artifacts, etc.
3. Bring the services up with `docker compose up`.
4. Run `sample_start.sh` to start pipeline. This sends curl request with pre-defined payload to the running DLStreamer Pipeline Server.
5. Run `sample_status.sh` or `sample_list.sh` to monitor pipeline status or list available pipelines.
6. Run `sample_stop.sh` to abort any running pipeline(s).
7. Bring the services down by `docker compose down`.

<br>

Using the template above, several industrial recipies have been provided for users to deploy using docker compose.
* Pallet Defect Detection
* Weld Porosity

We will now see how to deploy an application using docker compose

#### Steps
> Note that the following instructions assume Docker engine is setup in the host system.
1.  Set app specific environment variable file
    ```sh
    # For Pallet Defect Detection Sample Application
    cp .env_pallet_defect_detection .env

    # Or

    # For Weld Porosity Detection Sample Application
    cp .env_weld_porosity_classification .env
    ```    

2.  Edit the HOST_IP, proxy and other environment variables in `.env` file as follows
    ```sh
    HOST_IP=<HOST_IP>   # IP address of server where DLStreamer Pipeline Server is running.
    http_proxy=<http proxy> # proxy details if behind proxy
    https_proxy=<https proxy>

    MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
    MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>

    # application directory
    SAMPLE_APP=pallet-defect-detection # For weld porosity, SAMPLE_APP=weld-porosity
    ```
3.  Install pre-requisites. Run with sudo if needed.
    ```sh
    ./install.sh
    ```
    This sets up application pre-requisites, download artifacts, sets executable permissions for scripts etc. Downloaded resource directories are made available to the application via volume mounting in docker compose file automatically.

4.  Bring up the application
    ```sh
    docker compose up -d
    ```
5.  Fetch the list of pipeline loaded available to launch
    ```sh
    ./sample_list.sh
    ```
    This lists the pipeline loaded in DL Streamer Pipeline Server.
    
    Example Output:

    ```sh
    # This is an example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loaded pipelines:
    [
        ...
        {
            "description": "DL Streamer Pipeline Server pipeline",
            "name": "user_defined_pipelines",
            "parameters": {
            "properties": {
                "detection-properties": {
                "element": {
                    "format": "element-properties",
                    "name": "detection"
                }
                }
            },
            "type": "object"
            },
            "type": "GStreamer",
            "version": "pallet_defect_detection"
        }
        ...
    ]
    ```
6.  Start the sample application with a pipeline.
    ```sh
    # For Pallet Defect Detection
    ./sample_start.sh -p pallet_defect_detection

    # Or

    # For Weld Porosity Detection
    ./sample_start.sh -p weld_porosity_classification
    ```
    This command would look for the payload for the pipeline specified in `-p` argument above, inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available. 
    
    Output:

    ```sh
    # This is an example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/apps/pallet-defect-detection/payload.json
    Payload loaded successfully.
    Starting pipeline: pallet_defect_detection
    Launching pipeline: pallet_defect_detection
    Extracting payload for pipeline: pallet_defect_detection
    Found 1 payload(s) for pipeline: pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' {"source":{"uri":"file:///home/pipeline-server/resources/videos/warehouse.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"pdd"}},"parameters":{"detection-properties":{"model":"/home/pipeline-server/resources/models/pallet-defect-detection/model.xml","device":"CPU"}}}
    Posting payload to REST server at http://<HOST_IP>:8080/pipelines/user_defined_pipelines/pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' posted successfully. Response: "4b36b3ce52ad11f0ad60863f511204e2"
    ```
    NOTE: This would start the pipeline. We can view the inference stream on WebRTC by opening a browser and navigating to http://<HOST_IP>:8889/pdd/ for Pallet Defect Detection or http://<HOST_IP>:8889/weld/ for Weld Porosity Detection
    
7.  Get status of pipeline instance(s) running.
    ```sh
    ./sample_status.sh
    ```
    This command lists status of pipeline instances launced during the lifetime of sample application.
    
    Output:
    ```sh
    # This is an example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    [
    {
        "avg_fps": 30.00446179356829,
        "elapsed_time": 36.927825689315796,
        "id": "4b36b3ce52ad11f0ad60863f511204e2",
        "message": "",
        "start_time": 1750956469.620569,
        "state": "RUNNING"
    }
    ]
    ```
8.  Stop pipeline instance.
    ```sh
    ./sample_stop.sh
    ```
    This command will stop all instances that are currently in `RUNNING` state and respond with the last status.
    
    Output:
    ```sh
    # This is an example output for Pallet Defect Detection
    No pipelines specified. Stopping all pipeline instances
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 4b36b3ce52ad11f0ad60863f511204e2
    Pipeline instance with ID '4b36b3ce52ad11f0ad60863f511204e2' stopped successfully. Response: {
    "avg_fps": 30.002200575353214,
    "elapsed_time": 63.72864031791687,
    "id": "4b36b3ce52ad11f0ad60863f511204e2",
    "message": "",
    "start_time": 1750956469.620569,
    "state": "RUNNING"
    }
    ```
    If you wish to stop a specific instance, you can provide it with an `--id` argument to the command.    
    For example, `./sample_stop.sh --id 4b36b3ce52ad11f0ad60863f511204e2`

9.  Bring down the application
    ```sh
    docker compose down -v
    ```
    This will bring down the services in the application and remove any volumes.

### 2. Helm based deployment 

General instructions for helm based deployment is as follows. This assumes you have the Kubernetes cluster already setup and running.

1. Prepare `values.yaml` file to configure the helm chart for your application
2. Run `./install.sh helm` to set env file for scripts to source and identify application specific data such as `HOST_IP`, `REST_SERVER_PORT` and `SAMPLE_APP` directory.
3. Install the helm chart to deploy the app to Kubernetes
4. Copy the resources to container volumes. This is done so that deployments such as ITEP can run where volumes mounts are not feasible.
5. Run `sample_start.sh` to start pipeline. This sends curl request with pre-defined payload to the running DLStreamer Pipeline Server.
6. Run `sample_status.sh` or `sample_list.sh` to monitor pipeline status or list available pipelines.
7. Run `sample_stop.sh` to abort any running pipeline(s).
8. Uninstall the helm chart.

#### Steps
> Note that the following instructions assume Kubernetes and helm are setup in the host system.
1. Set app specific values.yaml file.
    ```sh
    # For Pallet Defect Detection Sample Application
    cp helm/values_pallet_defect_detection.yaml helm/values.yaml

    # Or

    # For Weld Porosity Detection Sample Application
    cp helm/values_weld_porosity_classification.yaml helm/values.yaml
    ```
2.  Edit the HOST_IP, proxy and other environment variables in `values.yaml` as follows
    ```yaml
    env:        
        HOST_IP: <HOST_IP>   # host IP address
        http_proxy: <http proxy> # proxy details if behind proxy
        https_proxy: <https proxy>
        SAMPLE_APP: pallet-defect-detection # application directory, for weld porosity it would be SAMPLE_APP: weld-porosity
    webrtcturnserver:
        username: <username>  # WebRTC credentials e.g. intel1234
        password: <password>
    ```
3.  Install pre-requisites. Run with sudo if needed.
    ```sh
    ./install.sh helm
    ```
    This sets up application pre-requisites, download artifacts, sets executable permissions for scripts etc. Downloaded resource directories.
4.  Install the helm chart
    ```sh
    helm install app-deploy helm -n apps --create-namespace
    ```
5.  Copy the resources such as video and model from local directory to the to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.
    ```sh
    # Below is an example for Pallet Defect Detection. Please adjust the source path of models and videos appropriately for other sample applications.
    POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/pallet-defect-detection/videos/warehouse.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

    kubectl cp resources/pallet-defect-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
    ```
6.  Fetch the list of pipeline loaded available to launch
    ```sh
    ./sample_list.sh
    ```
    This lists the pipeline loaded in DLStreamer Pipeline Server.
    
    Output:
    ```sh
    # This is an example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loaded pipelines:
    [
        ...
        {
            "description": "DL Streamer Pipeline Server pipeline",
            "name": "user_defined_pipelines",
            "parameters": {
            "properties": {
                "detection-properties": {
                "element": {
                    "format": "element-properties",
                    "name": "detection"
                }
                }
            },
            "type": "object"
            },
            "type": "GStreamer",
            "version": "pallet_defect_detection"
        }
        ...
    ]
    ```
7.  Start the sample application with a pipeline.
    ```sh
    # For Pallet Defect Detection
    ./sample_start.sh -p pallet_defect_detection

    # Or

    # For Weld Porosity Detection
    ./sample_start.sh -p weld_porosity_classification
    ```
    This command would look for the payload for the pipeline specified in `-p` argument above, inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available. 
    
    Output:
    ```sh
    # This is an example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/apps/pallet-defect-detection/payload.json
    Payload loaded successfully.
    Starting pipeline: pallet_defect_detection
    Launching pipeline: pallet_defect_detection
    Extracting payload for pipeline: pallet_defect_detection
    Found 1 payload(s) for pipeline: pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' {"source":{"uri":"file:///home/pipeline-server/resources/videos/warehouse.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"pdd"}},"parameters":{"detection-properties":{"model":"/home/pipeline-server/resources/models/models/pallet-defect-detection/model.xml","device":"CPU"}}}
    Posting payload to REST server at http://<HOST_IP>:30107/pipelines/user_defined_pipelines/pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' posted successfully. Response: "99ac50d852b511f09f7c2242868ff651"
    ```
    NOTE: This would start the pipeline. You can view the inference stream on WebRTC by opening a browser and navigating to http://<HOST_IP>:31111/pdd/ for Pallet Defect Detection, http://<HOST_IP>:31111/weld/ for Weld Porosity Detection.

8.  Get status of pipeline instance(s) running.
    ```sh
    ./sample_status.sh
    ```
    This command lists status of pipeline instances launced during the lifetime of sample application.
    
    Output:
    ```sh
    # This is an example output for Pallet Defect Detection
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    [
    {
        "avg_fps": 30.00446179356829,
        "elapsed_time": 36.927825689315796,
        "id": "99ac50d852b511f09f7c2242868ff651",
        "message": "",
        "start_time": 1750956469.620569,
        "state": "RUNNING"
    }
    ]
    ```

9.  Stop pipeline instance.
    ```sh
    ./sample_stop.sh
    ```
    This command will stop all instances that are currently in `RUNNING` state and respond with the last status.
    
    Output:
    ```sh
    # This is an example output for Pallet Defect Detection
    No pipelines specified. Stopping all pipeline instances
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pallet-defect-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 99ac50d852b511f09f7c2242868ff651
    Pipeline instance with ID '99ac50d852b511f09f7c2242868ff651' stopped successfully. Response: {
    "avg_fps": 30.01631239459745,
    "elapsed_time": 49.30651903152466,
    "id": "99ac50d852b511f09f7c2242868ff651",
    "message": "",
    "start_time": 1750960037.1471195,
    "state": "RUNNING"
    }
    ```
    If you wish to stop a specific instance, you can provide it with an `--id` argument to the command.    
    For example, `./sample_stop.sh --id 99ac50d852b511f09f7c2242868ff651`

10.  Uninstall the helm chart.
     ```sh
     helm uninstall app-deploy -n apps
     ```
    
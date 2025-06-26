# Industrial Edge Insights Vision
Industrial Edge Insights Vision is a template for users to create sample applications intended for industrial use cases in the edge.
Users can refer to one of many sample built from the template as a reference.

By adding mimimal application specific pre-requisites, the boiler plate code this template provides can help you successfully deploy your application in the edge. 

Both compose based as well as helm based deployments are supported by this application template.

## Description
### Directory structure
Following directory structure consisting of generic deployment code as well as pre-baked sample applications are provided

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
        models/
        videos/
    
    .env_app_name
    docker-compose.yml
    
    install.sh
    sample_list.sh
    sample_start.sh
    sample_status.sh
    sample_stop.sh

 - **apps**: containing application specific pre-requisite installers, configurations and runtime data. Users can follow the same structure to create their own application. The data from here is user for docker based deployments. More on the them [here]()

 - **helm**: contains helm charts and application specific pre-requisite installers, configurations and runtime data. The configs and data within it are similar to **apps** but are kept here for easy packaging. More on the them [here]()

 - **resources**: This directory and its subdirs are created only after installation is done by running `install.sh` for that application. It contains artificacts such as models, videos etc. Users can modify their application's `install.sh` script to download artifacts as per their usecase requriements.

 
    - *configs/*: 
            associated container configurations suchas DLStreamer Pipeline Server configuration, etc.
    - *install.sh*: 
            pre-requisite installer to setup envs, download artificats such as models/videos to `resources/` directory.sets It also sets executable permissions for scripts.
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

## Getting Started
### 1. Docker based deployment 

General Instruction for docker based deployment is as follows.

1. Prepare the `.env` file for compose to source during deployment. This chosen env file defines the application you would be running.
2. Run `install.sh` to setup pre-requisites, download artifacts,etc.
3. Bring the services up with `docker compose up`.
4. Run `sample_start.sh` to start pipeline. This sends curl request with pre-defined payload to the running DLStreamer Pipeline Server.
5. Run `sample_status.sh` or `sample_list.sh` to monitor pipeline status or list available pipelines.
6. Run `sample_stop.sh` to abort any running pipeline(s).
7. Bring the services down by `docker compose down`.

<br>

Using the template above, several industrial recipies have been provided for users to deploy using docker compose.
* Pallet Defect Detection
* Weld Porosity

We will demonstrate how to deploy Pallet Defect Detection application

### Pallet Defect Detection
#### Overview
This sample application enables real-time pallet condition monitoring by running inference workflows across multiple AI models. It connects multiple video streams from warehouse cameras to AI-powered pipelines, all operating efficiently on a single industrial PC. This solution enhances logistics efficiency and inventory management by detecting defects before they impact operations.
#### Features
The application offers following features

 - High-speed data exchange with low-latency compute.
 - AI-assisted defect detection in real-time as pallets are received at the warehouse.
 - On-premise data processing for data privacy and efficient use of bandwidth.
 - Interconnected warehouses deliver analytics for quick and informed tracking and decision making.

#### How It Works

1.  Set app specific environment variable file
    ```sh
    cp .env_pallet_defect_detection .env
    ```    

2.  Install pre-requisites. Run with sudo if needed.
    ```sh
    ./install.sh
    ```
    This sets up application pre-requisites, download artifacts, sets executable permissions for scripts etc. Downloaded resource directories are made available to the application via volume mounting in docker compose file automatically.

3.  Bring up the application
    ```sh
    docker compose up
    ```
4.  Fetch the list of pipeline loaded available to launch
    ```sh
    ./sample_list.sh
    ```
    This lists the pipeline loaded in DLStreamer Pipeline Server.
    
    Output:

    ```sh    
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
4.  Start the sample application with a pipeline.
    ```sh
    ./sample_start.sh -p pallet_defect_detection
    ```
    This command would look for the payload for the pipeline `pallet_defect_detection` inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available. 
    
    Output:

    ```sh
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
    Posting payload to REST server at http://10.223.22.63:8080/pipelines/user_defined_pipelines/pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' posted successfully. Response: "4b36b3ce52ad11f0ad60863f511204e2"
    ```
    
5.  Get status of pipeline instance(s) running.
    ```sh
    ./sample_status.sh
    ```
    This command lists status of pipeline instances launced during the lifetime of sample application.
    
    Output:
    ```sh
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
6.  Stop pipeline instance.
    ```sh
    ./sample_stop.sh
    ```
    This command will stop all instances that are currently in `RUNNING` state and respond with the last status.
    
    Output:
    ```sh
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

7.  Bring down the application
    ```sh
    docker compose down -v
    ```
    This will bring down the services in the application and remove any volumes.

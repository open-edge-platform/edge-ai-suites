# Industrial Edge Insights Vision
Industrial Edge Insights Vision is a template for users to be able to create sample applications intended for industrial use cases in the edge.
Users can refer to one of many sample built from the template as a reference.

You only need to update the install.sh to get the required artifcats downloaded, add configuration for the dlstreamer pipeline server and then provide the payload to launch pipelines.

## Get Started
### Directory structure

    apps/
        application_name/
            configs/
                pipeline-server-config.json
            payload.json
            install.sh
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

 - **configs**: directory containing dlstreamer pipeline server configuration files. To learn about it click here.

 - **resources**: This directory and its subdirs are created only after installation is done by running `install.sh` for that application. It contains artificacts such as models, videos etc. It can be populated by install script. Users can modify it as per their usecase requriements.

 - **payload.json**: A JSON array file containing one or more pipeline requests. Each JSON inside the array has two keys- `pipeline` and `payload` that refers to the pipeline it belongs to and the payload used to launch an instance of the pipeline. To learn more click here. 

 - **docker-compose.yml**: A generic, parameterized compose file that can launch a particular sample application defined in the environment variable `SAMPLE_APP`.

 - **.env_app_name**: Environment file containing application specific variables. Before starting the application, Users should rename it to `.env` for compose file to source it automatically.

 ### Script description
 
 | Shell Command         | Description                              | Parameters                    |
|-----------------------|----------------------------------------|-------------------------------|
| `./sample_start.sh`    | Runs all or specific pipeline from the config.json. <br> Optionally, run copies of payload (default 1)| `--all` (default) <br> `--pipeline` or `-p` <br> `--payload-copies` or `-n` |
| `./sample_stop.sh`     | Stops all/specific instance by id      | `--all` (default) <br> `--id` or `-i` |
| `./sample_list.sh`     | List loaded pipelines                   | *(none)*                      |
| `./sample_status.sh –i 89ab898e090a90b0c897d3ea7` | Get pipeline status of all/specific instance | `--all` (default) <br> `--id` or `-i`    |

## Sample Applications

Using the template above, several industrial recipies have been provided for users.
* Pallet Defect Detection
* Weld Porosity

### 1. Pallet Defect Detection
Automated quality control with AI-driven vision systems.
#### Overview
This sample application enables real-time pallet condition monitoring by running inference workflows across multiple AI models. It connects multiple video streams from warehouse cameras to AI-powered pipelines, all operating efficiently on a single industrial PC. This solution enhances logistics efficiency and inventory management by detecting defects before they impact operations.
#### Features
Following features are offered with the a sample application.

 - High-speed data exchange with low-latency compute.
 - AI-assisted defect detection in real-time as pallets are received at the warehouse.
 - On-premise data processing for data privacy and efficient use of bandwidth.
 - Interconnected warehouses deliver analytics for quick and informed tracking and decision making.

#### How It Works
Step-by-step

1.  Set app specific environment variable file
    ```sh
    cp .env_app_name .env
    ```    

2.  Install pre-requisites
    ```sh
    ./install.sh
    ```
    This sets up the application with any downloadble artifacts, generate certificates, etc. Both resources and videos directories are made available to the application via volume mounting in docker compose file.

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
4.  Start the sample application with a pipeline
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
    Loading payload from pallet-defect-detection/payload.json
    Payload loaded successfully.
    Starting pipeline: pallet_defect_detection
    Launching pipeline: pallet_defect_detection
    Extracting payload for pipeline: pallet_defect_detection
    Found 1 payload(s) for pipeline: pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' {"source":{"uri":"file:///home/pipeline-server/resources/videos/warehouse.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"pdd"}},"parameters":{"detection-properties":{"model":"/home/pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml","device":"CPU"}}}
    Posting payload to REST server at http://10.223.22.63:8080/pipelines/user_defined_pipelines/pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' posted successfully. Response: "29530ca84b8c11f0be4f92781fa8ebc0"
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
        "avg_fps": 30.000099621032163,
        "elapsed_time": 97.1996808052063,
        "id": "32021b104b8b11f0be4f92781fa8ebc0",
        "message": "",
        "start_time": 1750172166.2762897,
        "state": "COMPLETED"
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
    Stopping pipeline instance with ID: 635680864b8e11f0be4f92781fa8ebc0
    Pipeline instance with ID '635680864b8e11f0be4f92781fa8ebc0' stopped successfully. Response: {
    "avg_fps": 30.13758612746407,
    "elapsed_time": 6.7689526081085205,
    "id": "635680864b8e11f0be4f92781fa8ebc0",
    "message": "",
    "start_time": 1750173537.4881449,
    "state": "RUNNING"
    }
    ```
    If you wish to stop a specific instance, you can provide it with an --id argument to the command.    
    For example, `./sample_stop.sh --id 635680864b8e11f0be4f92781fa8ebc0`

7.  Bring down the application
    ```sh
    docker compose down -v
    ```
    This will bring down the services in the application and remove any volumes.

# Get Started

-   **Time to Complete:** 30 minutes
-   **Programming Language:**  Python 3

## Prerequisites

- [System Requirements](system-requirements.md)

## Setup the application
> Note that the following instructions assume Docker engine is setup in the host system.

1. Clone the **edge-ai-suites** repository and change into industrial-edge-insights-vision directory. The directory contains the utility scripts required in the instructions that follows.
    ```sh
    git clone https://github.com/open-edge-platform/edge-ai-suites.git
    cd manufacturing-ai-suite/industrial-edge-insights-vision
    ```
2.  Set app specific environment variable file
    ```sh
    cp .env_pallet_defect_detection .env
    ```    

3.  Edit the HOST_IP and other environment variables in `.env` file as follows
    ```sh
    HOST_IP=<HOST_IP>   # IP address of server where DLStreamer Pipeline Server is running.

    MR_PSQL_PASSWORD=  #PostgreSQL service & client adapter e.g. intel1234

    MR_MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
    MR_MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

    MR_URL= # Model registry url. Example http://<IP_address_of_model_registry_server>:32002

    MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
    MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>

    # application directory
    SAMPLE_APP=pallet-defect-detection
    ```
4.  Install pre-requisites. Run with sudo if needed.
    ```sh
    ./setup.sh
    ```
    This sets up application pre-requisites, download artifacts, sets executable permissions for scripts etc. Downloaded resource directories are made available to the application via volume mounting in docker compose file automatically.

## Deploy the Application

5.  Bring up the application
    ```sh
    docker compose up -d
    ```
6.  Fetch the list of pipeline loaded available to launch
    ```sh
    ./sample_list.sh
    ```
    This lists the pipeline loaded in DL Streamer Pipeline Server.
    
    Example Output:

    ```sh
    # Example output for Pallet Defect Detection
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
    ./sample_start.sh -p pallet_defect_detection
    ```
    This command would look for the payload for the pipeline specified in `-p` argument above, inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available. 
    
    Output:

    ```sh
    # Example output for Pallet Defect Detection
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
    NOTE: This would start the pipeline. We can view the inference stream on WebRTC by opening a browser and navigating to below url
    ```
    http://<HOST_IP>:8889/pdd/
    ```
    
8.  Get status of pipeline instance(s) running.
    ```sh
    ./sample_status.sh
    ```
    This command lists status of pipeline instances launched during the lifetime of sample application.
    
    Output:
    ```sh
    # Example output for Pallet Defect Detection
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
9.  Stop pipeline instance.
    ```sh
    ./sample_stop.sh
    ```
    This command will stop all instances that are currently in `RUNNING` state and respond with the last status.
    
    Output:
    ```sh
    # Example output for Pallet Defect Detection
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

10. Bring down the application
    ```sh
    docker compose down -v
    ```
    This will bring down the services in the application and remove any volumes.


## Further Reading
- [Helm based deployment](how-to-deploy-using-helm-charts.md)
- [MLOps using Model Registry](how-to-enable-mlops.md)
- [Run multiple AI pipelines](how-to-run-multiple-ai-pipelines.md)
- [Publish frames to S3 storage pipelines](how-to-run-store-frames-in-s3.md)
- [View telemetry data in Open Telemetry](how-to-view-telemetry-data.md)
- [Publish metadata to OPCUA](how-to-use-opcua-publisher.md)

## Troubleshooting
- [Troubleshooting Guide](troubleshooting-guide.md)

# Get Started

-   **Time to Complete:** 30 minutes
-   **Programming Language:**  Python 3

## Prerequisites

- [System Requirements](system-requirements.md)

## Set up the application

The following instructions assume Docker engine is correctly set up in the host system.
If not, follow the [installation guide for docker engine](https://docs.docker.com/engine/install/ubuntu/) at docker.com.

1. Clone the **edge-ai-suites** repository and change into industrial-edge-insights-vision directory. The directory contains the utility scripts required in the instructions that follows.

    ```bash
    git clone https://github.com/open-edge-platform/edge-ai-suites.git
    cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/
    ```

2.  Set app-specific environment variable file
    ```bash
    cp .env_pallet_defect_detection .env
    ```

3.  Edit the `HOST_IP`, `MTX_WEBRTCICESERVERS2_0_USERNAME` and `MTX_WEBRTCICESERVERS2_0_PASSWORD` environment variables in the `.env` file as follows:

    ```bash
    HOST_IP=<HOST_IP>   # IP address of server where DLStreamer Pipeline Server is running.

    MR_PSQL_PASSWORD=  #PostgreSQL service & client adapter e.g. intel1234

    MR_MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
    MR_MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

    MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
    MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>

    # application directory
    SAMPLE_APP=pallet-defect-detection
    ```

4.  Install the pre-requisites. Run with sudo if needed.

    ```bash
    ./setup.sh
    ```

    This script sets up application pre-requisites, download artifacts, sets executable permissions for scripts etc. Downloaded resource directories are made available to the application via volume mounting in docker compose file automatically.

## Deploy the Application

5.  Start the Docker application:

   The Docker daemon service should start automatically at boot. If not, you can start it manually:
   ```bash
   sudo systemctl start docker
   ```

    ```bash
    docker compose up -d
    ```

6.  Fetch the list of pipeline loaded available to launch:

    ```bash
    ./sample_list.sh
    ```

    This lists the pipeline loaded in DL Streamer Pipeline Server.

    Example Output:

    ```bash
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

    ```bash
    ./sample_start.sh -p pallet_defect_detection
    ```

    This command will look for the payload for the pipeline specified in the `-p` argument above, inside the `payload.json` file and launch a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different available options.

    Output:

    ```bash
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
    Posting payload to REST server at https://<HOST_IP>/api/pipelines/user_defined_pipelines/pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection' posted successfully. Response: "4b36b3ce52ad11f0ad60863f511204e2"
    ```

    > **NOTE:** This will start the pipeline. To view the inference stream on WebRTC, open a browser and navigate to https://<HOST_IP>/mediamtx/pdd/ for Pallet Defect Detection

8.  Get the status of running pipeline instance(s):

    ```bash
    ./sample_status.sh
    ```

    This command lists the statuses of pipeline instances launched during the lifetime of sample application.

    Output:

    ```bash
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

9.  Stop pipeline instances.

    ```bash
    ./sample_stop.sh
    ```

    This command will stop all instances that are currently in the `RUNNING` state and return their last status.

    Output:

    ```bash
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

    To stop a specific instance, identify it with the `--id` argument.
    For example, `./sample_stop.sh --id 4b36b3ce52ad11f0ad60863f511204e2`

10. Stop the Docker application.

    ```bash
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

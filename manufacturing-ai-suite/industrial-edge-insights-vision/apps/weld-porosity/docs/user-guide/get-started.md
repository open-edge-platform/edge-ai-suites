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

2.  Set app specific environment variable file

    ```bash
    cp .env_weld_porosity_classification .env
    ```

3.  Edit the `HOST_IP`, `MTX_WEBRTCICESERVERS2_0_USERNAME` and `MTX_WEBRTCICESERVERS2_0_PASSWORD` environment variables in `.env` file, as follows:

    ```bash
    HOST_IP=<HOST_IP>   # IP address of server where DLStreamer Pipeline Server is running.

    MR_PSQL_PASSWORD=  #PostgreSQL service & client adapter e.g. intel1234

    MR_MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
    MR_MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

    MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
    MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>

    # application directory
    SAMPLE_APP=env_weld_porosity_classification
    ```

4.  Install pre-requisites. Run with sudo if needed.

    ```bash
    ./setup.sh
    ```

    This sets up application pre-requisites, downloads artifacts, sets executable permissions for scripts etc. Downloaded resource directories are made available to the application via volume mounting in the docker compose file automatically.

## Deploy the Application

5.  Start the Docker application:

   The Docker daemon service should start automatically at boot. If not, you can start it manually:
   ```bash
   sudo systemctl start docker
   ```

    ```bash
    docker compose up -d
    ```

6.  Fetch the list of pipeline loaded available to launch

    ```bash
    ./sample_list.sh
    ```

    This lists the pipeline loaded in DL Streamer Pipeline Server.

    Example Output:

    ```bash
    # Example output for Weld Porosity Classification
    Environment variables loaded from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: weld-porosity
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
                "classification-properties": {
                "element": {
                    "format": "element-properties",
                    "name": "classification"
                }
                }
            },
            "type": "object"
            },
            "type": "GStreamer",
            "version": "weld_porosity_classification"
        },
        ...
    ]
    ```

7.  Start the sample application with a pipeline.

    ```bash
    ./sample_start.sh -p weld_porosity_classification
    ```

    This command will look for the payload for the pipeline specified in `-p` argument above, inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available.

    Output:

    ```bash
    # Example output for Weld Porosity Classification
    Environment variables loaded from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: weld-porosity
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/apps/weld-porosity/payload.json
    Payload loaded successfully.
    Starting pipeline: weld_porosity_classification
    Launching pipeline: weld_porosity_classification
    Extracting payload for pipeline: weld_porosity_classification
    Found 1 payload(s) for pipeline: weld_porosity_classification
    Payload for pipeline 'weld_porosity_classification' {"source":{"uri":"file:///home/pipeline-server/resources/videos/welding.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"weld"}},"parameters":{"classification-properties":{"model":"/home/pipeline-server/resources/models/weld-porosity/deployment/Classification/model/model.xml","device":"CPU"}}}
    Posting payload to REST server at https://<HOST_IP>/api/pipelines/user_defined_pipelines/weld_porosity_classification
    Payload for pipeline 'weld_porosity_classification' posted successfully. Response: "6d06422c5c7511f091f03266c7df2abf"

    ```

    > **NOTE:** This will start the pipeline. The inference stream can be viewed on WebRTC, in a browser, at the following url:
    
    ```bash
    https://<HOST_IP>/mediamtx/weld/
    ```

8.  Get status of pipeline instance(s) running.

    ```bash
    ./sample_status.sh
    ```

    This command lists status of pipeline instances launched during the lifetime of sample application.

    Output:

    ```bash
    # Example output for Weld Porosity Classification
    Environment variables loaded from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: weld-porosity
    [
    {
        "avg_fps": 30.20765374167394,
        "elapsed_time": 2.0193545818328857,
        "id": "0714ca6e5c7611f091f03266c7df2abf",
        "message": "",
        "start_time": 1752032244.3554578,
        "state": "RUNNING"
    }
    ]
    ```

9.  Stop pipeline instances.

    ```bash
    ./sample_stop.sh
    ```

    This command will stop all instances that are currently in `RUNNING` state and respond with the last status.

    Output:

    ```bash
    # Example output for Weld Porosity Classification
    No pipelines specified. Stopping all pipeline instances
    Environment variables loaded from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: weld-porosity
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 0714ca6e5c7611f091f03266c7df2abf
    Pipeline instance with ID '0714ca6e5c7611f091f03266c7df2abf' stopped successfully. Response: {
    "avg_fps": 30.00652493520486,
    "elapsed_time": 4.965576171875,
    "id": "0714ca6e5c7611f091f03266c7df2abf",
    "message": "",
    "start_time": 1752032244.3554578,
    "state": "RUNNING"
    }
    ```

    To stop a specific instance, identify it with the `--id` argument.
    For example, `./sample_stop.sh --id 0714ca6e5c7611f091f03266c7df2abf`

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
- [Publish metadata to MQTT](how-to-start-mqtt-publisher.md)

## Troubleshooting

- [Troubleshooting Guide](troubleshooting-guide.md)

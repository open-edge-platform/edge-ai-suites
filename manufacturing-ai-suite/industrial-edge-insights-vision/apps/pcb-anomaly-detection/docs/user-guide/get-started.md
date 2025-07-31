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
    cp .env_pcb_anomaly_detection .env
    ```    

3.  Edit the HOST_IP and other environment variables in `.env` file as follows
    ```sh
    HOST_IP=<HOST_IP>   # IP address of server where DLStreamer Pipeline Server is running.

    MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
    MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>

    # application directory
    SAMPLE_APP=pcb-anomaly-detection
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
    # Example output for PCB Anomaly Detection
    Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pcb-anomaly-detection
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
            "version": "pcb_anomaly_detection"
        }
        ...
    ]
    ```
7.  Start the sample application with a pipeline.
    ```sh
    ./sample_start.sh -p pcb_anomaly_detection
    ```
    This command would look for the payload for the pipeline specified in `-p` argument above, inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available. 
    
    Output:

    ```sh
    # Example output for PCB Anomaly Detection
    Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pcb-anomaly-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/apps/pcb-anomaly-detection/payload.json
    Payload loaded successfully.
    Starting pipeline: pcb_anomaly_detection
    Launching pipeline: pcb_anomaly_detection
    Extracting payload for pipeline: pcb_anomaly_detection
    Found 1 payload(s) for pipeline: pcb_anomaly_detection
    Payload for pipeline 'pcb_anomaly_detection' {"source":{"uri":"file:///home/pipeline-server/resources/videos/anomalib_pcb_test.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"anomaly"}},"parameters":{"classification-properties":{"model":"/home/pipeline-server/resources/models/pcb-anomaly-detection/deployment/Anomaly classification/model/model.xml","device":"CPU"}}}
    Posting payload to REST server at http://10.223.23.156:8080/pipelines/user_defined_pipelines/pcb_anomaly_detection
    Payload for pipeline 'pcb_anomaly_detection' posted successfully. Response: "f0c0b5aa5d4911f0bca7023bb629a486"
    ```
    NOTE: This would start the pipeline. We can view the inference stream on WebRTC by opening a browser and navigating to below url 
    ```
    http://<HOST_IP>:8889/anomaly/
    ```
    
8.  Get status of pipeline instance(s) running.
    ```sh
    ./sample_status.sh
    ```
    This command lists status of pipeline instances launched during the lifetime of sample application.
    
    Output:
    ```sh
    # Example output for PCB Anomaly Detection
    Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pcb-anomaly-detection
    [
    {
        "avg_fps": 24.123323428597942,
        "elapsed_time": 9.865960359573364,
        "id": "f0c0b5aa5d4911f0bca7023bb629a486",
        "message": "",
        "start_time": 1752123260.5558383,
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
    # Example output for PCB Anomaly Detection
    No pipelines specified. Stopping all pipeline instances
    Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: pcb-anomaly-detection
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: f0c0b5aa5d4911f0bca7023bb629a486
    Pipeline instance with ID 'f0c0b5aa5d4911f0bca7023bb629a486' stopped successfully. Response: {
        "avg_fps": 26.487679514091333,
        "elapsed_time": 25.634552478790283,
        "id": "f0c0b5aa5d4911f0bca7023bb629a486",
        "message": "",
        "start_time": 1752123260.5558383,
        "state": "RUNNING"
    }
    ```
    If you wish to stop a specific instance, you can provide it with an `--id` argument to the command.    
    For example, `./sample_stop.sh --id f0c0b5aa5d4911f0bca7023bb629a486`

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

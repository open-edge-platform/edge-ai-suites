# Get Started

- **Time to Complete:** 30 minutes
- **Programming Language:**  Python 3

## Prerequisites

- [System Requirements](./get-started/system-requirements.md)

## Setup the application

The following instructions assume Docker engine is correctly set up in the host system.
If not, follow the [installation guide for docker engine](https://docs.docker.com/engine/install/ubuntu/).

1. Clone the **edge-ai-suites** repository and change into industrial-edge-insights-vision directory. The directory contains the utility scripts required in the instructions that follows.

    ```bash
    git clone https://github.com/open-edge-platform/edge-ai-suites.git
    cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/
    ```

2. Set app specific environment variable file:

   ```bash
   cp .env_pcb-anomaly-detection .env
   ```

3. Edit the below mentioned environment variables in the `.env` file as follows:

   ```bash
   HOST_IP=<HOST_IP>   # IP address of server where DL Streamer Pipeline Server is running.

   MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
   MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

   MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
   MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>

   # application directory
   SAMPLE_APP=pcb-anomaly-detection
   ```

4. Install the pre-requisites. Run with sudo if needed.

   ```bash
   ./setup.sh
   ```

   This script sets up application pre-requisites, downloads artifacts, sets executable permissions for scripts etc. Downloaded resource directories are made available to the application via volume mounting in docker compose file automatically.

## Deploy the Application

1. Start the Docker application:
    >If you're running multiple instances of app, start the services using `./run.sh up` instead.
    ```bash
    docker compose up -d
    ```

2. Fetch the list of pipeline loaded available to launch:

   ```bash
   ./sample_list.sh
   ```

   This lists the pipeline loaded in DL Streamer Pipeline Server.

   Example Output:

   ```bash
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

3. Start the sample application with a pipeline.

   ```bash
   ./sample_start.sh -p pcb_anomaly_detection
   ```

   This command will look for the payload for the pipeline specified in the `-p` argument above, inside the `payload.json` file and launch a pipeline instance in DL Streamer Pipeline Server. Refer to the table, to learn about different available options.

   > **IMPORTANT**: Before you run `sample_start.sh` script, make sure that
   > `jq` is installed on your system. See the
   > [troubleshooting guide](./troubleshooting.md#unable-to-parse-json-payload-due-to-missing-jq-package)
   > for more details.

   Output:

   ```text
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
   Posting payload to REST server at https://<HOST_IP>/api/pipelines/user_defined_pipelines/pcb_anomaly_detection
   Payload for pipeline 'pcb_anomaly_detection' posted successfully. Response: "f0c0b5aa5d4911f0bca7023bb629a486"
   ```

   > **Note:** This will start the pipeline. The inference stream can be viewed on WebRTC, in a browser at the following url:
   
   >If you're running multiple instances of app, ensure to provide `NGINX_HTTPS_PORT` number in the url for the app instance i.e. replace <HOST_IP> with <HOST_IP>:<NGINX_HTTPS_PORT>

   ```bash
   https://<HOST_IP>/mediamtx/anomaly/
   ```

4. Get the status of running pipeline instance(s).

   ```bash
   ./sample_status.sh
   ```

   This command lists status of pipeline instances launched during the lifetime of sample application.

   Output:

   ```bash
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

5. Stop pipeline instances.

   ```bash
   ./sample_stop.sh
   ```

   This command will stop all instances that are currently in the `RUNNING` state and return their last status.

   Output:

   ```tex
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

   To stop a specific instance, identify it with the `--id` argument.
    For example, `./sample_stop.sh --id f0c0b5aa5d4911f0bca7023bb629a486`

6. Stop the Docker application:
    >If you're running multiple instances of app, stop the services using `./run.sh down` instead.
   ```bash
   docker compose down -v
   ```

   This will bring down the services in the application and remove any volumes.

## Further Reading

- [Deploy with Edge Orchestrator](./get-started/deploy-with-edge-orchestrator.md)
- [MLOps using Model Registry](./how-to-guides/enable-mlops.md)
- [Run multiple AI pipelines](./how-to-guides/run-multiple-ai-pipelines.md)
- [Publish frames to S3 storage pipelines](./how-to-guides/store-frames-in-s3.md)
- [View telemetry data in Open Telemetry](./how-to-guides/view-telemetry-data.md)
- [Publish metadata to OPCUA](./how-to-guides/use-opcua-publisher.md)
- [Troubleshooting](./troubleshooting.md)

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements.md
./get-started/environment-variables
./get-started/deploy-with-helm
./get-started/deploy-with-edge-orchestrator

:::
hide_directive-->

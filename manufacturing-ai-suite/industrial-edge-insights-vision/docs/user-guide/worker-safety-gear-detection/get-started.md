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

2. Set app specific environment variable file

   ```bash
   cp .env_worker-safety-gear-detection .env
   ```

3. Edit the below mentioned environment variables in the `.env` file as follows:

   ```bash
   HOST_IP=<HOST_IP>   # IP address of server where DL Streamer Pipeline Server is running.

   MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
   MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

   MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
   MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>

   # application directory
   SAMPLE_APP=worker-safety-gear-detection
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

2. Fetch the list of pipeline loaded available to launch

   ```bash
   ./sample_list.sh
   ```

   This lists the pipeline loaded in DL Streamer Pipeline Server.

   Example Output:

   ```bash
   # Example output for Worker Safety gear detection
   Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
   Running sample app: worker-safety-gear-detection
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
           "version": "worker_safety_gear_detection"
       }
       ...
   ]
   ```

3. Start the sample application with a pipeline.

   ```bash
   ./sample_start.sh -p worker_safety_gear_detection
   ```

   This command will look for the payload for the pipeline specified in the `-p` argument above, inside the `payload.json` file and launch a pipeline instance in DL Streamer Pipeline Server. Refer to the table, to learn about different available options.

   > **IMPORTANT**: Before you run `sample_start.sh` script, make sure that
   > `jq` is installed on your system. See the
   > [troubleshooting guide](./troubleshooting.md#unable-to-parse-json-payload-due-to-missing-jq-package)
   > for more details.

   Output:

   ```text
   # Example output for Worker Safety gear detection
   Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
   Running sample app: worker-safety-gear-detection
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/apps/worker-safety-gear-detection/payload.json
   Payload loaded successfully.
   Starting pipeline: worker_safety_gear_detection
   Launching pipeline: worker_safety_gear_detection
   Extracting payload for pipeline: worker_safety_gear_detection
   Found 1 payload(s) for pipeline: worker_safety_gear_detection
   Payload for pipeline 'worker_safety_gear_detection' {"source":{"uri":"file:///home/pipeline-server/resources/videos/Safety_Full_Hat_and_Vest.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"worker_safety"}},"parameters":{"detection-properties":{"model":"/home/pipeline-server/resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml","device":"CPU"}}}
   Posting payload to REST server at https://<HOST_IP>/api/pipelines/user_defined_pipelines/worker_safety_gear_detection
   Payload for pipeline 'worker_safety_gear_detection' posted successfully. Response: "784b87b45d1511f08ab0da88aa49c01e"
   ```

   NOTE: This will start the pipeline. The inference stream can be viewed on WebRTC, in a browser, at the following url:

   >If you're running multiple instances of app, ensure to provide `NGINX_HTTPS_PORT` number in the url for the app instance i.e. replace <HOST_IP> with <HOST_IP>:<NGINX_HTTPS_PORT>

   ```sh
   https://<HOST_IP>/mediamtx/worker_safety/
   ```

4. Get the status of running pipeline instance(s).

   ```bash
   ./sample_status.sh
   ```

   This command lists the statuses of pipeline instances launched during the lifetime of sample application.

   Output:

   ```text
   # Example output for Worker Safety gear detection
   Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
   Running sample app: worker-safety-gear-detection
   [
   {
       "avg_fps": 30.036955894826452,
       "elapsed_time": 3.096184492111206,
       "id": "784b87b45d1511f08ab0da88aa49c01e",
       "message": "",
       "start_time": 1752100724.3075056,
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

   ```bash
   # Example output for Worker Safety gear detection
   No pipelines specified. Stopping all pipeline instances
   Environment variables loaded from [WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision/.env
   Running sample app: worker-safety-gear-detection
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 784b87b45d1511f08ab0da88aa49c01e
   Pipeline instance with ID '784b87b45d1511f08ab0da88aa49c01e' stopped successfully. Response: {
       "avg_fps": 29.985911953641363,
       "elapsed_time": 37.45091152191162,
       "id": "784b87b45d1511f08ab0da88aa49c01e",
       "message": "",
       "start_time": 1752100724.3075056,
       "state": "RUNNING"
   }
   ```

   To stop a specific instance, identify it with the `--id` argument.
   For example, `./sample_stop.sh --id 784b87b45d1511f08ab0da88aa49c01e`

6. Stop the Docker application.
   
   >If you're running multiple instances of app, stop the services using `./run.sh down` instead.

   ```bash
   docker compose down -v
   ```

   This will bring down the services in the application and remove any volumes.

## Further Reading

- [Deploy with Helm](./get-started/deploy-with-helm.md)
- [Deploy with Edge Orchestrator](./get-started/deploy-with-edge-orchestrator.md)
- [MLOps using Model Registry](./how-to-guides/enable-mlops.md)
- [Run multiple AI pipelines](./how-to-guides/run-multiple-ai-pipelines.md)
- [Publish frames to S3 storage pipelines](./how-to-guides/store-frames-in-s3.md)
- [View telemetry data in Open Telemetry](./how-to-guides/view-telemetry-data.md)
- [Publish metadata to OPCUA](./how-to-guides/use-opcua-publisher.md)
- [Integrate Balluff SDK with supported cameras](./how-to-guides/integrate-balluff-sdk.md)
- [Integrate Pylon SDK for Basler camera support](./how-to-guides/integrate-pylon-sdk.md)

## Troubleshooting

- [Troubleshooting](./troubleshooting.md)

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements
./get-started/environment-variables
./get-started/deploy-with-helm
./get-started/deploy-with-edge-orchestrator

:::
hide_directive-->

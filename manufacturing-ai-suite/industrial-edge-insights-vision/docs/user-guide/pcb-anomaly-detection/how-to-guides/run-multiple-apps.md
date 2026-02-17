# Run Multiple Apps

- **Time to Complete:** 30 minutes
- **Programming Language:**  Python 3

## Prerequisites

- [System Requirements](../get-started/system-requirements.md)

## Overview

This tutorial demonstrates how to simultaneously deploy and manage multiple industrial edge AI vision applications using Docker Compose. You'll learn to configure and run multiple instances of the same application or different applications in parallel, with each instance operating its own isolated DLStreamer Pipeline Server and associated services, all accessible through dedicated NGINX proxy configurations.

**What you'll learn:**

- How to configure multiple application instances with unique port assignments
- How to independently deploy, start, stop, and monitor multiple running applications
- How to access and view streams from each application instance

## Set up the Applications

1. Clone the **edge-ai-suites** repository and navigate to the `industrial-edge-insights-vision` directory:

   ```bash
   git clone https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/
   ```

2. Create a `config.yml` file to define your application instances and their unique port configurations. Add the following sample contents and save.

   Example:

   ```text
   pcb-anomaly-detection:
     pcb1:
       NGINX_HTTP_PORT: 8080
       NGINX_HTTPS_PORT: 8443
       COTURN_UDP_PORT: 3478
       MINIO_SERVER_PORT: 8001
     pcb2:
       NGINX_HTTP_PORT: 9080
       NGINX_HTTPS_PORT: 9443
       COTURN_UDP_PORT: 3479
       MINIO_SERVER_PORT: 9001

   weld-porosity:
     weld1:
       NGINX_HTTP_PORT: 10080
       NGINX_HTTPS_PORT: 10443
       COTURN_UDP_PORT: 3480
       MINIO_SERVER_PORT: 10001
   ```

   > **Note:** A sample configuration file `sample_config.yml` is provided to help users understand the multi-instance setup and get started. This configuration defines three example instances with identifiers: pdd1, pdd2, and weld1. The accompanying sample scripts utilize these identifiers to perform operations on individual application instances.

3. Edit the environment variables below in all the `.env_<SAMPLE_APP>` files:

   ```text
   HOST_IP=<HOST_IP>   # IP address of server where DL Streamer Pipeline Server is running.

   MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
   MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

   MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
   MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>
   ```

4. Install pre-requisites for all the instances:

   ```bash
   ./setup.sh
   ```

   This does the following:

   - Parses through the config.yml
   - Downloads resources for each instance
   - Creates a folder temp_apps/<SAMPLE_APP>/<INSTANCE_NAME> that contains configs folder, .env file and payload.json
   - Updates and adds the ports mentioned in config.yml to the respective .env file
   - Sets executable permissions for scripts

## Deploy the Applications

### Deploy all the application instances

1. Deploy all the instances given in config.yml:

   ```bash
   ./run.sh up
   ```

   It starts all the containers for each instance in `config.yml`

2. Verify all containers are running:

   ```bash
   docker ps
   ```

## Start AI Pipelines

### Start pipeline for all instances

1. Fetch the list of pipelines for all instances:

   ```bash
   ./sample_list.sh
   ```

   Example Output:

   ```text
   -------------------------------------------
   Status of: pcb1 (SAMPLE_APP: pcb-anomaly-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Getting list of loaded pipelines...
   Loaded pipelines:
   [
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
           ...

   -------------------------------------------
   Status of: pcb2 (SAMPLE_APP: pcb-anomaly-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Getting list of loaded pipelines...
   Loaded pipelines:
   [
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
         ...
   -------------------------------------------
   Status of: weld1 (SAMPLE_APP: weld-porosity)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Getting list of loaded pipelines...
   Loaded pipelines:
   [
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
         ...
   ]
   ```

2. Start pipeline for all instances in config.yml:

   ```bash
   ./sample_start.sh
   ```

   > **Important:** Before you run `sample_start.sh` script, make sure that `jq` is installed on your system. See the [troubleshooting guide](../troubleshooting.md#unable-to-parse-json-payload-due-to-missing-jq-package) for more details.

   Output:

   ```text
   No pipeline specified. Starting the first pipeline.

   ------------------------------------------
   Processing instance: pcb1 from SAMPLE_APP: pcb-anomaly-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/payload.json
   Payload loaded successfully.
   Starting first pipeline: pcb_anomaly_detection
   Launching pipeline: pcb_anomaly_detection
   Extracting payload for pipeline: pcb_anomaly_detection
   Found 1 payload(s) for pipeline: pcb_anomaly_detection
   Payload for pipeline 'pcb_anomaly_detection'. Response: "111c75f00b0011f1905b4b91749d35cf"

   ------------------------------------------
   Processing instance: pcb2 from SAMPLE_APP: pcb-anomaly-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb2/payload.json
   Payload loaded successfully.
   Starting first pipeline: pcb_anomaly_detection
   Launching pipeline: pcb_anomaly_detection
   Extracting payload for pipeline: pcb_anomaly_detection
   Found 1 payload(s) for pipeline: pcb_anomaly_detection
   Payload for pipeline 'pcb_anomaly_detection'. Response: "1127a5530b0011f1bf5ab18e98b8d602"

   ------------------------------------------
   Processing instance: weld1 from SAMPLE_APP: weld-porosity
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/payload.json
   Payload loaded successfully.
   Starting first pipeline: weld_porosity_classification
   Launching pipeline: weld_porosity_classification
   Extracting payload for pipeline: weld_porosity_classification
   Found 1 payload(s) for pipeline: weld_porosity_classification
   Payload for pipeline 'weld_porosity_classification'. Response: "1130ca860b0011f1aa88a902d69c78e2"
   ```

3. Access WebRTC stream:

   The inference stream can be viewed on WebRTC, in a browser, at the following url depending on the SAMPLE_APP:

   > **Note:** The `NGINX_HTTPS_PORT` is different for each instance of the sample app. For example, for the sample config mentioned previously, the instance pcb1 has nginx port set to 8443, pcb2 set to 9443 & weld1 set to 10443.

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/anomaly/          # PCB Anomaly Detection
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/weld/             # Weld Porosity
   ```

### Start pipeline for a particular instance only

1. Fetch the list of pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_list.sh -i <INSTANCE_NAME>
   ```

   Example Output:

   ```text
   Instance name set to: pcb1
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Getting list of loaded pipelines...
   Loaded pipelines:
   [
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
           ...
   ]
   ```

2. Start the pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_start.sh -i <INSTANCE_NAME> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: pcb1
   Starting specified pipeline(s)...
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/payload.json
   Payload loaded successfully.
   Starting pipeline: pcb_anomaly_detection
   Launching pipeline: pcb_anomaly_detection
   Extracting payload for pipeline: pcb_anomaly_detection
   Found 1 payload(s) for pipeline: pcb_anomaly_detection
   Payload for pipeline 'pcb_anomaly_detection'. Response: "f4a2f7730b0011f1bd1a4b91749d35cf"
   ```

3. Access WebRTC stream:

   Open a browser and navigate to:

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/<peer-id of SAMPLE_APP>/
   ```

### Start pipeline for a particular instance from a custom payload.json

1. Fetch the list of pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_list.sh -i <INSTANCE_NAME>
   ```

   Example Output:

   ```text
   Instance name set to: pcb1
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Getting list of loaded pipelines...
   Loaded pipelines:
   [
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
           ...
   ]
   ```

2. Start the pipeline for <INSTANCE_NAME> where pipeline is loaded from <file>:

   ```bash
   ./sample_start.sh -i <INSTANCE_NAME> --payload <file> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: pcb2
   Custom payload file set to: custom_payload.json
   Starting specified pipeline(s)...
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb2
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from custom_payload.json
   Payload loaded successfully.
   Starting pipeline: pcb_anomaly_detection_gpu
   Launching pipeline: pcb_anomaly_detection_gpu
   Extracting payload for pipeline: pcb_anomaly_detection_gpu
   Found 1 payload(s) for pipeline: pcb_anomaly_detection_gpu
   Payload for pipeline 'pcb_anomaly_detection_gpu'. Response: "af5ddfba0b0111f183e2b18e98b8d602"
   ```

3. Access WebRTC stream:

   Open a browser and navigate to:

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/<peer-id of SAMPLE_APP>/
   ```

## Monitor Applications

### Check Pipeline Status

1. Check status of all instances:

   ```bash
   ./sample_status.sh
   ```

   Output:

   ```text
   No arguments provided. Fetching status for all pipeline instances.
   Config file found. Fetching status for all instances defined in /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/config.yml
   Processing instance: pcb1 from sample app: pcb-anomaly-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 29.38307701353888,
      "elapsed_time": 93.93162178993225,
      "id": "111c75f00b0011f1905b4b91749d35cf",
      "message": "",
      "start_time": 1771223034.2439265,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 29.382980506628957,
      "elapsed_time": 93.93193125724792,
      "id": "f4a2f7730b0011f1bd1a4b91749d35cf",
      "message": "",
      "start_time": 1771223415.8478491,
      "state": "COMPLETED"
   }
   ]
   Processing instance: pcb2 from sample app: pcb-anomaly-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 29.38333319994901,
      "elapsed_time": 93.93080592155457,
      "id": "1127a5530b0011f1bf5ab18e98b8d602",
      "message": "",
      "start_time": 1771223034.3642924,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 28.52731949007233,
      "elapsed_time": 38.76985263824463,
      "id": "af5ddfba0b0111f183e2b18e98b8d602",
      "message": "",
      "start_time": 1771223731.849365,
      "state": "RUNNING"
   }
   ]
   Processing instance: weld1 from sample app: weld-porosity
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.000609316876997,
      "elapsed_time": 22.466212511062622,
      "id": "1130ca860b0011f1aa88a902d69c78e2",
      "message": "",
      "start_time": 1771223034.8460093,
      "state": "COMPLETED"
   }
   ]
   ```

2. Check status of only a particular instance. You may refer to the config.yml for the instance names

   ```bash
   ./sample_status.sh -i <INSTANCE_NAME>
   ```

3. Check status of a particular instance_id of an instance

   ```bash
   ./sample_status.sh -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

### View Container Logs

View dlsps logs of an instance.

```bash
docker compose -p <INSTANCE_NAME> logs -f dlstreamer-pipeline-server
```

## Stop Applications

### Stop Pipeline Instances

1. Stop all pipelines:

   ```bash
   ./sample_stop.sh
   ```

   Output:

   ```text
   No pipelines specified. Stopping all pipeline instances

   -------------------------------------------
   Processing instance: pcb1 (SAMPLE_APP: pcb-anomaly-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 0a638eda0b0211f1a4734b91749d35cf
   Pipeline instance with ID '0a638eda0b0211f1a4734b91749d35cf' stopped successfully. Response: {
   "avg_fps": 10.03923888695388,
   "elapsed_time": 2.8886609077453613,
   "id": "0a638eda0b0211f1a4734b91749d35cf",
   "message": "",
   "start_time": 1771223881.8443167,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: pcb2 (SAMPLE_APP: pcb-anomaly-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 2 running pipeline instances.
   Stopping pipeline instance with ID: f1b692c60b0111f1b49db18e98b8d602
   Pipeline instance with ID 'f1b692c60b0111f1b49db18e98b8d602' stopped successfully. Response: {
   "avg_fps": 28.71575618334183,
   "elapsed_time": 44.4000039100647,
   "id": "f1b692c60b0111f1b49db18e98b8d602",
   "message": "",
   "start_time": 1771223840.4538686,
   "state": "RUNNING"
   }
   Stopping pipeline instance with ID: 0a7144ba0b0211f1bf96b18e98b8d602
   Pipeline instance with ID '0a7144ba0b0211f1bf96b18e98b8d602' stopped successfully. Response: {
   "avg_fps": 11.398401513154498,
   "elapsed_time": 3.0706019401550293,
   "id": "0a7144ba0b0211f1bf96b18e98b8d602",
   "message": "",
   "start_time": 1771223882.2535043,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: weld1 (SAMPLE_APP: weld-porosity)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 0a7cb5350b0211f18d33a902d69c78e2
   Pipeline instance with ID '0a7cb5350b0211f18d33a902d69c78e2' stopped successfully. Response: {
   "avg_fps": 30.26455178867368,
   "elapsed_time": 3.370274305343628,
   "id": "0a7cb5350b0211f18d33a902d69c78e2",
   "message": "",
   "start_time": 1771223882.0277128,
   "state": "RUNNING"
   }
   ```

2. Stop pipelines of given instance:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME>
   ```

   Output:

   ```text
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: aa41f9a50b0211f1b2064b91749d35cf
   Pipeline instance with ID 'aa41f9a50b0211f1b2064b91749d35cf' stopped successfully. Response: {
   "avg_fps": 23.18029767936354,
   "elapsed_time": 8.369171619415283,
   "id": "aa41f9a50b0211f1b2064b91749d35cf",
   "message": "",
   "start_time": 1771224150.084925,
   "state": "RUNNING"
   }
   ```

3. Stop pipelines of an instance with given instance_id:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

   Output:

   ```text
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb2
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Stopping pipeline instance with ID: aa55e26c0b0211f19dbfb18e98b8d602
   Pipeline instance with ID 'aa55e26c0b0211f19dbfb18e98b8d602' stopped successfully. Response: {
   "avg_fps": 28.77902768836767,
   "elapsed_time": 46.943902254104614,
   "id": "aa55e26c0b0211f19dbfb18e98b8d602",
   "message": "",
   "start_time": 1771224150.1473932,
   "state": "RUNNING"
   }
   ```

### Stop Docker Containers

1. Stop containers of all instances:

    ```bash
    ./run.sh down
    ```

1. Verify all containers are stopped:

    ```bash
    docker ps
    ```

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
   weld-porosity:
     weld1:
       NGINX_HTTP_PORT: 8080
       NGINX_HTTPS_PORT: 8443
       COTURN_UDP_PORT: 3478
       MINIO_SERVER_PORT: 8001
     weld2:
       NGINX_HTTP_PORT: 9080
       NGINX_HTTPS_PORT: 9443
       COTURN_UDP_PORT: 3479
       MINIO_SERVER_PORT: 9001

   pallet-defect-detection:
     pdd1:
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
   -------------------------------------------
   Status of: weld2 (SAMPLE_APP: weld-porosity)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld2/.env
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
   -------------------------------------------
   Status of: pdd1 (SAMPLE_APP: pallet-defect-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
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
         "detection-properties": {
            "element": {
               "format": "element-properties",
               "name": "detection"
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
   Payload for pipeline 'weld_porosity_classification'. Response: "07e3a89e0b0c11f197c97f94f81a2bf6"

   ------------------------------------------
   Processing instance: weld2 from SAMPLE_APP: weld-porosity
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld2/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld2/payload.json
   Payload loaded successfully.
   Starting first pipeline: weld_porosity_classification
   Launching pipeline: weld_porosity_classification
   Extracting payload for pipeline: weld_porosity_classification
   Found 1 payload(s) for pipeline: weld_porosity_classification
   Payload for pipeline 'weld_porosity_classification'. Response: "07efbfed0b0c11f1857c5f6284b18b7a"

   ------------------------------------------
   Processing instance: pdd1 from SAMPLE_APP: pallet-defect-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/payload.json
   Payload loaded successfully.
   Starting first pipeline: pallet_defect_detection
   Launching pipeline: pallet_defect_detection
   Extracting payload for pipeline: pallet_defect_detection
   Found 1 payload(s) for pipeline: pallet_defect_detection
   Payload for pipeline 'pallet_defect_detection'. Response: "07f972b50b0c11f1a09193badbd4eaa6"
   ```

3. Access WebRTC stream:

   The inference stream can be viewed on WebRTC, in a browser, at the following url depending on the SAMPLE_APP:

   > **Note:** The `NGINX_HTTPS_PORT` is different for each instance of the sample app. For example, for the sample config mentioned previously, the instance weld1 has nginx port set to 8443, weld2 set to 9443 & pdd1 set to 10443.

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/pdd/              # Pallet Defect Detection
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/weld/             # Weld Porosity
   ```

### Start pipeline for a particular instance only

1. Fetch the list of pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_list.sh -i <INSTANCE_NAME>
   ```

   Example Output:

   ```text
   Instance name set to: weld1
   Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
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

2. Start the pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_start.sh -i <INSTANCE_NAME> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: weld1
   Starting specified pipeline(s)...
   Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/payload.json
   Payload loaded successfully.
   Starting pipeline: weld_porosity_classification
   Launching pipeline: weld_porosity_classification
   Extracting payload for pipeline: weld_porosity_classification
   Found 1 payload(s) for pipeline: weld_porosity_classification
   Payload for pipeline 'weld_porosity_classification'. Response: "9d8ac23e0b0c11f19b287f94f81a2bf6"
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
   Instance name set to: weld1
   Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
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

2. Start the pipeline for <INSTANCE_NAME> where pipeline is loaded from <file>:

   ```bash
   ./sample_start.sh -i <INSTANCE_NAME> --payload <file> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: weld1
   Custom payload file set to: custom_payload.json
   Starting specified pipeline(s)...
   Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from custom_payload.json
   Payload loaded successfully.
   Starting pipeline: weld_porosity_classification_gpu
   Launching pipeline: weld_porosity_classification_gpu
   Extracting payload for pipeline: weld_porosity_classification_gpu
   Found 1 payload(s) for pipeline: weld_porosity_classification_gpu
   Payload for pipeline 'weld_porosity_classification_gpu'. Response: "260ded1e0b0d11f1be877f94f81a2bf6"
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
   Processing instance: weld1 from sample app: weld-porosity
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.001493154746807,
      "elapsed_time": 22.465550661087036,
      "id": "07e3a89e0b0c11f197c97f94f81a2bf6",
      "message": "",
      "start_time": 1771228172.7670474,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.190216602705384,
      "elapsed_time": 5.001618146896362,
      "id": "435274680b0d11f1858a7f94f81a2bf6",
      "message": "",
      "start_time": 1771228701.7791147,
      "state": "RUNNING"
   }
   ]
   Processing instance: weld2 from sample app: weld-porosity
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld2/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.00593828598509,
      "elapsed_time": 22.462225914001465,
      "id": "07efbfed0b0c11f1857c5f6284b18b7a",
      "message": "",
      "start_time": 1771228172.885318,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.138238041095267,
      "elapsed_time": 4.943884372711182,
      "id": "436199640b0d11f1813f5f6284b18b7a",
      "message": "",
      "start_time": 1771228701.876473,
      "state": "RUNNING"
   }
   ]
   Processing instance: pdd1 from sample app: pallet-defect-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.001843059404038,
      "elapsed_time": 97.19403505325317,
      "id": "07f972b50b0c11f1a09193badbd4eaa6",
      "message": "",
      "start_time": 1771228173.4003286,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.20333995270947,
      "elapsed_time": 4.701465606689453,
      "id": "436f327c0b0d11f1904493badbd4eaa6",
      "message": "",
      "start_time": 1771228702.1390438,
      "state": "RUNNING"
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

   ```test
   No pipelines specified. Stopping all pipeline instances

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
   Stopping pipeline instance with ID: 65793e840b0d11f1ac2b7f94f81a2bf6
   Pipeline instance with ID '65793e840b0d11f1ac2b7f94f81a2bf6' stopped successfully. Response: {
   "avg_fps": 30.06448918734938,
   "elapsed_time": 7.4506471157073975,
   "id": "65793e840b0d11f1ac2b7f94f81a2bf6",
   "message": "",
   "start_time": 1771228759.0638776,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: weld2 (SAMPLE_APP: weld-porosity)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld2/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 6583b55d0b0d11f1848d5f6284b18b7a
   Pipeline instance with ID '6583b55d0b0d11f1848d5f6284b18b7a' stopped successfully. Response: {
   "avg_fps": 30.01802976725066,
   "elapsed_time": 7.9618775844573975,
   "id": "6583b55d0b0d11f1848d5f6284b18b7a",
   "message": "",
   "start_time": 1771228759.1208313,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: pdd1 (SAMPLE_APP: pallet-defect-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 2 running pipeline instances.
   Stopping pipeline instance with ID: 436f327c0b0d11f1904493badbd4eaa6
   Pipeline instance with ID '436f327c0b0d11f1904493badbd4eaa6' stopped successfully. Response: {
   "avg_fps": 30.00611281530731,
   "elapsed_time": 65.2866837978363,
   "id": "436f327c0b0d11f1904493badbd4eaa6",
   "message": "",
   "start_time": 1771228702.1390438,
   "state": "RUNNING"
   }
   ```

2. Stop pipelines of given instance:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME>
   ```

   Output:

   ```text
   Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: ab32aa120b0d11f198697f94f81a2bf6
   Pipeline instance with ID 'ab32aa120b0d11f198697f94f81a2bf6' stopped successfully. Response: {
   "avg_fps": 30.03870516261253,
   "elapsed_time": 9.95381760597229,
   "id": "ab32aa120b0d11f198697f94f81a2bf6",
   "message": "",
   "start_time": 1771228876.0396237,
   "state": "RUNNING"
   }
   ```

3. Stop pipelines of an instance with given instance_id:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

   Output:

   ```text
   Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Stopping pipeline instance with ID: c2cd9ed10b0d11f1a4337f94f81a2bf6
   Pipeline instance with ID 'c2cd9ed10b0d11f1a4337f94f81a2bf6' stopped successfully. Response: {
   "avg_fps": 30.018450633462205,
   "elapsed_time": 12.325748205184937,
   "id": "c2cd9ed10b0d11f1a4337f94f81a2bf6",
   "message": "",
   "start_time": 1771228915.7712686,
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

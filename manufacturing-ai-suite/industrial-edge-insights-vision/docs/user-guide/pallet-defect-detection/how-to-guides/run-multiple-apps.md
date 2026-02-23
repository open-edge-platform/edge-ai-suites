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
   pallet-defect-detection:
     pdd1:
       NGINX_HTTP_PORT: 8080
       NGINX_HTTPS_PORT: 8443
       COTURN_UDP_PORT: 3478
       MINIO_SERVER_PORT: 8001
     pdd2:
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

3. Edit the environment variables below in `.env_<SAMPLE_APP>` files for all sample apps present in config.yml. 

   For the example above, modify the envs for pallet-defect-detection and weld-porosity i.e. env_pallet-defect-detection and .env_weld-porosity

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
   -------------------------------------------
   Status of: pdd2 (SAMPLE_APP: pallet-defect-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd2/.env
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
   Payload for pipeline 'pallet_defect_detection'. Response: "fd6e6f9f0b1811f191504920480d2bc6"

   ------------------------------------------
   Processing instance: pdd2 from SAMPLE_APP: pallet-defect-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd2/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd2/payload.json
   Payload loaded successfully.
   Starting first pipeline: pallet_defect_detection
   Launching pipeline: pallet_defect_detection
   Extracting payload for pipeline: pallet_defect_detection
   Found 1 payload(s) for pipeline: pallet_defect_detection
   Payload for pipeline 'pallet_defect_detection'. Response: "fd798f9f0b1811f1a42f1bffe3f91352"

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
   Payload for pipeline 'weld_porosity_classification'. Response: "fd84ad550b1811f1b60c936d4c42ec17"
   ```

3. Access WebRTC stream:

   The inference stream can be viewed on WebRTC, in a browser, at the following url depending on the SAMPLE_APP:

   > **Note:** The `NGINX_HTTPS_PORT` is different for each instance of the sample app. For example, for the sample config mentioned previously, the instance pdd1 has nginx port set to 8443, pdd2 set to 9443 & weld1 set to 10443.

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
   Instance name set to: pdd1
   Found SAMPLE_APP: pallet-defect-detection for INSTANCE_NAME: pdd1
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

2. Start the pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_start.sh -i <INSTANCE_NAME> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: pdd1
   Starting specified pipeline(s)...
   Found SAMPLE_APP: pallet-defect-detection for INSTANCE_NAME: pdd1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/payload.json
   Payload loaded successfully.
   Starting pipeline: pallet_defect_detection
   Launching pipeline: pallet_defect_detection
   Extracting payload for pipeline: pallet_defect_detection
   Found 1 payload(s) for pipeline: pallet_defect_detection
   Payload for pipeline 'pallet_defect_detection'. Response: "44e46ef30b1911f1a2e34920480d2bc6"
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
   Instance name set to: pdd1
   Found SAMPLE_APP: pallet-defect-detection for INSTANCE_NAME: pdd1
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

2. Start the pipeline for <INSTANCE_NAME> where pipeline is loaded from <file>:

   ```bash
   ./sample_start.sh -i <INSTANCE_NAME> --payload <file> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: pdd1
   Custom payload file set to: custom_payload.json
   Starting specified pipeline(s)...
   Found SAMPLE_APP: pallet-defect-detection for INSTANCE_NAME: pdd1
   Environment variables loaded from /home/intel/ird_instance/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from payload.json
   Payload loaded successfully.
   Starting pipeline: pallet_defect_detection_gpu
   Launching pipeline: pallet_defect_detection_gpu
   Extracting payload for pipeline: pallet_defect_detection_gpu
   Found 1 payload(s) for pipeline: pallet_defect_detection_gpu
   Payload for pipeline 'pallet_defect_detection_gpu' posted successfully. Response: "4f57b996ff5311f0aa82fa869454672b"
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
   Processing instance: pdd1 from sample app: pallet-defect-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.000878701220802,
      "elapsed_time": 97.19715881347656,
      "id": "fd6e6f9f0b1811f191504920480d2bc6",
      "message": "",
      "start_time": 1771233739.0876606,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 25.66489579665379,
      "elapsed_time": 5.9224841594696045,
      "id": "772ac89c0b1911f1ad464920480d2bc6",
      "message": "",
      "start_time": 1771233942.9697065,
      "state": "RUNNING"
   }
   ]
   Processing instance: pdd2 from sample app: pallet-defect-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd2/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.000722249076027,
      "elapsed_time": 97.19766521453857,
      "id": "fd798f9f0b1811f1a42f1bffe3f91352",
      "message": "",
      "start_time": 1771233739.292792,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.15376702990521,
      "elapsed_time": 6.035728454589844,
      "id": "7737e4570b1911f1baee1bffe3f91352",
      "message": "",
      "start_time": 1771233942.8786583,
      "state": "RUNNING"
   }
   ]
   Processing instance: weld1 from sample app: weld-porosity
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.001865362861874,
      "elapsed_time": 22.465271472930908,
      "id": "fd84ad550b1811f1b60c936d4c42ec17",
      "message": "",
      "start_time": 1771233738.8075953,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.126401681877375,
      "elapsed_time": 6.008018255233765,
      "id": "7749719d0b1911f1bef0936d4c42ec17",
      "message": "",
      "start_time": 1771233942.9226382,
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

   ```text
   No pipelines specified. Stopping all pipeline instances

   -------------------------------------------
   Processing instance: pdd1 (SAMPLE_APP: pallet-defect-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/ird_instance/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 5401c83aff5611f0aa82fa869454672b
   Pipeline instance with ID '5401c83aff5611f0aa82fa869454672b' stopped successfully. Response: {
   "avg_fps": 30.016161405973335,
   "elapsed_time": 16.457796335220337,
   "id": "5401c83aff5611f0aa82fa869454672b",
   "message": "",
   "start_time": 1769940669.0616643,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: pdd2 (SAMPLE_APP: pallet-defect-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/ird_instance/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd2/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 541d02bcff5611f0aafbda07c19c7336
   Pipeline instance with ID '541d02bcff5611f0aafbda07c19c7336' stopped successfully. Response: {
   "avg_fps": 30.02096208342521,
   "elapsed_time": 16.42185068130493,
   "id": "541d02bcff5611f0aafbda07c19c7336",
   "message": "",
   "start_time": 1769940669.2755027,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: weld1 (SAMPLE_APP: weld-porosity)
   -------------------------------------------
   Environment variables loaded from /home/intel/ird_instance/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 543ae1c4ff5611f0ad167a01fcf9b4b5
   Pipeline instance with ID '543ae1c4ff5611f0ad167a01fcf9b4b5' stopped successfully. Response: {
   "avg_fps": 30.030312784843783,
   "elapsed_time": 16.416736602783203,
   "id": "543ae1c4ff5611f0ad167a01fcf9b4b5",
   "message": "",
   "start_time": 1769940669.4774928,
   "state": "RUNNING"
   }
   ```

2. Stop pipelines of given instance:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME>
   ```

   Output:

   ```text
   Found SAMPLE_APP: pallet-defect-detection for INSTANCE_NAME: pdd2
   Environment variables loaded from /home/intel/ird_instance/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd2/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: af709322ff5611f0aafbda07c19c7336
   Pipeline instance with ID 'af709322ff5611f0aafbda07c19c7336' stopped successfully. Response: {
   "avg_fps": 30.10730708662458,
   "elapsed_time": 7.938256025314331,
   "id": "af709322ff5611f0aafbda07c19c7336",
   "message": "",
   "start_time": 1769940822.4814367,
   "state": "RUNNING"
   }
   ```

3. Stop pipelines of an instance with given instance_id:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

   Output:

   ```text
   Found SAMPLE_APP: pallet-defect-detection for INSTANCE_NAME: pdd1
   Environment variables loaded from /home/intel/ird_instance/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Stopping pipeline instance with ID: af5741baff5611f0aa82fa869454672b
   Pipeline instance with ID 'af5741baff5611f0aa82fa869454672b' stopped successfully. Response: {
   "avg_fps": 30.00011463267954,
   "elapsed_time": 97.19963002204895,
   "id": "af5741baff5611f0aa82fa869454672b",
   "message": "",
   "start_time": 1769940822.2892969,
   "state": "COMPLETED"
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

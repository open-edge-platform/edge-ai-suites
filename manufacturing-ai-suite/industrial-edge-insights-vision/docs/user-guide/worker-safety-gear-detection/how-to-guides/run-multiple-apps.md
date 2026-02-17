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
   worker-safety-gear-detection:
     wsg1:
       NGINX_HTTP_PORT: 8080
       NGINX_HTTPS_PORT: 8443
       COTURN_UDP_PORT: 3478
       MINIO_SERVER_PORT: 8001
     wsg2:
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
   Status of: wsg1 (SAMPLE_APP: worker-safety-gear-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
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
   Status of: wsg2 (SAMPLE_APP: worker-safety-gear-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg2/.env
   Running sample app: worker-safety-gear-detection
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
   Processing instance: wsg1 from SAMPLE_APP: worker-safety-gear-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/payload.json
   Payload loaded successfully.
   Starting first pipeline: worker_safety_gear_detection
   Launching pipeline: worker_safety_gear_detection
   Extracting payload for pipeline: worker_safety_gear_detection
   Found 1 payload(s) for pipeline: worker_safety_gear_detection
   Payload for pipeline 'worker_safety_gear_detection'. Response: "c940e6d60b1111f1926d4d2df68af72d"

   ------------------------------------------
   Processing instance: wsg2 from SAMPLE_APP: worker-safety-gear-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg2/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg2/payload.json
   Payload loaded successfully.
   Starting first pipeline: worker_safety_gear_detection
   Launching pipeline: worker_safety_gear_detection
   Extracting payload for pipeline: worker_safety_gear_detection
   Found 1 payload(s) for pipeline: worker_safety_gear_detection
   Payload for pipeline 'worker_safety_gear_detection'. Response: "c94c317b0b1111f188c40f57f8f9c534"

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
   Payload for pipeline 'pallet_defect_detection'. Response: "c956aac70b1111f1ae18b9075240129b"
   ```

3. Access WebRTC stream:

   The inference stream can be viewed on WebRTC, in a browser, at the following url depending on the SAMPLE_APP:

   > **Note:** The `NGINX_HTTPS_PORT` is different for each instance of the sample app. For example, for the sample config mentioned previously, the instance wsg1 has nginx port set to 8443, wsg2 set to 9443 & pdd1 set to 10443.

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/pdd/              # Pallet Defect Detection
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/worker_safety/    # Worker Safety Gear detection
   ```

### Start pipeline for a particular instance only

1. Fetch the list of pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_list.sh -i <INSTANCE_NAME>
   ```

   Example Output:

   ```text
   Instance name set to: wsg1
   Found SAMPLE_APP: worker-safety-gear-detection for INSTANCE_NAME: wsg1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
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
   Instance name set to: wsg1
   Starting specified pipeline(s)...
   Found SAMPLE_APP: worker-safety-gear-detection for INSTANCE_NAME: wsg1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/payload.json
   Payload loaded successfully.
   Starting pipeline: worker_safety_gear_detection
   Launching pipeline: worker_safety_gear_detection
   Extracting payload for pipeline: worker_safety_gear_detection
   Found 1 payload(s) for pipeline: worker_safety_gear_detection
   Payload for pipeline 'worker_safety_gear_detection'. Response: "274ef3ff0b1211f18c184d2df68af72d"
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
   Instance name set to: wsg1
   Found SAMPLE_APP: worker-safety-gear-detection for INSTANCE_NAME: wsg1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
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
   Instance name set to: wsg1
   Custom payload file set to: custom_payload.json
   Starting specified pipeline(s)...
   Found SAMPLE_APP: worker-safety-gear-detection for INSTANCE_NAME: wsg1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from custom_payload.json
   Payload loaded successfully.
   Starting pipeline: worker_safety_gear_detection_gpu
   Launching pipeline: worker_safety_gear_detection_gpu
   Extracting payload for pipeline: worker_safety_gear_detection_gpu
   Found 1 payload(s) for pipeline: worker_safety_gear_detection_gpu
   Payload for pipeline 'worker_safety_gear_detection_gpu'. Response: "6b447d8f0b1211f18e6e4d2df68af72d"
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
   Processing instance: wsg1 from sample app: worker-safety-gear-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.001040850463887,
      "elapsed_time": 65.0644142627716,
      "id": "c940e6d60b1111f1926d4d2df68af72d",
      "message": "",
      "start_time": 1771230644.9230769,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.046657837606574,
      "elapsed_time": 6.722876071929932,
      "id": "9dd771a50b1211f193454d2df68af72d",
      "message": "",
      "start_time": 1771231001.1606326,
      "state": "RUNNING"
   }
   ]
   Processing instance: wsg2 from sample app: worker-safety-gear-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg2/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.001943547561382,
      "elapsed_time": 65.06245851516724,
      "id": "c94c317b0b1111f188c40f57f8f9c534",
      "message": "",
      "start_time": 1771230645.3392272,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.135082993671546,
      "elapsed_time": 6.669965028762817,
      "id": "9de81f3b0b1211f182be0f57f8f9c534",
      "message": "",
      "start_time": 1771231001.2393894,
      "state": "RUNNING"
   }
   ]
   Processing instance: pdd1 from sample app: pallet-defect-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/pallet-defect-detection/pdd1/.env
   Running sample app: pallet-defect-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.00057875018982,
      "elapsed_time": 97.19813084602356,
      "id": "c956aac70b1111f1ae18b9075240129b",
      "message": "",
      "start_time": 1771230645.5429828,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.11388737798281,
      "elapsed_time": 6.608245134353638,
      "id": "9df363430b1211f1b572b9075240129b",
      "message": "",
      "start_time": 1771231001.327198,
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
   Processing instance: wsg1 (SAMPLE_APP: worker-safety-gear-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 9dd771a50b1211f193454d2df68af72d
   Pipeline instance with ID '9dd771a50b1211f193454d2df68af72d' stopped successfully. Response: {
   "avg_fps": 30.014294080812306,
   "elapsed_time": 62.53686475753784,
   "id": "9dd771a50b1211f193454d2df68af72d",
   "message": "",
   "start_time": 1771231001.1606326,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: wsg2 (SAMPLE_APP: worker-safety-gear-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg2/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 9de81f3b0b1211f182be0f57f8f9c534
   Pipeline instance with ID '9de81f3b0b1211f182be0f57f8f9c534' stopped successfully. Response: {
   "avg_fps": 30.007063280321198,
   "elapsed_time": 62.9851655960083,
   "id": "9de81f3b0b1211f182be0f57f8f9c534",
   "message": "",
   "start_time": 1771231001.2393894,
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
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 9df363430b1211f1b572b9075240129b
   Pipeline instance with ID '9df363430b1211f1b572b9075240129b' stopped successfully. Response: {
   "avg_fps": 30.01574070196512,
   "elapsed_time": 62.96695828437805,
   "id": "9df363430b1211f1b572b9075240129b",
   "message": "",
   "start_time": 1771231001.327198,
   "state": "RUNNING"
   }
   ```

2. Stop pipelines of given instance:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME>
   ```

   Output:

   ```text
   Found SAMPLE_APP: worker-safety-gear-detection for INSTANCE_NAME: wsg1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg1/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: de8e0ac10b1211f1ae604d2df68af72d
   Pipeline instance with ID 'de8e0ac10b1211f1ae604d2df68af72d' stopped successfully. Response: {
   "avg_fps": 30.009450510672455,
   "elapsed_time": 19.42720890045166,
   "id": "de8e0ac10b1211f1ae604d2df68af72d",
   "message": "",
   "start_time": 1771231109.7255032,
   "state": "RUNNING"
   }
   ```

3. Stop pipelines of an instance with given instance_id:

   ```bash
   ./sample_stop.sh -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

   Output:

   ```text
   Found SAMPLE_APP: worker-safety-gear-detection for INSTANCE_NAME: wsg2
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/temp_apps/worker-safety-gear-detection/wsg2/.env
   Running sample app: worker-safety-gear-detection
   Using default deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Stopping pipeline instance with ID: de9dce1e0b1211f1bd930f57f8f9c534
   Pipeline instance with ID 'de9dce1e0b1211f1bd930f57f8f9c534' stopped successfully. Response: {
   "avg_fps": 30.014757930584633,
   "elapsed_time": 46.27723026275635,
   "id": "de9dce1e0b1211f1bd930f57f8f9c534",
   "message": "",
   "start_time": 1771231109.9834328,
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

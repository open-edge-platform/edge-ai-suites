# Deploy Multiple Instances with Helm

## Prerequisites

- Ensure you have the **minimum system requirements** for this application.
- K8s installation on single or multi node must be done as pre-requisite to continue the following deployment. Note: The kubernetes cluster is set up with `kubeadm`, `kubectl` and `kubelet` packages on single and multi nodes with `v1.30.2`.
  Refer to tutorials online to setup kubernetes cluster on the web with host OS as ubuntu 22.04 and/or ubuntu 24.04.
- For helm installation, refer to [helm website](https://helm.sh/docs/intro/install/)

## Setup the application

> **Note**: The following instructions assume Kubernetes is already running in the host system with helm package manager installed.

1. Clone the **edge-ai-suites** repository and change into industrial-edge-insights-vision directory. The directory contains the utility scripts required in the instructions that follows.

   ```sh
   git clone https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/
   ```

   > **Note**: These steps demonstrate launching two pcb-anomaly-detection instances and one weld-porosity instance. Modify the sample apps and instances as needed for your use case.

2. Create a `config.yml` file to define your application instances and their unique port configurations. Add the following sample contents and save.

   Example:

   ```text
   pcb-anomaly-detection:
     pcb1:
       NGINX_HTTP_PORT: 30080
       NGINX_HTTPS_PORT: 30443
       COTURN_PORT: 30478
       S3_STORAGE_PORT: 30800
     pcb2:
       NGINX_HTTP_PORT: 30081
       NGINX_HTTPS_PORT: 30444
       COTURN_PORT: 30479
       S3_STORAGE_PORT: 30801

   weld-porosity:
     weld1:
       NGINX_HTTP_PORT: 30082
       NGINX_HTTPS_PORT: 30445
       COTURN_PORT: 30480
       S3_STORAGE_PORT: 30802
   ```

   > **Note:** A sample configuration file `sample_config.yml` is provided to help users understand the multi-instance setup and get started. This configuration defines three example instances with identifiers: pdd1, pdd2, and weld1. The accompanying sample scripts utilize these identifiers to perform operations on individual application instances.

3. Edit the below mentioned environment variables in all the `helm/values_<SAMPLE_APP>.yaml` files:

   ```yaml
   HOST_IP=<HOST_IP>   # IP address of server where DL Streamer Pipeline Server is running.

   MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
   MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

   MTX_WEBRTCICESERVERS2_0_USERNAME=<username>  # WebRTC credentials e.g. intel1234
   MTX_WEBRTCICESERVERS2_0_PASSWORD=<password>
   ```

4. Install pre-requisites for all instances

   ```sh
   ./setup.sh helm
   ```

   This does the following:
   - Parses through the config.yml
   - Downloads resources for each instance
   - Creates a folder helm/temp_apps/<SAMPLE_APP>/<INSTANCE_NAME> that contains configs folder, .env file, payload.json, Chart.yaml, pipeline-server-config.json and values.yaml.
   - Updates and adds the ports mentioned in config.yml to the respective values.yaml file
   - Sets executable permissions for scripts

## Deploy the application

### Install helm charts

1. Install the helm chart for all instances.

   ```sh
   ./run.sh helm_install
   ```

   After installation, check the status of the running pods for each instance:

   ```sh
   kubectl get pods -n <INSTANCE_NAME>
   ```

   To view logs of a specific pod, replace `<pod_name>` with the actual pod name from the output above:

   ```sh
   kubectl logs -n <INSTANCE_NAME> -f <pod_name>
   ```

2. Copy the resources such as video and model from local directory to the to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.

   ```sh
   # Below is an example for PCB Anomaly Detection. Please adjust the source path of models and videos appropriately for other sample applications.

   POD_NAME=$(kubectl get pods -n <INSTANCE_NAME> -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

   kubectl cp resources/pcb-anomaly-detection/videos/anomalib_pcb_test.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>

   kubectl cp  resources/pcb-anomaly-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>
   ```

### Start AI pipelines

#### Start pipeline for all instances

1. Fetch the list of pipeline loaded available to launch for all instances.

   ```sh
   ./sample_list.sh helm
   ```

   This lists the pipeline loaded in DLStreamer Pipeline Server.

   Output:

   ```text
   -------------------------------------------
   Status of: pcb1 (SAMPLE_APP: pcb-anomaly-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
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
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
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
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
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

2. Start the pipeline for all instances in the config.yml file

   ```sh
   ./sample_start.sh helm
   ```

   Example Output:

   ```text
   No pipeline specified. Starting the first pipeline.

   ------------------------------------------
   Processing instance: pcb1 from SAMPLE_APP: pcb-anomaly-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/payload.json
   Payload loaded successfully.
   Starting first pipeline: pcb_anomaly_detection
   Launching pipeline: pcb_anomaly_detection
   Extracting payload for pipeline: pcb_anomaly_detection
   Found 1 payload(s) for pipeline: pcb_anomaly_detection
   Payload for pipeline 'pcb_anomaly_detection'. Response: "41845fd208b811f19059d9c7fed5fa4f"

   ------------------------------------------
   Processing instance: pcb2 from SAMPLE_APP: pcb-anomaly-detection
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/payload.json
   Payload loaded successfully.
   Starting first pipeline: pcb_anomaly_detection
   Launching pipeline: pcb_anomaly_detection
   Extracting payload for pipeline: pcb_anomaly_detection
   Found 1 payload(s) for pipeline: pcb_anomaly_detection
   Payload for pipeline 'pcb_anomaly_detection'. Response: "41906efa08b811f1afb3199e28d0e6d7"

   ------------------------------------------
   Processing instance: weld1 from SAMPLE_APP: weld-porosity
   ------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/payload.json
   Payload loaded successfully.
   Starting first pipeline: weld_porosity_classification
   Launching pipeline: weld_porosity_classification
   Extracting payload for pipeline: weld_porosity_classification
   Found 1 payload(s) for pipeline: weld_porosity_classification
   Payload for pipeline 'weld_porosity_classification'. Response: "419b34f308b811f1a9cbb162d1d1cb15"
   ```

3. Access the WebRTC stream

   The inference stream can be viewed on WebRTC, in a browser, at the following url depending on the SAMPLE_APP:

   > **Note:** The `NGINX_HTTPS_PORT` is different for each instance of the sample app. For example, for the sample config mentioned previously, the instance pcb1 has nginx port set to 30443, pcb2 set to 30444 & weld1 set to 30445.

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/anomaly/          # PCB Anomaly Detection
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/weld/             # Weld Porosity
   ```

#### Start pipeline for a particular instance only

1. Fetch the list of pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_list.sh helm -i <INSTANCE_NAME>
   ```

    Example Output:

   ```text
   Instance name set to: pcb1
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
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
   ./sample_start.sh helm -i <INSTANCE_NAME> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: pcb1
   Starting specified pipeline(s)...
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/payload.json
   Payload loaded successfully.
   Starting pipeline: pcb_anomaly_detection
   Launching pipeline: pcb_anomaly_detection
   Extracting payload for pipeline: pcb_anomaly_detection
   Found 1 payload(s) for pipeline: pcb_anomaly_detection
   Payload for pipeline 'pcb_anomaly_detection'. Response: "f5d6f4a308b811f183a7d9c7fed5fa4f"
   ```

3. Access WebRTC stream:

   Open a browser and navigate to

   ```bash
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/<peer-id of SAMPLE_APP>/
   ```

### Start pipeline for a particular instance from a custom payload.json

1. Fetch the list of pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_list.sh helm -i <INSTANCE_NAME>
   ```

    Example Output:

   ```text
   Instance name set to: pcb2
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb2
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
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
       ...
   ]
   ```

2. Start the pipeline for <INSTANCE_NAME> where pipeline is loaded from <file>:

   ```bash
   ./sample_start.sh helm -i <INSTANCE_NAME> --payload <file> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: pcb1
   Custom payload file set to: custom_payload.json
   Starting specified pipeline(s)...
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb1
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Loading payload from custom_payload.json
   Payload loaded successfully.
   Starting pipeline: pcb_anomaly_detection_gpu
   Launching pipeline: pcb_anomaly_detection_gpu
   Extracting payload for pipeline: pcb_anomaly_detection_gpu
   Found 1 payload(s) for pipeline: pcb_anomaly_detection_gpu
   Payload for pipeline 'pcb_anomaly_detection_gpu'. Response: "c0afa09d08b911f19167d9c7fed5fa4f"
   ```

3. Access WebRTC stream:

   Open a browser and navigate to:

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/<peer-id of SAMPLE_APP>/
   ```

## Monitor Applications

### Check Pipeline Status

1. Get status of pipeline instance(s) of all instances.

   ```bash
   ./sample_status.sh helm
   ```

   This command lists status of pipeline instances launched during the lifetime of sample application of all instances in the config file

   Output:

   ```text
   No arguments provided. Fetching status for all pipeline instances.
   Config file found. Fetching status for all instances defined in /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/config.yml
   Processing instance: pcb1 from sample app: pcb-anomaly-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 26.471909092423328,
      "elapsed_time": 104.26146626472473,
      "id": "6d3285c708bb11f1a7041b0626dce0fd",
      "message": "",
      "start_time": 1770973651.1545439,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 24.73910453736799,
      "elapsed_time": 42.604612827301025,
      "id": "a06b0f0408bb11f1b34a1b0626dce0fd",
      "message": "",
      "start_time": 1770973737.2003956,
      "state": "RUNNING"
   }
   ]
   Processing instance: pcb2 from sample app: pcb-anomaly-detection
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 27.271058988731575,
      "elapsed_time": 101.20619368553162,
      "id": "6d3ffca108bb11f18ed0358a457b6922",
      "message": "",
      "start_time": 1770973651.33268,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 26.302732903939624,
      "elapsed_time": 42.54310607910156,
      "id": "a07dee8e08bb11f1b22c358a457b6922",
      "message": "",
      "start_time": 1770973737.297148,
      "state": "RUNNING"
   }
   ]
   Processing instance: weld1 from sample app: weld-porosity
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   [
   {
      "avg_fps": 30.007090623930345,
      "elapsed_time": 22.461360216140747,
      "id": "9651bc0708bb11f1ab65fd970995bf83",
      "message": "",
      "start_time": 1770973720.580919,
      "state": "COMPLETED"
   },
   {
      "avg_fps": 30.044665525605428,
      "elapsed_time": 22.433268785476685,
      "id": "a0909c7308bb11f1a663fd970995bf83",
      "message": "",
      "start_time": 1770973737.3773737,
      "state": "COMPLETED"
   }
   ]
   ```

2. Check status of only a particular instance:

   ```bash
   ./sample_status.sh helm -i <INSTANCE_NAME>
   ```

3. Check status of a particular instance_id of an instance

   ```bash
   ./sample_status.sh helm -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

## Stop Applications

### Stop Pipeline Instances

1. Stop all pipelines of all instances:

   ```bash
   ./sample_stop.sh helm
   ```

   Output

   ```text
   No pipelines specified. Stopping all pipeline instances

   -------------------------------------------
   Processing instance: pcb1 (SAMPLE_APP: pcb-anomaly-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb1/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 4ad8cb0608bc11f1837a1b0626dce0fd
   Pipeline instance with ID '4ad8cb0608bc11f1837a1b0626dce0fd' stopped successfully. Response: {
   "avg_fps": 24.92580082541783,
   "elapsed_time": 11.393810749053955,
   "id": "4ad8cb0608bc11f1837a1b0626dce0fd",
   "message": "",
   "start_time": 1770974022.8910992,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: pcb2 (SAMPLE_APP: pcb-anomaly-detection)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 4ae9e06808bc11f18ee0358a457b6922
   Pipeline instance with ID '4ae9e06808bc11f18ee0358a457b6922' stopped successfully. Response: {
   "avg_fps": 24.99570324372322,
   "elapsed_time": 11.361947774887085,
   "id": "4ae9e06808bc11f18ee0358a457b6922",
   "message": "",
   "start_time": 1770974023.0342877,
   "state": "RUNNING"
   }

   -------------------------------------------
   Processing instance: weld1 (SAMPLE_APP: weld-porosity)
   -------------------------------------------
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/.env
   Running sample app: weld-porosity
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 4af687de08bc11f1a1a0fd970995bf83
   Pipeline instance with ID '4af687de08bc11f1a1a0fd970995bf83' stopped successfully. Response: {
   "avg_fps": 30.011190146566342,
   "elapsed_time": 11.429064750671387,
   "id": "4af687de08bc11f1a1a0fd970995bf83",
   "message": "",
   "start_time": 1770974023.0493774,
   "state": "RUNNING"
   }
   ```

2. Stop pipelines of given instance:

   ```bash
   ./sample_stop.sh helm -i <INSTANCE_NAME>
   ```

   Output:

   ```text
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb2
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Instance list fetched successfully. HTTP Status Code: 200
   Found 1 running pipeline instances.
   Stopping pipeline instance with ID: 7e9e81f608bc11f18cec358a457b6922
   Pipeline instance with ID '7e9e81f608bc11f18cec358a457b6922' stopped successfully. Response: {
   "avg_fps": 27.322731725040388,
   "elapsed_time": 21.41073751449585,
   "id": "7e9e81f608bc11f18cec358a457b6922",
   "message": "",
   "start_time": 1770974109.734703,
   "state": "RUNNING"
   }
   ```

3. Stop pipelines of an instance with a given instance_id:

   ```sh
   ./sample_stop.sh helm -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

   Output:

   ```text
   Found SAMPLE_APP: pcb-anomaly-detection for INSTANCE_NAME: pcb2
   Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pcb-anomaly-detection/pcb2/.env
   Running sample app: pcb-anomaly-detection
   Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
   Checking status of dlstreamer-pipeline-server...
   Server reachable. HTTP Status Code: 200
   Stopping pipeline instance with ID: 9ba7321408bc11f180fe1b0626dce0fd
   ERROR: Failed to stop pipeline instance with ID '9ba7321408bc11f180fe1b0626dce0fd'. HTTP Status Code: 400
   Response body: "Invalid pipeline, version or instance"
   ```

## Uninstall Helm Charts

```sh
./run.sh helm_uninstall
```

## Storing frames to S3 storage

Applications can take advantage of S3 publish feature from DL Streamer Pipeline Server and use it to save frames to an S3 compatible storage.

1. Run all the steps mentioned in above [section](#setup-the-application) to setup the application.

2. Install the helm chart.

   ```sh
   ./run.sh helm_install
   ```

3. Copy the resources such as video and model from local directory to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.

   ```sh
   # Below is an example for PCB Anomaly Detection. Please adjust the source path of models and videos appropriately for other sample applications.

   POD_NAME=$(kubectl get pods -n <INSTANCE_NAME> -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

   kubectl cp resources/pcb-anomaly-detection/videos/anomalib_pcb_test.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>

   kubectl cp  resources/pcb-anomaly-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>
   ```

4. Install the package `boto3` in your python environment if not installed.

   It is recommended to create a virtual environment and install it there. You can run the following commands to add the necessary dependencies as well as create and activate the environment.

   ```sh
   sudo apt update && \
   sudo apt install -y python3 python3-pip python3-venv
   ```

   ```sh
   python3 -m venv venv && \
   source venv/bin/activate
   ```

   Once the environment is ready, install `boto3` with the following command

   ```sh
   pip3 install --upgrade pip && \
   pip3 install boto3==1.36.17
   ```

   > **Note:** DL Streamer Pipeline Server expects the bucket to be already present in the database. The next step will help you create one.

5. Create a S3 bucket using the following script.

   Update the `HOST_IP` and `S3_STORAGE_PORT` mentioned in config.yml for each instance and credentials with that of the running MinIO server. Name the file as `create_bucket_<INSTANCE_NAME>.py`.

   ```python
   import boto3
   url = "http://<HOST_IP>:<S3_STORAGE_PORT>"
   user = "<value of MINIO_ACCESS_KEY used in helm/temp_apps/SAMPLE_APP/INSTANCE_NAME/values.yaml>"
   password = "<value of MINIO_SECRET_KEY used in helm/temp_apps/SAMPLE_APP/INSTANCE_NAME/values.yaml>"
   bucket_name = "ecgdemo"

   client= boto3.client(
               "s3",
               endpoint_url=url,
               aws_access_key_id=user,
               aws_secret_access_key=password
   )
   client.create_bucket(Bucket=bucket_name)
   buckets = client.list_buckets()
   print("Buckets:", [b["Name"] for b in buckets.get("Buckets", [])])
   ```

   Run the above script to create the bucket.

   ```sh
   python3 create_bucket_<INSTANCE_NAME>.py
   ```

6. Start the pipeline with the following cURL command  with `<HOST_IP>` set to system IP and the `<NGINX_HTTPS_PORT>` mentioned in the config.yml for each instance. Ensure to give the correct path to the model as seen below. This example starts an AI pipeline for pcb-anomaly-detection.  Please adjust the source path of models and videos appropriately for other sample applications.

   ```sh
   curl -k https://<HOST_IP>:<NGINX_HTTPS_PORT>/api/pipelines/user_defined_pipelines/pcb_anomaly_detection_s3write -X POST -H 'Content-Type: application/json' -d '{
      "source": {
         "uri": "file:///home/pipeline-server/resources/videos/anomalib_pcb_test.avi",
         "type": "uri"
      },
      "destination": {
         "frame": {
               "type": "webrtc",
               "peer-id": "anomaly_s3"
         }
      },
      "parameters": {
         "classification-properties": {
               "model": "/home/pipeline-server/resources/models/pcb-anomaly-detection/deployment/Anomaly classification/model/model.xml",
               "device": "CPU"
         }
      }
   }'
   ```

7. Go to MinIO console on `https://<HOST_IP>:<NGINX_HTTPS_PORT>/minio/` and login with `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` provided in `helm/temp_apps/SAMPLE_APP/INSTANCE_NAME/values.yaml` file. After logging into console, you can go to `ecgdemo` bucket and check the frames stored.

   ![S3 minio image storage](../_assets/s3-minio-storage.png)

8. Uninstall the helm chart.

   ```sh
   ./run.sh helm_uninstall
   ```


## MLOps using Model Download

1. Run all the steps mentioned in above [section](#setup-the-application) to setup the application.

2. Install the helm chart

   ```sh
   ./run.sh helm_install
   ```

3. Copy the resources such as video and model from local directory to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.

   ```sh
   # Below is an example for PCB Anomaly Detection. Please adjust the source path of models and videos appropriately for other sample applications.

   POD_NAME=$(kubectl get pods -n <INSTANCE_NAME> -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

   kubectl cp resources/pcb-anomaly-detection/videos/anomalib_pcb_test.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>

   kubectl cp  resources/pcb-anomaly-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>
   ```

4. Modify the payload in `helm/temp_apps/<SAMPLE_APP>/<INSTANCE_NAME>/payload.json` to launch an instance for the mlops pipeline. 
   
   Below is an example for pcb-anomaly-detection. Please modify the payload for other sample applications.

   ```json
   [
      {
         "pipeline": "pcb_anomaly_detection_mlops",
         "payload":{
               "source": {
                  "uri": "file:///home/pipeline-server/resources/videos/anomalib_pcb_test.avi",
                  "type": "uri"
               },
               "destination": {
               "frame": {
                  "type": "webrtc",
                  "peer-id": "anomaly"
               }
               },
               "parameters": {
                  "classification-properties": {
                     "model": "/home/pipeline-server/resources/models/pcb-anomaly-detection/deployment/Anomaly classification/model/model.xml",
                     "device": "CPU"
                  }
               }
         }
      }
   ]
   ```

5. Start the pipeline with the above payload. 

   Below is an example for starting an instance for pcb-anomaly-detection:

   ```sh
   ./sample_start.sh helm -i <INSTANCE_NAME> -p pcb_anomaly_detection_mlops
   ```
   Note the instance-id.

6. Download and prepare the model. Below is an example for downloading and preparing model for pcb-anomaly-detection. Please modify MODEL_URL for the other sample applications.
   >NOTE- For sake of simplicity, we assume that the new model has already been downloaded by Model Download microservice. The following curl command is only a simulation that just downloads the model. In production, however, they will be downloaded by the Model Download service.

   ```sh
   export MODEL_URL='https://github.com/open-edge-platform/edge-ai-resources/raw/a7c9522f5f936c47de8922046db7d7add13f93a0/models/FP16/pcb-anomaly-detection.zip'

   curl -L "$MODEL_URL" -o "$(basename $MODEL_URL)"

   unzip "$(basename $MODEL_URL)" -d new-model # downloaded model is now extracted to `new-model` directory.
   ```

7. Copy the new model to the `dlstreamer-pipeline-server` pod to make it available for application while launching pipeline.

   ```sh
   
   POD_NAME=$(kubectl get pods -n <INSTANCE_NAME> -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

   kubectl cp new-model $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>
   ```
   >NOTE- If there are multiple sample_apps in config.yml, repeat steps 6 and 7 for each sample app and instance.


8. Stop the existing pipeline before restarting it with a new model. Use the instance-id generated from step 5.
   ```sh
   curl -k --location -X DELETE https://<HOST_IP>:<NGINX_HTTPS_PORT>/api/pipelines/{instance_id}
   ```

9. Modify the payload in `helm/temp_apps/<SAMPLE_APP>/<INSTANCE_NAME>/payload.json` to launch an instance for the mlops pipeline with this new model.
   
   Below is an example for pcb-anomaly-detection. Please modify the payload for other sample applications.

   ```json
   [
      {
         "pipeline": "pcb_anomaly_detection_mlops",
         "payload":{
               "source": {
                  "uri": "file:///home/pipeline-server/resources/videos/anomalib_pcb_test.avi",
                  "type": "uri"
               },
               "destination": {
               "frame": {
                  "type": "webrtc",
                  "peer-id": "anomaly"
               }
               },
               "parameters": {
                  "classification-properties": {
                     "model": "/home/pipeline-server/resources/models/new-model/deployment/Anomaly classification/model/model.xml",
                     "device": "CPU"
                  }
               }
         }
      }
   ]
   ```

10. View the WebRTC streaming on `https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/<peer-str-id>/` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.


## Troubleshooting

- [Troubleshooting Guide](../troubleshooting.md)
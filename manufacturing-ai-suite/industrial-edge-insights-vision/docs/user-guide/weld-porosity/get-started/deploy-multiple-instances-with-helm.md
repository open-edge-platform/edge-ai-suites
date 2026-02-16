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

   > **Note:** These steps demonstrate launching two weld-porosity instances and one pallet-defect-detection instance. Modify the sample apps and instances as needed for your use case.

2. Create a `config.yml` file to define your application instances and their unique port configurations. Add the following sample contents and save.

   Example:

   ```text
   weld-porosity:
     weld1:
       NGINX_HTTP_PORT: 30080
       NGINX_HTTPS_PORT: 30443
       COTURN_PORT: 30478
       S3_STORAGE_PORT: 30800
     weld2:
       NGINX_HTTP_PORT: 30081
       NGINX_HTTPS_PORT: 30444
       COTURN_PORT: 30479
       S3_STORAGE_PORT: 30801

   pallet-defect-detection:
     pdd1:
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

1. Install the helm chart for all instances

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
    # Below is an example for Weld Porosity Classification. Please adjust the source path of models and videos appropriately for other sample applications.

    POD_NAME=$(kubectl get pods -n <INSTANCE_NAME> -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/weld-porosity/videos/welding.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>

    kubectl cp resources/weld-porosity/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>
   ```

### Start AI pipelines

#### Start pipeline for all instances

1. Fetch the list of pipeline loaded available to launch for all instances

   ```sh
   ./sample_list.sh helm
   ```

   This lists the pipeline loaded in DLStreamer Pipeline Server.

   Output:

   ```text
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
    -------------------------------------------
    Status of: weld2 (SAMPLE_APP: weld-porosity)
    -------------------------------------------
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/.env
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

    -------------------------------------------
    Status of: pdd1 (SAMPLE_APP: pallet-defect-detection)
    -------------------------------------------
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pallet-defect-detection/pdd1/.env
    Running sample app: pallet-defect-detection
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
            "detection-properties": {
            "element": {
                "format": "element-properties",
                "name": "detection"
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
    Payload for pipeline 'weld_porosity_classification'. Response: "b93bfeac08be11f1ad7e65ddafc77c95"

    ------------------------------------------
    Processing instance: weld2 from SAMPLE_APP: weld-porosity
    ------------------------------------------
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/payload.json
    Payload loaded successfully.
    Starting first pipeline: weld_porosity_classification
    Launching pipeline: weld_porosity_classification
    Extracting payload for pipeline: weld_porosity_classification
    Found 1 payload(s) for pipeline: weld_porosity_classification
    Payload for pipeline 'weld_porosity_classification'. Response: "b94a431e08be11f1a909473ed1791112"

    ------------------------------------------
    Processing instance: pdd1 from SAMPLE_APP: pallet-defect-detection
    ------------------------------------------
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pallet-defect-detection/pdd1/.env
    Running sample app: pallet-defect-detection
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pallet-defect-detection/pdd1/payload.json
    Payload loaded successfully.
    Starting first pipeline: pallet_defect_detection
    Launching pipeline: pallet_defect_detection
    Extracting payload for pipeline: pallet_defect_detection
    Found 1 payload(s) for pipeline: pallet_defect_detection
    Payload for pipeline 'pallet_defect_detection'. Response: "b954c96e08be11f186da8998a0e335d7"
   ```

3. Access the WebRTC stream

   The inference stream can be viewed on WebRTC, in a browser, at the following url depending on the SAMPLE_APP:

   > **Note:** The `NGINX_HTTPS_PORT` is different for each instance of the sample app. For example, for the sample config mentioned previously, the instance weld1 has nginx port set to 30443, weld2 set to 30444 & pdd1 set to 30445.

   ```text
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/weld/             # Weld Porosity
   https://<HOST_IP>:<NGINX_HTTPS_PORT>/mediamtx/pdd/              # Pallet Defect Detection
   ```

#### Start pipeline for a particular instance only

1. Fetch the list of pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_list.sh helm -i <INSTANCE_NAME>
   ```

   Example Output:

   ```text
    Instance name set to: weld1
    Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
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

2. Start the pipeline for <INSTANCE_NAME>:

   ```bash
   ./sample_start.sh helm -i <INSTANCE_NAME> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: weld2
    Starting specified pipeline(s)...
    Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld2
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/payload.json
    Payload loaded successfully.
    Starting pipeline: weld_porosity_classification_gpu
    Launching pipeline: weld_porosity_classification_gpu
    Extracting payload for pipeline: weld_porosity_classification_gpu
    Found 1 payload(s) for pipeline: weld_porosity_classification_gpu
    Payload for pipeline 'weld_porosity_classification_gpu'Response: "5e34d76308bf11f180cd473ed1791112"
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
    Instance name set to: weld1
    Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
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


2. Start the pipeline for <INSTANCE_NAME> where pipeline is loaded from <file>:

   ```bash
   ./sample_start.sh helm -i <INSTANCE_NAME> --payload <file> -p <PIPELINE_NAME>
   ```

   Output:

   ```text
   Instance name set to: weld1
    Custom payload file set to: custom_payload.json
    Starting specified pipeline(s)...
    Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld1
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from custom_payload.json
    Payload loaded successfully.
    Starting pipeline: weld_porosity_classification
    Launching pipeline: weld_porosity_classification
    Extracting payload for pipeline: weld_porosity_classification
    Found 1 payload(s) for pipeline: weld_porosity_classification
    Payload for pipeline 'weld_porosity_classification'. Response: "ce19bc0908bf11f1a35265ddafc77c95"
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
    Processing instance: weld1 from sample app: weld-porosity
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    [
    {
        "avg_fps": 30.00142374484543,
        "elapsed_time": 22.4656023979187,
        "id": "b93bfeac08be11f1ad7e65ddafc77c95",
        "message": "",
        "start_time": 1770975067.2788885,
        "state": "COMPLETED"
    },
    {
        "avg_fps": 30.42922851463312,
        "elapsed_time": 1.8074719905853271,
        "id": "f76e7ccb08bf11f186f065ddafc77c95",
        "message": "",
        "start_time": 1770975600.9002106,
        "state": "RUNNING"
    }
    ]
    Processing instance: weld2 from sample app: weld-porosity
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    [
    {
        "avg_fps": 29.999166506145382,
        "elapsed_time": 22.46729850769043,
        "id": "b94a431e08be11f1a909473ed1791112",
        "message": "",
        "start_time": 1770975067.406253,
        "state": "COMPLETED"
    },
    {
        "avg_fps": 30.54844642721685,
        "elapsed_time": 1.7349472045898438,
        "id": "f7802bd908bf11f1a94d473ed1791112",
        "message": "",
        "start_time": 1770975600.9935298,
        "state": "RUNNING"
    }
    ]
    Processing instance: pdd1 from sample app: pallet-defect-detection
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pallet-defect-detection/pdd1/.env
    Running sample app: pallet-defect-detection
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    [
    {
        "avg_fps": 30.001247319522257,
        "elapsed_time": 97.19596409797668,
        "id": "b954c96e08be11f186da8998a0e335d7",
        "message": "",
        "start_time": 1770975067.9525275,
        "state": "COMPLETED"
    },
    {
        "avg_fps": 30.215796665327662,
        "elapsed_time": 1.5223815441131592,
        "id": "f78ddb9308bf11f189938998a0e335d7",
        "message": "",
        "start_time": 1770975601.231348,
        "state": "RUNNING"
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
    Processing instance: weld1 (SAMPLE_APP: weld-porosity)
    -------------------------------------------
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld1/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 9838a5fc08c011f1952765ddafc77c95
    Pipeline instance with ID '9838a5fc08c011f1952765ddafc77c95' stopped successfully. Response: {
    "avg_fps": 30.039388029430235,
    "elapsed_time": 6.924229145050049,
    "id": "9838a5fc08c011f1952765ddafc77c95",
    "message": "",
    "start_time": 1770975870.6583247,
    "state": "RUNNING"
    }

    -------------------------------------------
    Processing instance: weld2 (SAMPLE_APP: weld-porosity)
    -------------------------------------------
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 984bd77408c011f18784473ed1791112
    Pipeline instance with ID '984bd77408c011f18784473ed1791112' stopped successfully. Response: {
    "avg_fps": 30.069113014911213,
    "elapsed_time": 6.9173901081085205,
    "id": "984bd77408c011f18784473ed1791112",
    "message": "",
    "start_time": 1770975870.7897067,
    "state": "RUNNING"
    }

    -------------------------------------------
    Processing instance: pdd1 (SAMPLE_APP: pallet-defect-detection)
    -------------------------------------------
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/pallet-defect-detection/pdd1/.env
    Running sample app: pallet-defect-detection
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 9859e83508c011f197ba8998a0e335d7
    Pipeline instance with ID '9859e83508c011f197ba8998a0e335d7' stopped successfully. Response: {
    "avg_fps": 30.087479509211562,
    "elapsed_time": 6.913166284561157,
    "id": "9859e83508c011f197ba8998a0e335d7",
    "message": "",
    "start_time": 1770975870.8848493,
    "state": "RUNNING"
    }
   ```

2. Stop pipelines of given instance:

   ```bash
   ./sample_stop.sh helm -i <INSTANCE_NAME>
   ```

   Output:

   ```text
    Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld2
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: d39e02a808c011f1814e473ed1791112
    Pipeline instance with ID 'd39e02a808c011f1814e473ed1791112' stopped successfully. Response: {
    "avg_fps": 30.04035470517983,
    "elapsed_time": 15.945207834243774,
    "id": "d39e02a808c011f1814e473ed1791112",
    "message": "",
    "start_time": 1770975970.288273,
    "state": "RUNNING"
    }
   ```

3. Stop pipelines of an instance with a given instance_id:

   ```sh
   ./sample_stop.sh helm -i <INSTANCE_NAME> --id <INSTANCE_ID>
   ```

   Output:

   ```text
    Found SAMPLE_APP: weld-porosity for INSTANCE_NAME: weld2
    Environment variables loaded from /home/intel/IRD/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/temp_apps/weld-porosity/weld2/.env
    Running sample app: weld-porosity
    Using Helm deployment - curl commands will use: <HOST_IP>:<NGINX_HTTPS_PORT>
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Stopping pipeline instance with ID: f3ba8df108c011f1bbb7473ed1791112
    Pipeline instance with ID 'f3ba8df108c011f1bbb7473ed1791112' stopped successfully. Response: {
    "avg_fps": 30.066449153101424,
    "elapsed_time": 15.432467937469482,
    "id": "f3ba8df108c011f1bbb7473ed1791112",
    "message": "",
    "start_time": 1770976024.176582,
    "state": "RUNNING"
    }
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
    # Below is an example for Weld Porosity Classification. Please adjust the source path of models and videos appropriately for other sample applications.

    POD_NAME=$(kubectl get pods -n <INSTANCE_NAME> -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/weld-porosity/videos/welding.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>

    kubectl cp resources/weld-porosity/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>
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

6. Start the pipeline with the following cURL command  with `<HOST_IP>` set to system IP and the `<NGINX_HTTPS_PORT>` mentioned in the config.yml for each instance. Ensure to give the correct path to the model as seen below. This example starts an AI pipeline for weld-porosity.  Please adjust the source path of models and videos appropriately for other sample applications.

   ```sh
    curl -k https://<HOST_IP>:<NGINX_HTTPS_PORT>/api/pipelines/user_defined_pipelines/weld_porosity_classification_s3write -X POST -H 'Content-Type: application/json' -d '{
        "source": {
            "uri": "file:///home/pipeline-server/resources/videos/welding.avi",
            "type": "uri"
        },
        "destination": {
            "frame": {
                "type": "webrtc",
                "peer-id": "welds3"
            }
        },
        "parameters": {
            "classification-properties": {
                "model": "/home/pipeline-server/resources/models/weld-porosity/deployment/Classification/model/model.xml",
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
    # Below is an example for Weld Porosity Classification. Please adjust the source path of models and videos appropriately for other sample applications.

    POD_NAME=$(kubectl get pods -n <INSTANCE_NAME> -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/weld-porosity/videos/welding.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>

    kubectl cp resources/weld-porosity/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n <INSTANCE_NAME>
   ```

4. Modify the payload in `helm/temp_apps/<SAMPLE_APP>/<INSTANCE_NAME>/payload.json` to launch an instance for the mlops pipeline. 

   ```json
    [
        {
            "pipeline": "weld_porosity_classification_mlops",
            "payload": {
                "destination": {
                    "frame": {
                        "type": "webrtc",
                        "peer-id": "weld"
                    }
                },
                "parameters": {
                    "classification-properties": {
                        "model": "/home/pipeline-server/resources/models/weld-porosity/deployment/Classification/model/model.xml",
                        "device": "CPU"
                    }
                }
            }
        }
    ]
   ```

5. Start the pipeline with the above payload. 

   ```sh
   ./sample_start.sh helm -i <INSTANCE_NAME> -p weld_porosity_classification_mlops
   ```
   Note the instance-id.

6. Download and prepare the model. Below is an example for downloading and preparing model for weld-porosity-classification. Please modify MODEL_URL for the other sample applications.
   >NOTE- For sake of simplicity, we assume that the new model has already been downloaded by Model Download microservice. The following curl command is only a simulation that just downloads the model. In production, however, they will be downloaded by the Model Download service.

   ```sh
    export MODEL_URL='https://github.com/open-edge-platform/edge-ai-resources/raw/a7c9522f5f936c47de8922046db7d7add13f93a0/models/FP16/weld_porosity_classification.zip'

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
   
   Below is an example for weld-porosity-classification. Please modify the payload for other sample applications.

   ```json
    [
        {
            "pipeline": "weld_porosity_classification_mlops",
            "payload": {
                "destination": {
                    "frame": {
                        "type": "webrtc",
                        "peer-id": "weld"
                    }
                },
                "parameters": {
                    "classification-properties": {
                        "model": "/home/pipeline-server/resources/models/new-model/deployment/Classification/model/model.xml",
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
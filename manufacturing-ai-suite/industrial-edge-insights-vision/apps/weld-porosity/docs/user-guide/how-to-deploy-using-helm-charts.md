# Deploy using Helm charts

## Prerequisites

- [System Requirements](system-requirements.md)
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
2. Set app specific values.yaml file.
    ```sh
    cp helm/values_weld_porosity_classification.yaml helm/values.yaml
    ```
3. Optional: Pull the helm chart and replace the existing helm folder with it
    - Note: The helm chart should be downloaded when you are not using the helm chart provided in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm`

    - Download helm chart with the following command

        `helm pull oci://registry-1.docker.io/intel/weld-porosity-sample-application --version 1.2.0`
    - unzip the package using the following command

        `tar -xvf weld-porosity-sample-application-1.2.0.tgz`
    - Replace the helm directory

        `rm -rf helm && mv weld-porosity-sample-application helm`
4.  Edit the HOST_IP, proxy and other environment variables in `helm/values.yaml` as follows
    ```yaml
    env:        
        HOST_IP: <HOST_IP>   # host IP address
        MINIO_ACCESS_KEY: <DATABASE USERNAME> #  example: minioadmin
        MINIO_SECRET_KEY: <DATABASE PASSWORD> #  example: minioadmin
        http_proxy: <http proxy> # proxy details if behind proxy
        https_proxy: <https proxy>
        POSTGRES_PASSWORD: <POSTGRES PASSWORD> #  example: intel1234
        MR_URL: <PROTOCOL>://<HOST_IP>:32002 # example: http://<ip-addr>:32002
        SAMPLE_APP: weld-porosity # application directory
    webrtcturnserver:
        username: <username>  # WebRTC credentials e.g. intel1234
        password: <password>
    ```
5.  Install pre-requisites. Run with sudo if needed.
    ```sh
    ./setup.sh helm
    ```
    This sets up application pre-requisites, download artifacts, sets executable permissions for scripts etc.

## Deploy the application

1.  Install the helm chart
    ```sh
    helm install app-deploy helm -n apps --create-namespace
    ```
    After installation, check the status of the running pods:
    ```sh
    kubectl get pods -n apps
    ```
    To view logs of a specific pod, replace `<pod_name>` with the actual pod name from the output above:
    ```sh
    kubectl logs -n apps -f <pod_name>
    ```

2.  Copy the resources such as video and model from local directory to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.
    ```sh
    # Below is an example for Weld Porosity Classification. Please adjust the source path of models and videos appropriately for other sample applications.
    
    POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/weld-porosity/videos/welding.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

    kubectl cp resources/weld-porosity/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
    ```
3.  Fetch the list of pipeline loaded available to launch
    ```sh
    ./sample_list.sh
    ```
    This lists the pipeline loaded in DLStreamer Pipeline Server.
    
    Output:
    ```sh
    # Example output for Weld Porosity Classification
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
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
        }
        ...
    ]
    ```
4.  Start the sample application with a pipeline.
    ```sh
    ./sample_start.sh -p weld_porosity_classification
    ```
    This command would look for the payload for the pipeline specified in `-p` argument above, inside the `payload.json` file and launch the a pipeline instance in DLStreamer Pipeline Server. Refer to the table, to learn about different options available. 
    
    Output:
    ```sh
    # Example output for Weld Porosity Classification
    Environment variables loaded from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: weld-porosity
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Loading payload from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/helm/apps/weld-porosity/payload.json
    Payload loaded successfully.
    Starting pipeline: weld_porosity_classification
    Launching pipeline: weld_porosity_classification
    Extracting payload for pipeline: weld_porosity_classification
    Found 1 payload(s) for pipeline: weld_porosity_classification
    Payload for pipeline 'weld_porosity_classification' {"source":{"uri":"file:///home/pipeline-server/resources/videos/welding.avi","type":"uri"},"destination":{"frame":{"type":"webrtc","peer-id":"weld"}},"parameters":{"classification-properties":{"model":"/home/pipeline-server/resources/models/weld-porosity/deployment/Classification/model/model.xml","device":"CPU"}}}
    Posting payload to REST server at http://10.223.22.63:30107/pipelines/user_defined_pipelines/weld_porosity_classification
    Payload for pipeline 'weld_porosity_classification' posted successfully. Response: "895130405c8e11f08b78029627ef9c6b"
    ```
    >NOTE- This would start the pipeline. You can view the inference stream on WebRTC by opening a browser and navigating to http://<HOST_IP>:31111/weld/

5.  Get status of pipeline instance(s) running.
    ```sh
    ./sample_status.sh
    ```
    This command lists status of pipeline instances launched during the lifetime of sample application.
    
    Output:
    ```sh
    # Example output for Weld Porosity Classification
    Environment variables loaded from /home/intel/OEP/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: weld-porosity
    [
        {
            "avg_fps": 30.09161750097031,
            "elapsed_time": 2.3594603538513184,
            "id": "895130405c8e11f08b78029627ef9c6b",
            "message": "",
            "start_time": 1752042770.7844434,
            "state": "RUNNING"
        }
    ]
    ```

6. Stop pipeline instance.
    ```sh
    ./sample_stop.sh
    ```
    This command will stop all instances that are currently in `RUNNING` state and respond with the last status.
    
    Output:
    ```sh
    # Example output for Weld Porosity Classification
    No pipelines specified. Stopping all pipeline instances
    Environment variables loaded from /home/intel/OEP/new/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision/.env
    Running sample app: weld-porosity
    Checking status of dlstreamer-pipeline-server...
    Server reachable. HTTP Status Code: 200
    Instance list fetched successfully. HTTP Status Code: 200
    Found 1 running pipeline instances.
    Stopping pipeline instance with ID: 895130405c8e11f08b78029627ef9c6b
    Pipeline instance with ID '895130405c8e11f08b78029627ef9c6b' stopped successfully. Response: {
    "avg_fps": 30.04385410714797,
    "elapsed_time": 6.457224130630493,
    "id": "895130405c8e11f08b78029627ef9c6b",
    "message": "",
    "start_time": 1752042770.7844434,
    "state": "RUNNING"
    }

    ```
    If you wish to stop a specific instance, you can provide it with an `--id` argument to the command.    
    For example, `./sample_stop.sh --id 895130405c8e11f08b78029627ef9c6b`

7. Uninstall the helm chart.
     ```sh
     helm uninstall app-deploy -n apps
     ```

## Storing frames to S3 storage

Applications can take advantage of S3 publish feature from DLStreamer Pipeline Server and use it to save frames to an S3 compatible storage.

1. Run all the steps mentioned in above [section](./how-to-deploy-using-helm-charts.md#setup-the-application) to setup the application. 

2. Install the helm chart
    ```sh
    helm install app-deploy helm -n apps --create-namespace
    ```

3. Copy the resources such as video and model from local directory to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.
    ```sh
    # Below is an example for Weld Porosity Classification. Please adjust the source path of models and videos appropriately for other sample applications.

    POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/weld-porosity/videos/welding.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

    kubectl cp resources/weld-porosity/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
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
    > **Note** DLStreamer Pipeline Server expects the bucket to be already present in the database. The next step will help you create one.

5. Create a S3 bucket using the following script. 

    Update the `HOST_IP` and credentials with that of the running MinIO server. Name the file as `create_bucket.py`.

   ```python
   import boto3
   url = "http://<HOST_IP>:30800"
   user = "<value of MR_MINIO_ACCESS_KEY used in helm/values.yaml>"
   password = "<value of MR_MINIO_SECRET_KEY used in helm/values.yaml>"
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
   python3 create_bucket.py
   ```

6. Start the pipeline with the following cURL command  with `<HOST_IP>` set to system IP. Ensure to give the correct path to the model as seen below. This example starts an AI pipeline.

    ```sh
    curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/weld_porosity_classification_s3write -X POST -H 'Content-Type: application/json' -d '{
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

7. Go to MinIO console on `http://<HOST_IP>:30800/` and login with `MR_MINIO_ACCESS_KEY` and `MR_MINIO_SECRET_KEY` provided in `helm/values.yaml` file. After logging into console, you can go to `ecgdemo` bucket and check the frames stored.

   ![S3 minio image storage](./images/s3-minio-storage.png)

8. Uninstall the helm chart.
    ```sh
    helm uninstall app-deploy -n apps
    ```

## MLOps using Model Registry

1. Run all the steps mentioned in above [section](./how-to-deploy-using-helm-charts.md#setup-the-application) to setup the application. 

2. Install the helm chart
    ```sh
    helm install app-deploy helm -n apps --create-namespace
    ```

3. Copy the resources such as video and model from local directory to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.
    ```sh
    # Below is an example for Weld Porosity Classification. Please adjust the source path of models and videos appropriately for other sample applications.

    POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/weld-porosity/videos/welding.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

    kubectl cp resources/weld-porosity/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
    ```

4. Modify the payload in `helm/apps/weld-porosity/payload.json` to launch an instance for the mlops pipeline
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
    ```
    ./sample_start.sh -p weld_porosity_classification_mlops
    ```

6. Download and prepare the model.
    ```sh
    export MODEL_URL='https://github.com/open-edge-platform/edge-ai-resources/raw/c13b8dbf23d514c2667d39b66615bd1400cb889d/models/weld_porosity_classification.zip'
    
    curl -L "$MODEL_URL" -o "$(basename $MODEL_URL)"
    ```

7. Run the following curl command to upload the local model. 
    ```sh
    curl -L -X POST "http://<HOST_IP>:32002/models" \
    -H 'Content-Type: multipart/form-data' \
    -F 'name="YOLO_Test_Model"' \
    -F 'precision="fp32"' \
    -F 'version="v1"' \
    -F 'origin="Geti"' \
    -F 'file=@<model_file_path.zip>;type=application/zip' \
    -F 'project_name="weld-porosity-classification"' \
    -F 'architecture="YOLO"' \
    -F 'category="Classification"'
    ```
   > NOTE: Replace model_file_path.zip in the cURL request with the actual file path of your model's .zip file, and HOST_IP with the IP address of the host machine.

8. Check if the model is uploaded successfully.

    ```sh
    curl 'http://<HOST_IP>:32002/models'
    ```

9. Check the instance ID of the currently running pipeline to use it for the next step.
   ```sh
   curl --location -X GET http://<HOST_IP>:30107/pipelines/status
   ```

10. Restart the model with a new model from Model Registry.
    The following curl command downloads the model from Model Registry using the specs provided in the payload. Upon download, the running pipeline is restarted with replacing the older model with this new model. Replace the `<instance_id_of_currently_running_pipeline>` in the URL below with the id of the pipeline instance currently running.
    ```sh
    curl 'http://<HOST_IP>:30107/pipelines/user_defined_pipelines/weld_porosity_classification_mlops/<instance_id_of_currently_running_pipeline>/models' \
    --header 'Content-Type: application/json' \
    --data '{
    "project_name": "weld-porosity-classification",
    "version": "v1",
    "category": "Classification",
    "architecture": "YOLO",
    "precision": "fp32",
    "deploy": true,
    "pipeline_element_name": "classification",
    "origin": "Geti",
    "name": "YOLO_Test_Model"
    }'
    ```

    > NOTE- The data above assumes there is a model in the registry that contains these properties. Also, the pipeline name that follows `user_defined_pipelines/`, will affect the `deployment` folder name.

11. View the WebRTC streaming on `http://<HOST_IP>:<mediamtx-port>/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

    ![WebRTC streaming](./images/webrtc-streaming.png)

## Troubleshooting
- [Troubleshooting Guide](troubleshooting-guide.md)
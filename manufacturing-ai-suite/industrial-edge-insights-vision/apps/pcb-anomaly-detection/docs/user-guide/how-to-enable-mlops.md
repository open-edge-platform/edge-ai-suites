# MLOps using Model Registry
Applications for industrial vision can also be used to demonstrate MLOps workflow using Model Registry microservice.
With this feature, during runtime, you can download a new model from the registry and restart the pipeline with the new model.

## Contents

### Launch a pipeline in DLStreamer Pipeline Server
1.  Set up the sample application to start a pipeline. A pipeline named `pcb_anomaly_detection_mlops` is already provided in the `pipeline-server-config.json` for this demonstration with the PCB anomaly detection sample app.

    > Ensure that the pipeline inference element such as gvadetect/gvaclassify/gvainference should not have a `model-instance-id` property set. If set, this would not allow the new model to be run with the same value provided in the model-instance-id.

    Navigate to the `[WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision` directory and set up the app.
    ```sh
    cp .env_weld_porosity_classification .env
    ```
    Edit the HOST_IP and other environment variables in `.env` file
    ```sh
    ./setup.sh
    ```
2. Bring up the containers
    ```sh
    docker compose up -d
    ```
3. Check to see if the pipeline is loaded is present which in our case is `pcb_anomaly_detection_mlops`.
    ```sh
    ./sample_list.sh
    ```
4. Modify the payload in `apps/pcb-anomaly-detection/payload.json` to launch an instance for the mlops pipeline
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
    ```
    ./sample_start.sh -p pcb_anomaly_detection_mlops
    ```

    
### Upload a model to Model Registry

   > The following section assumes Model Registry microservice is up and running. 

   > For this demonstration we will be using Geti trained PCB anomaly detection model. Usually, the newer model is the same as older, architecture wise, but is retrained for better performance. We will using the same model and call it a different version.

1.  Download and prepare the model.
    ```sh
    export MODEL_URL='<URL to MODEL.zip>'
    
    curl -L "$MODEL_URL" -o "$(basename $MODEL_URL)"
    ```

2.  Run the following curl command to upload the local model. 
    ```sh
    curl -L -X POST "http://<HOST_IP>:32002/models" \
    -H 'Content-Type: multipart/form-data' \
    -F 'name="YOLO_Test_Model"' \
    -F 'precision="fp32"' \
    -F 'version="v1"' \
    -F 'origin="Geti"' \
    -F 'file=@<model_file_path.zip>;type=application/zip' \
    -F 'project_name="pcb-anomaly-detection"' \
    -F 'architecture="YOLO"' \
    -F 'category="Anomaly classification"'
    ```
   > NOTE: Replace model_file_path.zip in the cURL request with the actual file path of your model's .zip file, and HOST_IP with the IP address of the host machine.

3. Check if the model is uploaded successfully.

    ```sh
    curl 'http://<HOST_IP>:32002/models'
    ```

### Steps

> The following steps assume a pipeline is already running on DLStreamer Pipeline Server that you wish to update with a new model. If you would like to launch a sample pipeline for this demonstration, see [here](#launch-a-pipeline-in-dlstreamer-pipeline-server). Note the instance ID. You would need it in the steps below while restarting the pipeline with a newer model.

1. Update the following variables in `.env` file
    ``` sh
    HOST_IP= # <IP Adress of the host machine>

    MR_PSQL_PASSWORD=  #PostgreSQL service & client adapter e.g. intel1234

    MR_MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
    MR_MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

    MR_URL= # Model registry url. Example http://<IP_address_of_model_registry_server>:32002

    MTX_WEBRTCICESERVERS2_0_USERNAME=  # Webrtc-mediamtx username. e.g intel1234
    MTX_WEBRTCICESERVERS2_0_PASSWORD=  # Webrtc-mediamtx password. e.g intel1234
    ```

2. List all the registered models in the model registry
    ```sh
    curl 'http://<HOST_IP>:32002/models'
    ```
    If you do not have a model available, follow the steps [here](#upload-a-model-to-model-registry) to upload a sample model in Model Registry

3. Check the instance ID of the currently running pipeline to use it for the next step.
   ```sh
   curl --location -X GET http://<HOST_IP>:8080/pipelines/status
   ```
   > NOTE- Replace the port in the curl request according to the deployment method i.e. default 8080 for compose based.

4. Restart the model with a new model from Model Registry.
    The following curl command downloads the model from Model Registry using the specs provided in the payload. Upon download, the running pipeline is restarted with replacing the older model with this new model. Replace the `<instance_id_of_currently_running_pipeline>` in the URL below with the id of the pipeline instance currently running.
    ```sh
    curl 'http://<HOST_IP>:8080/pipelines/user_defined_pipelines/pcb_anomaly_detection_mlops/{instance_id_of_currently_running_pipeline}/models' \
    --header 'Content-Type: application/json' \
    --data '{
    "project_name": "pcb-anomaly-detection",
    "version": "v1",
    "category": "Anomaly classification",
    "architecture": "YOLO",
    "precision": "fp32",
    "deploy": true,
    "pipeline_element_name": "classification",
    "origin": "Geti",
    "name": "YOLO_Test_Model"
    }'
   ```

    > NOTE- The data above assumes there is a model in the registry that contains these properties. Also, the pipeline name that follows `user_defined_pipelines/`, will affect the `deployment` folder name.

4. View the WebRTC streaming on `http://<HOST_IP>:<mediamtx-port>/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

    ![WebRTC streaming](./images/webrtc-streaming.png)

6. You can also stop any running pipeline by using the pipeline instance "id"
   ```sh
   curl --location -X DELETE http://<HOST_IP>:8080/pipelines/{instance_id}
   ```

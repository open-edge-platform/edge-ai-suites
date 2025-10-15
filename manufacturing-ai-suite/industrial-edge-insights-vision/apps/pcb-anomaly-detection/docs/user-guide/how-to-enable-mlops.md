# MLOps using Model Registry
Applications for industrial vision can also be used to demonstrate MLOps workflow using Model Registry microservice.
With this feature, during runtime, you can download a new model from the registry and restart the pipeline with the new model.

## Contents

### Launch a pipeline in DLStreamer Pipeline Server
1.  Set up the sample application to start a pipeline. A pipeline named `pcb_anomaly_detection_mlops` is already provided in the `pipeline-server-config.json` for this demonstration with the PCB anomaly detection sample app.

    > Ensure that the pipeline inference element such as gvadetect/gvaclassify/gvainference should not have a `model-instance-id` property set. If set, this would not allow the new model to be run with the same value provided in the model-instance-id.

    Navigate to the `[WORKDIR]/manufacturing-ai-suite/industrial-edge-insights-vision` directory and set up the app.
    ```sh
    cp .env_pcb_anomaly_detection .env
    ```
2. Update the following variables in `.env` file
    ``` sh
    HOST_IP= # <IP Adress of the host machine>

    MR_PSQL_PASSWORD=  #PostgreSQL service & client adapter e.g. intel1234

    MR_MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
    MR_MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

    MTX_WEBRTCICESERVERS2_0_USERNAME=  # Webrtc-mediamtx username. e.g intel1234
    MTX_WEBRTCICESERVERS2_0_PASSWORD=  # Webrtc-mediamtx password. e.g intel1234
    ```
3. Run the setup script using the following command
    ```sh
    ./setup.sh
    ```
4. Bring up the containers
    ```sh
    docker compose up -d
    ```
5. Check to see if the pipeline is loaded is present which in our case is `pcb_anomaly_detection_mlops`.
    ```sh
    ./sample_list.sh
    ```
6. Modify the payload in `apps/pcb-anomaly-detection/payload.json` to launch an instance for the mlops pipeline
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
7. Start the pipeline with the above payload.
    ```
    ./sample_start.sh -p pcb_anomaly_detection_mlops
    ```

    
### Upload a model to Model Registry

   > The following section assumes Model Registry microservice is up and running. 

   > For this demonstration we will be using Geti trained PCB anomaly detection model. Usually, the newer model is the same as older, architecture wise, but is retrained for better performance. We will using the same model and call it a different version.

1.  Download and prepare the model.
    ```sh
    export MODEL_URL='https://github.com/open-edge-platform/edge-ai-resources/raw/2d63ba48e2ac3c09339f27c32267bb026e146175/models/pcb-anomaly-detection.zip'
    
    curl -L "$MODEL_URL" -o "$(basename $MODEL_URL)"
    ```

2.  Run the following curl command to upload the local model. 
    ```sh
    curl -k -L -X POST "https://<HOST_IP>/registry/models" \
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
    curl -k 'https://<HOST_IP>/registry/models'
    ```

### Steps to use the new model

1. List all the registered models in the model registry
    ```sh
    curl -k 'https://<HOST_IP>/registry/models'
    ```
    If you do not have a model available, follow the steps [here](#upload-a-model-to-model-registry) to upload a sample model in Model Registry

2. Check the instance ID of the currently running pipeline to use it for the next step.
   ```sh
   curl -k --location -X GET https://<HOST_IP>/api/pipelines/status
   ```

3. Restart the model with a new model from Model Registry.
    The following curl command downloads the model from Model Registry using the specs provided in the payload. Upon download, the running pipeline is restarted with replacing the older model with this new model. Replace the `<instance_id_of_currently_running_pipeline>` in the URL below with the id of the pipeline instance currently running.
    ```sh
    curl -k 'https://<HOST_IP>/api/pipelines/user_defined_pipelines/pcb_anomaly_detection_mlops/{instance_id_of_currently_running_pipeline}/models' \
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

5. You can also stop any running pipeline by using the pipeline instance "id"
   ```sh
   curl -k --location -X DELETE https://<HOST_IP>/api/pipelines/{instance_id}
   ```

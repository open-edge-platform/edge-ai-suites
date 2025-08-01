# How to use an AI Model and Video File of your own


You can bring your own model and run this sample application the same way as how we bring in the Worker Safety Gear Detection model. You can also bring your own video file source. Please see below for details:
>**Important** If you have previously run the setup for the sample app using `setup.sh`, default sample model and video are downloaded under `resource/<app_name>` in your repo directory. You can manually add the model and video of your choice and keep it in this structure. 
For compose based deployment, the entire resources directory is volume mounted and made available to pipeline server. However for helm, you need to manually copy those to the container.

## For docker compose based deployment

1. The worker safety gear detection model is placed in the repository under  `resources/worker-safety-gear-detection/models`. You can also find the input video file source for inference under `resources/worker-safety-gear-detection/videos`.
/home/pipeline-server/resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml
- resources/
  - worker-safety-gear-detection/
    - models/
      - worker-safety-gear-detection/
        - deployment/
          - Detection/
            - model/
              - model.bin
              - model.xml
    - videos/
      - Safety_Full_Hat_and_Vest.avi

   > **Note**
   > You can organize the directory structure for models for different use cases.


2. The `resources` folder containing both the model and video file is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` (present in the repository) file as follows.
    ```sh
    volumes:
    - ./resources/${SAMPLE_APP}/:/home/pipeline-server/resources/
    ```
    > The value of `${SAMPLE_APP}` is fetched from the `.env` file specifying the particular sample app you are running.

3. Since this is a detection model, ensure to use gvadetect in the pipeline. For example: See the `worker_safety_gear_detection` pipeline in `pipeline-server-config.json` (present in the repository) where gvadetect is used.

4. The `pipeline-server-config.json` is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` as follows:

    ```sh
    volumes:
    - ./apps/${SAMPLE_APP}/configs/pipeline-server-config.json:/home/pipeline-server/config.json
    ```

4. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:
    ```sh
        curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/worker_safety_gear_detection -X POST -H 'Content-Type: application/json' -d '{
            "source": {
                "uri": "file:///home/pipeline-server/resources/videos/Safety_Full_Hat_and_Vest.avi",
                "type": "uri"
            },
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "worker_safety"
                }
            },
            "parameters": {
                "detection-properties": {
                    "model": "/home/pipeline-server/resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml",
                    "device": "CPU"
                }
            }
        }'
    ```

## For helm chart based deployment

You can bring your own model and run this sample application the same way as how we bring in the worker safety gear detection model as follows:

1. The worker safety gear detection model is placed in the repository under `resources/worker-safety-gear-detection/models`. You can also find the input video file source for inference under `resources/worker-safety-gear-detection/videos`.

- resources/
  - worker-safety-gear-detection/
    - models/
      - worker-safety-gear-detection/
        - deployment/
          - Detection/
            - model/
              - model.bin
              - model.xml
    - videos/
      - Safety_Full_Hat_and_Vest.avi

   > **Note**
   > You can organize the directory structure for models for different use cases.


2. Copy the resources such as video and model from local directory to the to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.
    > **NOTE** It is assumed that the sample app is already deployed in the cluster
    ```sh
    # Below is an example for Worker Safety gear detection. Please adjust the source path of models and videos appropriately for other sample applications.
    POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/worker-safety-gear-detection/videos/Safety_Full_Hat_and_Vest.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps
 
    kubectl cp resources/worker-safety-gear-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
    ```
    - Please update `imagePullPolicy` as `imagePullPolicy: IfNotPresent` in `values.yaml` in order to use the above built image.

3. Since this is a detection model, ensure to use gvadetect in the pipeline. For example: See the `worker_safety_gear_detection` pipeline in `pipeline-server-config.json` (present in the repository) where gvadetect is used.

4. The `pipeline-server-config.json` is volume mounted into DL Streamer Pipeline Server in `provision-configmap.yaml` as follows:

    ```sh
    apiVersion: v1
    kind: ConfigMap
    metadata:
      namespace: {{ .Values.namespace }}
      name: dlstreamer-pipeline-server-config-input
    data:
      config.json: |-
    {{ .Files.Get "config.json" | indent 4 }}
    ```

4. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:
    ```sh
        curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/worker_safety_gear_detection -X POST -H 'Content-Type: application/json' -d '{
            "source": {
                "uri": "file:///home/pipeline-server/resources/videos/Safety_Full_Hat_and_Vest.avi",
                "type": "uri"
            },
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "worker_safety"
                }
            },
            "parameters": {
                "detection-properties": {
                        "model": "/home/pipeline-server/resources/models/worker-safety-gear-detection/deployment/Detection/model/model.xml",
                        "device": "CPU"
                }
            }
        }'
    ```
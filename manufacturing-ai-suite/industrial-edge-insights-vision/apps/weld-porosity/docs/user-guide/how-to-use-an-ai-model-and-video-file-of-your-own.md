# How to use an AI Model and Video File of your own


You can bring your own model and run this sample application the same way as how we bring in the weld porosity classification model. You can also bring your own video file source. Please see below for details:
>**Important** If you have previously run the setup for the sample app using `setup.sh`, default sample model and video are downloaded under `resource/<app_name>` in your repo directory. You can manually add the model and video of your choice and keep it in this structure. 
For compose based deployment, the entire resources directory is volume mounted and made available to pipeline server. However for helm, you need to manually copy those to the container.

## For docker compose based deployment

1. The weld porosity classification model is placed as below in the repository under  `resources/weld-porosity/models`. You can also find the input video file source for inference under `videos` in the same directory level.

- resources/
  - weld-porosity/
    - models/
        - weld-porosity/
            - deployment/
                - Classification/
                    - model/
                        - model.bin
                        - model.xml
    - videos/
        - welding.avi

   > **Note**
   > You can organize the directory structure for models for different use cases.


2. The `resources` folder containing both the model and video file is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` (present in the repository) file as follows.
    ```sh
    volumes:
    - ./resources/${SAMPLE_APP}/:/home/pipeline-server/resources/
    ```
    > The value of `${SAMPLE_APP}` is fetched from the `.env` file specifying the particular sample app you are running.

3. Since this is a classficiation model, ensure to use gvaclassify in the pipeline. For example: See the `weld_porosity_classification` pipeline in `pipeline-server-config.json` (present in the repository) where gvadetect is used.

4. The `pipeline-server-config.json` is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` as follows:

    ```sh
    volumes:
    - ./apps/${SAMPLE_APP}/configs/pipeline-server-config.json:/home/pipeline-server/config.json
    ```

4. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:
    ```sh
        curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/weld_porosity_classification -X POST -H 'Content-Type: application/json' -d '{
            "source": {
                "uri": "file:///home/pipeline-server/resources/videos/welding.avi",
                "type": "uri"
            },
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "samplestream"
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

## For helm chart based deployment

You can bring your own model and run this sample application the same way as how we bring in the weld porosity classification model as follows:

1. The weld porosity classification model is placed as below in the repository under `resources/weld-porosity/models`. You can also find the input video file source for inference under `videos` in the same directory level.

- resources/
  - weld-porosity/
    - models/
        - weld-porosity/
            - deployment/
                - Classification/
                    - model/
                        - model.bin
                        - model.xml
    - videos/
        - welding.avi

   > **Note**
   > You can organize the directory structure for models for different use cases.


2. Copy the resources such as video and model from local directory to the to the `dlstreamer-pipeline-server` pod to make them available for application while launching pipelines.
    > **NOTE** It is assumed that the sample app is already deployed in the cluster
    ```sh
    # Below is an example for Weld Porosity classification. Please adjust the source path of models and videos appropriately for other sample applications.
    POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

    kubectl cp resources/weld-porosity/videos/warehouse.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

    kubectl cp resources/weld-porosity/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
    ```
    - Please update `imagePullPolicy` as `imagePullPolicy: IfNotPresent` in `values.yaml` in order to use the above built image.

3. Since this is a classification model, ensure to use gvaclassify in the pipeline. For example: See the `weld_porosity_classification` pipeline in `pipeline-server-config.json` (present in the repository) where gvaclassify is used.

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
        curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/weld_porosity_classification -X POST -H 'Content-Type: application/json' -d '{
            "source": {
                "uri": "file:///home/pipeline-server/resources/videos/welding.avi",
                "type": "uri"
            },
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "samplestream"
                }
            },
            "parameters": {
                "classification-properties": {
                        "model": "/home/pipeline-server/resources/models/geti/weld_porosity_classification/deployment/Classification/model/model.xml",
                        "device": "CPU"
                }
            }
        }'
    ```
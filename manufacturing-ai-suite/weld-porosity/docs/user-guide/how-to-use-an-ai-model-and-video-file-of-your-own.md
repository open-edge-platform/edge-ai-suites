# How to use an AI Model and Video File of your own

## For docker compose based deployment

You can bring your own model and run this sample application the same way as how we bring in the weld porosity classification model. You can also bring your own video file source. Please see below for details:

1. The weld porosity classification model is placed as below in the repository under `models`. You can also find the input video file source for inference under `videos`.

- resources/
  - models/
    - weld_porosity/
      - weld_porosity_classification/
        - deployment/
          - Classification/
            - model/
              - model.bin
              - model.xml
  - videos/
    - welding.avi

   > **Note**  
   > You can organize the directory structure for models for different use cases.

2. The `resources` folder containing both the model and video file is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` (present in the repository) file as follows:

    ```sh
    volumes:
    - ./resources/:/home/pipeline-server/resources/
    ```

3. Since this is a classification model, ensure to use gvaclassify in the pipeline. For example: See the `"/home/pipeline-server/resources/models/weld_porosity/weld_porosity_classification/deployment/Classification/model/model.xml"` pipeline in `config.json` (present in the repository) where gvaclassify is used.

4. The `config.json` is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` as follows:

    ```sh
    volumes:
    - ./configs/config.json:/home/pipeline-server/config.json
    ```

4. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:
    ```sh
        curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/"/home/pipeline-server/resources/models/weld_porosity/weld_porosity_classification/deployment/Classification/model/model.xml" -X POST -H 'Content-Type: application/json' -d '{
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
                    "model": "/home/pipeline-server/resources/models/weld_porosity/weld_porosity_classification/deployment/Classification/model/model.xml",
                    "device": "CPU"
                }
            }
        }'
    ```

## For helm chart based deployment

You can bring your own model and run this sample application the same way as how we bring in the weld porosity classification model as follows:

1. The weld porosity classification model is placed as below in the repository under `models`. You can also find the input video file source for inference under `videos`.

- resources/
  - models/
    - weld_porosity/
      - weld_porosity_classification/
        - deployment/
          - Classification/
            - model/
              - model.bin
              - model.xml
  - videos/
    - welding.avi

   > **Note**  
   > You can organize the directory structure for models for different use cases.


2. Build DL Streamer Pipeline Server by including your new AI model (weld porosity classification model used here as an example) and video file. Example steps below:
    - Create the below `Dockerfile` at the root of the repository
      ```sh
      FROM intel/dlstreamer-pipeline-server:3.0.0
      # Copy the application files
      COPY ./resources/models/weld_porosity /home/pipeline-server/resources/models/weld_porosity
      COPY ./resources/videos/welding.avi /home/pipeline-server/resources/videos/welding.avi
      # Define the command to run the application
      ENTRYPOINT ["./run.sh"]
      ```
    - Build a new DL Streamer Pipeline Server image with the below command from the root of the repository
      ```sh
      docker build -t intel/dlstreamer-pipeline-server:3.0.0 .
      ```
    - Please update `imagePullPolicy` as `imagePullPolicy: IfNotPresent` in `values.yaml` in order to use the above built image.


3. Since this is a classification model, ensure to use gvaclassify in the pipeline. For example: See the `weld_porosity_classification` pipeline in `config.json` (present in the repository) where gvaclassify is used.

4. The `config.json` is volume mounted into DL Streamer Pipeline Server in `provision-configmap.yaml` as follows:
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

5. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:
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
                    "model": "/home/pipeline-server/resources/models/weld_porosity/weld_porosity_classification/deployment/Classification/model/model.xml",
                    "device": "CPU"
            }
        }
    }'
    ```

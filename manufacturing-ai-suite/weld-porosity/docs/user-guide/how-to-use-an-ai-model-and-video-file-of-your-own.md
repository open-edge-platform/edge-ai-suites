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


2. Copy your new AI model (weld porosity classification model used here as an example) and video file to `dlstreamer-pipeline-server` pod.

       POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

       kubectl cp <repo_workdir>/resources/videos/welding.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

       kubectl cp <repo_workdir>/resources/models/weld_porosity/ $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps

   > **Note**
   > You need to run the above commands only after performing the Helm install, and before executing any pipeline.
   > Make sure to replace the 'apps' namespace in the above command with the namespace you are using.

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
    curl http://<HOST_IP>:31107/pipelines/user_defined_pipelines/weld_porosity_classification -X POST -H 'Content-Type: application/json' -d '{
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

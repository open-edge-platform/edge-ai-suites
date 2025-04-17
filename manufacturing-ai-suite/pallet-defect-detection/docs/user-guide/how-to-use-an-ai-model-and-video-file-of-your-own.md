# How to use an AI Model and Video File of your own

## For docker compose based deployment

You can bring your own model and run this sample application the same way as how we bring in the pallet defect detection model. You can also bring your own video file source. Please see below for details:

1. The pallet defect detection model is placed as below in the repository under `models`. You can also find the input video file source for inference under `videos`.

- resources/
  - models/
    - geti/
      - pallet_defect_detection/
        - deployment/
          - Detection/
            - model/
              - model.bin
              - model.xml
  - videos/
    - warehouse.avi

   > **Note**  
   > You can organize the directory structure for models for different use cases.


2. The `resources` folder containing both the model and video file is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` (present in the repository) file as follows:

    ```sh
    volumes:
    - ./resources/:/home/pipeline-server/resources/
    ```

3. Since this is a detection model, ensure to use gvadetect in the pipeline. For example: See the `pallet_defect_detection` pipeline in `config.json` (present in the repository) where gvadetect is used.

4. The `config.json` is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` as follows:

    ```sh
    volumes:
    - ./configs/config.json:/home/pipeline-server/config.json
    ```

4. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:
    ```sh
        curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/pallet_defect_detection -X POST -H 'Content-Type: application/json' -d '{
            "source": {
                "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
                "type": "uri"
            },
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "samplestream"
                }
            },
            "parameters": {
                "detection-properties": {
                    "model": "/home/pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml",
                    "device": "CPU"
                }
            }
        }'
    ```

## For helm chart based deployment

You can bring your own model and run this sample application the same way as how we bring in the pallet defect detection model as follows:

1. The pallet defect detection model is placed as below in the repository under `models`. You can also find the input video file source for inference under `videos`.

- resources/
  - models/
    - geti/
      - pallet_defect_detection/
        - deployment/
          - Detection/
            - model/
              - model.bin
              - model.xml
  - videos/
    - warehouse.avi

   > **Note**  
   > You can organize the directory structure for models for different use cases.


2. Build DL Streamer Pipeline Server by including your new AI model (pallet defect detection model used here as an example) and video file. Example steps below:
    - Create the below `Dockerfile` at the root of the repository
      ```sh
      FROM intel/dlstreamer-pipeline-server:3.0.0

      # Copy the application files
      COPY ./resources/models/geti /home/pipeline-server/resources/models/geti
      COPY ./resources/videos/warehouse.avi /home/pipeline-server/resources/videos/warehouse.avi

      # Define the command to run the application
      ENTRYPOINT ["./run.sh"]
      ```
    - Build a new DL Streamer Pipeline Server image with the below command from the root of the repository
      ```sh
      docker build -t intel/dlstreamer-pipeline-server:3.0.0 .
      ```
    - Please update `imagePullPolicy` as `imagePullPolicy: IfNotPresent` in `values.yaml` in order to use the above built image.

3. Since this is a detection model, ensure to use gvadetect in the pipeline. For example: See the `pallet_defect_detection` pipeline in `config.json` (present in the repository) where gvadetect is used.

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

4. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:
    ```sh
        curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/pallet_defect_detection -X POST -H 'Content-Type: application/json' -d '{
            "source": {
                "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
                "type": "uri"
            },
            "destination": {
                "frame": {
                    "type": "webrtc",
                    "peer-id": "samplestream"
                }
            },
            "parameters": {
                "detection-properties": {
                        "model": "/home/pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml",
                        "device": "CPU"
                }
            }
        }'
    ```
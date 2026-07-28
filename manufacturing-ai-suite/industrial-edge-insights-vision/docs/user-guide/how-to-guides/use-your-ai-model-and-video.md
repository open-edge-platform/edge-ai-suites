# Use Your AI Model and Video

You can use your own model and run it with the sample applications provided.
You can also bring your own video file source. This article will show you how to do it.

> **Important:** If you have previously run the setup for the sample app using `setup.sh`,
> the default sample model and video are downloaded under `resource/<app_name>` in your repo.
> You can manually add your files next to them.
>
> For compose-based deployment, the entire resources directory is a volume mounted and made
> available to pipeline server. However for Helm, you need to manually copy those to the
> container.

## File Location

The model and the input video file are placed in the `resources/<app name>/` folder, under
the `model` and `video` directories:

<!--hide_directive::::{tab-set} hide_directive-->
<!--hide_directive:::{tab-item} hide_directive-->**Pallet Defect Detection**
<!--hide_directive:sync: pallet-detect hide_directive-->

```text
- resources/
  - pallet-defect-detection/
    - models/
        - pallet_defect_detection/
            - deployment/
                - Detection/
                    - model/
                        - model.bin
                        - model.xml
    - videos/
        - warehouse.avi
```

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
<!--hide_directive :sync: pcb-detect hide_directive-->

```text
- resources/
  - pcb-anomaly-detection/
    - models/
      - pcb-anomaly-detection/
        - deployment/
          - Anomaly classification/
            - model/
              - model.bin
              - model.xml
    - videos/
      - anomalib_pcb_test.avi
```

<!--hide_directive
:::
::::
hide_directive-->

> **Note:**
> You can customize the directory structure for different resources and use cases.

## Docker compose deployment

1. The `resources` folder containing both the model and video file is a volume mounted
   into DL Streamer Pipeline Server in `docker-compose.yml` (included in the repository),
   like so:

   ```text
   volumes:
   - ./resources/${SAMPLE_APP}/:/home/pipeline-server/resources/
   ```

   > **Note:** The value of `${SAMPLE_APP}` is fetched from the `.env` file specifying the
     particular sample app you are running.

2. Make sure to adjust the pipeline to the model you are using. See the
   `pipeline-server-config.json` included in the repository.

   - for a **detection model**, use `gvadetect` - as used in the `pallet_defect_detection`
     pipeline.
   - for a **classification model**, use `gvaclassify` - as used in the `pcb_anomaly_detection`
     pipeline.

3. The `pipeline-server-config.json` is a volume mounted into DL Streamer Pipeline Server in
   `docker-compose.yml` (included in the repository), like so:

   ```text
   volumes:
   - ${APP_DIR}/configs/pipeline-server-config.json:/home/pipeline-server/config.json
   ```

4. Provide the model path and video file path in the REST/curl command to start an inference
   workload. For example:

   > **Note:** If you are running multiple instances of the application, make sure to provide
   > `NGINX_HTTPS_PORT` number in the URL for the application instance, i.e., replace `<HOST_IP>` with
     `<HOST_IP>:<NGINX_HTTPS_PORT>`
   >
   > If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the
     default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

   <!--hide_directive::::{tab-set} hide_directive-->
   <!--hide_directive:::{tab-item} hide_directive-->**Pallet Defect Detection**
   <!--hide_directive:sync: pallet-detect hide_directive-->

   ```sh
       curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/pallet_defect_detection -X POST -H 'Content-Type: application/json' -d '{
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
                   "model": "/home/pipeline-server/resources/models/pallet-defect-detection/deployment/Detection/model/model.xml",
                   "device": "CPU"
               }
           }
       }'
   ```

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   ```sh
       curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/pcb_anomaly_detection -X POST -H 'Content-Type: application/json' -d '{
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
       }'
   ```

   <!--hide_directive
   :::
   ::::
   hide_directive-->

## Helm chart deployment

1. Copy the resources such as video and model from local directory to the to the
   `dlstreamer-pipeline-server` pod to make them available for application while launching
   pipelines.

   > **Note:** This guide assumes that the sample app is already deployed in the cluster
   >
   > For multi-instance app deployment, use the instance name in the name space, i.e.,
     `-n <INSTANCE_NAME>` instead of `-n app`. `<INSTANCE_NAME>` is present in config.yml
     for multi instance app deployment.

   <!--hide_directive::::{tab-set} hide_directive-->
   <!--hide_directive:::{tab-item} hide_directive-->**Pallet Defect Detection**
   <!--hide_directive:sync: pallet-detect hide_directive-->

   ```sh
   POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

   kubectl cp resources/pallet-defect-detection/videos/warehouse.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

   kubectl cp resources/pallet-defect-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
   ```

   To use the above built image, change `imagePullPolicy` to `imagePullPolicy: IfNotPresent`
   in `values.yaml`.

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   ```sh
   POD_NAME=$(kubectl get pods -n apps -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-dlstreamer-pipeline-server | head -n 1)

   kubectl cp resources/pcb-anomaly-detection/videos/anomalib_pcb_test.avi $POD_NAME:/home/pipeline-server/resources/videos/ -c dlstreamer-pipeline-server -n apps

   kubectl cp  resources/pcb-anomaly-detection/models/* $POD_NAME:/home/pipeline-server/resources/models/ -c dlstreamer-pipeline-server -n apps
   ```

   <!--hide_directive
   :::
   ::::
   hide_directive-->

2. Make sure to adjust the pipeline to the model you are using. See the
   `pipeline-server-config.json` included in the repository.

   - for a **detection model**, use `gvadetect` - as used in the `pallet_defect_detection`
     pipeline.
   - for a **classification model**, use `gvaclassify` - as used in the `pcb_anomaly_detection`
     pipeline.

3. The `pipeline-server-config.json` is volume mounted into DL Streamer Pipeline Server in
   `provision-configmap.yaml`, like so:

   ```yaml
   apiVersion: v1
   kind: ConfigMap
   metadata:
     namespace: {{ .Values.namespace }}
     name: dlstreamer-pipeline-server-config-input
   data:
     config.json: |-
   {{ .Files.Get "config.json" | indent 4 }}
   ```

4. Provide the model path and video file path in the REST/curl command to start an inference
   workload. For example:

   > **Note:** If you are running multiple instances of the application, make sure to provide
   > `NGINX_HTTPS_PORT` number in the URL for the application instance, i.e., replace `<HOST_IP>` with
     `<HOST_IP>:<NGINX_HTTPS_PORT>`
   >
   > If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the
     default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

   <!--hide_directive::::{tab-set} hide_directive-->
   <!--hide_directive:::{tab-item} hide_directive-->**Pallet Defect Detection**
   <!--hide_directive:sync: pallet-detect hide_directive-->

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
                       "model": "/home/pipeline-server/resources/models/pallet-defect-detection/deployment/Detection/model/model.xml",
                       "device": "CPU"
               }
           }
       }'
   ```

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   ```sh
       curl http://<HOST_IP>:30107/pipelines/user_defined_pipelines/pcb_anomaly_detection -X POST -H 'Content-Type: application/json' -d '{
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
       }'
   ```

   <!--hide_directive
   :::
   ::::
   hide_directive-->

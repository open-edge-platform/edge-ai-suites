# Enable MLOps in Vision AI Detection Apps

Applications for industrial edge insights vision can also be used to demonstrate MLOps workflow using Model Download microservice.
With this feature, during runtime, you can download a new model using the microservice and restart the pipeline with the new model.

## Contents

### Prerequisites

This guide assumes that Model Download service has already downloaded the model to be updated to `/tmp/models`.
To learn how to setup Model Download, see [here](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/get-started.html#start-with-setup-script).

If not available, you can simulate this by downloading the appropriate sample model from the Edge AI Resources repository by using the link from the tabs below. Once downloaded, extract to `/tmp/models` directory.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
<!--hide_directive :sync: pallet-detect hide_directive-->

[Download Pallet Defect Detection Model](https://github.com/open-edge-platform/edge-ai-resources/blob/main/models/INT8/pallet_defect_detection.zip)

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
<!--hide_directive :sync: pcb-detect hide_directive-->

[Download PCB Anomaly Detection Model](https://github.com/open-edge-platform/edge-ai-resources/blob/main/models/FP16/pcb-anomaly-detection.zip)

<!--hide_directive
:::
::::
hide_directive-->

### Steps

> **Note:** If you are running multiple instances of the application, ensure to provide `NGINX_HTTPS_PORT` number in the URL for the app instance, i.e., replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.
> If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

1. Set up the sample application to start a pipeline. A named pipeline (`pallet_defect_detection_mlops` or `pcb_anomaly_detection_mlops`) is already provided in the `pipeline-server-config.json` for this demonstration with the Pallet Defect Detection or PCB Anomaly Detection sample app.

   > **Note:** Ensure that the pipeline inference element, such as gvadetect/gvaclassify/gvainference, does not have a `model-instance-id` property set. If set, this would not allow the new model to be run with the same value provided in the `model-instance-id`.

   Navigate to the `[WORKDIR]/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision` directory and set up the app.

   <!--hide_directive ::::{tab-set} hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
   <!--hide_directive :sync: pallet-detect hide_directive-->

   ```sh
   cp .env_pallet-defect-detection .env
   ```

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   ```sh
   cp .env_pcb-anomaly-detection .env
   ```

   <!--hide_directive
   :::
   ::::
   hide_directive-->

2. Update the following variables in the `.env` file.

   ```sh
   HOST_IP= # <IP Address of the host machine>

   MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
   MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

   MTX_WEBRTCICESERVERS2_0_USERNAME=  # Webrtc-mediamtx username. e.g intel1234
   MTX_WEBRTCICESERVERS2_0_PASSWORD=  # Webrtc-mediamtx password. e.g intel1234
   ```

3. Run the setup script using the following command.

   ```sh
   ./setup.sh
   ```

4. Bring up the containers.

   ```sh
   docker compose up -d
   ```

5. Check to see if the pipeline (`pallet_defect_detection_mlops` or `pcb_anomaly_detection_mlops`) is present among the list of loaded pipelines.

   ```sh
   ./sample_list.sh
   ```

6. Modify the payload in the appropriate `payload.json` to launch an instance for the MLOps pipeline.

   <!--hide_directive ::::{tab-set} hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
   <!--hide_directive :sync: pallet-detect hide_directive-->

   `apps/pallet-defect-detection/payload.json`

   ```json
   [
     {
       "pipeline": "pallet_defect_detection_mlops",
       "payload": {
         "source": {
           "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
           "type": "uri"
         },
         "destination": {
           "frame": {
             "type": "webrtc",
             "peer-id": "pdd"
           }
         },
         "parameters": {
           "detection-properties": {
             "model": "/home/pipeline-server/resources/models/pallet-defect-detection/deployment/Detection/model/model.xml",
             "device": "CPU"
           }
         }
       }
     }
   ]
   ```

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   `apps/pcb-anomaly-detection/payload.json`

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

   <!--hide_directive
   :::
   ::::
   hide_directive-->

7. Start the pipeline with the selected payload.

   <!--hide_directive ::::{tab-set} hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
   <!--hide_directive :sync: pallet-detect hide_directive-->

   ```sh
   ./sample_start.sh -p pallet_defect_detection_mlops
   ```

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   ```sh
   ./sample_start.sh -p pcb_anomaly_detection_mlops
   ```

   <!--hide_directive
   :::
   ::::
   hide_directive-->

   Note the instance-id of the pipeline launched.

8. Verify the pipeline is running. You can View the WebRTC streaming on `https://<HOST_IP>/mediamtx/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

   <!--hide_directive ::::{tab-set} hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
   <!--hide_directive :sync: pallet-detect hide_directive-->

   ![WebRTC streaming](../_assets/pdd-webrtc-streaming.png)

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   ![WebRTC streaming](../_assets/pcb-webrtc-streaming.png)

   <!--hide_directive
   :::
   ::::
   hide_directive-->

   #### Downloading a Model with Model Download

   At this point, restart the pipeline with a newer model. The new model can be a retrained version of the existing model or a different model altogether. We use the [Model Download](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/index.html) microservice to help download the model. It supports downloading public models as well as Geti™ models from a running Geti™ server. To learn more about the microservice, see how to [get started with it](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/get-started.html).

   For this demonstration, the guide assumes that:
   - the appropriate model (Pallet Defect Detection or PCB Anomaly Detection) has been retrained and is available for download from a Geti™ server using the Model Download service.
   - the downloaded location is accessible by the DL Streamer Pipeline Server. In our example, it is `/tmp/models`.
   - the `/tmp` directory is already accessible by the sample application. If not, add it to the `volumes` section of `dlstreamer-pipeline-server` service in the docker-compose file.

9. Stop the running pipeline by using the pipeline instance-id noted in step 7.

   ```sh
   curl -k --location -X DELETE https://<HOST_IP>/api/pipelines/{instance_id}
   ```

10. Modify the `payload.json` to use the new model and start a new pipeline with it. Notice the model path in the payload has changed to the new model.

    <!--hide_directive ::::{tab-set} hide_directive-->
    <!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
    <!--hide_directive :sync: pallet-detect hide_directive-->

    `apps/pallet-defect-detection/payload.json`

    ```json
    [
      {
        "pipeline": "pallet_defect_detection_mlops",
        "payload": {
          "source": {
            "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
            "type": "uri"
          },
          "destination": {
            "frame": {
              "type": "webrtc",
              "peer-id": "pdd"
            }
          },
          "parameters": {
            "detection-properties": {
              "model": "/tmp/models/pallet-defect-detection/deployment/Detection/model/model.xml",
              "device": "CPU"
            }
          }
        }
      }
    ]
    ```

    Run the following.

    ```bash
    ./sample_start.sh -p pallet_defect_detection_mlops
    ```

    <!--hide_directive ::: hide_directive-->
    <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
    <!--hide_directive :sync: pcb-detect hide_directive-->

    `apps/pcb-anomaly-detection/payload.json`

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
                      "model": "/tmp/models/pcb-anomaly-detection/deployment/Anomaly classification/model/model.xml",
                      "device": "CPU"
                   }
                }
          }
       }
    ]
    ```

    Run the following.

    ```bash
    ./sample_start.sh -p pcb_anomaly_detection_mlops
    ```

    <!--hide_directive
    :::
    ::::
    hide_directive-->

11. View the WebRTC streaming on `https://<HOST_IP>/mediamtx/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

## Additional resources

### Downloading models from Geti™ Server

To learn how to download models from a running Geti™ server, see [here](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/get-started.html#sample-usage-with-curl-command).

> **Note:** The downloaded model(s) must be accessible to the DL Streamer Pipeline Server container. If necessary, add it to volumes section of `dlstreamer-pipeline-server` in compose file, and restart the DLSPS service.

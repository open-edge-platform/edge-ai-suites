# Enable MLOps

Applications for industrial edge insights vision can also be used to demonstrate MLOps workflow using Model Download microservice.
With this feature, during runtime, you can download a new model using the microservice and restart the pipeline with the new model.

>To simplify this demonstration, we assume that models have already been downloaded to an accessible location (`/tmp/models`) using the Model Download from a running Geti server before restarting the pipeline.

## Contents

### Pre-requisites
>NOTE: Model Download service has already downloaded the model to be updated to `/tmp/models`


### Steps
1. Set up the sample application to start a pipeline. A pipeline named `weld_porosity_classification_mlops` is already provided in the `pipeline-server-config.json` for this demonstration with the Weld Porosity classification sample app.

   > **Note:** Ensure that the pipeline inference element such as gvadetect/gvaclassify/gvainference should not have a `model-instance-id` property set. If set, this would not allow the new model to be run with the same value provided in the model-instance-id.

   Navigate to the `[WORKDIR]/edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-vision` directory and set up the app.

   ```sh
   cp .env_weld-porosity .env
   ```

2. Update the following variables in `.env` file

   ``` sh
   HOST_IP= # <IP Adress of the host machine>

   MINIO_ACCESS_KEY=   # MinIO service & client access key e.g. intel1234
   MINIO_SECRET_KEY=   # MinIO service & client secret key e.g. intel1234

   MTX_WEBRTCICESERVERS2_0_USERNAME=  # Webrtc-mediamtx username. e.g intel1234
   MTX_WEBRTCICESERVERS2_0_PASSWORD=  # Webrtc-mediamtx password. e.g intel1234
   ```

3. Run the setup script using the following command.

   ```sh
   ./setup.sh
   ```

4. Bring up the containers

   ```sh
   docker compose up -d
   ```

5. Check to see if the pipeline is loaded is present which in our case is `weld_porosity_classification_mlops`.

   ```sh
   ./sample_list.sh
   ```

6. Modify the payload in `apps/weld-porosity/payload.json` to launch an instance for the mlops pipeline.

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

7. Start the pipeline with the above payload.

   ```sh
   ./sample_start.sh -p weld_porosity_classification_mlops
   ```

8. Verify the pipeline is running. You can View the WebRTC streaming on `http://<HOST_IP>:<mediamtx-port>/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

   ![WebRTC streaming](../_assets/webrtc-streaming.png)

    ### Downloading model with Model Download 

    At this point, user would like to restart the pipeline with a newer model. The new model can bea retrained version of the existing model or a different model altogether. We use [Model Download](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/Overview.md) microservice to help download the model. It supports downloading  public models as well as geti models from a running Geti server. To learn more about it, see [here](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started.md).

    For our demonstration, we will assume the weld porosity model has been retrained and is available for downloaded from a Geti server using the Model Download service. Also, the downloaded location is accessible by the dlstreamer pipeline server. In our example, it is `/tmp/tmp-models`. The `/tmp`dir is already accessible by the sample application. If not, please add it to the `volumes` section of `dlstreamer-pipeline-server service in docker-compose file.

9. Stop the running pipeline by using the pipeline instance "id".

   ```sh
   curl -k --location -X DELETE https://<HOST_IP>/api/pipelines/{instance_id}
   ```
10. Start a new pipeline with this new model. Before that modify the payload.json to use this new model in `apps/weld-porosity/payload.json`. Notice the model path in the payload has changed to the new model.
    
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
                       "model": "/tmp/models/weld-porosity/deployment/Classification/model/model.xml",
                       "device": "CPU"
                   }
               }
           }
       }
   ]
   ```

11. View the WebRTC streaming on `http://<HOST_IP>:<mediamtx-port>/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

## Additional resources
### Setting up Model Download
To learn how to setup Model Download, see [here](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started.md#quick-start)

### Downloading models from Geti Server
To learn how to download models from a running Geti server, see [here](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started.md#sample-usage-with-curl-command)


> **Note:**: The downloaded model(s) must be accessible to the DLStreamer pipeline server container. If not, please add it to volumes section of dltreamer-pipeline-server in compose file, and restart the DLSPS service.

# Enable MLOps

Applications for industrial edge insights vision can also be used to demonstrate MLOps workflow using Model Download microservice.
With this feature, during runtime, you can download a new model using the microservice and restart the pipeline with the new model.

> **Note:** To simplify this demonstration, we assume that models have already been downloaded to an accessible location (`/tmp/models`) using the Model Download from a running Geti™ server before restarting the pipeline.

## Contents

### Prerequisites

We assume that Model Download service has already downloaded the model to be updated to `/tmp/models`.
To learn how to setup Model Download, see [here](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/model-download/get-started.html#start-with-setup-script)

If not available, you can simulate this by downloading the sample model from the [`edge-ai-resources` repository](https://github.com/open-edge-platform/edge-ai-resources/blob/main/models/FP16/weld_porosity_classification.zip). Once downloaded, extract to `/tmp/models` directory.

### Steps

> **Note:** If you are running multiple instances of the app, ensure to provide `NGINX_HTTPS_PORT` number in the url for the app instance, i.e., replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.
> If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

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

6. Modify the payload in `apps/weld-porosity/payload.json` to launch an instance for the MLOps pipeline.

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

8. Verify the pipeline is running. You can View the WebRTC streaming on `https://<HOST_IP>/mediamtx/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

   ![WebRTC streaming](../_assets/webrtc-streaming.png)

#### Downloading model with Model Download

At this point, restart the pipeline with a newer model. The new model can be a retrained version of the existing model or a different model altogether. We use the [Model Download](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/model-download/index.html) microservice to help download the model. It supports downloading public models as well as Geti™ models from a running Geti™ server. To learn more about it, see [here](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/model-download/get-started.html).

For our demonstration, we will assume that:

- Weld Porosity Model has been retrained and is available for downloaded from a Geti™ server using the Model Download service.
- the downloaded location is accessible by the dlstreamer pipeline server. In our example, it is `/tmp/models`
- the `/tmp`dir is already accessible by the sample application. If not, please add it to the `volumes` section of `dlstreamer-pipeline-server` service in docker-compose file.

1. Stop the running pipeline by using the pipeline instance "id".

   ```sh
   curl -k --location -X DELETE https://<HOST_IP>/api/pipelines/{instance_id}
   ```

2. Start a new pipeline with this new model. Before that modify the `payload.json` to use this new model in `apps/weld-porosity/payload.json`. Notice the model path in the payload has changed to the new model.

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

   Run the following:

   ```bash
   ./sample_start.sh -p weld_porosity_classification_mlops
   ```

3. View the WebRTC streaming on `https://<HOST_IP>/mediamtx/<peer-str-id>` by replacing `<peer-str-id>` with the value used in the original cURL command to start the pipeline.

## Additional resources

### Downloading models from Geti Server

To learn how to download models from a running Geti™ server, see [here](https://docs.openedgeplatform.intel.com/2026.1/edge-ai-libraries/model-download/get-started.html#sample-usage-with-curl-command).

> **Note:** The downloaded model(s) must be accessible to the DL Streamer pipeline server container. If necessary, add it to volumes section of `dlstreamer-pipeline-server` in compose file, and restart the DL Streamer Pipeline Server service.

# Use Your AI Model and Video

You can bring your own model and run this sample application the same way as how we bring in any of the sample app model. You can also bring your own video file source. Please see below for details:

>**Important** If you have previously run the setup for the instances using `setup.sh`, default sample model and video are downloaded under `resource/<app_name>` in your repo directory. You can manually add the model and video of your choice and keep it in this structure.

For compose based deployment, the entire resources directory is volume mounted and made available to pipeline server. However for helm, you need to manually copy those to the container.

## For docker compose based deployment

1. The SAMPLE_APP model is placed as below in the repository under  `resources/{SAMPLE_APP}/models`. You can also find the input video file source for inference under `videos` in the same directory level.

   ```text
   - resources/
     - SAMPLE_APP/
       - models/
           - SAMPLE_APP/
               - deployment/
                   - Detection/
                       - model/
                           - model.bin
                           - model.xml
       - videos/
           - warehouse.avi
   ```

   > **Note**
   > You can organize the directory structure for models for different use cases.

2. The `resources` folder containing both the model and video file is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` (present in the repository) file as follows.

   ```text
   volumes:
   - ./resources/${SAMPLE_APP}/:/home/pipeline-server/resources/
   ```

   > The value of `${SAMPLE_APP}` is fetched from the `.env` file specifying the particular sample app you are running.

3. Since this is a detection model, ensure to use gvadetect in the pipeline. For example: See the `pallet_defect_detection` pipeline in `pipeline-server-config.json` (present in the repository) where gvadetect is used.

4. The `pipeline-server-config.json` is volume mounted into DL Streamer Pipeline Server in `docker-compose.yml` as follows:

   ```text
   volumes:
   - ./{APP_DIR}/configs/pipeline-server-config.json:/home/pipeline-server/config.json
   ```

5. Provide the model path and video file path in the REST/curl command for starting an inferencing workload. Example:

   ```sh
       curl -k https://<HOST_IP>:<NGINX_HTTPS_PORT>/api/pipelines/user_defined_pipelines/pallet_defect_detection -X POST -H 'Content-Type: application/json' -d '{
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

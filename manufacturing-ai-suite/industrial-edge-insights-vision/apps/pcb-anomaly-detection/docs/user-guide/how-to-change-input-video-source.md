# How to change the Input Video Source

Typically, a pipeline is started with a cURL request with JSON payload containing source, destination and parameters. For example, the following cURL request start an AI pipeline on a file inferencing on PCB anomaly detection model.

         curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/<pipeline_name> -X POST -H 'Content-Type: application/json' -d '{
            "source": {
               "uri": "file:///home/pipeline-server/resources/videos/anomalib_pcb_test.avi",
               "type": "uri"
            },
            "parameters": {
               "classification-properties": {
                  "model": "/home/pipeline-server/resources/models/pcb-anomaly-detection/deployment/Anomaly classification/model/model.xml",
                  "device": "CPU"
               }
            }
         }'

To change the input video source for the pipeline, refer to the following table:

| Video Source | Source Section of the cURL Request                          | Remark                          |
|--------------|-------------------------------------------------------------|---------------------------------|
| File         | <pre><code>"source": {<br>  "uri": "file://path",<br>  "type": "uri"<br>} </code></pre>       |    |
| RTSP         | <pre><code>"source": {<br>  "uri": "rtsp://url",<br>  "type": "uri"<br>}</code></pre>        | In the **values.yaml** file inside the helm folder in the repository for helm based deployments, or in the **.env** file at the root of the repository for docker compose based deployment, update **RTSP_CAMERA_IP** to the IP of the machine where the RTSP stream is coming from:<br> RTSP_CAMERA_IP=<IP_where_RTSP_stream_is_originating_from><br><br> |
| Web Camera   | <pre><code>"source": {<br>  "device": "/dev/video0",<br>  "type": "webcam"<br>}</code></pre> | The pipeline in **pipeline-server-config.json** in the helm chart needs to be changed as follows: <pre><code>"pipeline": "v4l2src device=/dev/video0 name=source ! video/x-raw,format=YUY2 ! videoconvert ! video/x-raw,format=RGB ! gvaclassify name=classification model-instance-id=inst0 ! queue ! gvawatermark ! gvafpscounter ! appsink name=destination",</code></pre>`
   |
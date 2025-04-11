# How to change the Input Video Source

You start a Weld Porosity Detection pipeline with the following Client URL (cURL) command. The following example is the command to start an AI pipeline.

         curl http://<HOST_IP>:8080/pipelines/user_defined_pipelines/weld_porosity_classification_mlops -X POST -H 'Content-Type: application/json' -d '{
            "source": {
               "uri": "file:///home/pipeline-server/resources/videos/welding.avi",
               "type": "uri"
            },
            "parameters": {
               "classification-properties": {
                  "model": "/home/pipeline-server/resources/models/weld_porosity/weld_porosity_classification/deployment/Classification/model/model.xml",
                  "device": "CPU"
               }
            }
         }'

To change the input video source for the pipeline, refer to the following table:

| Video Source | Source Section of the cURL Request                          | Remark                          |
|--------------|-------------------------------------------------------------|---------------------------------|
| File         | <pre><code>"source": {<br>  "uri": "file://path",<br>  "type": "uri"<br>} </code></pre>       |    |
| RTSP         | <pre><code>"source": {<br>  "uri": "rtsp://url",<br>  "type": "uri"<br>}</code></pre>        | In the **values.yaml** file inside the helm folder in the repository for helm based deployments, or in the **.env** file at the root of the repository for docker compose based deployment, update **RTSP_CAMERA_IP** to the IP of the machine where the RTSP stream is coming from:<br> RTSP_CAMERA_IP=<IP_where_RTSP_stream_is_originating_from><br><br> |
| Web Camera   | <pre><code>"source": {<br>  "device": "/dev/video0",<br>  "type": "webcam"<br>}</code></pre> | The pipeline in **config.json** in the helm chart needs to be changed as follows: <pre><code>"pipeline": "v4l2src device=/dev/video0 name=source ! video/x-raw,format=YUY2 ! videoconvert ! video/x-raw,format=RGB ! gvaclassify name=classification model-instance-id=inst0 ! queue ! gvawatermark ! gvafpscounter ! appsink name=destination",</code></pre>`
   |


# Change Video Source In Vision AI Detection Apps

Typically, a pipeline is started with a cURL request with JSON payload containing source, destination and parameters. For example, the following cURL request start an AI pipeline on a file inferencing on either the pallet defect detection model or the PCB anomaly detection model.

> **Note:** If you are running multiple instances of the application, ensure to provide `NGINX_HTTPS_PORT` number in the URL for the app instance, i.e., replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.
> If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
<!--hide_directive :sync: pallet-detect hide_directive-->

```bash
curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/<pipeline_name> -X POST -H 'Content-Type: application/json' -d '{
   "source": {
      "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
      "type": "uri"
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

```bash
curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/<pipeline_name> -X POST -H 'Content-Type: application/json' -d '{
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
```

<!--hide_directive
:::
::::
hide_directive-->

To change the input video source for the pipeline, refer to the following table:

<!--hide_directive ::::{tab-set} hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
<!--hide_directive :sync: pallet-detect hide_directive-->

| Video Source | Source Section of the cURL Request                          | Remark                          |
|--------------|-------------------------------------------------------------|---------------------------------|
| File         | <pre><code>"source": {<br>  "uri": "file://path",<br>  "type": "uri"<br>} </code></pre>       |    |
| RTSP         | <pre><code>"source": {<br>  "uri": "rtsp://url",<br>  "type": "uri"<br>}</code></pre>        | In the **values.yaml** file inside the helm folder in the repository for helm based deployments, or in the **.env** file at the root of the repository for Docker Compose based deployment, update **RTSP_CAMERA_IP** to the IP of the machine where the RTSP stream is coming from:<br> RTSP_CAMERA_IP=<IP_where_RTSP_stream_is_originating_from><br><br> |
| Web Camera   | <pre><code>"source": {<br>  "device": "/dev/video0",<br>  "type": "webcam"<br>}</code></pre> | The pipeline in **pipeline-server-config.json** in the helm chart needs to be changed as follows: <pre><code>"pipeline": "v4l2src device=/dev/video0 name=source ! video/x-raw,format=YUY2 ! videoconvert ! video/x-raw,format=RGB ! gvadetect name=detection model-instance-id=inst0 ! queue ! gvawatermark ! gvafpscounter ! appsink name=destination",</code></pre>`
   |

<!--hide_directive ::: hide_directive-->
<!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
<!--hide_directive :sync: pcb-detect hide_directive-->

| Video Source | Source Section of the cURL Request                          | Remark                          |
|--------------|-------------------------------------------------------------|---------------------------------|
| File         | <pre><code>"source": {<br>  "uri": "file://path",<br>  "type": "uri"<br>} </code></pre>       |    |
| RTSP         | <pre><code>"source": {<br>  "uri": "rtsp://url",<br>  "type": "uri"<br>}</code></pre>        | In the **values.yaml** file inside the helm folder in the repository for helm based deployments, or in the **.env** file at the root of the repository for docker compose based deployment, update **RTSP_CAMERA_IP** to the IP of the machine where the RTSP stream is coming from:<br> RTSP_CAMERA_IP=<IP_where_RTSP_stream_is_originating_from><br><br> |
| Web Camera   | <pre><code>"source": {<br>  "device": "/dev/video0",<br>  "type": "webcam"<br>}</code></pre> | The pipeline in **pipeline-server-config.json** in the helm chart needs to be changed as follows: <pre><code>"pipeline": "v4l2src device=/dev/video0 name=source ! video/x-raw,format=YUY2 ! videoconvert ! video/x-raw,format=RGB ! gvaclassify name=classification model-instance-id=inst0 ! queue ! gvawatermark ! gvafpscounter ! appsink name=destination",</code></pre>`
   |

<!--hide_directive
:::
::::
hide_directive-->

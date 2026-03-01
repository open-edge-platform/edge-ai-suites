# Manage Pipeline

This section describes how to create custom AI pipelines for the sample application and the commands to manage these pipelines.

## Create Pipelines

The AI pipelines are defined by the `pipeline-server-config.json` file present under the configs subdirectory of a particular application directory (for docker compose deployment) and similary inside the helm directory (for helm based deployment).
The following is an example of the weld porosity classification pipeline, which is included in the `pipeline-server-config.json` file.

```json
"config": {
    "pipelines": [
        {
            "name": "weld_porosity_classification",
            "source": "gstreamer",
            "queue_maxsize": 50,
            "pipeline": "{auto_source} name=source ! decodebin3 ! gvaclassify inference-region=full-frame device=CPU model-instance-id=inst0 name=classification ! queue ! gvametaconvert add-empty-results=true name=metaconvert ! queue ! gvafpscounter ! appsink name=destination",
            "parameters": {
                "type": "object",
                "properties": {
                    "classification-properties": {
                        "element": {
                            "name": "classification",
                            "format": "element-properties"
                        }
                    }
                }
            },
            "auto_start": false
        }
    ]
}
```

Customize the pipeline according to your needs. For details, see the following DL Streamer Pipeline Server documentation:

- [Launch configurable pipelines](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-libraries/dlstreamer-pipeline-server/how-to-guides/launch-configurable-pipelines.html)
- [Autostart pipelines](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-libraries/dlstreamer-pipeline-server/how-to-guides/autostart-pipelines.html)

## Start the Pipeline

>Note: If you're running multiple instances of app, ensure to provide `NGINX_HTTPS_PORT` number in the url for the app instance i.e. replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`
>If you're running a single instance and using an NGINX_HTTPS_PORT other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

Follow this procedure to start the pipeline.

1. In the `pipeline-server-config.json` file, identify the name of the pipeline you want to start.

   The name of the pipeline is defined by the **name** parameter.

   ```text
   "pipelines": [
       {
             "name": "pipeline_name",
             "source": "....",
             "pipeline": "...."
             "..."
       }
    ]
   ```

2. You use a Client URL (cURL) command to start the pipeline.

   In this example, a pipeline included in this sample application is `weld_porosity_classification`. Start this pipeline with the following cURL command.

   ```sh
   curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/weld_porosity_classification -X POST -H 'Content-Type: application/json' -d '{
       "source": {
           "uri": "file:///home/pipeline-server/resources/videos/welding.avi",
           "type": "uri"
       },
       "parameters": {
           "classification-properties": {
               "model": "/home/pipeline-server/resources/models/weld-porosity/deployment/Classification/model/model.xml",
               "device": "CPU"
           }
       }
   }'
   ```

3. Take note of the instance ID (without quotes).

   Each pipeline has its **instance ID**. You will need the instance ID to stop the pipeline later.

## Get Statistics of the Running Pipelines

Request the pipeline statistics with this cURL command.

Replace `HOST_IP` with the IP address of your system.

```sh
curl -k --location -X GET https://<HOST_IP>/api/pipelines/status
```

## Stop the Pipeline

Stop the pipeline with the following cURL command.

Replace `HOST_IP` with the IP address of your system and `instance_id` with the instance ID (without quotes) of the running pipeline.

```sh
curl -k --location -X DELETE https://<HOST_IP>/api/pipelines/{instance_id}
```

> **Note:**
> The instance ID is shown in the Terminal when the
> [pipeline was started](#start-the-pipeline) or when
>[pipeline statistics were requested](#get-statistics-of-the-running-pipelines).

## Additional Usage
### Frame Batching
You can process multiple streams together when batching is enabled and the same model instance (that is, the same model-instance-id) is used across pipeline instances.

To enable this, configure the pipeline’s inference element to support batching and assign a shared model instance ID. For example:
```sh
... ! gvadetect model=/path/to/model.xml model-instance-id=inst0 batch-size=4 ! ...
```

In this configuration, if 4 instances (or any multiple of 4) of the pipeline are launched (for example, using the curl commands described in the previous section), their frames will be grouped into batches of four and processed in a single inference call.

For more details about batching in DL Streamer, refer to [this documentation](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-libraries/dlstreamer/dev_guide/performance_guide.html#multi-stream-pipelines-with-single-ai-stage).

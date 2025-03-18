# Deploy Pipeline with Intel® Geti™ Platform Model

Follow this procedure to configure a pallet defect detection pipeline that uses a model trained with Intel® Geti™ platform.

> **Note**  
> Learn more about training your own models for object detection, classification, segmentation, and anomaly with [Intel® Geti™ platform](https://geti.intel.com/).

1. Copy the model created with Intel® Geti™ platform into the following directory in the reference implementation.

         resources/models/geti/<model_use_case>/deployment/

   > **Note**  
   > You can organize the directory structure for models for different use cases.


2. If the reference implementation is running, restart the reference implementation before you proceed to the next step.

         helm uninstall pdd-deploy -n apps
         helm install pdd-deploy . -n apps  --create-namespace

3. Start the pipeline with the following cURL command. Ensure to give the correct path to the model as seen below. This example starts an AI pipeline.

         curl http://localhost:30107/pipelines/user_defined_pipelines/pallet_defect_detection_mlops -X POST -H 'Content-Type: application/json' -d '{
            "source": {
               "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
               "type": "uri"
            },
            "parameters": {
               "detection-properties": {
                  "model": "/home/pipeline-server/resources/models/geti/pallet_defect_detection/deployment/Detection/model/model.xml",
                  "device": "CPU"
               }
            }
         }'
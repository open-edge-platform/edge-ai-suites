# Use Your AI Model and Video

You can use your own model and run it with the sample applications provided.
You can also bring your own video file source. This article will show you how to do it.

> **Important:** If you have previously run the setup for the sample app using `setup.sh`,
> the default sample model and video are downloaded under `resource/<app_name>` in your repo.
> You can manually add your files next to them.
>
> For compose-based deployment, the entire resources directory is a volume mounted and made
> available to pipeline server. However for helm, you need to manually copy those to the
> container.

## Docker compose deployment

1. The model and the input video file are placed in the `resources/<app name>/` folder, under
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

   <!--hide_directive :::{tab-item} hide_directive-->**PCB Anomaly Detection**
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

   > **Note**
   > You can customize the directory structure for different resources and use cases.
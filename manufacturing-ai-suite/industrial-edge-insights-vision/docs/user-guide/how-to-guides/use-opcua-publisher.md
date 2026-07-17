# Use OPC UA Publisher in Vision AI Detection Apps

Follow this procedure to test the DL Streamer Pipeline Server OPC UA publishing using the docker.

1. Configure and start the OPC UA Server

   If you already have a functioning OPC UA server, you can skip this step. Otherwise, this section provides instructions for using the OPC UA server provided by [Unified Automation](https://www.unified-automation.com).

   1. **Download and Install the OPC UA Server**
      Download the [OPC UA C++ Demo Server (Windows)](https://www.unified-automation.com/downloads/opc-ua-servers.html) and install it on your Windows machine. Please note that this server is available only for Windows.
   2. **Starting the OPC UA Server**

      - Open the Start menu on your Windows machine and search for **UaCPPServer**.
      - Launch the application to start the server.

2. Update the following variables related to the OPC UA server in `.env`.

   ```sh
   OPCUA_SERVER_IP= # <IP-Address of the OPC UA server>
   OPCUA_SERVER_PORT= # example: 48010
   OPCUA_SERVER_USERNAME= # example: root
   OPCUA_SERVER_PASSWORD= # example: secret
   ```

3. Update the OPC UA `variable` to appropriate value for the pipeline in `pipeline-server-config.json`.

   <!--hide_directive ::::{tab-set} hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
   <!--hide_directive :sync: pallet-detect hide_directive-->

   Use pipeline `pallet_defect_detection_opcua` in `apps/pallet-defect-detection/configs/pipeline-server-config.json`.

   ```sh
       "opcua_publisher": {
           "publish_frame" : true,
           "variable" : "ns=3;s=Demo.Static.Scalar.String"
       },
   ```

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   Use pipeline `pcb_anomaly_detection_opcua` in `apps/pcb-anomaly-detection/configs/pipeline-server-config.json`.

   ```sh
       "opcua_publisher": {
           "publish_frame" : true,
           "variable" : "ns=3;s=Demo.Static.Scalar.String"
       },
   ```

   <!--hide_directive
   :::
   ::::
   hide_directive-->

4. To use an AI model of your own please follow the steps as mentioned in this [document](./use-your-ai-model-and-video.md)

5. Setup the application to use the Docker based deployment following this [document](../get-started.md#set-up-the-application).

6. Start the pipeline using the following cURL command. Update the `HOST_IP` and ensure the correct path to the model is provided as shown below. This example starts an AI pipeline.

   > **Note:** If you are running multiple instances of the application, ensure to provide `NGINX_HTTPS_PORT` number in the URL for the app instance, i.e., replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`
   > If you are running a single instance and using an `NGINX_HTTPS_PORT` other than the default 443, replace `<HOST_IP>` with `<HOST_IP>:<NGINX_HTTPS_PORT>`.

   <!--hide_directive ::::{tab-set} hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **Pallet Defect Detection**
   <!--hide_directive :sync: pallet-detect hide_directive-->

   ```sh
   curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/pallet_defect_detection_opcua -X POST -H 'Content-Type: application/json' -d '{
       "source": {
           "uri": "file:///home/pipeline-server/resources/videos/warehouse.avi",
           "type": "uri"
       },
       "destination": {
           "metadata": [
               {
                   "type": "opcua",
                   "publish_frame": true,
                   "variable": "ns=3;s=Demo.Static.Scalar.String"
               }
           ],
           "frame": {
               "type": "webrtc",
               "peer-id": "pddopcua",
               "overlay": false
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

   <!--hide_directive ::: hide_directive-->
   <!--hide_directive :::{tab-item} hide_directive--> **PCB Anomaly Detection**
   <!--hide_directive :sync: pcb-detect hide_directive-->

   ```sh
   curl -k https://<HOST_IP>/api/pipelines/user_defined_pipelines/pcb_anomaly_detection_opcua -X POST -H 'Content-Type: application/json' -d '{
       "source": {
           "uri": "file:///home/pipeline-server/resources/videos/anomalib_pcb_test.avi",
           "type": "uri"
       },
       "destination": {
           "metadata": [
               {
                   "type": "opcua",
                   "publish_frame": true,
                   "variable": "ns=3;s=Demo.Static.Scalar.String"
               }
           ],
           "frame": {
               "type": "webrtc",
               "peer-id": "anomaly_opcua",
               "overlay": false
           }
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

7. Run the following sample OPC UA subscriber on a different machine by updating the `<IP-Address of OPCUA Server>` to read the meta-data written to the server variable from DL Streamer Pipeline Server.

   > **Note:** Install `asyncua` before running the script below (if not already installed):
   >
   > ```sh
   > pip3 install asyncua
   > ```

   ```python
   import asyncio
   from asyncua import Client, Node
   class SubscriptionHandler:
      def datachange_notification(self, node: Node, val, data):
         print(val)
   async def main():
      client = Client(url="opc.tcp://<IP-Address of OPCUA Server>:48010")
      client.set_user("root")
      client.set_password("secret")
      async with client:
         handler = SubscriptionHandler()
         subscription = await client.create_subscription(50, handler)
         myvarnode = client.get_node("ns=3;s=Demo.Static.Scalar.String")
         await subscription.subscribe_data_change(myvarnode)
         await asyncio.sleep(100)
         await subscription.delete()
         await asyncio.sleep(1)
   if __name__ == "__main__":
      asyncio.run(main())
   ```

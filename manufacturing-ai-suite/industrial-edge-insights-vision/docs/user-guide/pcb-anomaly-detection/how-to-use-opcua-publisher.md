# How to use OPC UA publisher

Follow this procedure to test the DL Streamer Pipeline Server OPC UA publishing using the docker.

1. Configure and start the OPC UA Server
   If you already have a functioning OPC UA server, you can skip this step. Otherwise, this section provides instructions for using the OPC UA server provided by [Unified Automation](https://www.unified-automation.com).
   1. **Download and Install the OPC UA Server**
      Download the [OPC UA C++ Demo Server (Windows)](https://www.unified-automation.com/downloads/opc-ua-servers.html) and install it on your Windows machine. Please note that this server is available only for Windows.
   2. **Starting the OPC UA Server**
      * Open the Start menu on your Windows machine and search for **UaCPPServer**.
      * Launch the application to start the server.

2. Update the following variables related to the OPC UA server in `.env`.
    ``` sh
    OPCUA_SERVER_IP= # <IP-Adress of the OPCUA server>
    OPCUA_SERVER_PORT= # example: 48010
    OPCUA_SERVER_USERNAME= # example: root
    OPCUA_SERVER_PASSWORD= # example: secret
    ```

3. Update the OPC UA `variable` to appropriate value for the pipeline `pcb_anomaly_detection_opcua` in `apps/pcb-anomaly-detection/configs/pipeline-server-config.json`.

    ```shell
        "opcua_publisher": {
            "publish_frame" : true,
            "variable" : "ns=3;s=Demo.Static.Scalar.String"
        },
    ```

4. To use an AI model of your own please follow the steps as mentioned in this [document](./how-to-use-an-ai-model-and-video-file-of-your-own.md)

5. Setup the application to use the docker based deployment following this [document](./get-started.md#setup-the-application).

6. Start the pipeline using the following cURL command. Update the `HOST_IP` and ensure the correct path to the model is provided as shown below. This example starts an AI pipeline.

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

7. Run the following sample OPC UA subscriber on the different machine by updating the `<IP-Address of OPCUA Server>` to read the meta-data written to server variable from DL Streamer Pipeline Server.
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
   Install asyncua before running the above script (if not already installed):
   ```sh
   pip3 install asyncua
   ```

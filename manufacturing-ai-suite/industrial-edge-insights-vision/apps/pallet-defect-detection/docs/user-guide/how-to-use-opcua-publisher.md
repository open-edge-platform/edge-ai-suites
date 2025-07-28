# How to use OPC UA publisher

Follow this procedure to test the DL Streamer Pipeline Server OPC UA publishing using the docker or helm.

1. Configure and start the OPC UA Server
   If you already have a functioning OPC UA server, you can skip this step. Otherwise, this section provides instructions for using the OPC UA server provided by [Unified Automation](https://www.unified-automation.com).
   1. **Download and Install the OPC UA Server**
      Download the [OPC UA C++ Demo Server (Windows)](https://www.unified-automation.com/downloads/opc-ua-servers.html) and install it on your Windows machine. Please note that this server is available only for Windows.
   2. **Starting the OPC UA Server**
      * Open the Start menu on your Windows machine and search for **UaCPPServer**.
      * Launch the application to start the server.

2. Update the following variables related to the OPC UA server in `.env` for docker or `helm/values.yml` for helm.
    ``` sh
    OPCUA_SERVER_IP= # <IP-Adress of the OPCUA server>
    OPCUA_SERVER_PORT= # example: 48010
    OPCUA_SERVER_USERNAME= # example: root
    OPCUA_SERVER_PASSWORD= # example: secret
    ```

3. Update the OPC UA `variable` to appropriate value for the pipeline `pallet_defect_detection_opcua` in `configs/config.json` for docker or `helm/config.json` for helm.

    ```shell
        "opcua_publisher": {
            "publish_frame" : true,
            "variable" : "ns=3;s=Demo.Static.Scalar.String"
        },
    ```

4. Bring up the containers for docker or deploy helm chart.

5. Start the pipeline with the following cURL command. Ensure to give the correct path to the model as seen below. This example starts an AI pipeline.

   **Note: Update the port to `30107` for helm or `8080` if you are using docker environment**

   ```sh
    curl http://<HOST_IP>:<port>/pipelines/user_defined_pipelines/pallet_defect_detection_opcua -X POST -H 'Content-Type: application/json' -d '{
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

6. Run the following sample OPC UA subscriber on the different machine by updating the `<IP-Address of OPCUA Server>` to read the meta-data written to server variable from DL Streamer Pipeline Server.
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

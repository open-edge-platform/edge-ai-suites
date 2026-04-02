# Configure RTSP Camera

The camera must support **RTCP Sender Reports (SR)** to ensure proper timestamp synchronization and smooth video processing in the pipeline. The camera’s system time and time zone must also be synchronized with the edge device time and configured time zone to avoid timestamp drift and inconsistencies during stream processing.

## Configure RTSP Camera in the Multimodal App

1. **Obtain the RTSP URI**  
   Get the RTSP stream URL from your camera configuration software. You can validate the stream using **VLC Media Player** if needed.

2. **Update the pipeline configuration**  
   Edit `configs/dlstreamer-pipeline-server/config.json` and update the `pipeline` string:

   ```json
   "pipeline": "rtspsrc add-reference-timestamp-meta=true location=\"rtsp://<USERNAME>:<PASSWORD>@<RTSP_CAMERA_IP>:<PORT>/<FEED>\" latency=100 name=source ! rtph264depay ! h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR ! gvaclassify inference-region=full-frame name=classification ! gvawatermark ! gvametaconvert add-empty-results=true add-rtp-timestamp=true name=metaconvert ! queue ! gvafpscounter ! appsink name=destination"
   ```

3. **Set environment variables**  
   Update `.env` with the correct value for:
   ```
   RTSP_CAMERA_IP
   ```

4. **Redeploy the application**  
   Restart the services to apply the changes:
   ```bash
   make down && make up
   ```

For more on RTSP, see [RTSP protocol](https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol) and [DL Streamer Pipeline Server RTSP guide](https://docs.openedgeplatform.intel.com/2025.2/edge-ai-libraries/dlstreamer-pipeline-server/advanced-guide/detailed_usage/camera/rtsp.html#rtsp-cameras).
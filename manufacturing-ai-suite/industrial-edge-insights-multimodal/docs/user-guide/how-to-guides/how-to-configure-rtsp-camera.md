# Configure an RTSP Camera

To ensure proper timestamp synchronization and smooth video processing in the pipeline, the RTSP camera **must support RTCP Sender Reports (SR)**.

In addition, the camera’s system time should be synchronized with the edge device using a common time source such as **NTP**. The camera and edge device should also use the **same time zone** to avoid timestamp drift, log mismatches, and inconsistencies during stream processing.

---

## Check Whether the RTSP Camera Supports RTCP Sender Reports (SR)

### 1. Install required GStreamer packages (Ubuntu)

To inspect SR packets, you’ll use `gst-launch-1.0` with `rtspsrc` and RTP/RTCP components (via `rtpsession`). Install the required packages:

```bash
sudo apt update
sudo apt install -y \
  gstreamer1.0-tools \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav
```

### 2. Run the SR detection command

Update the RTSP URL in the pipeline and replace the placeholders with your camera details and run the below command

- `<USERNAME>`: camera username  
- `<PASSWORD>`: camera password  
- `<RTSP_CAMERA_IP>`: camera IP address  
- `<PORT>`: RTSP port (commonly `554`)  
- `<FEED>`: stream path (varies by camera model/vendor)

> Note: If you are behind a proxy network, make sure the camera IP is added to `no_proxy` or `NO_PROXY`

```bash
rm -f text.txt; timeout 15s sh -c "GST_DEBUG=rtpsession:7 \
gst-launch-1.0 -v rtspsrc protocols=tcp add-reference-timestamp-meta=true location=\"rtsp://<USERNAME>:<PASSWORD>@<RTSP_CAMERA_IP>:<PORT>/<FEED>\" latency=100 ! fakesink 2>&1 \
| grep 'GstRtpSession:rtpsession0: stats' > text.txt"; grep 'internal\\=\\(boolean\\)false' text.txt | grep -q 'have-sr\\=\\(boolean\\)true' && echo true
```

### 3. Interpret the output

- If you see `true` printed in the console, the camera supports **RTCP Sender Reports (SR)**.
- If nothing is printed, the camera likely does **not** provide SR packets (or they were not observed during the 15-second window).

> **Note**: If you suspect SR exists but wasn’t observed, increase the timeout window (e.g., `timeout 30s`) and re-run.

---

## Configure the RTSP Camera in the Multimodal App

### 1. Obtain the RTSP URI

Get the RTSP stream URL from the camera configuration software. Optionally validate the stream using **VLC Media Player**.

### 2. Update the pipeline configuration

Edit `configs/dlstreamer-pipeline-server/config.json` and update the `pipeline` string.

Update the RTSP URL in the pipeline and replace the placeholders with your camera details:

- `<USERNAME>`: camera username  
- `<PASSWORD>`: camera password  
- `<RTSP_CAMERA_IP>`: camera IP address / hostname  
- `<PORT>`: RTSP port (commonly `554`)  
- `<FEED>`: stream path (varies by camera model/vendor)

```json
"pipeline": "rtspsrc add-reference-timestamp-meta=true location=\"rtsp://<USERNAME>:<PASSWORD>@<RTSP_CAMERA_IP>:<PORT>/<FEED>\" latency=100 name=source ! rtph264depay ! h264parse ! decodebin ! videoconvert ! video/x-raw,format=BGR ! gvaclassify inference-region=full-frame name=classification ! gvawatermark displ-cfg=\"font-scale=1.5,thickness=3,color-idx=2,font-type=plain\" ! gvametaconvert add-empty-results=true add-rtp-timestamp=true name=metaconvert ! queue ! gvafpscounter ! appsink name=destination"
```

### 3. Update environment variables with RTSP Camera IP

Update `.env` with the RTSP Camera IP for:

```text
RTSP_CAMERA_IP
```

### 4. Redeploy the application

Restart the services to apply the changes:

```bash
make down && make up
```

---

## References

- [RTSP protocol](https://en.wikipedia.org/wiki/Real_Time_Streaming_Protocol)
- [DL Streamer Pipeline Server RTSP guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/dlstreamer-pipeline-server/advanced-guide/detailed_usage/camera/rtsp.html#rtsp-cameras)
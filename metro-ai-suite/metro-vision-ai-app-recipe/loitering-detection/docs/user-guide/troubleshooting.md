# Troubleshooting

This page provides troubleshooting steps, FAQs, and resources to help you resolve common
issues. If you encounter any problems with the application not addressed here, check the
[GitHub Issues](https://github.com/open-edge-platform/edge-ai-suites/issues) board. Feel free
to file new tickets there (after learning about the guidelines for
[Contributing](https://github.com/open-edge-platform/edge-ai-suites/blob/main/CONTRIBUTING.md)).

## Troubleshooting Steps

1. **Changing the Host IP Address**

   - If you need to use a specific Host IP address instead of the one automatically detected
     during installation, you can explicitly provide it using the following command:

     ```bash
     ./install.sh <application-name> <HOST_IP>
     ```

     Example:

     ```bash
     ./install.sh smart-parking 192.168.1.100
     ```

2. **Containers Not Starting**:

   - Check the Docker logs for errors:

     ```bash
     docker ps -a
     docker logs <CONTAINER_ID>
     ```

3. **Failed Service Deployment**:

   - If unable to deploy services successfully due to proxy issues, ensure the proxy is
     configured in the `~/.docker/config.json`:

     ```json
     {
       "proxies": {
         "default": {
           "httpProxy": "http://your-proxy:port",
           "httpsProxy": "https://your-proxy:port",
           "noProxy": "localhost,127.0.0.1"
         }
       }
     }
     ```

   - After editing the file, restart docker:

     ```bash
     sudo systemctl daemon-reload
     sudo systemctl restart docker
     ```

4. **Video stream not displaying on Grafana UI**

   - If you do not see the video stream because of a URL issue, then ensure that `WEBRTC_URL`
     in Grafana has:

     ```bash
     # When Grafana is opened on https://localhost/grafana
     https://localhost/mediamtx/

     # When Grafana is opened on https://<HOST_IP>/grafana
     https://<HOST_IP>/mediamtx/
     ```

5. **Resolving Time Sync Issues in Prometheus**

   If you see the following warning in Prometheus, it indicates a time sync issue.

   ```text
    Warning: Error fetching server time: Detected xxx.xxx seconds time difference between your browser and the server.
   ```

   You can follow the steps below to synchronize system time using NTP.
   1. **Install systemd-timesyncd** if not already installed:

      ```bash
      sudo apt install systemd-timesyncd
      ```

   2. **Check service status**:

      ```bash
      systemctl status systemd-timesyncd
      ```

   3. **Configure an NTP server** (if behind a corporate proxy):

      ```bash
      sudo nano /etc/systemd/timesyncd.conf
      ```

      Add:

      ```ini
      [Time]
      NTP=corp.intel.com
      ```

      Replace `corp.intel.com` with a different ntp server that is supported on your network.

   4. **Restart the service**:

      ```bash
      sudo systemctl restart systemd-timesyncd
      ```

   5. **Verify the status**:

      ```bash
      systemctl status systemd-timesyncd
      ```

   This should resolve the time discrepancy in Prometheus.

## Troubleshooting the Console UI

See [Getting started - Loitering Detection Console UI](./getting-started-ui.md) for normal
usage; the issues below are specific to it.

1. **No bounding boxes on a stream**

   - Detection runs on the full frame and every detected object gets a box regardless of zone
     (see [How detection and zones interact](./getting-started-ui.md#how-detection-and-zones-interact)),
     so a missing box means the model did not detect that object that frame (confidence below
     the pipeline's threshold), not a zone restriction. Check the stream's raw MQTT topic to
     confirm, or try different model for better recall on some object types/angles.

2. **An object is in the zone outline but never appears in the table below it**

   - The table only lists objects `gvaanalytics` has matched to that zone, which depends on
     `evaluation-point=bottom-center` (the object's bottom-center point, not its whole box, must
     be inside the zone polygon) - an object whose box overlaps the zone but whose feet/base are
     still outside it will not match yet. Widen or reposition the zone if the area you care
     about needs to catch objects earlier.

2. **Zone edits not taking effect**

   - `gvaanalytics` cannot update a zone on a running pipeline, so **Apply zone to live
     streams** always restarts every live stream — expect a brief reconnect of each video
     panel.

3. **Pipeline start fails with `400 ... BAD REQUEST`, or a stream connects but never shows video
   or detections (any device, including GPU)**

   - **Most likely cause**: a proxy having a bad moment during `install.sh` can return
     its own HTML error page (e.g. "504 Gateway Timeout") with an HTTP 200 status - `curl` treats
     that as a successful download, silently leaving an HTML file in place of a real model or
     video file. Check for this first:

     ```bash
     file loitering-detection/src/dlstreamer-pipeline-server/videos/*.mp4 \
          loitering-detection/src/dlstreamer-pipeline-server/models/intel/*/*.json \
          loitering-detection/src/dlstreamer-pipeline-server/models/intel/*/FP16/*
     ```

     Any result reported as `HTML document` instead of a video/model format confirms this - every
     device fails identically on corrupted input, so this is not a DEVICE-specific problem. Re-run 
     `install.sh` to redownload, then restart the pipeline server so it
     drops any model-instance-id it already marked broken from the earlier corrupted file:

     ```bash
     docker compose up -d --force-recreate dlstreamer-pipeline-server
     ```

   - **Less common cause**: DL Streamer caches a loaded model against its `model-instance-id`;
     if a pipeline using that id is ever stopped uncleanly, a shared id can leave the cache entry
     wedged so every later launch reusing it silently stalls. The Console UI and
     `sample_start.sh` both generate a unique id per launch, so this should no longer happen in
     normal use. The same restart command above clears this too.
   - If it recurs reliably for a specific model/device combination even with valid files, check
     the pipeline server's logs for errors around that model's load, since that points at a
     model or device-compatibility problem rather than either cause above.

4. **GPU utilization always shows "n/a" even while a GPU stream is running**

   - The gauge reads Prometheus's `qmmd_gpu_engine_utilization_ratio` compute-engine series,
     whose engine label varies by GPU generation/qmassa version (`ccs` on some, `compute` on
     others). If it is still n/a after upgrading to a version with both labels recognized,
     confirm Prometheus actually has GPU series at all:

     ```bash
     docker exec ui-console curl -sk 'http://prometheus:9090/prometheus/api/v1/query?query=qmmd_gpu_engine_utilization_ratio'
     ```

     An empty `result` array means the metrics pipeline itself (`metrics-manager`'s `qmassa`)
     is not reporting for this GPU, not a Console UI bug - check `docker logs metrics-manager`.

## Troubleshooting Helm Deployments

1. Deploying with Intel® GPU K8S Extension on Open Edge Platform

   If you're deploying a GPU based pipeline (example: with VA-API elements like `vapostproc`,
   `vah264dec`, etc., and/or with `device=GPU` in `gvadetect` in `config.json`) with Intel® GPU
   k8s Extension on Open Edge Platform, ensure to set the below details in the file
   `helm/values.yaml` appropriately in order to utilize the underlying GPU.

   ```sh
   gpu:
     enabled: true
     type: "gpu.intel.com/i915"
     count: 1
   ```

2. **`dlstreamer-pipeline-server` pod shows `CreateContainerError`**

  - **Issue**: The `dlstreamer-pipeline-server` pod fails to start and shows `CreateContainerError`. This issue is seen only on environments using the `docker://` container runtime.
  - **Check Container Runtime**: Run the following command to check which container runtime is being used:

    ```bash
    kubectl get nodes -o wide
    ```

    Inspect the `CONTAINER-RUNTIME` column to check if the node is using the `docker://` runtime.

  - **Fix**: Run the following command to configure the Intel GPU device plugin for container runtime compatibility:

    ```bash
    kubectl patch ds intel-gpu-plugin -n intel-device-plugins --type='json' \
      -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "-bypath=none"}]'
    ```
    Restart the Helm deployment once this fix is implemented.


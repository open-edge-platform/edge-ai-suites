# Troubleshooting

The following are options to help you resolve issues with the sample application.

---

## WebRTC Stream on web browser
The firewall may prevent you from viewing the video stream on web browser. Please disable the firewall using this command.
```sh
sudo ufw disable
```

---

## Error Logs

View the container logs using this command.
```sh
docker logs -f <CONTAINER_NAME>
```

---

## Resolving Time Sync Issues in Prometheus

If you see the following warning in Prometheus, it indicates a time sync issue.

**Warning: Error fetching server time: Detected xxx.xxx seconds time difference between your browser and the server.**

You can following the below steps to synchronize system time using NTP.
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

---

## Axis RTSP camera freezes or pipeline stops

Restart the DL Streamer pipeline server container with the pipeline that has this rtsp source.

---

## Deploying with Intel GPU K8S Extension

If you're deploying a GPU based pipeline (example: with VA-API elements like `vapostproc`, `vah264dec` etc., and/or with `device=GPU` in `gvadetect` in `dlstreamer_pipeline_server_config.json`) with Intel GPU k8s Extension, ensure to set the below details in the file `helm/values.yaml` appropriately in order to utilize the underlying GPU.
```sh
gpu:
   enabled: true
   type: "gpu.intel.com/i915"
   count: 1
```

---

## Deploying without Intel GPU K8S Extension

If you're deploying a GPU based pipeline (example: with VA-API elements like `vapostproc`, `vah264dec` etc., and/or with `device=GPU` in `gvadetect` in `dlstreamer_pipeline_server_config.json`) without Intel GPU k8s Extension, ensure to set the below details in the file `helm/values.yaml` appropriately in order to utilize the underlying GPU.
```sh
privileged_access_required: true
```

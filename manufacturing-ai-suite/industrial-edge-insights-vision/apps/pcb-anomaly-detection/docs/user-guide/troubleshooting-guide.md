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
---

## Inferencing on NPU

To perform inferencing on an NPU device (for platforms with NPU accelerators such as Ultra Core processors), ensure you have completed the required pre-requisites. Refer to the instructions [here](https://dlstreamer.github.io/dev_guide/advanced_install/advanced_install_guide_prerequisites.html#prerequisite-2-install-intel-npu-drivers) to install Intel NPU drivers.

---

## Unable to parse JSON payload due to missing `jq` package

While running `sample_start.sh` script, you may get an error-
`ERROR: jq is not installed. Cannot parse JSON payload.` This is due to mising `jq` package that is need to parse the payload JSON. Please follow the steps to install it.

```sh
sudo apt update
sudo apt install jq
```

---

## Unable to run GPU inference on some Arrow Lake machines with `resource allocation failed` errors

For example:

`ERROR vafilter gstvafilter.c:390:gst_va_filter_open:<vafilter0> vaCreateContext: resource allocation failed`

This issue has been observed on systems with the Ultra Core 7 265K processor running Ubuntu 22.04.
There are few options to fix this. 

One is updating the kernel to `6.11.11-061111-generic` in the host system.

Alternately, install OpenCL runtime packages in the host system. Refer to the instructions from OpenVINO documentation [here](https://docs.openvino.ai/2025/get-started/install-openvino/configurations/configurations-intel-gpu.html#linux) to install GPU drivers.
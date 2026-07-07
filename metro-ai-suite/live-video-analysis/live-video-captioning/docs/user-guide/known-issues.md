# Known Issues

## NPU pipeline ignores user-selected resolution and uses 160×160

Symptoms:

- When the `NPU` VLM Device is selected, the frame resolution shown or chosen in the UI is not applied. The backend always sends frames at 160×160 pixels regardless of what the user selects.

Details:

- This is a current limitation of the DLStreamer `gvagenai` element on Intel NPU. For VLM workloads, hardcoded prompt-token limits and the lack of exposed NPU-specific configuration in the `gvagenai` element can cause pipeline failures when higher frame resolutions generate input embeddings that exceed the default 1024-token limit. For now, 160×160 is the only validated input size for the supported VLMs running on NPU as a workaround until a fix is available.

Impact:

- When using the NPU pipeline, captioning frames are limited to 160×160 resolution, which can reduce visual quality and may result in lower caption quality than CPU or GPU pipelines that support higher frame resolutions.

## Pipeline server exits with 2 GPU streams

Symptoms:

- When two GPU pipeline streams are started, the pipeline server exits from the container.

Hardware:

- Issue observed on BMG-580 discrete GPU.

## RTSP Stream not reachable from Live Video Captioning Application

Symptoms:

- Stream not able to play or pipeline not able to start
- DLSPS container shows logs as below:

     ```text
     dlstreamer-pipeline-server  | 0:01:06.194223369     8 0x7060180012c0 ERROR           default gstrtspconnection.c:1291:gst_rtsp_connection_connect_with_response_usec: failed to connect: Could not connect to 10.102.14.14: Socket I/O timed out
     ```

Checks:

- Include rtsp stream ip in no_proxy environment variable.

## Pipeline server core dump sometimes

Symptoms:

- New pipelines cannot be created after pipeline server exits.
- Logs show the pipeline server core-dumping.

Details:

- This issue appears to be caused by resource pressure or instability in the pipeline server rather than in the live-video-captioning application itself.

Checks:

- Verify the `dlstreamer-pipeline-server` service is running.
- Restart the pipeline server or the full application stack if the service is not running.

Tip:

- Size the number of streams according to the available hardware resources.

## Proxy and no_proxy configuration (mandatory)

Behind a corporate network, incorrect proxy settings are the most common cause of model-download failures and DL Streamer Pipeline Server crashes. Make sure both the Docker daemon proxy and `no_proxy` are set correctly and kept consistent.

Docker daemon proxy (required for internet access during model download):

- Configure the proxy for the Docker daemon.
- Restart Docker after updating:

  ```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
  ```

`no_proxy` (required so DLSPS does not crash):

- Add the required entries in `/etc/environment`, including your local network ranges:

  ```bash
  no_proxy=localhost,127.0.0.1,<add-local-network-ranges>
  ```

- Reload the environment:

  ```bash
  source /etc/environment
  ```
Note:

- On an open network (no proxy), remove the proxy settings from the DLSPS (`dlstreamer-pipeline-server`) service in `compose.yaml`. This is a known bug and will be fixed soon.

## DLSPS segfault from improper proxy configuration

Symptoms:

- Pipeline server failure.
- Segmentation fault in the DLSPS (DL Streamer Pipeline Server) container.

Details:

- Improper or inconsistent proxy configuration can lead to segmentation faults in DLSPS.

Workarounds:

- Ensure both the Docker daemon proxy and `no_proxy` are configured correctly (see the proxy configuration issue above).
- Avoid inconsistent proxy settings in `compose.yaml`.
- Restart the containers after any configuration change.

## Memory deallocation issue on Panther Lake (PTL)

Impact:

- On Panther Lake (PTL) systems, DLSPS may have memory deallocation issues, leading to pipeline instability over time.

Mitigation:

- Restart the services if instability is observed.
- Monitor memory usage during long runs.

## WebRTC connectivity issues

Symptoms:

- Black video, no stream, or connection failures in the dashboard.

Checks:

- Verify `HOST_IP` in `.env` is reachable from the browser client.
- Confirm firewall rules allow the configured ports.

## Camera not supported (hardware-encoded webcam format)

Symptoms:

- USB/webcam input cannot be started for specific camera devices.

Details:

- Some webcams expose hardware-encoded formats (for example H.264) instead of raw formats expected by this application.

Checks:

- Use a compatible webcam that provides raw video output (for example, YUYV or MJEPG).

## No models in dropdown

Symptoms:

- Model list is empty in the UI.

Checks:

- Ensure `ov_models/` contains at least one model directory with OpenVINO IR files.
- If you downloaded models, re-run the stack so the service rescans.

## Pipeline server unreachable

Symptoms:

- Starting a run fails; backend reports it cannot reach the pipeline server.

Checks:

- Ensure the `dlstreamer-pipeline-server` service is running.
- Verify `PIPELINE_SERVER_URL` (defaults to `http://dlstreamer-pipeline-server:8080`).

## Port conflicts

If the dashboard or APIs are not reachable, check whether the ports are already in use and update the `.env` values (for example `DASHBOARD_PORT`).

## Performance/throughput lower than expected

- Larger VLMs require more compute and memory; try a smaller model.
- Reduce `max_tokens`.
- Ensure hardware acceleration and drivers are installed if using GPU.

## Metrics graphs lag on GPU pipelines when running in Helm Deployments

Symptoms:

- Live metrics graphs in the dashboard trail behind real-time by a few seconds intermittently when the pipeline is running on a GPU node.

Details:

- The lag is a display artifact caused by the metrics-manager Telegraf `inputs.exec` plugin taking longer than expected to gather CPU frequency data on high-core-count GPU nodes (e.g. nodes with 192 CPUs). This can cause metric batches to queue up and be flushed slightly out of sync.
- The pipeline inference and captioning are unaffected; only the metrics visualization is delayed.

## Gemma model not working in GPU

- Gemma model is not working on GPU. Only working on CPU.

## Limited testing on EMT-S and EMT-D

- This release includes only limited testing on EMT‑S and EMT‑D, some behaviors may not yet be fully validated across all scenarios.

## PVCs bound to local storage prevent reinstall on a different worker node

If the cluster default `StorageClass` uses node-local storage (for example `local-path`), the PersistentVolumes backing the model PVCs are physically stored on the node where the chart was first installed.
When `keepPvc` is `true` (the default), uninstalling the chart preserves the PVCs.
If you then reinstall the chart targeting a different worker node (`global.nodeName`), the pods will remain in `Pending` because the existing PVs are only accessible from the original node.

Workaround — choose one of the following:

- **Delete the old PVCs** before reinstalling on a different node:

  ```bash
  kubectl delete pvc <release>-live-video-captioning-models
  kubectl delete pvc <release>-live-video-captioning-detection-models
  ```

  The model-download hook will repopulate the PVCs on the new node.

- **Set `keepPvc` to `false`** in your override values so Helm deletes and recreates the PVCs on every install:

  ```yaml
  modelsPvc:
    keepPvc: false
  detectionModelsPvc:
    keepPvc: false
  ```

- **Use a network-attached `StorageClass`** (for example NFS, Ceph, or Longhorn) by setting `global.storageClassName` so that PVs are accessible from any node.

## Known EMT Limitation with External RTSP Streams

Due to an EMT networking limitation, RTSP streams must be deployed within the same Docker network as the application (accessed via container/service name). RTSP streams hosted outside the Docker network or accessed using <host-ip> are not supported.

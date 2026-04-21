# Known Issues

## Pipeline server exits with 2 GPU streams

Symptoms:
- When two GPU pipeline streams are started, the pipeline server exits from the container.

Hardware:
- Issue observed on BMG-580 discrete GPU.

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

## WebRTC connectivity issues

Symptoms:
- Black video, no stream, or connection failures in the dashboard.

Checks:
- Verify `HOST_IP` in `.env` is reachable from the browser client.
- Confirm firewall rules allow the configured ports.

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
- The lag is a display artifact caused by the collector's `inputs.exec` plugin taking longer than expected to gather CPU frequency data on high-core-count GPU nodes (e.g. nodes with 192 CPUs). This can cause metric batches to queue up and be flushed slightly out of sync.
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

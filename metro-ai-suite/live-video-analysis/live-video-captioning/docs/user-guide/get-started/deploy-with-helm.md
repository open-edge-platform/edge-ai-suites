# How to Deploy with Helm Chart

This guide shows how to deploy the Live Video Captioning application on Kubernetes with the Helm chart included in this repository.

## Prerequisites

Before you begin, ensure that you have the following:

- A Kubernetes cluster with `kubectl` configured for access.
- Helm installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).
- Dynamic Persistent Volume provisioning available in the cluster, or a `StorageClass` you can set in the chart values.
- A worker node reachable by your browser client. Prefer a GPU-capable worker node when available, because the chart pins the media and inference workloads to the selected node and DL Streamer benefits most from GPU access.
- Sufficient storage for model PVCs. The default chart configuration requests `50Gi` for VLM models and `5Gi` for detection models.
- An RTSP source reachable from the Kubernetes node that runs `dlstreamer-pipeline-server`.

## Prepare the Cluster

### 1. Select the target node

The chart pins the workloads that need to stay together to the target node selected in the chart values:

- `dlstreamer-pipeline-server`
- `video-caption-service`
- `mediamtx`
- `coturn`
- `collector`

These workloads are kept on the same worker because they rely on node-local access patterns:

- `dlstreamer-pipeline-server` and `video-caption-service` share the model PVCs.
- `dlstreamer-pipeline-server` and `collector` need direct access to node hardware and host resources.
- `mediamtx` and `coturn` expose browser-facing WebRTC and TURN endpoints that must match the selected node's reachable IP.

For best performance, choose a worker node with a GPU. The chart can run with CPU-only inference, but a GPU-capable node is the preferred deployment target for DL Streamer and real-time media processing.

Set `global.nodeName` to the Kubernetes node name.

Example:

```yaml
global:
  nodeName: worker4
```

### 2. Get the IP of the selected node

Use the same node that you selected for the pinned media workloads. First list the nodes and labels:

```bash
kubectl get nodes --show-labels
```

Then inspect the selected node:

```bash
kubectl get node <node-name> -o wide
```

Set `global.hostIP` to the node address that is reachable by the browser:

- In clusters without worker-node external IPs, use `INTERNAL-IP`.
- Use `EXTERNAL-IP` only if the node actually has one and your browser reaches the application through it.
- Use `INTERNAL-IP` when your browser is on the same LAN or VPN and can reach the node directly.

To print the value directly:

```bash
kubectl get node <node-name> -o jsonpath='{.status.addresses[?(@.type=="ExternalIP")].address}'
```

If no external address is present, use:

```bash
kubectl get node <node-name> -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'
```

Set that value in `global.hostIP`.

If the worker node does not have any browser-reachable IP, direct NodePort access will not work. This capability will be added to the chart in a future update.

## Known Limitations

### Single-node deployment with host port binding

This chart is designed to run on a **single worker node**. Several workloads bind directly to host ports on that node so that the browser and RTSP clients can reach them without a LoadBalancer or Ingress.

Because of these host port bindings:

- **`replicaCount` must remain `1`** for all workloads that use host ports. Increasing it will fail at scheduling time because two pods cannot bind the same host port on the same node.
- **Multi-node or high-availability deployments are not supported.** The chart intentionally pins all workloads to a single node via `global.nodeName`.
- **Port conflicts with other applications on the same node** are possible. Ensure the ports listed above are not already in use on the target worker node before deploying.

## Configure Required Values

The chart includes a sample override file at `charts/values-override.yaml`. Update it before deploying.

The most important values are:

| Key | Description | Example |
| --- | --- | --- |
| `global.hostIP` | Browser-reachable IP of the selected node that runs the pinned media workloads. In many on-prem clusters this is the node `INTERNAL-IP`. Retrieve it with `kubectl get node <node-name> -o wide` | `192.168.1.20` |
| `global.nodeName` | Kubernetes node name used to pin the media, TURN, and host-coupled workloads to one worker node. Prefer a GPU-capable node when available | `worker4` |
| `global.storageClassName` | StorageClass for the chart PVCs. Leave empty to use the cluster default. If the default class uses node-local storage, see [Known Issues](../known-issues.md#pvcs-bound-to-local-storage-prevent-reinstall-on-a-different-worker-node) | `` |
| `global.models` | **Required.** List of VLM models to export to OpenVINO format. Must contain at least one entry — the chart will fail if this list is empty. The download job always runs and uses this list as its source of truth | `OpenGVLab/InternVL2-1B` |
| `modelsPvc.size` | PVC size for VLM models | `50Gi` |
| `detectionModelsPvc.size` | PVC size for object detection models | `5Gi` |
| `modelsDownload.hfToken` | HuggingFace access token for gated-model downloads, passed as a plain value. Leave empty for public models. | `hf_abc123…` |
| `video-caption-service.env.enableDetectionPipeline` | Enables the object-detection pipeline. When set to `"true"`, the chart automatically downloads the models listed in `global.detectionModels` into the detection models PVC | `"true"` or `"false"` |
| `global.detectionModels` | List of detection model names to download. Each entry is passed to the DL Streamer `download_public_models.sh` helper. Only downloaded when `enableDetectionPipeline` is `"true"` | `["yolov8s"]` |
| `video-caption-service.env.defaultRtspUrl` | Default RTSP URL shown in the dashboard | `rtsp://camera.example/live` |
| `video-caption-service.env.alertMode` | Switches captioning to binary alert-style responses | `"true"` or `"false"` |

### HuggingFace Token for Gated Models

Some models (for example `google/gemma-3-4b-it`) require a HuggingFace access token. Set `modelsDownload.hfToken` directly in your override file:

```yaml
modelsDownload:
  hfToken: "hf_<your-token>"
```

The chart injects `HF_TOKEN` and `HUGGINGFACEHUB_API_TOKEN` as environment variables in the model download job. Leave the field empty for public models that do not require authentication.

### Proxy Configuration

If your cluster runs behind a proxy, set the proxy fields under `global`:

```yaml
global:
  httpProxy: "http://<your-proxy-host>:<port>"
  httpsProxy: "http://<your-proxy-host>:<port>"
  noProxy: "<your-rtsp-camera-host-or-ip>"
```

Important: the host portion of every RTSP URL must be included in `noProxy` when the deployment runs behind a proxy.

For example:

- If your stream URL is `rtsp://camera.example.com:8554/live`, add `camera.example.com` to `noProxy`.
- If your stream URL is `rtsp://192.168.1.50:554/stream1`, add `192.168.1.50` to `noProxy`.

If the RTSP host is not listed in `noProxy`, the application may try to reach the stream through the proxy and fail to connect.

## Build Chart Dependencies

Run the following command from the chart directory:

```bash
helm dependency update
```

This refreshes the chart dependencies from `subcharts/` and updates `Chart.lock`.

## Install the Chart

From `charts/`, install the application with the override file:

```bash
helm install lvc . \
  -f values-override.yaml \
  -n "$my_namespace"
```

## Verify the Deployment

Check the hook job, pods, services, and PVCs:

```bash
kubectl get jobs,pods,svc,pvc -n "$my_namespace"
```

The model downloader runs before the main workloads start. If the initial deployment takes time, inspect the job logs:

```bash
kubectl logs -n "$my_namespace" -l app.kubernetes.io/component=model-downloader
```

Before accessing the application, confirm the following:

- The model download job has completed successfully.
- All pods are in the `Running` state.
- All containers report `Ready`.
- The PVCs are bound.

The first deployment can take several minutes because the chart may download and export VLM models before starting the application pods.

## Access the Application

By default the chart exposes these NodePort services:

- Dashboard UI: `http://<global.hostIP>:4173`

If you changed the service ports in your override values, use those instead.

To start captioning after deployment:

1. Open the dashboard URL in your browser.
2. Enter an RTSP stream URL, unless you preconfigured `defaultRtspUrl`.
3. Select the model you downloaded into the models PVC.
4. Adjust the prompt and generation parameters if needed.
5. Start the stream.

## Upgrade the Release

If you modify the chart or subcharts, refresh dependencies first:

```bash
helm dependency update
```

Then upgrade the release:

```bash
helm upgrade lvc . \
  -f values-override.yaml \
  -n "$my_namespace"
```

## Uninstall the Release

```bash
helm uninstall lvc -n "$my_namespace"
```

## Troubleshooting

- If pods remain `Pending`, check that `global.nodeName` matches the correct node name, that the selected node has the required hardware access, and that the requested `StorageClass` can provision the PVCs.
- If the install fails before pods appear, inspect the model download logs and confirm that the selected model ID and Hugging Face credentials are valid. Note that `global.models` must contain at least one entry — the chart will reject an empty list at render time.
- If the dashboard opens but video does not start, confirm that `global.hostIP` is reachable from the browser. If your worker nodes do not have external IPs, this usually means using the node `INTERNAL-IP` over a reachable LAN or VPN. Also confirm that the RTSP source is reachable from the Kubernetes node.
- If WebRTC negotiation fails, verify that `global.hostIP` points to the same node that runs `mediamtx` and `coturn`, and that the required ports are allowed by your network policy or firewall.
- If detection is enabled but the pipeline cannot start, ensure the detection models PVC contains the required OpenVINO detection model artifacts.
- If the collector does not report metrics, confirm that the host path in `collector.collectorSignalsHostPath` exists on the selected node and that the pod is scheduled there.

## Related Links

- [Get Started](../get-started.md)
- [System Requirements](../get-started/system-requirements.md)
- [How it Works](../how-it-works.md)
- [Object Detection Pipeline](../how-to-guides/configure-object-detection-pipeline.md)
- [Build from Source](../get-started/build-from-source.md)

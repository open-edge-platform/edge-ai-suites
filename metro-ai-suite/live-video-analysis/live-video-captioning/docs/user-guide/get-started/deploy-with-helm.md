# How to Deploy with Helm Chart

This guide shows how to deploy the Live Video Captioning application on Kubernetes with the Helm chart included in this repository.

## Prerequisites

Before you begin, ensure that you have the following:

- A Kubernetes cluster with `kubectl` configured for access.
- Helm installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. See [Kubernetes Documentation on Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for details.
- A worker node reachable by your browser client. Prefer a GPU-capable worker node when available, because the chart pins the media and inference workloads to the selected node and DL Streamer benefits most from GPU access.
- A writable host path for collector signal files on the target node. By default the chart uses `/tmp/lvc/collector-signals`.
- An RTSP source reachable from the Kubernetes node that runs `dlstreamer-pipeline-server`.
- Setup [model-download chart](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started/deploy-with-helm-chart.md) which responsible for all the models used in this Live Video Captioning chart. If you use gated Hugging Face models, a Hugging Face token is required.

## Prepare/Deploy model-download chart

[Model-download service](https://github.com/open-edge-platform/edge-ai-libraries/tree/main/microservices/model-download) from [Open Edge Platform - Edge AI Libraries](https://github.com/open-edge-platform/edge-ai-libraries) will be used for models management in Live Video Captioning.

1. Install the model-download chart
   <br>Refer to this [guide section](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started/deploy-with-helm-chart.md#install-helm-chart-from-docker-hub-or-from-source) to download and install the chart.

2. Configure the values.yaml file
   <br> Edit the [`values.yaml`](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/chart/values.yaml) located in the chart.

   Configure the following:

   | Parameter                  | Description                                                                                                             | Required Values                        |
   | -------------------------- | ----------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
   | proxy                      | Set the proxy value based on your system environment                                                                    | <your_system_proxy>                    |
   | HUGGINGFACEHUB_API_TOKEN   | HuggingFace token to download gated model                                                                               | <your_huggingface_token>               |
   | ENABLE_PLUGINS             | Comma-separated list of plugins to enable                                                                               | "openvino,ultralytics"                 |
   | gpu.enabled                | For model-download service pod to be deployed on GPU                                                                    | true                                   |
   | gpu.key                    | Label assigned to the GPU node on kubernetes cluster by the device plugin. Identify by running `kubectl describe node` | gpu.intel.com/i915 or gpu.intel.com/xe |
   | affinity.enabled           | Set to true to deploy on dedicated node                                                                                 | true                                   |
   | affinity.value             | Your dedicated node name/value. Identify by running `kubectl get node`                                                  | <your_node_name>                       |

   > **Note**: This chart can run on CPU‑only nodes; however, a GPU‑enabled node is strongly recommended to host the models and deliver optimal performance.

3. Deploy the chart
   <br>Deploy the chart using command below:
      ```bash
      helm install model-download . -n <your-namespace>
      ```

   > **Note**: `model-download` creates and manages a shared PVC that used by live-video-captioning. Hence, do not delete or uninstall helm chart when live-video-captioning chart is running.

4. Verify the deployment
   <br>Check the status of the deployed resources to ensure they are running correctly.
      ```bash
      kubectl get pods -n <your-namespace>
      kubectl get services -n <your-namespace>
      ```

## Prepare/Deploy live-video-captioning chart

To set up the live-video-captioning application, you must obtain the charts and install them with optimal values and configurations. The following sections provide step-by-step instructions for this process.

### Acquire the helm chart

There are 2 options to obtain the charts in your workspace:

#### Option 1: Get the charts from Docker Hub

##### Step 1: Pull the Chart

Use the following command to pull the [prebuild chart](https://hub.docker.com/r/intel/live-video-captioning/tags) from Docker Hub:

```bash
helm pull oci://registry-1.docker.io/intel/live-video-captioning --version <version-no>
```

Refer to the release notes for details on the latest version number to use for the sample application.

##### Step 2: Extract the `.tgz` File

After pulling the chart, extract the `.tgz` file:

```bash
tar -xvf live-video-captioning-<version-no>.tgz
```

This will create a directory named `live-video-captioning` containing the chart files. Navigate to the extracted directory to access the charts.

```bash
cd live-video-captioning
```

#### Option 2: Install from Source

##### Step 1: Clone the repository

Clone the repository containing the charts files:

```bash
# Clone the latest on mainline
git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
# Alternatively, clone a specific release branch
git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites -b <release-tag>
```

##### Step 2: Navigate to the chart directory

Navigate to the chart directory:

```bash
cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning/charts
```

### Select the target node

The chart pins the workloads that need to stay together to the target node selected in the chart values:

- `model-download`
- `dlstreamer-pipeline-server`
- `video-caption-service`
- `mediamtx`
- `coturn`
- `collector`
- `live-video-captioning-rag (if RAG is enabled)`

These workloads are kept on the same worker because they rely on node-local access patterns:

- `dlstreamer-pipeline-server`, `video-caption-service`, `live-video-captioning-rag` and `model-download` share the model PVCs that created by `model-download`.
- `dlstreamer-pipeline-server` and `collector` need direct access to node hardware and host resources.
- `mediamtx` and `coturn` expose browser-facing WebRTC and TURN endpoints that must match the selected node's reachable IP.

Other supporting services such as `mqtt-broker`, `live-metrics-service`, `multimodal-embedding` (when RAG is enabled), and `vdms-vectordb` (when RAG is enabled) do not require pinning to the same worker node.

For best performance, choose a worker node with a GPU. The chart can run with CPU-only inference, but a GPU-capable node is the preferred deployment target for DL Streamer and real-time media processing.

In the [values-override.yaml](../../charts/values-override.yaml), specify the Kubernetes node name by setting `global.nodeName`. This references the built-in `kubernetes.io/hostname` label, so no node labeling permissions are required.

Example:

```yaml
global:
  nodeName: worker4
```

#### Get the IP of the selected node

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

### Configure Required Values

Prior to deployment, edit the sample override file at `charts/values-override.yaml`, focusing on the key configuration parameters below:

| Key | Description | Example |
| --- | --- | --- |
| `global.hostIP` | Browser-reachable IP of the selected node that runs the pinned media workloads. In many on-prem clusters this is the node `INTERNAL-IP`. Retrieve it with `kubectl get node <node-name> -o wide` | `192.168.1.20` |
| `global.nodeName` | Kubernetes node name used to pin the media, TURN, and host-coupled workloads to one worker node. Prefer a GPU-capable node when available | `worker4` |
| `global.models` | List of VLM models from HuggingFace to export to OpenVINO format (at least one VLM required) | `OpenGVLab/InternVL2-1B` |
| `global.huggingface.apiToken` | HuggingfaceHub token to download gated model. | <your_huggingfacehub_token> |
| `video-caption-service.env.enableDetectionPipeline` | Enables detection filtering in the pipeline. When set to `"true"` and configure `global.detectionModels` so the chart downloads the required detection models automatically | `"true"` or `"false"` |
| `global.detectionModels` | List of detection model names to download (only required when `video-caption-service.enableDetectionPipeline` is enabled) | `["yolov8s"]` |
| `video-caption-service.env.defaultRtspUrl` | Default RTSP URL shown in the dashboard | `rtsp://camera.example/live` |
| `video-caption-service.env.alertMode` | Switches captioning to binary alert-style responses | `"true"` or `"false"` |

#### Proxy Configuration

If your cluster runs behind a proxy, set the proxy fields under `global`:

```yaml
global:
  httpProxy: "http://<your-proxy-host>:<port>"
  httpsProxy: "http://<your-proxy-host>:<port>"
  noProxy: "<your-rtsp-camera-host-or-ip>"
```

> **Important**: the host portion of every RTSP URL must be included in `noProxy` when the deployment runs behind a proxy.

>For example:
>- If your stream URL is `rtsp://camera.example.com:8554/live`, add `camera.example.com` to `noProxy`.
>- If your stream URL is `rtsp://192.168.1.50:554/stream1`, add `192.168.1.50` to `noProxy`.

>If the RTSP host is not listed in `noProxy`, the application may try to reach the stream through the proxy and fail to connect.

#### Optional: Enable RAG with Live-Video-Captioning

Live‑Video‑Captioning includes an optional RAG (Retrieval‑Augmented Generation) capability. You can leave this disabled for a standard captioning deployment, or enable it to add retrieval-backed chatbot features. When enabled, generated caption text is converted into embeddings and stored in a vector store along with the associated frame data and metadata. A RAG‑based chatbot service is included, allowing users to submit queries and receive LLM‑generated responses using context retrieved from the vector store.

If you want to enable this optional feature, edit the override file at `charts/values-override.yaml` and configure the following additional parameters:

| Key | Description | Example |
| --- | --- | --- |
| global.enableRAG | Set to `true` to enable RAG subchart to deploy RAG service | `true` or `false` |
| global.llmModel.modelId  | Configure choice of LLM in RAG | `"microsoft/Phi-3.5-mini-instruct"` |
| global.llmModel.weightFormat | Model Quantization | `"int4"` or `"int8"` or `"fp16"` |
| global.embeddingModel.modelId | Configure choice of embedding model for embedding creation | `"QwenText/qwen3-embedding-0.6b"` |

> **Note**: To deploy the llmModel or embeddingModel on a GPU, set `global.llmModel.useGPU.enabled` or `global.embeddingModel.useGPU.enabled` to `true`.

> For `global.llmModel.useGPU.key`, set the value to the GPU resource key label that set in the configured `nodeName`, as the LLM models share the same PVC on that node.

> For `global.embeddingModel.useGPU.key`, you may specify any available GPU resource key label if multiple GPU‑enabled nodes are present. The embedding model does not share the PVC and is managed independently by the embedding service.

> A GPU resource key refers to the label assigned to a GPU‑enabled node by the Kubernetes device plugin. This label is used by Kubernetes to identify and schedule workloads onto nodes with specific GPU resources. You can identify the available GPU resource keys by running `kubectl describe node <node-name>`. Example values include `gpu.intel.com/i915` or `gpu.intel.com/xe`.

### Build Chart Dependencies

Run the following command from the chart directory:

```bash
helm dependency update
```

This refreshes the chart dependencies from `subcharts/` and updates `Chart.lock`.

### Install the Chart

From `charts/`, install the application with the override file:

```bash
helm install lvc . \
  -f values-override.yaml \
  -n "$my_namespace" \
  --timeout 60m
```

You can also install from the repository root:

```bash
helm install lvc ./charts \
  -f ./charts/values-override.yaml \
  -n "$my_namespace" \
```

## Verify the Deployment

Before accessing the application, confirm the following:

- Status of `models-pvc` created by model-download chart is bound. You can check via `kubectl get pvc` command.
- All pods are in the `Running` state.
- All containers report `Ready`. Check via `kubectl get pods` command.

> The initial deployment may take several minutes, as the chart performs multiple model downloads and conversion steps before the application pods are started.

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
6. To submit query via RAG chatbot. Click on the `chat icon` button located top right of the dashboard. The button only visible when RAG is enabled.

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

- If pods remain `Pending`, check that `global.nodeName` matches the correct node name, that the selected node has the required hardware access.
- If the dashboard opens but video does not start, confirm that `global.hostIP` is reachable from the browser. If your worker nodes do not have external IPs, this usually means using the node `INTERNAL-IP` over a reachable LAN or VPN. Also confirm that the RTSP source is reachable from the Kubernetes node.
- If WebRTC negotiation fails, verify that `global.hostIP` points to the same node that runs `mediamtx` and `coturn`, and that the required ports are allowed by your network policy or firewall.
- If detection is enabled but the pipeline cannot start, ensure the detection models PVC contains the required OpenVINO detection model artifacts.
- If the collector does not report metrics, confirm that the host path in `collector.collectorSignalsHostPath` exists on the selected node and that the pod is scheduled there.
- If the `live-video-captioning` and `video-caption-service` pods stuck in `Init` or `Pending` state, check whether the models successfully download or not.
   ```bash
   # Get the pods
   kubectl get pods -n <your_namespace>

   # View the logs of initContainers where it process for model download and conversion
   kubectl logs -f <video-caption-service pod or live-video-captioning pod> -n <your_namespace> -c download-models
   ```
- If the PVC created during a Helm chart deployment is not removed or auto-deleted due to a deployment failure or being stuck, delete it manually:
   ```bash
   # List the PVCs present in the given namespace
   kubectl get pvc -n <namespace>

   # Delete the required PVC from the namespace
   kubectl delete pvc <pvc-name> -n <namespace>
   ```
> **Note**: Delete the shared PVC only after confirming no other workload or application depends on it. In such cases, uninstall the dependent application first, then clean up model-download resources, and finally delete the shared PVC if required.

## Related Links

- [Get Started](../get-started.md)
- [System Requirements](../get-started/system-requirements.md)
- [How it Works](../how-it-works.md)
- [Object Detection Pipeline](../how-to-guides/configure-object-detection-pipeline.md)
- [Build from Source](../get-started/build-from-source.md)
- [Embedding Creation with RAG](../how-to-guides/configure-embedding-creation-with-rag.md)
- [Model Download Service](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/docs/user-guide/get-started/deploy-with-helm-chart.md)

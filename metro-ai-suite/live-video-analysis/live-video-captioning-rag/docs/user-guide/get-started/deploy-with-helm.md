# Deploy with Helm Chart

This guide shows how to deploy the Live Video Captioning RAG application on Kubernetes with the Helm chart included in this repository.

The `live-video-captioning-rag/charts` chart is a parent chart that deploys:

- Live Video Captioning core services (`mqtt-broker`, `dlstreamer-pipeline-server`, `video-caption-service`, `mediamtx`, `coturn`, and `metrics-manager`)
- Live Video Captioning RAG service
- Multimodal embedding service
- VDMS vector database service

## Prerequisites

Before you begin, ensure that you have the following:

- A Kubernetes cluster with `kubectl` configured for access.
- Helm installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).
- The cluster must support dynamic provisioning of Persistent Volumes (PV). See [Kubernetes Documentation on Dynamic Volume Provisioning](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for details.
- A worker node reachable by your browser client. Prefer a GPU-capable worker node when available, because the chart pins media and inference workloads to the selected node.
- An Intel GPU/NPU-capable worker node is recommended so the `metrics-manager` can report GPU and NPU utilization (via qmassa). GPU/NPU metrics are omitted on nodes without the hardware.
- An RTSP source reachable from the Kubernetes node that runs `dlstreamer-pipeline-server`.
- Setup the [Model Download chart](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/get-started/deploy-with-helm-chart.html), which is responsible for downloading and converting models used by this deployment. If you use gated Hugging Face models, a Hugging Face token is required.

## Prepare/Deploy model-download chart

[Model Download Service](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/index.html) from [Open Edge Platform - Edge AI Libraries](https://github.com/open-edge-platform/edge-ai-libraries) is used for model management.

1. Install the model-download chart.

	 Refer to this [guide section](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/get-started/deploy-with-helm-chart.html#install-helm-chart-from-docker-hub-or-from-source) to download and install the chart.

2. Configure the values.yaml file.

	 Edit the [`values.yaml`](https://github.com/open-edge-platform/edge-ai-libraries/blob/main/microservices/model-download/chart/values.yaml) located in the model-download chart.

	 Configure the following:

	 | Parameter | Description | Required Values |
	 | --- | --- | --- |
	 | `proxy` | Set the proxy value based on your system environment | `<your_system_proxy>` |
	 | `HUGGINGFACEHUB_API_TOKEN` | HuggingFace token to download gated model | `<your_huggingface_token>` |
	 | `ENABLE_PLUGINS` | Comma-separated list of plugins to enable | `"openvino,ultralytics"` |
	 | `OVMS_RELEASE_TAG` | OVMS release tag used by the conversion script | default: `v2025.4.1` |
	 | `gpu.enabled` | Deploy model-download service pod on GPU node | `true` |
	 | `gpu.key` | GPU node resource key from your Kubernetes node | `gpu.intel.com/i915` or `gpu.intel.com/xe` |
	 | `affinity.enabled` | Set to true to deploy on dedicated node | `true` |
	 | `affinity.value` | Dedicated node name/value from `kubectl get node` | `<your_node_name>` |

	 > **Note:** The chart can run on CPU-only nodes; however, a GPU-enabled node is strongly recommended for better conversion and runtime performance.

3. Deploy the chart.

	 ```bash
	 helm install model-download . -n <your-namespace>
	 ```

	 > **Note:** `model-download` creates and manages a shared PVC consumed by Live Video Captioning and Live Video Captioning RAG workloads.

4. Verify deployment.

	 ```bash
	 kubectl get pods -n <your-namespace>
	 kubectl get services -n <your-namespace>
	 ```

## Prepare/Deploy live-video-captioning-rag chart

To set up the integrated deployment, obtain the chart and install it with your environment-specific overrides.

### Acquire the chart

#### Option 1: Get charts from Docker Hub

1. Run the following command to pull the [prebuild chart](https://hub.docker.com/r/intel/live-video-captioning-rag/tags) from Docker Hub. Refer to the release notes for details on the latest version number to use for the sample application.

   ```bash
   helm pull oci://registry-1.docker.io/intel/live-video-captioning-rag --version <version-no>
   ```

   > **Note:** When browsing available tags, look for tags ending with the `helm` suffix — these indicate a Helm chart package.

2. Extract the `.tgz` file.

   ```bash
   tar -xvf live-video-captioning-rag-<version-no>.tgz
   cd live-video-captioning-rag
   ```

3. Configure the `values-override.yaml` using the [Select target node](#select-the-target-node) and [Configured required values](#configure-required-values) sections below.

4. Install/Deploy the chart.

   ```bash
   helm install lvc-rag . \
   -f values-override.yaml \
   -n "$my_namespace"
   ```

5. See the [Verify the deployment section](#verify-the-deployment) to confirm the deployment.

6. If you modify the chart or subcharts, refresh dependencies first:

   ```bash
   # Update/refresh the chart
   helm dependency update
   ```

   Then upgrade the deployment:

   ```bash
   helm upgrade lvc-rag . \
   -f values-override.yaml \
   -n "$my_namespace"
   ```

7. Uninstall the chart.

   ```bash
   helm uninstall lvc-rag -n "$my_namespace"
   ```

#### Option 2: Install from source

1. Clone the repository.

   ```bash
   # Clone the mainline branch
   git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites -b main
   ```

2. Navigate to the chart directory.

   ```bash
   cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-captioning-rag/charts
   ```

### Select the target node

The chart pins host-coupled workloads from both to one target node via `global.nodeName`, including:

- `model-download`
- `dlstreamer-pipeline-server`
- `video-caption-service`
- `mediamtx`
- `coturn`
- `metrics-manager`
- `live-video-captioning-rag`

This keeps media, model PVC access, and host-exposed ports aligned on a single reachable worker.

In `charts/values-override.yaml`, set:

```yaml
global:
  nodeName: worker4
```

Use the same node that you used for model-download.

### Configure host-reachable IP

Set `global.hostIP` to the node IP your browser can reach.

Helpful commands:

```bash
kubectl get node <your_node_name> -owide
kubectl get node <node-name> -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'
kubectl get node <node-name> -o jsonpath='{.status.addresses[?(@.type=="ExternalIP")].address}'
```

- Use `INTERNAL-IP` when your browser is on the same reachable network (LAN/VPN).
- Use `EXTERNAL-IP` when internal networking is not directly reachable.

### Configure required values

Prior to deployment, edit `charts/values-override.yaml` and set at least the following:

| Key | Description | Example |
| --- | --- | --- |
| `global.hostIP` | Browser-reachable IP of the selected node | `192.168.1.20` |
| `global.nodeName` | Node name used to pin host-coupled services | `worker4` |
| `global.models` | VLM model entries for captioning (`modelId`, `modelType`, `weightFormat`, `device`) | `OpenGVLab/InternVL2-1B` |
| `global.huggingface.apiToken` | Hugging Face token for gated models (if needed) | `<your_huggingfacehub_token>` |
| `global.llmModel.modelId` | LLM model for RAG chatbot | `microsoft/Phi-3.5-mini-instruct` |
| `gloval.llmModel.weightFormat` | Precision of model weights for conversion | `int8 / int4 / fp16` |
| `global.llmModel.useGPU.enabled` | Enable GPU scheduling for LLM model runtime | `true / false` |
| `global.llmModel.useGPU.key` | GPU resource key used to schedule the LLM workload | `gpu.intel.com/i915` |
| `global.embeddingModel.useGPU.enabled` | Enable GPU scheduling for embedding model runtime | `true / false` |
| `global.embeddingModel.useGPU.key` | GPU resource key used to schedule embedding workload | `gpu.intel.com/i915 / gpu.intel.com/xe` |
| `live-video-captioning-rag.env.maxTokens` | Max generated tokens for RAG response | `1024` |
| `live-video-captioning-rag.env.topK` | Number of retrieved context candidates | `1` |

> **Note:** You can find GPU resource keys by running `kubectl describe node <node-name>`. Common values for intel GPUs include `gpu.intel.com/i915` and `gpu.intel.com/xe`.
>
> **Note:** If `NPU` is selected in `global.models[].device` for VLM models, `weightFormat` is automatically forced to `int4`.
>
> **Note:** LLM models in the Live-Video-Captioning-RAG application currently do not support NPU inference.

#### Optional: Proxy configuration

If your cluster is behind a proxy, configure:

```yaml
global:
    httpProxy: "http://<your-proxy-host>:<port>"
    httpsProxy: "http://<your-proxy-host>:<port>"
    noProxy: "<your-rtsp-camera-host-or-ip>"
```

> **Important:** the host portion of every RTSP URL must be included in `noProxy` when the deployment runs behind a proxy.
>
> For example:
>
> - If your stream URL is `rtsp://camera.example.com:8554/live`, add `camera.example.com` to `noProxy`.
> - If your stream URL is `rtsp://192.168.1.50:554/stream1`, add `192.168.1.50` to `noProxy`.
>
> If the RTSP host is not listed in `noProxy`, the application may try to reach the stream through the proxy and fail to connect.

#### Optional: Detection pipeline

To enable detection filtering in captioning flow, set:

- `live-video-captioning.video-caption-service.env.enableDetectionPipeline: "true"`
- `global.detectionModels` with required detection models (for example, `yolov8s`)

### Build chart dependencies

Run from the `charts/` directory, build the chart using the Makefile target:

```bash
make deps
```

This builds dependencies in the required order for both child and parent charts.

### Install the chart

From `charts/`, deploy using the Makefile target:

```bash
make deploy NAMESPACE=<your-namespace>
```

To see available targets and overridable variables for Makefile (for example, `RELEASE`, `NAMESPACE`, and `VALUES_FILE`), run:

```bash
make help
```

## Verify the deployment

Before accessing the application, confirm:

- `models-pvc` is in `Bound` state.
- All pods are in `Running` state.
- All containers are `Ready`.

```bash
kubectl get pvc -n <your-namespace>
kubectl get pods -n <your-namespace>
kubectl get services -n <your-namespace>
```

> **Note:** First-time deployment can take several minutes because models may be downloaded and converted before services become ready.

## Access the application

By default, the chart exposes:

- Live Video Captioning dashboard: `http://<global.hostIP>:4173`
- Live Video Captioning RAG dashboard/API: `http://<global.hostIP>:4172`

To start:

1. Open the Live Video Captioning dashboard.
2. Provide RTSP URL (or select available USB/webcam source).
3. Select runtime device and model.
4. Start stream to generate captions and embedding context.
5. Use the chat icon in the Live Video Captioning UI (RAG-enabled flow), or access the RAG dashboard directly on port `4172`.

## Upgrade the release

If you modify chart or subcharts, rerun:

```bash
make deps
```

Then apply the update:

```bash
make deploy NAMESPACE=<your-namespace>
```

## Uninstall the release

```bash
make uninstall
```

## Known Limitations

### Single-node deployment with host port binding

This chart is designed to run on a single worker node.

- `global.nodeName` pins host-coupled workloads to one node.
- `live-video-captioning-rag` uses host port binding on port `4172`; `replicaCount` must remain `1`.
- Multi-node or high-availability deployment is not supported in the current chart design.
- Ensure required host ports are not already in use on the selected node.

## Troubleshooting

- If pods remain `Pending`, verify `global.nodeName` and hardware/resource availability on the selected node.
- If dashboard opens but video does not start, verify `global.hostIP` reachability and RTSP source reachability from the node.
- If RAG service remains in `Init`, inspect init container logs for model download and embedding readiness:

	```bash
	kubectl get pods -n <your-namespace>
	kubectl logs -f <live-video-captioning-rag-pod> -n <your-namespace> -c download-models
	kubectl logs -f <live-video-captioning-rag-pod> -n <your-namespace> -c wait-for-multimodal-embedding
	```

- If `metrics-manager` does not report metrics, verify scheduling on the target node and required host access permissions.
- If model download fails for gated models, ensure `global.huggingface.apiToken` is configured with a valid token.
- If PVCs are left behind after failed deployments, list and clean them manually only after confirming no dependent workloads are running:

	```bash
	kubectl get pvc -n <your-namespace>
	kubectl delete pvc <pvc-name> -n <your-namespace>
	```

## Related Links

- [Get Started](../get-started.md)
- [System Requirements](../get-started/system-requirements.md)
- [How it Works](../how-it-works.md)
- [Build from Source](../get-started/build-from-source.md)
- [Model Download Service](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/model-download/get-started/deploy-with-helm-chart.html)

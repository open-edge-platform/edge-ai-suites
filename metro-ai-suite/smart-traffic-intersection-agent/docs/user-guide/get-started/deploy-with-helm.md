# How to Deploy with Helm

This guide provides step-by-step instructions for deploying the Smart Traffic Intersection Agent application using Helm.

## Prerequisites

Before you begin, ensure that you have the following prerequisites:

- Kubernetes cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. Refer to the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster.
- Helm installed on your system: [Installation Guide](https://helm.sh/docs/intro/install/).
- A running **Smart Intersection** deployment (provides MQTT broker, camera pipelines, and scene analytics). See [Step 4](#step-4-deploy-smart-intersection) below.
- The SceneScape CA certificate file (`scenescape-ca.pem`) for TLS connections to the MQTT broker (created during the Smart Intersection installation).
- *(Optional)* A [Hugging Face](https://huggingface.co/) API token if the VLM model requires authentication.
- **Storage Requirement:** The VLM model cache PVC requests 20 GiB by default. Ensure the cluster has sufficient storage available.
- *(Optional — GPU inference)* To run VLM inference on an Intel GPU:
  - An Intel integrated, Arc, or Data Center GPU must be available on at least one worker node.
  - The [Intel GPU device plugin for Kubernetes](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/main/cmd/gpu_plugin/README.md) must be installed so that GPU resources (e.g., `gpu.intel.com/i915` or `gpu.intel.com/xe`) are advertised to the scheduler. Verify by running:
    ```bash
    kubectl describe node <gpu-node> | grep gpu.intel.com
    ```
  - The `/dev/dri/renderD*` device must be accessible inside containers. The Helm chart automatically adds the correct `supplementalGroups` entry for the render group.

## Steps to Deploy with Helm

The following steps walk through deploying the Smart Traffic Intersection Agent application using Helm. You can install from source code or pull the chart from a registry.

**_Steps 1 to 3 vary depending on whether you prefer to build or pull the Helm chart._**

### Option 1: Install from a Registry

#### Step 1: Pull the Chart

Use the following command to pull the Helm chart:

```bash
helm pull oci://registry-1.docker.io/intel/smart-traffic-intersection-agent --version 1.0.0-helm
```

#### Step 2: Extract the `.tgz` File

After pulling the chart, extract the `.tgz` file:

```bash
tar -xvf smart-traffic-intersection-agent-1.0.0-helm.tgz
```

Navigate to the extracted directory:

```bash
cd smart-traffic-intersection-agent
```

#### Step 3: Configure the `values.yaml` File

Edit the `values.yaml` file to set the necessary environment variables. Refer to the [values reference table](#valuesyaml-reference) below.

---

### Option 2: Install from Source

#### Step 1: Clone the Repository

Clone the repository containing the Helm chart:

```bash
# Clone the release branch
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b release-2026.0.0
```

#### Step 2: Change to the Chart Directory

Navigate to the chart directory:

```bash
cd edge-ai-suites/metro-ai-suite/smart-traffic-intersection-agent/chart
```

#### Step 3: Configure the `values.yaml` File

Edit the `values.yaml` file located in the chart directory to set the necessary environment variables. Refer to the [values reference table](#valuesyaml-reference) below.

---

## Common Steps After Configuration

### Step 4: Deploy Smart Intersection

The Smart Traffic Intersection Agent depends on a running **Smart Intersection** deployment, which includes [SceneScape](https://github.com/open-edge-platform/scenescape). It provides the MQTT broker, camera pipelines, and scene analytics that the Traffic Agent consumes.

Follow the [Smart Intersection Helm Deployment Guide](https://github.com/open-edge-platform/edge-ai-suites/blob/release-1.2.0/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/how-to-deploy-helm.md) to deploy it. Once all Smart Intersection pods are running and the MQTT broker is reachable, proceed to the next step.

### Step 5: Configure GPU Support (Optional)

By default, the chart deploys VLM inference on an **Intel GPU**. To change graph or verify GPU configuration, edit the following values in `values.yaml`:

| Value | Description | Default |
| --- | --- | --- |
| `vlmServing.gpu.enabled` | Enable Intel GPU for VLM inference. When `true`, `VLM_DEVICE` is automatically set to `GPU` and workers are forced to `1`. | `true` |
| `vlmServing.gpu.resourceName` | Kubernetes GPU resource name exposed by the Intel device plugin. Use `gpu.intel.com/i915` for integrated/Arc GPUs, `gpu.intel.com/xe` for Data Center GPU Flex/Max. | `gpu.intel.com/i915` |
| `vlmServing.gpu.resourceLimit` | Number of GPU devices to request | `1` |
| `vlmServing.gpu.renderGroupIds` | List of render group GIDs for `/dev/dri` access. Defaults cover all common distros. | `[44, 109, 992]` |
| `vlmServing.nodeSelector` | Pin VLM pod to nodes with GPUs (e.g., `intel.feature.node.kubernetes.io/gpu: "true"`) | `{}` |

Identify your cluster's GPU resource key by running:

```bash
kubectl describe node <gpu-node> | grep gpu.intel.com
```

To deploy on **CPU instead**, set:

```bash
helm install stia . -n <your-namespace> --create-namespace \
  --set vlmServing.gpu.enabled=false
```

> **Note:** The `OV_CONFIG` environment variable is automatically set based on the device. When GPU is enabled, CPU-only options like `INFERENCE_NUM_THREADS` are excluded to avoid runtime errors.

### Step 6: Deploy the Helm Chart

Deploy the Smart Traffic Intersection Agent Helm chart:

```bash
helm install stia . -n <your-namespace> --create-namespace
```

> **Note:** Please make sure to use the same namespace as the Smart Intersection application. Default namespace for Smart Intersection is `smart-intersection`.


> **Note:** The VLM OpenVINO Serving pod will download and convert the model on first startup. This may take several minutes depending on network speed and model size. To avoid re-downloading the model on every install cycle, set `vlmServing.persistence.keepOnUninstall` to `true` (the default). This tells Helm to retain the model cache PVC on uninstall.

### Step 7: Verify the Deployment

Check the status of the deployed resources to ensure everything is running correctly:

```bash
kubectl get pods -n <your-namespace>
kubectl get services -n <your-namespace>
```

You should see two pods:

| Pod | Description |
| --- | ----------- |
| `stia-traffic-agent-*` | The traffic intersection agent (backend + Gradio UI) |
| `stia-vlm-openvino-serving-*` | The VLM inference server |

Wait until both pods show `Running` and `READY 1/1`:

```bash
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=stia -n <your-namespace> --timeout=600s
```

### Step 8: Access the Application

#### Using NodePort (default)

The chart deploys services as `NodePort` by default. Retrieve the allocated ports and a node IP:

```bash
# Get the NodePort values
kubectl get svc stia-traffic-agent -n <your-namespace>

# Get the node IP
kubectl get nodes -o wide
# Use the INTERNAL-IP of any node
```

Then open your browser at:

```
http://<node-ip>:<backend-node-port>   # Backend API (default NodePort: 30881)
http://<node-ip>:<ui-node-port>         # Gradio UI   (default NodePort: 30860)
```

> **Note:** If you are behind a corporate proxy, make sure the node IPs are included in your `no_proxy` / browser proxy exceptions.

#### Using Port-Forward (ClusterIP)

If you changed the service type to `ClusterIP` in `values.yaml`:

```bash
# Traffic Agent Backend API
kubectl port-forward svc/stia-traffic-agent 8081:8081 -n <your-namespace> &

# Traffic Agent Gradio UI
kubectl port-forward svc/stia-traffic-agent 7860:7860 -n <your-namespace> &
```

Then open your browser at:

- **Backend API:** `http://127.0.0.1:8081/docs`
- **Gradio UI:** `http://127.0.0.1:7860`

### Step 9: Uninstall the Helm Chart

To uninstall the deployed Helm chart:

```bash
helm uninstall stia -n <your-namespace>
```

> **Note:** When `vlmServing.persistence.keepOnUninstall` is `true` (the default), the VLM model cache PVC is **retained** after uninstall to avoid re-downloading the model. This is recommended during development and testing. To fully clean up all PVCs:
>
> ```bash
> kubectl get pvc -n <your-namespace>
> kubectl delete pvc <pvc-name> -n <your-namespace>
> ```
>
> To have Helm delete the PVC automatically on uninstall, set `vlmServing.persistence.keepOnUninstall=false` before deploying.

---

## `values.yaml` Reference

### Global Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `global.proxy.httpProxy` | HTTP proxy URL | `""` |
| `global.proxy.httpsProxy` | HTTPS proxy URL | `""` |
| `global.proxy.noProxy` | Comma-separated no-proxy list | `""` |

### Traffic Agent Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `trafficAgent.image.repository` | Traffic agent container image repository | `intel/smart-traffic-intersection-agent` |
| `trafficAgent.image.tag` | Image tag | `1.0.0` |
| `trafficAgent.service.type` | Kubernetes service type (`NodePort` or `ClusterIP`) | `NodePort` |
| `trafficAgent.service.backendPort` | Backend API port | `8081` |
| `trafficAgent.service.backendNodePort` | NodePort for backend API (only used when type is `NodePort`) | `30881` |
| `trafficAgent.service.uiPort` | Gradio UI port | `7860` |
| `trafficAgent.service.uiNodePort` | NodePort for Gradio UI (only used when type is `NodePort`) | `30860` |
| `trafficAgent.intersection.name` | Unique intersection identifier | `intersection_1` |
| `trafficAgent.intersection.latitude` | Intersection latitude | `37.51358` |
| `trafficAgent.intersection.longitude` | Intersection longitude | `-122.25591` |
| `trafficAgent.env.logLevel` | Application log level | `INFO` |
| `trafficAgent.env.refreshInterval` | Dashboard refresh interval (seconds) | `15` |
| `trafficAgent.env.weatherMock` | Use mock weather data (`true`/`false`) | `false` |
| `trafficAgent.env.vlmTimeoutSeconds` | Timeout for VLM inference requests (seconds) | `600` |
| `trafficAgent.mqtt.host` | MQTT broker hostname (SceneScape K8s service name) | `smart-intersection-broker` |
| `trafficAgent.mqtt.port` | MQTT broker port | `1883` |
| `trafficAgent.traffic.highDensityThreshold` | Object count for high-density classification | `10` |
| `trafficAgent.traffic.moderateDensityThreshold` | Object count for moderate-density classification | `""` |
| `trafficAgent.traffic.bufferDuration` | Traffic analysis buffer window | `""` |
| `trafficAgent.persistence.enabled` | Enable persistent storage for agent data | `true` |
| `trafficAgent.persistence.size` | PVC size for agent data | `1Gi` |
| `trafficAgent.persistence.storageClass` | Storage class (empty = cluster default) | `""` |

### VLM OpenVINO Serving Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `vlmServing.image.repository` | VLM serving container image repository | `intel/vlm-openvino-serving` |
| `vlmServing.image.tag` | Image tag | `1.3.2` |
| `vlmServing.service.type` | Kubernetes service type (`NodePort` or `ClusterIP`) | `NodePort` |
| `vlmServing.service.port` | VLM HTTP API port | `8000` |
| `vlmServing.service.nodePort` | NodePort for VLM API (only used when type is `NodePort`) | `30800` |
| `vlmServing.env.modelName` | Hugging Face model identifier | `microsoft/Phi-3.5-vision-instruct` |
| `vlmServing.env.compressionWeightFormat` | Model weight format (`int4`, `int8`, `fp16`) | `int4` |
| `vlmServing.env.device` | OpenVINO inference device when GPU is disabled (`CPU` or `GPU`). Ignored when `vlmServing.gpu.enabled=true` (auto-set to `GPU`). | `CPU` |
| `vlmServing.env.maxCompletionTokens` | Max tokens per completion | `1500` |
| `vlmServing.env.workers` | Number of serving workers. Forced to `1` when GPU is enabled. | `1` |
| `vlmServing.env.logLevel` | VLM serving log level | `info` |
| `vlmServing.env.openvinoLogLevel` | OpenVINO runtime log level | `1` |
| `vlmServing.env.accessLogFile` | Access log file path (`/dev/null` to suppress) | `/dev/null` |
| `vlmServing.env.seed` | Random seed for reproducible inference | `42` |
| `vlmServing.env.ovConfigCpu` | OpenVINO config JSON for CPU mode (supports `INFERENCE_NUM_THREADS`) | `{"PERFORMANCE_HINT": "LATENCY", "INFERENCE_NUM_THREADS": 32}` |
| `vlmServing.env.ovConfigGpu` | OpenVINO config JSON for GPU mode (includes GPU model cache) | `{"PERFORMANCE_HINT": "LATENCY", "CACHE_DIR": "/app/ov-model/gpu-cache"}` |
| `vlmServing.huggingfaceToken` | Hugging Face API token (stored as a Secret) | `""` |
| `vlmServing.gpu.enabled` | Enable Intel GPU for VLM inference. Auto-sets `VLM_DEVICE=GPU` and `WORKERS=1`. | `true` |
| `vlmServing.gpu.resourceName` | Kubernetes GPU resource name exposed by the Intel device plugin (`gpu.intel.com/i915` or `gpu.intel.com/xe`) | `gpu.intel.com/i915` |
| `vlmServing.gpu.resourceLimit` | Number of GPU devices to request | `1` |
| `vlmServing.gpu.renderGroupIds` | List of GIDs for the `render` group added to `supplementalGroups` for `/dev/dri` access. All common distro values are included by default (44, 109, 992). | `[44, 109, 992]` |
| `vlmServing.nodeSelector` | Pin VLM pod to GPU nodes (e.g., `intel.feature.node.kubernetes.io/gpu: "true"`) | `{}` |
| `vlmServing.persistence.enabled` | Enable persistent storage for model cache | `true` |
| `vlmServing.persistence.size` | PVC size for model cache | `20Gi` |
| `vlmServing.persistence.storageClass` | Storage class (empty = cluster default) | `""` |
| `vlmServing.persistence.keepOnUninstall` | Retain PVC on `helm uninstall` to avoid re-downloading the model | `true` |

### TLS / Secrets Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `tls.caCert` | PEM-encoded CA certificate for the MQTT broker (base64-encoded in the Secret) | `""` |
| `tls.caCertSecretName` | Name of an existing Secret containing the CA cert (overrides `tls.caCert`) | `smart-intersection-broker-rootcert` |
| `tls.caCertKey` | Key name inside the external secret (required when `caCertSecretName` is set) | `root-cert` |

---

## Example: Minimal Deployment

```yaml
# values-override.yaml
global:
  proxy:
    httpProxy: "http://proxy.example.com:8080"
    httpsProxy: "http://proxy.example.com:8080"
    noProxy: "localhost,127.0.0.1,10.0.0.0/8,.example.com"

trafficAgent:
  intersection:
    name: "intersection_main_st"
    latitude: "37.7749"
    longitude: "-122.4194"
  mqtt:
    host: "smart-intersection-broker"

tls:
  caCert: |
    -----BEGIN CERTIFICATE-----
    MIIDxTCCA...
    -----END CERTIFICATE-----
```

```bash
helm install stia . -n traffic -f values-override.yaml --create-namespace
```

### Example: GPU Deployment

To deploy VLM inference on an Intel GPU (the default), ensure `vlmServing.gpu.enabled` is `true` and the GPU resource name matches your cluster:

```yaml
# values-gpu-override.yaml
vlmServing:
  gpu:
    enabled: true
    # Use "gpu.intel.com/i915" for integrated / Arc A-series
    # Use "gpu.intel.com/xe" for Data Center GPU Flex / Max
    resourceName: "gpu.intel.com/i915"
    resourceLimit: 1
    # All common render group GIDs included by default — works across distros
    renderGroupIds:
      - 44
      - 109
      - 992
  # Optional: pin to GPU nodes
  nodeSelector:
    intel.feature.node.kubernetes.io/gpu: "true"
  persistence:
    keepOnUninstall: true
```

```bash
helm install stia . -n traffic -f values-override.yaml -f values-gpu-override.yaml --create-namespace
```

### Example: CPU-Only Deployment

To run VLM inference on CPU:

```bash
helm install stia . -n traffic -f values-override.yaml \
  --set vlmServing.gpu.enabled=false \
  --create-namespace
```

---

## Verification

- Ensure that all pods are running and the services are accessible.
- Access the Gradio UI and verify that it is showing the traffic intersection dashboard.
- Check the backend API at `/docs` for the interactive Swagger documentation.
- Verify that the traffic agent is receiving MQTT messages from SceneScape by checking the logs:

  ```bash
  kubectl logs -l app=stia-traffic-agent -n <your-namespace> -f
  ```

## Troubleshooting

- If you encounter any issues during the deployment process, check the Kubernetes logs for errors:

  ```bash
  kubectl logs <pod-name> -n <your-namespace>
  ```

- **VLM pod stuck in CrashLoopBackOff:** The model download may have failed. Check logs and verify proxy settings (`global.proxy.httpProxy` / `global.proxy.httpsProxy`) and `huggingfaceToken` if the model requires authentication.

- **VLM model download stuck or not progressing:** Verify that proxy environment variables are correctly set inside the pod. A common cause is a mismatch between `values.yaml` key names and the template references (e.g., `http_proxy` vs `httpProxy`). Check with:

  ```bash
  kubectl exec <vlm-pod-name> -n <your-namespace> -- env | grep -i proxy
  ```

- **`Option not found: INFERENCE_NUM_THREADS` error on GPU:** This occurs when the `OV_CONFIG` contains CPU-only options while running on GPU. Ensure `vlmServing.env.ovConfigGpu` does **not** include `INFERENCE_NUM_THREADS`. The chart automatically selects the correct config (`ovConfigCpu` or `ovConfigGpu`) based on `vlmServing.gpu.enabled`.

- **GPU not detected / VLM pod Pending:** Verify the Intel GPU device plugin is installed and the GPU resource is available:

  ```bash
  kubectl describe node <gpu-node> | grep gpu.intel.com
  ```

  If no GPU resource is listed, install the [Intel GPU device plugin for Kubernetes](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/main/cmd/gpu_plugin/README.md). Also verify that `vlmServing.gpu.resourceName` matches the resource key reported by the device plugin (`gpu.intel.com/i915` for integrated/Arc, `gpu.intel.com/xe` for Data Center GPUs).

- **GPU permission denied (`/dev/dri` access):** The chart includes all common render group GIDs (44, 109, 992) by default. If your distro uses a different GID, find it with `getent group render` on the node and override:
  ```bash
  helm install stia . --set-json 'vlmServing.gpu.renderGroupIds=[<your-gid>]'
  ```

- **Traffic agent cannot connect to MQTT broker:** Verify that the SceneScape deployment is reachable from the cluster, the `trafficAgent.mqtt.host` value is correct, and the CA certificate is provided via `tls.caCert` or `tls.caCertSecretName`.

- **PVC not cleaned up after uninstall:** When `vlmServing.persistence.keepOnUninstall` is `true` (the default), the model cache PVC is intentionally retained. To reclaim storage, delete it manually:

  ```bash
  # List the PVCs present in the given namespace
  kubectl get pvc -n <your-namespace>

  # Delete the required PVC from the namespace
  kubectl delete pvc <pvc-name> -n <your-namespace>
  ```

## Related Links

- [Get Started](../get-started.md)
- [API Reference](https://docs.openedgeplatform.intel.com/2026.0/edge-ai-suites/smart-traffic-intersection-agent/api-reference.html)
- [Release Notes](../release-notes.md)

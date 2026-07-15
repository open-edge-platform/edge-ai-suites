# Deploy with Helm

This guide provides step-by-step instructions for deploying the Smart Traffic Intersection Agent application using Helm.

## Prerequisites

Before you begin, ensure that you have the following prerequisites:

- Kubernetes cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. Refer to the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster.
- Helm installed on your system: [Installation Guide](https://helm.sh/docs/intro/install/).
- A running **Smart Intersection** deployment (provides MQTT broker, camera pipelines, and scene analytics). See [Step 4](#step-5-deploy-smart-intersection) below.
- The Scenescape CA certificate file (`scenescape-ca.pem`) for TLS connections to the MQTT broker (created during the Smart Intersection installation).
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
helm pull oci://registry-1.docker.io/intel/smart-traffic-intersection-agent --version <version-no>
```

Refer to release notes for details on the latest version to use.

#### Step 2: Extract the `.tgz` File

After pulling the chart, extract the `.tgz` file:

```bash
tar -xvf smart-traffic-intersection-agent-<version-no>.tgz
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
# Clone the latest on mainline
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b main
# Alternatively, clone a specific release branch
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b <release-tag>
```

#### Step 2: Change to the Chart Directory

Navigate to the chart directory:

```bash
cd edge-ai-suites/metro-ai-suite/smart-traffic-intersection-agent/chart
```

#### Step 3: Build Chart Dependencies

The OVMS and Metrics Manager components are packaged as local subcharts under `subcharts/`.
Since the generated dependency archives in `charts/` are not committed to the repository, build
them from source before installing:

```bash
helm dependency build .
```

This downloads/packages the `ovms` and `metrics-manager` subcharts into `chart/charts/*.tgz`,
which Helm requires at render/install time. Re-run this command whenever the subchart sources
under `subcharts/` change.

```bash
helm lint .
```

#### Step 4: Configure the `values.yaml` File

Edit the `values.yaml` file located in the chart directory to set the necessary environment variables. Refer to the [values reference table](#valuesyaml-reference) below.

---

## Common Steps After Configuration

### Step 5: Deploy Smart Intersection

The Smart Traffic Intersection Agent depends on a running **Smart Intersection** deployment, which includes [Scenescape](https://github.com/open-edge-platform/scenescape). It provides the MQTT broker, camera pipelines, and scene analytics that the Traffic Agent consumes.

Follow the [Smart Intersection Helm Deployment Guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/smart-intersection/get-started/deploy-with-helm.html) to deploy it. Once all Smart Intersection pods are running and the MQTT broker is reachable, proceed to the next step.

### Step 6: Configure GPU Support (Optional)

By default, the chart deploys VLM inference on an **Intel GPU**. To change graph or verify GPU configuration, edit the following values in `values.yaml`:

| Value | Description | Default |
| --- | --- | --- |
| `ovms.gpu.enabled` | Enable Intel GPU for VLM inference. When `true`, the target device is automatically set to `GPU`. | `true` |
| `ovms.gpu.resourceName` | Kubernetes GPU resource name exposed by the Intel device plugin. Use `gpu.intel.com/i915` for integrated/Arc GPUs, `gpu.intel.com/xe` for Data Center GPU Flex/Max. | `gpu.intel.com/i915` |
| `ovms.gpu.resourceLimit` | Number of GPU devices to request | `1` |
| `ovms.gpu.renderGroupIds` | List of render group GIDs for `/dev/dri` access. Defaults cover all common distros. | `[44, 109, 992]` |
| `ovms.nodeSelector` | Pin VLM pod to nodes with GPUs (e.g., `intel.feature.node.kubernetes.io/gpu: "true"`) | `{}` |

Identify your cluster's GPU resource key by running:

```bash
kubectl describe node <gpu-node> | grep gpu.intel.com
```

To deploy on **CPU instead**, set:

```bash
helm install stia . -n <your-namespace> --create-namespace \
  --set ovms.gpu.enabled=false
```

> **Note:** The `OV_CONFIG` environment variable is automatically set based on the device. When GPU is enabled, CPU-only options like `INFERENCE_NUM_THREADS` are excluded to avoid runtime errors.

### Supported VLM Models

The default model is `OpenVINO/Phi-3.5-vision-instruct-int8-ov`. To use a different model, override it at install time:

```bash
helm install stia . -n <your-namespace> --create-namespace \
  --set ovms.env.modelName=OpenVINO/InternVL2-1B-int4-ov
```

| Model | Structured JSON | Notes |
| --- | --- | --- |
| `OpenVINO/Phi-3.5-vision-instruct-int8-ov` | Good | Default. Pre-converted OpenVINO model; avoids on-cluster Hugging Face export flow. |
| `OpenVINO/InternVL2-1B-int4-ov` | Good | Pre-converted OpenVINO alternative model; avoids on-cluster Hugging Face export flow. |

> **Note:** The OVMS init container downloads and converts the selected model on first startup. Changing the model name requires deleting the existing model cache PVC so the init container re-downloads the new model.

### Step 7: Deploy the Helm Chart

Deploy the Smart Traffic Intersection Agent Helm chart:

```bash
helm install stia . -n <your-namespace> --create-namespace
```

> **Note:** By default, the chart assumes the Smart Intersection RI (MQTT broker) is deployed in the same namespace as the STIA release. If the RI is in a different namespace, add `--set mqtt.brokerNamespace=<ri-namespace>`.

> **Note:** The OVMS init container will download and convert the model on first startup. This may take several minutes depending on network speed and model size. To avoid re-downloading the model on every install cycle, set `ovms.persistence.keepOnUninstall` to `true` (the default). This tells Helm to retain the model cache PVC on uninstall.

### Step 8: Verify the Deployment

Check the status of the deployed resources to ensure everything is running correctly:

```bash
kubectl get pods -n <your-namespace>
kubectl get services -n <your-namespace>
```

You should see these pods:

| Pod | Description |
| --- | ----------- |
| `stia-traffic-agent-*` | The traffic intersection agent (backend + Gradio UI) |
| `stia-ovms-service-*` | The OVMS VLM inference server |
| `<release>-metrics-manager-*` | Metrics Manager for System Telemetry and STIA application metrics |

Wait until all pods show `Running` and `READY 1/1`:

```bash
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=stia -n <your-namespace> --timeout=600s
```

### Step 9: Access the Application

#### Using NodePort (default)

The chart deploys services as `NodePort` by default. Retrieve the allocated ports and a node IP:

```bash
# Get the NodePort values
kubectl get svc stia-traffic-agent -n <your-namespace>

# Find the node where the traffic-agent pod is running
kubectl get pod -n <your-namespace> -o wide | grep traffic-agent
# Use the INTERNAL-IP of that node (see NODE column)
kubectl get nodes -o wide
```

Then open your browser at:

```
http://<node-ip>:<backend-node-port>   # Backend API
http://<node-ip>:<ui-node-port>         # Gradio UI
```

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

### Step 10: Uninstall the Helm Chart

To uninstall the deployed Helm chart:

```bash
helm uninstall stia -n <your-namespace>
```

> **Note:** When `ovms.persistence.keepOnUninstall` is `true` (the default), the VLM model cache PVC is **retained** after uninstall to avoid re-downloading the model. This is recommended during development and testing. To fully clean up all PVCs:
>
> ```bash
> kubectl get pvc -n <your-namespace>
> kubectl delete pvc <pvc-name> -n <your-namespace>
> ```
>
> To have Helm delete the PVC automatically on uninstall, set `ovms.persistence.keepOnUninstall=false` before deploying.

---

## `values.yaml` Reference

### Global Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `global.httpProxy` | HTTP proxy URL | `""` |
| `global.httpsProxy` | HTTPS proxy URL | `""` |
| `global.noProxy` | Comma-separated no-proxy list | `""` |

### Traffic Agent Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `image.repository` | Traffic agent container image repository | `intel/smart-traffic-intersection-agent` |
| `image.tag` | Image tag | `latest` |
| `service.type` | Kubernetes service type (`NodePort` or `ClusterIP`) | `NodePort` |
| `service.backendPort` | Backend API port | `8081` |
| `service.uiPort` | Gradio UI port | `7860` |
| `intersection.name` | Unique intersection identifier | `intersection_1` |
| `intersection.latitude` | Intersection latitude | `37.51358` |
| `intersection.longitude` | Intersection longitude | `-122.25591` |
| `env.logLevel` | Application log level | `INFO` |
| `env.refreshInterval` | Dashboard refresh interval (seconds) | `15` |
| `env.weatherMock` | Use mock weather data (`true`/`false`) | `false` |
| `env.vlmTimeoutSeconds` | Timeout for VLM inference requests (seconds) | `1800` |
| `mqtt.host` | MQTT broker hostname. If set, takes precedence over the constructed FQDN. | `""` |
| `mqtt.serviceName` | MQTT broker K8s service name | `smart-intersection-broker` |
| `mqtt.brokerNamespace` | Namespace where the Smart Intersection RI (MQTT broker) is deployed. Only set this if the RI is in a different namespace than the STIA release. The FQDN is built as `<serviceName>.<brokerNamespace>.svc.cluster.local`. | `""` (defaults to release namespace) |
| `mqtt.port` | MQTT broker port | `1883` |
| `traffic.highDensityThreshold` | Object count for high-density classification | `10` |
| `traffic.moderateDensityThreshold` | Object count for moderate-density classification | `""` |
| `traffic.bufferDuration` | Traffic analysis buffer window | `""` |
| `metrics.managerUrl` | External Metrics Manager API URL. Empty uses the bundled Metrics Manager service. | `""` |
| `metrics.streamUrl` | External Metrics Manager SSE stream URL. Empty uses `<managerUrl>/metrics/stream`. | `""` |
| `metrics.healthUrl` | External Metrics Manager health URL. Empty uses `<managerUrl>/health`. | `""` |
| `metrics.pushEnabled` | Override custom STIA metric publishing. Empty follows `metricsManager.enabled`. | `""` |
| `metrics.pushTimeoutSeconds` | Timeout for best-effort STIA metric publishing | `1.0` |
| `persistence.enabled` | Enable persistent storage for agent data | `true` |
| `persistence.size` | PVC size for agent data | `1Gi` |
| `persistence.storageClass` | Storage class (empty = cluster default) | `""` |

### OVMS (OpenVINO Model Server) Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `ovms.image.repository` | OVMS container image repository | `openvino/model_server` |
| `ovms.image.tag` | Image tag (CPU) | `2026.1` |
| `ovms.image.gpuTag` | Image tag (GPU) | `2026.1-gpu` |
| `ovms.service.type` | Kubernetes service type (`NodePort` or `ClusterIP`) | `NodePort` |
| `ovms.service.port` | OVMS HTTP API port | `8000` |
| `ovms.env.modelName` | Hugging Face/OpenVINO model identifier | `OpenVINO/Phi-3.5-vision-instruct-int8-ov` |
| `ovms.env.targetDevice` | Inference device when GPU is disabled (`CPU`). Ignored when `ovms.gpu.enabled=true` (auto-set to `GPU`). | `CPU` |
| `ovms.env.weightFormat` | Model weight format (`int4`, `int8`). Empty = auto-detect based on device. | `""` |
| `ovms.env.maxCompletionTokens` | Max tokens per completion | `1500` |
| `ovms.env.logLevel` | OVMS log level | `INFO` |
| `ovms.huggingfaceToken` | Hugging Face API token (stored as a Secret) | `""` |
| `ovms.gpu.enabled` | Enable Intel GPU for VLM inference. Auto-sets target device to `GPU`. | `true` |
| `ovms.gpu.resourceName` | Kubernetes GPU resource name exposed by the Intel device plugin (`gpu.intel.com/i915` or `gpu.intel.com/xe`) | `gpu.intel.com/i915` |
| `ovms.gpu.resourceLimit` | Number of GPU devices to request | `1` |
| `ovms.gpu.renderGroupIds` | List of GIDs for the `render` group added to `supplementalGroups` for `/dev/dri` access. All common distro values are included by default (44, 109, 992). | `[44, 109, 992]` |
| `ovms.nodeSelector` | Pin VLM pod to GPU nodes (e.g., `intel.feature.node.kubernetes.io/gpu: "true"`) | `{}` |
| `ovms.persistence.enabled` | Enable persistent storage for model cache | `true` |
| `ovms.persistence.size` | PVC size for model cache | `20Gi` |
| `ovms.persistence.storageClass` | Storage class (empty = cluster default) | `""` |
| `ovms.persistence.keepOnUninstall` | Retain PVC on `helm uninstall` to avoid re-downloading the model | `true` |

### TLS / Secrets Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `tls.caCert` | PEM-encoded CA certificate for the MQTT broker (base64-encoded in the Secret) | `""` |
| `tls.caCertSecretName` | Name of an existing Secret containing the CA cert (overrides `tls.caCert`). The Smart Intersection RI (release-2026.0.0) creates `smart-intersection-ca-secret`. | `smart-intersection-ca-secret` |
| `tls.caCertKey` | Key name inside the external secret (required when `caCertSecretName` is set) | `root-cert` |

### Metrics Manager Settings

Metrics Manager provides the UI **System Telemetry** stream and accepts STIA application metrics.
Keys are nested under `metricsManager` (camelCase — no hyphen).

| Key | Description | Default |
| --- | ----------- | ------- |
| `metricsManager.enabled` | Deploy Metrics Manager | `true` |
| `metricsManager.service.metricsPort` | Metrics Manager API and `/metrics/stream` port | `9090` |
| `metricsManager.service.telegrafPort` | Telegraf Prometheus metrics port | `9273` |
| `metricsManager.service.telegrafHttpPort` | Telegraf HTTP listener port for custom metrics | `8186` |
| `metricsManager.hardware.gpu.enabled` | Enable Intel GPU telemetry through `/dev/dri` | `true` |
| `metricsManager.pod.hostPID` | Enable host process namespace access for host telemetry | `true` |
| `metricsManager.securityContext.privileged` | Enable privileged access for NPU telemetry on trusted nodes | `false` |

> **Security/runtime note:** Host telemetry may require the Metrics Manager pod to run with
> `hostPID` and hostPath mounts such as `/sys`, `/run`, and `/dev/dri`. Intel NPU telemetry
> may additionally require `metricsManager.securityContext.privileged=true`. Enable elevated
> deployment-time permissions only on trusted nodes and in accordance with your cluster security
> policy.

> **Note — using an external Metrics Manager:** If you set `metricsManager.enabled=false` to skip
> deploying the bundled Metrics Manager, also set `metrics.managerUrl` (and optionally
> `metrics.streamUrl` / `metrics.healthUrl`) to point at your external instance. Otherwise the
> traffic-agent keeps its default URLs pointed at the (now-absent) bundled service, so the UI
> **System Telemetry** stream and health checks will fail. Custom STIA metric publishing is
> automatically disabled when Metrics Manager is disabled unless you override `metrics.pushEnabled`.

---

## Example: Minimal Deployment

```yaml
# values-override.yaml
global:
  httpProxy: "http://proxy.example.com:8080"
  httpsProxy: "http://proxy.example.com:8080"
  noProxy: "localhost,127.0.0.1,10.0.0.0/8,.example.com"

intersection:
  name: "intersection_main_st"
  latitude: "37.7749"
  longitude: "-122.4194"

mqtt:
  brokerNamespace: ""  # defaults to release namespace; set only if RI is in a different namespace

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

To deploy VLM inference on an Intel GPU (the default), ensure `ovms.gpu.enabled` is `true` and the GPU resource name matches your cluster:

```yaml
# values-gpu-override.yaml
ovms:
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
  --set ovms.gpu.enabled=false \
  --create-namespace
```

---

## Deploy with Trusted Compute

Intel Trusted Compute runs workloads inside a hardware-isolated virtual machine, providing an additional layer of security for sensitive AI workloads.

> **Note:** GPU acceleration is currently not supported when deploying with Trusted Compute.

### 1. Install Trusted Compute

Follow the [Trusted Compute baremetal installation guide](https://github.com/open-edge-platform/trusted-compute/blob/main/docs/trusted_compute_baremetal.md) to install Trusted Compute runtime version 1.5.0 on your Kubernetes nodes. Complete the following sections:
1. Prerequisites
2. Download the Trusted Compute Package
3. Kubernetes Option

> **Note:** Trusted Compute version 1.5.0 is required for this deployment.

### 2. Deploy with Trusted Compute

Deploy the Smart Traffic Intersection Agent with Trusted Compute enabled by adding the `--set ovms.trustedCompute.enabled=true` and `--set ovms.gpu.enabled=false` flags to the helm command:

```bash
helm install stia . -n <your-namespace> --create-namespace \
  --set ovms.trustedCompute.enabled=true \
  --set ovms.gpu.enabled=false
```

The OVMS VLM serving pods will run inside hardware-isolated Trusted Compute VMs, protecting inference workloads and model data from untrusted co-tenants on the same host.

> **Note:** When Trusted Compute is enabled, the OVMS VLM serving service type is automatically set to `ClusterIP` instead of the default `NodePort`. This restricts the model server to in-cluster access only, ensuring the inference endpoint is not externally exposed. To access the OVMS service for debugging, use `kubectl port-forward`.

> **Note:** All other setup and configuration steps remain the same as described in the [Steps to Deploy with Helm](#steps-to-deploy-with-helm) section above.

### 3. Verify Trusted Compute Deployment

Verify that the pods are running with the Trusted Compute runtime:

```bash
# Check that OVMS pods are using the trusted compute runtime class
kubectl get pods -n <your-namespace> -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.runtimeClassName}{"\n"}{end}' | grep ovms

# Verify the pods are running
kubectl get pods -n <your-namespace>

# Check OVMS pod logs to ensure containers started successfully
kubectl logs -n <your-namespace> -l app=stia-ovms-service
```

You should see the OVMS VLM serving pods running with the Trusted Compute runtime class.

---

## Verification

- Ensure that all pods are running and the services are accessible.
- Access the Gradio UI and verify that it is showing the traffic intersection dashboard.
- Check the backend API at `/docs` for the interactive Swagger documentation.
- Verify that the traffic agent is receiving MQTT messages from Scenescape by checking the logs:

  ```bash
  kubectl logs -l app=stia-traffic-agent -n <your-namespace> -f
  ```

## Troubleshooting

- If you encounter any issues during the deployment process, check the Kubernetes logs for errors:

  ```bash
  kubectl logs <pod-name> -n <your-namespace>
  ```

- **VLM pod stuck in CrashLoopBackOff:** The model download may have failed. Check logs and verify proxy settings (`global.httpProxy` / `global.httpsProxy`) and `huggingfaceToken` if the model requires authentication.

- **VLM model download stuck or not progressing:** Verify that proxy environment variables are correctly set inside the pod. A common cause is a mismatch between `values.yaml` key names and the template references (e.g., `http_proxy` vs `httpProxy`). Check with:

  ```bash
  kubectl exec <ovms-pod-name> -n <your-namespace> -- env | grep -i proxy
  ```

- **GPU not detected / VLM pod Pending:** Verify the Intel GPU device plugin is installed and the GPU resource is available:

  ```bash
  kubectl describe node <gpu-node> | grep gpu.intel.com
  ```

  If no GPU resource is listed, install the [Intel GPU device plugin for Kubernetes](https://github.com/intel/intel-device-plugins-for-kubernetes/blob/main/cmd/gpu_plugin/README.md). Also verify that `ovms.gpu.resourceName` matches the resource key reported by the device plugin (`gpu.intel.com/i915` for integrated/Arc, `gpu.intel.com/xe` for Data Center GPUs).

- **GPU permission denied (`/dev/dri` access):** The chart includes all common render group GIDs (44, 109, 992) by default. If your distro uses a different GID, find it with `getent group render` on the node and override:

  ```bash
  helm install stia . --set-json 'ovms.gpu.renderGroupIds=[<your-gid>]'
  ```

- **Traffic agent cannot connect to MQTT broker:** Verify that the Scenescape deployment is reachable from the cluster, the `mqtt.host` value is correct, and the CA certificate is provided via `tls.caCert` or `tls.caCertSecretName`.

- **System Telemetry metrics are missing:** Verify the Metrics Manager pod is running and check its logs. Then port-forward its API and Prometheus ports to test `/health` and Telegraf metrics:

  ```bash
  kubectl get pods -n <your-namespace> | grep metrics-manager
  kubectl logs <metrics-manager-pod-name> -n <your-namespace>
  kubectl port-forward <metrics-manager-pod-name> 9090:9090 9273:9273 -n <your-namespace>
  curl -fsS http://127.0.0.1:9090/health
  curl -fsS http://127.0.0.1:9273/metrics | head
  ```

- **PVC not cleaned up after uninstall:** When `ovms.persistence.keepOnUninstall` is `true` (the default), the model cache PVC is intentionally retained. To reclaim storage, delete it manually:

  ```bash
  # List the PVCs present in the given namespace
  kubectl get pvc -n <your-namespace>

  # Delete the required PVC from the namespace
  kubectl delete pvc <pvc-name> -n <your-namespace>
  ```

## Clean Up the Trusted Compute Deployment

To uninstall Trusted Compute from the Kubernetes nodes after you have removed the application, refer to the [Trusted Compute documentation](https://github.com/open-edge-platform/trusted-compute/blob/main/docs/trusted_compute_baremetal.md).

## Related Links

- [Get Started](../get-started.md)
- [API Reference](../api-reference.md)
- [Release Notes](../release-notes.md)

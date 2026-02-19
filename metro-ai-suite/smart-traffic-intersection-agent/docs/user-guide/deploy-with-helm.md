# How to Deploy with Helm

This guide provides step-by-step instructions for deploying the Smart Traffic Intersection Agent application using Helm.

## Prerequisites

Before you begin, ensure that you have the following prerequisites:

- Kubernetes cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. Refer to the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster.
- Helm installed on your system: [Installation Guide](https://helm.sh/docs/intro/install/).
- A running [SceneScape](https://github.com/open-edge-platform/scenescape) deployment reachable from the cluster (provides the MQTT broker, camera pipelines and scene analytics).
- The SceneScape CA certificate file (`scenescape-ca.pem`) for TLS connections to the MQTT broker.
- *(Optional)* A [Hugging Face](https://huggingface.co/) API token if the VLM model requires authentication.

## Steps to Deploy with Helm

The following steps walk through deploying the Smart Traffic Intersection Agent application using Helm. You can install from source code or pull the chart from a registry.

**_Steps 1 to 3 vary depending on whether you prefer to build or pull the Helm chart._**

### Option 1: Install from a Registry

#### Step 1: Pull the Chart

Use the following command to pull the Helm chart:

```bash
helm pull oci://registry-1.docker.io/intel/smart-traffic-intersection-agent --version <version-no>
```

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
git clone https://github.com/open-edge-platform/edge-ai-suites.git
# Alternatively, clone a specific release branch
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b <release-tag>
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

### Step 4: Deploy the Helm Chart

Deploy the Smart Traffic Intersection Agent Helm chart:

```bash
helm install stia . -n <your-namespace> --create-namespace
```

> **Note:** The VLM OpenVINO Serving pod will download and convert the model on first startup. This may take several minutes depending on network speed and model size.

### Step 5: Verify the Deployment

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

### Step 6: Access the Application

#### Using Port-Forward (ClusterIP — default)

```bash
# Traffic Agent Backend API
kubectl port-forward svc/stia-traffic-agent 8081:8081 -n <your-namespace> &

# Traffic Agent Gradio UI
kubectl port-forward svc/stia-traffic-agent 7860:7860 -n <your-namespace> &
```

Then open your browser at:

- **Backend API:** `http://127.0.0.1:8081/docs`
- **Gradio UI:** `http://127.0.0.1:7860`

#### Using NodePort

If you changed the service type to `NodePort` in `values.yaml`:

```bash
# Get the NodePort values
kubectl get svc stia-traffic-agent -n <your-namespace>

# Get the node IP
kubectl get nodes -o wide
# Use the INTERNAL-IP of any node

# Access via browser
http://<node-ip>:<backend-node-port>
http://<node-ip>:<ui-node-port>
```

### Step 7: Uninstall the Helm Chart

To uninstall the deployed Helm chart:

```bash
helm uninstall stia -n <your-namespace>
```

> **Note:** PersistentVolumeClaims (PVCs) are not automatically deleted on uninstall. To reclaim storage, delete them manually:
>
> ```bash
> kubectl get pvc -n <your-namespace>
> kubectl delete pvc <pvc-name> -n <your-namespace>
> ```

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
| `trafficAgent.image.repository` | Traffic agent container image repository | `smart-traffic-intersection-agent` |
| `trafficAgent.image.tag` | Image tag | `latest` |
| `trafficAgent.service.type` | Kubernetes service type (`ClusterIP` or `NodePort`) | `ClusterIP` |
| `trafficAgent.service.backendPort` | Backend API port | `8081` |
| `trafficAgent.service.uiPort` | Gradio UI port | `7860` |
| `trafficAgent.intersection.name` | Unique intersection identifier | `intersection_1` |
| `trafficAgent.intersection.latitude` | Intersection latitude | `37.51358` |
| `trafficAgent.intersection.longitude` | Intersection longitude | `-122.25591` |
| `trafficAgent.env.logLevel` | Application log level | `INFO` |
| `trafficAgent.env.refreshInterval` | Dashboard refresh interval (seconds) | `15` |
| `trafficAgent.env.weatherMock` | Use mock weather data (`true`/`false`) | `false` |
| `trafficAgent.mqtt.host` | MQTT broker hostname (SceneScape) | `broker.scenescape.intel.com` |
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
| `vlmServing.service.port` | VLM HTTP API port | `8000` |
| `vlmServing.env.modelName` | Hugging Face model identifier | `Qwen/Qwen2.5-VL-3B-Instruct` |
| `vlmServing.env.compressionWeightFormat` | Model weight format (`int4`, `int8`, `fp16`) | `int4` |
| `vlmServing.env.device` | OpenVINO inference device (`CPU` or `GPU`) | `CPU` |
| `vlmServing.env.maxCompletionTokens` | Max tokens per completion | `1500` |
| `vlmServing.env.workers` | Number of serving workers | `1` |
| `vlmServing.huggingfaceToken` | Hugging Face API token (stored as a Secret) | `""` |
| `vlmServing.gpu.enabled` | Request Intel GPU resources | `false` |
| `vlmServing.gpu.resourceName` | Kubernetes GPU resource name | `gpu.intel.com/i915` |
| `vlmServing.gpu.resourceLimit` | Number of GPU devices to request | `1` |
| `vlmServing.persistence.enabled` | Enable persistent storage for model cache | `true` |
| `vlmServing.persistence.size` | PVC size for model cache | `20Gi` |
| `vlmServing.persistence.storageClass` | Storage class (empty = cluster default) | `""` |

### TLS / Secrets Settings

| Key | Description | Default |
| --- | ----------- | ------- |
| `tls.caCert` | PEM-encoded CA certificate for the MQTT broker (base64-encoded in the Secret) | `""` |
| `tls.caCertSecretName` | Name of an existing Secret containing the CA cert (overrides `tls.caCert`) | `""` |

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
    host: "broker.scenescape.intel.com"

tls:
  caCert: |
    -----BEGIN CERTIFICATE-----
    MIIDxTCCA...
    -----END CERTIFICATE-----
```

```bash
helm install stia . -n traffic -f values-override.yaml --create-namespace
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

- **VLM pod stuck in CrashLoopBackOff:** The model download may have failed. Check logs and verify proxy settings and `huggingfaceToken` if the model requires authentication.

- **Traffic agent cannot connect to MQTT broker:** Verify that the SceneScape deployment is reachable from the cluster, the `trafficAgent.mqtt.host` value is correct, and the CA certificate is provided via `tls.caCert` or `tls.caCertSecretName`.

- **PVC not cleaned up after failed deployment:** PersistentVolumeClaims are not auto-deleted. Remove them manually:

  ```bash
  # List the PVCs present in the given namespace
  kubectl get pvc -n <your-namespace>

  # Delete the required PVC from the namespace
  kubectl delete pvc <pvc-name> -n <your-namespace>
  ```

## Related Links

- [Get Started](./get-started.md)
- [API Reference](./api-reference.md)
- [Release Notes](./release-notes.md)

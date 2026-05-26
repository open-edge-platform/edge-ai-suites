# How to deploy with Helm\* Chart

This section shows how to deploy the Live Video Search sample application using Helm chart.

## Prerequisites

Before you begin, ensure that you have the following:

- Kubernetes\* cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. See the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster.
- Helm installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).
- **Storage Requirement:** Ensure enough storage is available in the cluster for PVC-backed services.

See also: [System Requirements](./system-requirements.md).

## Helm Chart Installation

To set up the end-to-end application, acquire the chart and install it with the required values and scenario overrides.

### 1. Acquire the Helm chart

There are 2 options to get the charts in your workspace:

#### Option 1: Get the charts from Docker Hub

##### Step 1: Pull the specific chart

Use the following command to pull the Helm chart from Docker Hub:

```bash
helm pull oci://registry-1.docker.io/intel/live-video-search --version <version-no>
```

Refer to release notes for details on the latest version to use.

##### Step 2: Extract the `.tgz` file

After pulling the chart, extract the `.tgz` file:

```bash
tar -xvf live-video-search-<version-no>.tgz
```

This creates a directory named `live-video-search` containing chart files. Navigate to the extracted directory:

```bash
cd live-video-search
```

#### Option 2: Install from Source

Clone the repository and navigate to the chart directory:

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites -b main
cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-search/chart
```

### 2. Configure Required Values

The application requires a few user-provided values. Use `user_values_override.yaml` as the single user-edit file:

```bash
nano user_values_override.yaml
```

Update these required values:

| Key | Description | Example Value |
| --- | ----------- | ------------- |
| `global.credentials.minioRootUser` | MinIO user | `<your-minio-user>` |
| `global.credentials.minioRootPassword` | MinIO password | `<your-minio-password>` |
| `global.credentials.postgresUser` | PostgreSQL user | `<your-postgres-user>` |
| `global.credentials.postgresPassword` | PostgreSQL password | `<your-postgres-password>` |
| `global.credentials.mqttUser` | MQTT user | `<your-mqtt-user>` |
| `global.credentials.mqttPassword` | MQTT password | `<your-mqtt-password>` |
| `global.env.embeddingModelName` | Embedding model used by search stack | `CLIP/clip-vit-b-32` |

Common optional values:

| Key | Description | Example Value |
| --- | ----------- | ------------- |
| `global.registry` | Optional image registry override | `intel` |
| `global.tag` | Shared image tag | `latest` |
| `global.vssStackTag` | Override tag for VSS stack services | `1.3.2` |
| `global.smartNvrStackTag` | Override tag for Smart NVR services | `1.2.4` |
| `global.proxy.httpProxy` | HTTP proxy | `http://proxy-example.com:000` |
| `global.proxy.httpsProxy` | HTTPS proxy | `http://proxy-example.com:000` |
| `global.usePvc` | Use PVC-backed storage paths for MME/DataPrep | `true` or `false` |
| `global.keepPvc` | Retain PVCs on uninstall | `true` or `false` |
| `global.gpu.multimodalEmbeddingEnabled` | Enable MME on GPU | `true` or `false` |
| `global.gpu.vdmsDataprepEnabled` | Enable DataPrep on GPU | `true` or `false` |
| `global.gpu.key` | GPU resource key from device plugin | `gpu.intel.com/xe` / `gpu.intel.com/i915` |
| `global.gpu.device` | Device mode for GPU deployment | `GPU` |
| `frigate.usbCameraDevice` | USB device path (used with USB profile) | `/dev/video0` |

> **Note:** Scenario selection is profile-driven. Use override profiles for mode switching (`default_override.yaml`, `rtsp_test_override.yaml`, `usb_camera_override.yaml`) instead of setting mode switches in `user_values_override.yaml`.

> **Tag Resolution Note:** `global.tag` is the fallback image tag. If `global.vssStackTag` is non-empty, VSS-side services use it instead of `global.tag`. If `global.smartNvrStackTag` is non-empty, Smart NVR-side services use it instead of `global.tag`. Leaving stack-specific tags empty makes those services inherit `global.tag`.

> **Device Note:** `global.env.embeddingDevice` defaults to `CPU` in chart values and is internally resolved for non-GPU mode.

> **GPU Note:** If enabling GPU for search embeddings, set both `global.gpu.multimodalEmbeddingEnabled=true` and `global.gpu.vdmsDataprepEnabled=true`, and also set `global.gpu.key` and `global.gpu.device`.

### 3. Build Helm Dependencies

Run from the chart directory:

```bash
helm dependency build
```

### 4. Set and Create a Namespace

1. Set a namespace variable:

   ```bash
   my_namespace=lvs
   ```

2. Create namespace:

   ```bash
   kubectl create namespace $my_namespace
   ```

> **_NOTE:_** All subsequent steps assume `my_namespace` is set in your shell.

### 5. Deploy the Helm Chart

Deploy one of the following use cases.

> **Note:** Before switching use cases, uninstall the existing release if it is already running:
> `helm uninstall lvs -n $my_namespace`

#### Use Case 1: Default Live Video Search

```bash
helm install lvs . -f user_values_override.yaml -f default_override.yaml -n $my_namespace
```

#### Use Case 2: RTSP Test Mode

```bash
helm install lvs . -f user_values_override.yaml -f rtsp_test_override.yaml -n $my_namespace
```

#### Use Case 3: USB Camera Mode

```bash
helm install lvs . -f user_values_override.yaml -f usb_camera_override.yaml -n $my_namespace
```

#### Use Case 4: GPU-enabled MME + DataPrep

First update `user_values_override.yaml`:

- `global.gpu.multimodalEmbeddingEnabled: true`
- `global.gpu.vdmsDataprepEnabled: true`
- `global.gpu.key: <gpu-resource-key>`
- `global.gpu.device: GPU`

Then deploy with your selected scenario profile (example: default):

```bash
helm install lvs . -f user_values_override.yaml -f default_override.yaml -n $my_namespace
```

### Step 6: Verify the Deployment

```bash
kubectl get pods -n $my_namespace
kubectl get svc -n $my_namespace
```

Before proceeding, ensure:

1. Pods are in `Running` state.
2. Containers are in ready state.

> **Note:** `init-resources` runs as a Kubernetes Job. Its pod can show `0/1 Completed` (for example, `lvs-live-video-search-init-resources-xxxxx 0/1 Completed`), which is expected. Use `kubectl get jobs -n $my_namespace` and confirm `lvs-live-video-search-init-resources` shows `COMPLETIONS 1/1` and `STATUS Complete`.

If needed, inspect specific workloads:

```bash
kubectl describe pod <pod-name> -n $my_namespace
kubectl logs <pod-name> -n $my_namespace
```

### Step 7: Accessing the application

Nginx service runs as a reverse proxy in one of the pods and is exposed via NodePort by default. Get the host IP and NodePort using:

```bash
lvs_hostip=$(kubectl get pods -l app=nginx -n $my_namespace -o jsonpath='{.items[0].status.hostIP}')
lvs_port=$(kubectl get service nginx -n $my_namespace -o jsonpath='{.spec.ports[0].nodePort}')
echo "http://${lvs_hostip}:${lvs_port}"
```

Copy the printed URL and open it in your browser to access the **Live Video Search Application**.

If you prefer local access without NodePort:

```bash
kubectl port-forward svc/nginx 12345:80 -n $my_namespace
```

Open `http://localhost:12345`.

### Step 8: Update Helm Dependencies

If subchart dependencies change:

```bash
helm dependency build
```

### Step 9: Uninstall Helm chart

```bash
helm uninstall lvs -n $my_namespace
```

PVC retention on uninstall is controlled by `global.keepPvc`.

When `global.keepPvc: true`, PVC-backed data is retained across uninstall/reinstall and pod restarts. This includes persisted application state (for example, stored query-related data in backing services) and converted OpenVINO model assets stored on persistent volumes.

If you want a clean reset, delete all PVCs for the `lvs` release:

```bash
kubectl delete pvc -n "$my_namespace" -l app.kubernetes.io/instance=lvs
```

## Troubleshooting

- **Pods stay Pending or not Ready:**
  Check storage provisioning, node capacity, and device plugin availability (for GPU mode).

- **Node allocation/scheduling issues caused by PVC affinity conflicts (often from old PVCs):**
  Delete old release PVCs and redeploy:

  ```bash
  kubectl delete pvc -n "$my_namespace" -l app.kubernetes.io/instance=lvs
  ```

- **Search not returning expected results:**
  Verify `global.env.embeddingModelName` and confirm clips are ingested.

- **USB mode does not detect camera:**
  Confirm device path and override `frigate.usbCameraDevice` in `user_values_override.yaml` when not using `/dev/video0`.

- **GPU deployment fails validation:**
  Ensure both MME and DataPrep GPU flags are aligned, and both `global.gpu.key` and `global.gpu.device` are set.

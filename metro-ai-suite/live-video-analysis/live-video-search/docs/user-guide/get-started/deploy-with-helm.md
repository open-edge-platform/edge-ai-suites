# Deploy with Helm\* Chart

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
helm pull oci://registry-1.docker.io/intel/live-video-search --version 2026.2.0-rc1-helm
```

Use chart version `2026.2.0-rc1-helm` for this release workflow.

##### Step 2: Extract the `.tgz` file

After pulling the chart, extract the `.tgz` file:

```bash
tar -xvf live-video-search-2026.2.0-rc1-helm.tgz
```

This creates a directory named `live-video-search` containing chart files. Navigate to the extracted directory:

```bash
cd live-video-search
```

#### Option 2: Install from Source

Clone the repository and navigate to the chart directory:

```bash
# Clone the release branch
git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites -b release-2026.2.0
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
| `global.tag` | Shared image tag | `2026.2.0-rc1` |
| `global.vssStackTag` | Override tag for VSS stack services | `2026.2.0-rc1` |
| `global.smartNvrStackTag` | Override tag for Smart NVR services | `2026.2.0-rc1` |
| `global.pullPolicy` | Pull-policy override for application images selected by the shared or stack-specific tags | `Always`, `IfNotPresent`, or `Never` |
| `global.vectordbBackend` | Vector database used by Multimodal DataPrep and Vector Retriever | `vdms` (default) or `milvus` |
| `global.metricsManager.enabled` | Deploy Metrics Manager and enable live system/DataPrep metrics | `true` (default) or `false` |
| `metrics-manager.image.repository` | Metrics Manager image repository | `intel/metrics-manager` |
| `metrics-manager.image.tag` | Metrics Manager image tag | `2026.2.0-rc1` |
| `global.proxy.httpProxy` | HTTP proxy | `http://proxy-example.com:000` |
| `global.proxy.httpsProxy` | HTTPS proxy | `http://proxy-example.com:000` |
| `global.usePvc` | Use PVC-backed storage paths for MME/DataPrep | `true` or `false` |
| `global.keepPvc` | Retain PVCs on uninstall | `true` or `false` |
| `global.devices.multimodalEmbedding.device` | MME embedding execution device | `CPU`, `GPU`, or `NPU` |
| `global.devices.multimodalEmbedding.key` | MME accelerator key (required when device=GPU/NPU) | `gpu.intel.com/xe`, `gpu.intel.com/i915`, or `npu.intel.com/accel` |
| `global.devices.multimodalDataprep.embedding.device` | DataPrep indexing-embedding device | `CPU`, `GPU`, or `NPU` |
| `global.devices.multimodalDataprep.embedding.key` | DataPrep embedding accelerator key (required when embedding.device=GPU/NPU) | `gpu.intel.com/xe`, `gpu.intel.com/i915`, or `npu.intel.com/accel` |
| `global.devices.multimodalDataprep.detection.device` | DataPrep detection execution device | `CPU`, `GPU`, or `NPU` |
| `global.devices.multimodalDataprep.detection.key` | DataPrep detection accelerator key (required when detection.device=GPU/NPU) | `gpu.intel.com/xe`, `gpu.intel.com/i915`, or `npu.intel.com/accel` |
| `global.accelGroupIds` | Host group ids owning the accelerator device nodes (`/dev/dri`, `/dev/accel`); added to the pod `supplementalGroups` when a service uses GPU/NPU | `[992]` |
| `frigate.usbCameraDevice` | USB device path (used with USB profile) | `/dev/video0` |

> **Note:** Scenario selection is profile-driven. Use override profiles for mode switching (`default_override.yaml`, `rtsp_test_override.yaml`, `usb_camera_override.yaml`) instead of setting mode switches in `user_values_override.yaml`.

> **Tag Resolution Note:** `global.tag` is the fallback image tag. If `global.vssStackTag` is non-empty, VSS-side services use it instead of `global.tag`. If `global.smartNvrStackTag` is non-empty, Smart NVR-side services use it instead of `global.tag`. Leaving stack-specific tags empty makes those services inherit `global.tag`.

> **Pull Policy Note:** Leaving `global.pullPolicy` empty preserves each subchart's default. Values are case-insensitive and normalized to Kubernetes' canonical spelling. Setting it overrides the pull policy for Pipeline Manager, Video Search, VSS UI, Multimodal DataPrep, Multimodal Embedding Serving, Vector Retriever, and NVR Event Router. Third-party infrastructure images retain their component-specific policies.

> **Device Note:** All device selection is per-component via the `global.devices.*` block. Each component defaults to `CPU` and requires its matching `key` only when set to `GPU` or `NPU`.

> **Accelerator Note:** Multimodal DataPrep creates indexing embeddings in-process and uses `global.devices.multimodalDataprep.*`. MME uses `global.devices.multimodalEmbedding.*` for query embeddings requested by Vector Retriever.

> **Device Permissions Note:** When a component runs on GPU or NPU, its host accelerator nodes (`/dev/dri` for GPU, `/dev/accel` for NPU) are mounted and the gids in `global.accelGroupIds` are added to the pod `supplementalGroups` so the non-root container user can open the device. These gids are host-specific — check the target node with `ls -ln /dev/accel` and `ls -ln /dev/dri` and override `global.accelGroupIds` to match (default `[992]`).

> **OpenVINO Cache Note:** On GPU/NPU, MME and DataPrep write the first-time OpenVINO model compilation to `ovCacheDir` (default `/app/ov_models/ov_cache`) on the persistent models mount, so the compile is reused across pod restarts instead of recompiling on every start.

> **Storage Note:** MME and DataPrep now use independent PVCs (`<release>-live-video-search-mmes-models-pvc` and `<release>-live-video-search-dataprep-models-pvc`, with per-service `*-data-pvc` fallback), so they are no longer coupled through a shared PVC.

> **Metrics Manager Note:** Metrics Manager runs with host PID access,
> privileged device access, and read-only `/sys` and `/run` mounts so it can
> collect host metrics. It does not use or share a PVC. Multimodal DataPrep
> publishes throughput metrics directly to `metrics-manager:9090`; NGINX exposes
> only the health and SSE stream endpoints to the UI. Publishing is non-blocking,
> so ingestion continues if Metrics Manager becomes unavailable. The bundled
> DataPrep image must support `MM_DATAPREP_METRICS_MANAGER_URL`.

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

#### Use Case 4: Accelerator-enabled MME + DataPrep (GPU or NPU)

First update `user_values_override.yaml`:

- `global.devices.multimodalEmbedding.device: GPU|NPU`
- `global.devices.multimodalEmbedding.key: <accelerator-resource-key>` (for example `gpu.intel.com/xe` or `npu.intel.com/accel`)
- `global.devices.multimodalDataprep.embedding.device: GPU|NPU`
- `global.devices.multimodalDataprep.embedding.key: <accelerator-resource-key>`
- `global.devices.multimodalDataprep.detection.device: GPU|NPU`
- `global.devices.multimodalDataprep.detection.key: <accelerator-resource-key>`
- `global.accelGroupIds: [<gid>]` (host gids owning `/dev/dri` and `/dev/accel`; check the target node with `ls -ln /dev/accel` and `ls -ln /dev/dri`)

Then deploy with your selected scenario profile (example: default):

```bash
helm install lvs . -f user_values_override.yaml -f default_override.yaml -n $my_namespace
```

#### Use Case 5: Milvus Vector Database

Milvus uses the same application and camera profiles. Add `milvus_override.yaml` after the selected scenario override:

```bash
helm install lvs . -f user_values_override.yaml -f default_override.yaml -f milvus_override.yaml -n $my_namespace
```

The override sets `global.vectordbBackend: milvus`, disables the VDMS workload, and enables the pinned Milvus standalone and etcd workloads. Vector Retriever automatically selects the `vector-retriever-milvus` image. Without this override, the chart deploys VDMS and `vector-retriever-vdms`.

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

When metrics are enabled, verify the same-origin endpoints through NGINX:

```bash
kubectl get pods -n $my_namespace -l app.kubernetes.io/name=metrics-manager
kubectl port-forward svc/nginx 12345:80 -n $my_namespace
curl http://localhost:12345/metrics-manager/health
curl -N -H "Accept: text/event-stream" \
  http://localhost:12345/metrics-manager/metrics/stream
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
  Check storage provisioning, node capacity, and device plugin availability (for GPU/NPU accelerator mode).

- **Node allocation/scheduling issues caused by PVC affinity conflicts (often from old PVCs):**
  Delete old release PVCs and redeploy:

  ```bash
  kubectl delete pvc -n "$my_namespace" -l app.kubernetes.io/instance=lvs
  ```

- **`VolumeBinding` "object has been modified" warning during scheduling:**
  A one-off `FailedScheduling ... running PreBind plugin "VolumeBinding": ... the object has been modified` warning that is immediately followed by a successful `Scheduled` event is a transient optimistic-lock retry and is safe to ignore — it self-heals on the scheduler's next attempt. The MME and DataPrep pods now reference each model PVC through a single volume, so this should no longer recur. If a pod stays `Pending` and the warning repeats indefinitely, treat it as a real failure: check that the model PVC is `Bound` (`kubectl get pvc -n "$my_namespace"`) and that the `WaitForFirstConsumer` storage class can provision on the target node.

- **Search not returning expected results:**
  Verify `global.env.embeddingModelName`, confirm clips are ingested, and check that Vector Retriever is ready with the same backend selected by `global.vectordbBackend`.

- **Live metrics are not displayed:**
  Confirm `global.metricsManager.enabled` is `true`, the Metrics Manager pod is
  ready, and `kubectl logs deployment/metrics-manager -n "$my_namespace"` does
  not report missing host access.

- **USB mode does not detect camera:**
  Confirm device path and override `frigate.usbCameraDevice` in `user_values_override.yaml` when not using `/dev/video0`.

- **Accelerator deployment fails validation:**
  Verify the required key is set for each accelerator path (`global.devices.multimodalEmbedding.key` for MME, `global.devices.multimodalDataprep.embedding.key` / `global.devices.multimodalDataprep.detection.key` for DataPrep) whenever the matching device is set to `GPU` or `NPU`.

- **Accelerator pod cannot access the device (NPU/GPU init fails):**
  Confirm `global.accelGroupIds` matches the host gids owning `/dev/accel` (NPU) and `/dev/dri` (GPU) on the scheduled node (`ls -ln /dev/accel`, `ls -ln /dev/dri`). The non-root container needs these in its `supplementalGroups` to open the device.

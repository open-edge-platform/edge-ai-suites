# Deploy with Helm

This section shows how to deploy the Live Video Alert Agent using the Helm chart.

## Prerequisites

Before you begin, ensure that you have the following:

- Kubernetes* cluster set up and running.
- The cluster must support **dynamic provisioning of Persistent Volumes (PV)**. Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for more details.
- Install `kubectl` on your system. See the [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/). Ensure access to the Kubernetes cluster.
- Helm installed on your system. See the [Installation Guide](https://helm.sh/docs/intro/install/).
- **Storage Requirement:** The chart creates a **10 Gi** PVC for the VLM model on first run.


## Helm Chart Installation

### 1. Acquire the Helm chart

#### Option 1: Get the chart from Docker Hub
```bash
helm pull oci://registry-1.docker.io/intel/live-video-alert-agent-chart --version <version-no>
tar -xvf live-video-alert-agent-chart<version-no>.tgz
cd live-video-alert-agent-chart
```
Refer to the [Release Notes](../release-notes.md) for the latest version.

#### Option 2: Install from Source
```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git edge-ai-suites
cd edge-ai-suites/metro-ai-suite/live-video-analysis/live-video-alert-agent/chart
```

### 2. Configure Required Values

Edit `user_values_override.yaml` with values for your environment:

| Key | Description | Example |
|-----|-------------|---------|
| `global.externalIP` | **(Required)** IP of a cluster node reachable by your browser | `<clusternodeip>` |
| `global.keepPvc` | Retain model PVC on uninstall (avoids ~10 min re-download) | `true` |
| `global.huggingfaceToken` | Required only for gated models on first download | `hf_xxx` |
| `global.proxy.httpProxy` | HTTP proxy for outbound connections | `http://proxy.example.com:<port>` |
| `global.proxy.httpsProxy` | HTTPS proxy for outbound connections | `http://proxy.example.com:<port>` |
| `global.proxy.noProxy` | Addresses that bypass the proxy | `localhost,127.0.0.1,...,.svc.cluster.local` |
| `global.gpu.enabled` | Enable Intel GPU for VLM inference | `true` / `false` |
| `global.gpu.key` | GPU resource key from the device plugin | `gpu.intel.com/i915` |
| `global.gpu.device` | Target device for inference | `GPU` |
| `global.gpu.supplementalGroups` | Linux group IDs for GPU device access. Run `getent group render video \| cut -d: -f3` on the GPU node to find values | `[109, 44]` |
| `app.rtspUrl` | RTSP stream URL to load at startup (optional) | `rtsp://host:port/stream` |
| `app.nodeSelector` | Schedule app pod on a specific node | `kubernetes.io/hostname: worker1` |

> **Note:** `user_values_override.yaml` may contain credentials. Do not commit it to version control.

### 3. Build Helm Dependencies
```bash
helm dependency build
```

### 4. Set and Create a Namespace
```bash
my_release=lva
my_namespace=lva
kubectl create namespace $my_namespace || true
```

> **Note:** All subsequent steps assume `my_release` and `my_namespace` are set in your shell session. The `|| true` makes the namespace creation safe to re-run.

### 5. Deploy the Helm Chart
```bash
helm install $my_release . -f user_values_override.yaml -n $my_namespace
```

### 6. Verify the Deployment
```bash
kubectl get pods -n $my_namespace
kubectl get svc -n $my_namespace
```

Before proceeding, ensure all pods show `Running` status and `1/1` in the READY column.

> **Note:** The OVMS pod may take up to 10 minutes on first start while the VLM model is downloaded. Set `global.keepPvc: true` to retain the model across reinstalls.

### 7. Access the Application
```bash
node_ip=$(kubectl get pods -l app.kubernetes.io/component=app -n $my_namespace -o jsonpath='{.items[0].status.hostIP}')
app_port=$(kubectl get svc -l app.kubernetes.io/component=app -n $my_namespace -o jsonpath='{.items[0].spec.ports[0].nodePort}')
echo "http://${node_ip}:${app_port}"
```

Open the printed URL in your browser to access the Live Video Alert Agent dashboard.

### 8. Uninstall Helm Chart
```bash
helm uninstall $my_release -n $my_namespace
```

PVC retention on uninstall is controlled by `global.keepPvc`. To delete the PVC manually:
```bash
kubectl delete pvc ${my_release}-ovms-models -n $my_namespace
```

---

## Upgrading

After modifying subchart sources or pulling a new chart version, rebuild dependencies before redeploying:
```bash
helm dependency build
helm upgrade $my_release . -f user_values_override.yaml -n $my_namespace
```

---

## Troubleshooting

- **Pods stuck in `Pending`:** Check storage availability and node capacity.
  ```bash
  kubectl describe pod <pod-name> -n $my_namespace
  kubectl get events -n $my_namespace --sort-by='.metadata.creationTimestamp'
  ```
- **OVMS pod slow to start:** Expected on first deploy — model is downloading (~2 GB). Monitor with:
  ```bash
  kubectl logs -n $my_namespace deployment/${my_release}-ovms --follow
  ```
- **`ImagePullBackOff`:** Check image name and tag overrides in `user_values_override.yaml`. Ensure registry is reachable.
- **GPU not working:** Verify device plugin resource key with `kubectl describe node <gpu-node> | grep gpu.intel.com`.
- **Check logs:**
  ```bash
  kubectl logs <pod-name> -n $my_namespace
  ```

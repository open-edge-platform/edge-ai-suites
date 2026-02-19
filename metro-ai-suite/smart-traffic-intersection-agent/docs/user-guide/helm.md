# Deploy the Complete Application with Helm

This guide provides end-to-end instructions for deploying the **Smart Traffic Intersection Agent**
along with its dependency — the **Smart Intersection RI** (SceneScape) — on a Kubernetes cluster using Helm.

The full application is composed of **two independent Helm releases** that communicate via the MQTT broker:

```
 ┌──────────────────────────────────────────────────────────────────┐
 │               Helm Release: smart-intersection                   │
 │  (SceneScape RI — infrastructure services)                       │
 │                                                                  │
 │  ┌──────────┐ ┌─────────┐ ┌────────┐ ┌─────────┐ ┌──────────┐ │
 │  │ Mosquitto│ │DLStreamer│ │InfluxDB│ │ Grafana │ │SceneScape│ │
 │  │  Broker  │ │ Pipeline│ │        │ │         │ │ Web + Ctrl│ │
 │  │  :1883   │ │  Server │ │ :30086 │ │         │ │  :30443  │ │
 │  └────┬─────┘ └─────────┘ └────────┘ └─────────┘ └──────────┘ │
 │       │ MQTT (TLS)                                              │
 └───────┼─────────────────────────────────────────────────────────┘
         │
         │  K8s Service DNS
         │
 ┌───────┼─────────────────────────────────────────────────────────┐
 │       ▼          Helm Release: stia                              │
 │  (Smart Traffic Intersection Agent)                              │
 │                                                                  │
 │  ┌─────────────────────┐    HTTP :8000    ┌───────────────────┐ │
 │  │   traffic-agent     │ ──────────────▶  │ vlm-openvino-     │ │
 │  │  :8081 API          │   K8s svc DNS    │ serving            │ │
 │  │  :7860 UI           │                  │ :8000              │ │
 │  └─────────────────────┘                  └───────────────────┘ │
 └──────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

Before you begin, ensure the following:

- **Kubernetes Cluster**: A properly installed and configured Kubernetes cluster.
- **System Requirements**: Verify that your system meets the
  [minimum requirements](./get-started/system-requirements.md).
- **Tools Installed**:
  - Kubernetes CLI (`kubectl`): [Installation Guide](https://kubernetes.io/docs/tasks/tools/install-kubectl/)
  - Helm 3 or later: [Installation Guide](https://helm.sh/docs/intro/install/)
- **Storage Provisioner**: A default storage class is required for persistent volumes.
  Refer to the [Kubernetes Dynamic Provisioning Guide](https://kubernetes.io/docs/concepts/storage/dynamic-provisioning/) for details.
- **Docker Hub access**: The container images for both charts are hosted on
  [Docker Hub](https://hub.docker.com/u/intel).
- *(Optional)* A [Hugging Face](https://huggingface.co/) API token if the VLM model
  requires authentication.

---

## Step 0: Set Up a Storage Provisioner (Single-Node Clusters)

Check if your cluster has a default storage class with dynamic provisioning:

```bash
kubectl get storageclass
```

If no storage classes exist or none are marked as default, install a local-path provisioner:

```bash
# Install local-path-provisioner
kubectl apply -f \
  https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml

# Set it as the default storage class
kubectl patch storageclass local-path -p \
  '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Verify
kubectl get storageclass
```

> **Note:** Managed clusters (EKS, GKE, AKS) typically already have a default storage
> class configured.

---

## Step 1: Deploy the Smart Intersection RI

The Smart Intersection RI provides SceneScape infrastructure: the MQTT broker,
DLStreamer pipeline server, InfluxDB, Grafana, and the SceneScape web UI.

Refer to the full RI deployment guide:
[Smart Intersection — Deploy with Helm](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/get-started/deploy-with-helm.md)

### Quick Summary

```bash
# Option A: Pull the chart from Docker Hub
helm pull oci://registry-1.docker.io/intel/smart-intersection --version 1.17.0
tar -xvf smart-intersection-1.17.0.tgz
cd smart-intersection

# Option B: From source
git clone https://github.com/open-edge-platform/edge-ai-suites.git
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/chart
```

Configure `values.yaml`:

| Key | Description | Required |
| --- | ----------- | -------- |
| `global.externalIP` | Cluster node's external IP address | **Yes** |
| `supass` | Admin password for SceneScape web UI | **Yes** |
| `pgpass` | Postgres database password | **Yes** |
| `http_proxy` / `https_proxy` / `no_proxy` | Proxy settings (if behind a proxy) | If applicable |
| `gpuWorkload` | Set to `true` to run DLStreamer on GPU | No |

Deploy the chart:

```bash
helm upgrade --install smart-intersection . \
  --create-namespace \
  --set global.storageClassName="" \
  -n smart-intersection

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n smart-intersection --timeout=300s
```

### Verify the RI Deployment

```bash
kubectl get pods -n smart-intersection
kubectl get svc -n smart-intersection
```

Note the **broker service name** — typically `smart-intersection-broker`. The full
Kubernetes DNS name is:

```
smart-intersection-broker.smart-intersection.svc.cluster.local
```

---

## Step 2: Retrieve the SceneScape CA Certificate

The traffic agent requires the SceneScape CA certificate for TLS connections to the
MQTT broker.

```bash
# Extract the CA cert from the RI deployment
kubectl get secret smart-intersection-certs -n smart-intersection \
  -o jsonpath='{.data.scenescape-ca\.pem}' | base64 -d > scenescape-ca.pem

# Verify
cat scenescape-ca.pem
```

> **Note:** The secret name may vary depending on the RI release. List available
> secrets with `kubectl get secrets -n smart-intersection` and look for one
> containing `certs`.

---

## Step 3: Build and Push the Traffic Agent Image

The traffic agent image must be available in a container registry that your cluster
can pull from. The image is published to Docker Hub at
`intel/smart-traffic-intersection-agent`.

If you need to build from source:

```bash
cd edge-ai-suites/metro-ai-suite/smart-traffic-intersection-agent

# Build the image
docker build -t intel/smart-traffic-intersection-agent:1.0.0 src/

# Push to Docker Hub (or your private registry)
docker push intel/smart-traffic-intersection-agent:1.0.0
```

> **Note:** The VLM serving image (`intel/vlm-openvino-serving:1.3.2`) is already
> available on Docker Hub — no build is needed.

---

## Step 4: Configure the Traffic Agent Chart

### Option A: Pull from Docker Hub

```bash
helm pull oci://registry-1.docker.io/intel/smart-traffic-intersection-agent --version <version-no>
tar -xvf smart-traffic-intersection-agent-<version-no>.tgz
cd smart-traffic-intersection-agent
```

### Option B: From Source

```bash
cd edge-ai-suites/metro-ai-suite/smart-traffic-intersection-agent/chart
```

### Edit `values.yaml` or Create an Override File

Create a `values-prod.yaml` file with your environment-specific settings:

```yaml
# values-prod.yaml
global:
  proxy:
    httpProxy: "http://your-proxy:port"
    httpsProxy: "http://your-proxy:port"
    noProxy: "localhost,127.0.0.1,10.0.0.0/8,.cluster.local,.intel.com"

trafficAgent:
  image:
    repository: intel/smart-traffic-intersection-agent
    tag: "1.0.0"
  intersection:
    name: "intersection_1"
    latitude: "37.51358"
    longitude: "-122.25591"
  mqtt:
    # Point to the RI broker's Kubernetes service DNS
    host: "smart-intersection-broker.smart-intersection.svc.cluster.local"
    port: "1883"

vlmServing:
  env:
    modelName: "Qwen/Qwen2.5-VL-3B-Instruct"
    device: "CPU"              # or "GPU"
  gpu:
    enabled: false             # set to true if device is GPU
  # huggingfaceToken: ""       # set if model requires authentication

tls:
  caCert: |
    -----BEGIN CERTIFICATE-----
    <paste contents of scenescape-ca.pem here>
    -----END CERTIFICATE-----
```

### `values.yaml` Reference

Refer to the [Deploy with Helm guide](./deploy-with-helm.md#valuesyaml-reference) for
the complete reference table of all configurable values.

The most important settings for connecting to the RI are:

| Key | Description | Example |
| --- | ----------- | ------- |
| `trafficAgent.mqtt.host` | MQTT broker hostname (SceneScape) | `smart-intersection-broker.smart-intersection.svc.cluster.local` |
| `trafficAgent.mqtt.port` | MQTT broker port | `1883` |
| `trafficAgent.intersection.name` | Unique intersection identifier | `intersection_1` |
| `trafficAgent.intersection.latitude` | Intersection latitude | `37.51358` |
| `trafficAgent.intersection.longitude` | Intersection longitude | `-122.25591` |
| `tls.caCert` | PEM-encoded CA certificate from SceneScape | Contents of `scenescape-ca.pem` |
| `tls.caCertSecretName` | Use an existing K8s Secret instead of `tls.caCert` | `smart-intersection-certs` |

---

## Step 5: Deploy the Traffic Agent

```bash
helm install stia . \
  -n smart-intersection \
  -f values-prod.yaml

# Wait for pods (VLM model download can take several minutes on first startup)
kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=stia \
  -n smart-intersection --timeout=600s
```

> **Namespace:** Deploying into the same namespace as the RI (`smart-intersection`)
> simplifies DNS resolution and network policies. You can use a separate namespace —
> just ensure you use the full FQDN for the MQTT host.

---

## Step 6: Verify the Deployment

```bash
# Check all pods
kubectl get pods -n smart-intersection
```

You should see pods from both Helm releases:

| Pod | Source |
| --- | ------ |
| `smart-intersection-broker-*` | RI chart |
| `smart-intersection-dlstreamer-*` | RI chart |
| `smart-intersection-grafana-*` | RI chart |
| `smart-intersection-influxdb-*` | RI chart |
| `smart-intersection-web-*` | RI chart |
| `smart-intersection-scene-*` | RI chart |
| `stia-traffic-agent-*` | Traffic agent chart |
| `stia-vlm-openvino-serving-*` | Traffic agent chart |

Check services:

```bash
kubectl get svc -n smart-intersection
```

Check traffic agent logs to verify MQTT connectivity:

```bash
kubectl logs -l app=stia-traffic-agent -n smart-intersection -f
```

---

## Step 7: Access the Application

### Traffic Agent (port-forward)

```bash
# Backend API
kubectl port-forward svc/stia-traffic-agent 8081:8081 -n smart-intersection &

# Gradio UI
kubectl port-forward svc/stia-traffic-agent 7860:7860 -n smart-intersection &
```

### Service Endpoints

| Service | URL | Credentials |
| ------- | --- | ----------- |
| **Traffic Agent UI** | `http://localhost:7860` | None |
| **Traffic Agent API** | `http://localhost:8081/docs` | None |
| **SceneScape Web UI** | `https://<NODE_IP>:30443/` | `admin` / `<supass>` |
| **Grafana Dashboard** | `https://<NODE_IP>:30443/grafana/` | `admin` / `admin` |
| **InfluxDB** | `http://<NODE_IP>:30086/` | See RI docs |
| **Node-RED** | `https://<NODE_IP>:30443/nodered/` | None |
| **DLStreamer Pipeline** | `https://<NODE_IP>:30443/api/pipelines/status` | None |

> **Security Note:** The RI uses self-signed certificates for HTTPS. Your browser will
> show a security warning — click "Advanced" → "Proceed" to continue.

---

## Uninstall

### Uninstall the Traffic Agent

```bash
helm uninstall stia -n smart-intersection
```

### Uninstall the Smart Intersection RI

```bash
helm uninstall smart-intersection -n smart-intersection
```

### Clean Up PVCs and Namespace

PersistentVolumeClaims are not automatically deleted on uninstall:

```bash
# List remaining PVCs
kubectl get pvc -n smart-intersection

# Delete specific PVCs
kubectl delete pvc <pvc-name> -n smart-intersection

# Or delete all PVCs in the namespace
kubectl delete pvc --all -n smart-intersection

# Delete the namespace
kubectl delete namespace smart-intersection
```

---

## What Replaces What (Docker Compose → Helm)

For users migrating from the Docker Compose deployment (`setup.sh`):

| Docker Compose (`setup.sh`) | Helm Equivalent |
| ---------------------------- | --------------- |
| `ri-compose.yaml` (SceneScape RI) | `helm install smart-intersection` (RI chart) |
| `agent-compose.yaml` (traffic-agent + VLM) | `helm install stia` (traffic agent chart) |
| `docker compose build` (build image from `src/`) | `docker build` + `docker push` to Docker Hub |
| `src/config/*.json` (bind mount) | ConfigMap rendered from `values.yaml` |
| Docker secret for CA cert | Kubernetes Secret from `tls.caCert` |
| Docker named volumes (`ov-models`, `traffic-agent-data`) | Kubernetes PersistentVolumeClaims |
| Docker `scenescape` bridge network | Kubernetes Service DNS (automatic) |
| `source setup.sh --stop` | `helm uninstall stia` + `helm uninstall smart-intersection` |
| `source setup.sh --clean --all` | `helm uninstall` + `kubectl delete pvc` |

---

## Troubleshooting

### VLM Pod Stuck in CrashLoopBackOff

The model download or conversion may have failed. Check the logs:

```bash
kubectl logs -l app=stia-vlm-openvino-serving -n smart-intersection
```

Common causes:
- **Proxy not set:** Verify `global.proxy.*` values in `values.yaml`.
- **Authentication required:** Set `vlmServing.huggingfaceToken` if the model is gated.
- **Insufficient memory:** The VLM pod requests 4 Gi by default. Increase
  `vlmServing.resources.requests.memory` if needed.

### Traffic Agent Cannot Connect to MQTT Broker

```bash
kubectl logs -l app=stia-traffic-agent -n smart-intersection | grep -i mqtt
```

Common causes:
- **Wrong broker hostname:** Verify `trafficAgent.mqtt.host` matches the RI broker
  service name. Check with `kubectl get svc -n smart-intersection | grep broker`.
- **Missing CA certificate:** Ensure `tls.caCert` is set or `tls.caCertSecretName`
  points to a valid secret.
- **Cross-namespace DNS:** If deploying in a different namespace, use the full FQDN:
  `<service>.<namespace>.svc.cluster.local`.

### Pods Pending Due to Storage

```bash
kubectl describe pod <pod-name> -n smart-intersection
```

If you see `no persistent volumes available`, ensure a default storage class exists:

```bash
kubectl get storageclass
```

---

## Related Links

- [Deploy with Helm (Chart Reference)](./deploy-with-helm.md)
- [Get Started](./get-started.md)
- [API Reference](./api-reference.md)
- [Smart Intersection RI — Deploy with Helm](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/get-started/deploy-with-helm.md)
- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/home/)

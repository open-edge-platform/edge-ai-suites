# NICU Warmer – Helm Deployment

This Helm chart deploys the **NICU Warmer Patient Monitoring** application on Kubernetes.

## Prerequisites

- Kubernetes cluster (K3s / Minikube / Kind / Bare-metal)
- `kubectl`
- `helm` (v3+)
- A working PersistentVolume provisioner (required for PVC binding)
- An actively-maintained **Ingress Controller** (required when `ingress.enabled: true`, which is the default)
- Intel GPU + NPU hardware (Meteor Lake / Arrow Lake) for accelerated inference

### Ingress Controller prerequisite (required for default configuration)

> **Important:** The community `kubernetes/ingress-nginx` controller was **retired in
> March 2026** and no longer receives bug fixes or security updates. It must **not** be
> used. See the [retirement notice](https://github.com/kubernetes/ingress-nginx#retiring).

This chart is **ingress-controller-agnostic**: it routes all traffic to the `nicu-ui`
service, whose internal reverse proxy forwards `/api/*` requests to the backend. Because
of this, the chart requires **no controller-specific rewrite annotations** and works with
any actively-maintained ingress controller.

The chart defaults to **Traefik** (`ingressClassName: traefik`) — an actively maintained,
CNCF-graduated controller that ships **by default with K3s**, so no extra installation is
needed there. For other distributions, install a supported controller and set
`ingress.className` to match its IngressClass (or set it to `""` to use the cluster default).

```bash
# Example: install Traefik on a non-K3s cluster
helm repo add traefik https://traefik.github.io/charts
helm repo update
helm install traefik traefik/traefik \
  --namespace traefik --create-namespace

# Verify the IngressClass is available
kubectl get ingressclass
```

To use a different controller, override the class at install time, for example:

```bash
helm install nicu-warmer . -n nicu --create-namespace \
  --set ingress.className=haproxy   # or contour, etc.
```

If you do not have an ingress controller and do not wish to install one, set
`ingress.enabled: false` in `values.yaml` and use port-forwarding to access the
application (see [Access without Ingress](#access-without-ingress-controller) below).

### Storage prerequisite (required)

This chart creates PVCs (`nicu-models-pvc`, `nicu-uploads-pvc`) and expects your
cluster to provide PersistentVolumes through a StorageClass.

If your cluster has no dynamic provisioner, PVCs will remain `Pending` and workloads will not
schedule.

```bash
# Check for existing storage classes
kubectl get storageclass

# If no default storage class exists, install local-path-provisioner
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml

# Set it as default storage class
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

## Prepare Offline Assets

The NICU Warmer requires model files, video, and Python extensions to be available on the
Kubernetes node. Extract the offline assets zip to the host path:

```bash
sudo mkdir -p /opt/nicu-warmer-assets
sudo unzip nicu-warmer-assets.zip -d /opt/nicu-warmer-assets/
```

The chart accepts both the canonical nested layout shown below and the legacy flat
bundle layout used by some previously shipped asset zips.

Expected directory structure:

```
/opt/nicu-warmer-assets/
├── models/
│   ├── person-detect-fp32.xml
│   ├── person-detect-fp32.bin
│   ├── patient-detect-fp32.xml
│   ├── patient-detect-fp32.bin
│   ├── latch-detect-fp32.xml
│   ├── latch-detect-fp32.bin
│   ├── rppg/
│   │   ├── mtts_can.xml
│   │   └── mtts_can.bin
│   └── action/
│       ├── FP32/
│       │   ├── action-recognition-0001-encoder.xml
│       │   ├── action-recognition-0001-encoder.bin
│       │   ├── action-recognition-0001-decoder.xml
│       │   └── action-recognition-0001-decoder.bin
│       └── kinetics.txt
├── videos/
│   └── Warmer_Testbed_YTHD.mp4
└── extensions/
    ├── rppg_gva.py
    ├── action_gva.py
    └── publisher_utils_patched.py
```

Legacy flat bundles are also supported during install, for example:

```text
/opt/nicu-warmer-assets/
├── person-detect-fp32.xml
├── person-detect-fp32.bin
├── patient-detect-fp32.xml
├── patient-detect-fp32.bin
├── latch-detect-fp32.xml
├── latch-detect-fp32.bin
├── action-recognition-0001-encoder.xml
├── action-recognition-0001-encoder.bin
├── action-recognition-0001-decoder.xml
├── action-recognition-0001-decoder.bin
├── Warmer_Testbed_YTHD.mp4
├── models_rppg/
│   ├── mtts_can.xml
│   └── mtts_can.bin
└── extensions/
  ├── rppg_gva.py
  ├── action_gva.py
  └── publisher_utils_patched.py
```

To customize the host path:

```bash
--set assets.loadJob.hostPath=/your/custom/path
```

## Optional: Proxy Configuration

If deploying behind a proxy, update the proxy settings:

```bash
helm install nicu-warmer . \
  --set http_proxy="http://your-proxy:port" \
  --set https_proxy="http://your-proxy:port" \
  --set no_proxy="localhost,127.0.0.1,.svc,.cluster.local"
```

## Install

```bash
cd health-and-life-sciences-ai-suite/NICU-Warmer/helm/nicu-warmer

# Default install (mixed-optimized: GPU detection, CPU rPPG, NPU action)
helm install nicu-warmer . \
  --namespace nicu \
  --create-namespace
```

### Device Profile Override

The chart defaults to the **mixed-optimized** profile (GPU for detection, CPU for rPPG,
NPU for action recognition) which gives ~15 FPS on Meteor Lake.

Override device selection at install time:

```bash
# All-CPU (no accelerator required, ~6 FPS)
helm install nicu-warmer . -n nicu --create-namespace \
  --set devices.DETECTION_DEVICE=CPU \
  --set devices.ACTION_DEVICE=CPU

# All-GPU
helm install nicu-warmer . -n nicu --create-namespace \
  --set devices.DETECTION_DEVICE=GPU \
  --set devices.ACTION_DEVICE=GPU \
  --set devices.RPPG_DEVICE=GPU

# All-NPU
helm install nicu-warmer . -n nicu --create-namespace \
  --set devices.DETECTION_DEVICE=NPU \
  --set devices.ACTION_DEVICE=NPU \
  --set devices.RPPG_DEVICE=NPU
```

| Profile                   | DETECTION_DEVICE | RPPG_DEVICE | ACTION_DEVICE | Expected FPS |
| ------------------------- | ---------------- | ----------- | ------------- | ------------ |
| mixed-optimized (default) | GPU              | CPU         | NPU           | ~15          |
| all-gpu                   | GPU              | GPU         | GPU           | ~15          |
| all-cpu                   | CPU              | CPU         | CPU           | ~6           |
| all-npu                   | NPU              | NPU         | NPU           | ~10          |

> **Limitation:** NPU-optimized (FP16/INT8) models are not yet available; all profiles currently use FP32 models.

## Upgrade (after changes)

```bash
helm upgrade nicu-warmer . -n nicu
```

## Verify Deployment

### Pods

```bash
kubectl get pods -n nicu
```

All pods should show:

```
STATUS: Running
READY: 1/1
```

Expected pods:

- `nicu-backend` — Flask API for inference orchestration
- `nicu-dlsps` — DL Streamer Pipeline Server (video inference)
- `nicu-ui` — React frontend served by nginx
- `nicu-metrics-collector` — System metrics (CPU/GPU/NPU/Memory)
- `nicu-mqtt` — MQTT broker for pipeline events

### Services

```bash
kubectl get svc -n nicu
```

### Check Logs

```bash
kubectl logs -n nicu deploy/nicu-backend
kubectl logs -n nicu deploy/nicu-dlsps
kubectl logs -n nicu deploy/nicu-metrics-collector
kubectl logs -n nicu deploy/nicu-ui
```

### Start the Pipeline

```bash
# Port-forward to backend
kubectl port-forward -n nicu svc/nicu-backend 5001:5001

# Start inference
curl -X POST http://localhost:5001/start

# Check status
curl http://localhost:5001/metrics
```

Expected output when running:

```json
{
  "fps": 15.0,
  "frame_count": 1500,
  "lifecycle": "running",
  "runtime_status": "running"
}
```

## Access the Frontend UI

### With Ingress (default)

```bash
kubectl get ingress -n nicu
```

Add the hostname mapping:

```bash
echo "<INGRESS-IP> nicu-warmer.local" | sudo tee -a /etc/hosts
```

Open: `http://nicu-warmer.local/`

### Access without Ingress Controller

If deployed with `ingress.enabled: false` or no ingress controller available:

```bash
# Forward UI service
kubectl port-forward -n nicu svc/nicu-ui 3000:80 --address 0.0.0.0
```

Open: `http://localhost:3000`

From the UI you can:

- View live video feed with person/patient/latch detection bounding boxes
- Monitor rPPG (remote photoplethysmography) vitals
- See action recognition (caretaker activity)
- View real-time system metrics (CPU/GPU/NPU utilization, memory, power)
- Start/Stop the inference pipeline

## Architecture

| Service                | Description                                       | Port |
| ---------------------- | ------------------------------------------------- | ---- |
| nicu-backend           | Flask API — pipeline orchestration, MQTT consumer | 5001 |
| nicu-ui                | React dashboard served by nginx                   | 3000 |
| nicu-metrics-collector | Hardware metrics (GPU/NPU/CPU/Memory)             | 9000 |
| nicu-dlsps             | DL Streamer Pipeline Server — GStreamer inference | 8080 |
| nicu-mqtt              | Eclipse Mosquitto MQTT broker                     | 1883 |

## Configuration

See [values.yaml](https://github.com/open-edge-platform/edge-ai-suites/blob/release-2026.1.0/health-and-life-sciences-ai-suite/NICU-Warmer/helm/nicu-warmer/values.yaml) for all configurable parameters.

### Key Parameters

| Parameter                  | Description                   | Default                   |
| -------------------------- | ----------------------------- | ------------------------- |
| `devices.DETECTION_DEVICE` | Device for detection models   | `GPU`                     |
| `devices.RPPG_DEVICE`      | Device for rPPG model         | `CPU`                     |
| `devices.ACTION_DEVICE`    | Device for action recognition | `NPU`                     |
| `devices.TARGET_FPS`       | Target frame rate             | `30`                      |
| `backend.image.tag`        | Backend image tag             | `2026.1.0-rc1`            |
| `ui.image.tag`             | UI image tag                  | `2026.1.0-rc1`            |
| `dlsps.image.tag`          | DLSPS image tag               | `2026.1.0-ubuntu24-rc1`   |
| `metrics.image.tag`        | Metrics collector tag         | `2026.0-rc1`              |
| `ingress.enabled`          | Enable ingress routing        | `true`                    |
| `assets.loadJob.hostPath`  | Host path for offline assets  | `/opt/nicu-warmer-assets` |
| `persistence.size`         | PVC storage size              | `20Gi`                    |

## Uninstall

```bash
helm uninstall nicu-warmer -n nicu
kubectl delete namespace nicu
```

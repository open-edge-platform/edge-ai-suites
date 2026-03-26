# Multi modal patient monitoring – Helm Deployment

This Helm chart deploys the **Multi modal patient monitoring app** on Kubernetes.


## Prerequisites

- Kubernetes cluster (Minikube / Kind / Bare-metal)
- `kubectl`
- `helm` (v3+)
- A working PersistentVolume provisioner (required for PVC binding)
- **NGINX Ingress Controller** (required when `ingress.enabled: true`, which is the default)

### Ingress Controller prerequisite (required for default configuration)

This chart creates Ingress resources that use `ingressClassName: nginx`. You must have the
NGINX Ingress Controller running in your cluster before installing the chart with ingress enabled.

```bash
# Install NGINX Ingress Controller via Helm
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx --create-namespace

# Wait for the controller to be ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s
```

For **Minikube**, enable the built-in ingress addon instead:
```bash
minikube addons enable ingress
```

If your ingress controller `EXTERNAL-IP` stays `pending` (common on bare-metal clusters),
you have two supported options:

1. Install a LoadBalancer implementation such as MetalLB.
2. Expose the ingress controller via NodePort.

Example for existing ingress-nginx install:
```bash
kubectl patch svc ingress-nginx-controller -n ingress-nginx \
  -p '{"spec":{"type":"NodePort"}}'
```

If you do not have an ingress controller and do not wish to install one, set
`ingress.enabled: false` in `values.yaml` and use port-forwarding to access the
application (see [Access without Ingress](#access-without-ingress-controller) below).

### Storage prerequisite (required)

This chart creates PVCs (`models-pvc`, `videos-pvc`, `health-ai-assets-pvc`) and expects your
cluster to provide PersistentVolumes through a StorageClass.

If your cluster has no dynamic provisioner, PVCs will remain `Pending` and workloads will not
schedule.

- For single-node/local clusters, install a dynamic provisioner (for example,
  `local-path-provisioner`) before installing this chart.
- Or pre-create matching static PersistentVolumes for all claims.

> `local-path-provisioner` does **not** support `ReadWriteMany`.
> Use `ReadWriteOnce` (this chart default) unless you use a RWX-capable storage backend.

## Optional: Proxy configuration 

Configure Proxy Settings (If behind a proxy)

If you are deploying in a proxy environment, also update the proxy settings in the same values.yaml file:
```bash
http_proxy: "http://your-proxy-server:port"
https_proxy: "http://your-proxy-server:port"
no_proxy: "localhost,127.0.0.1,.local,.cluster.local"
```
Replace your-proxy-server:port with your actual proxy server details.
 

Set via CLI if needed:

```bash
--set assets.proxy.enabled=true \
--set assets.proxy.httpProxy=http://your-proxy-server:port\
--set assets.proxy.httpsProxy=http://your-proxy-server:port\
--set assets.proxy.noProxy=localhost,127.0.0.1,.svc,.cluster.local
```

## Setup Storage Provisioner (For Single-Node Clusters)
Check if your cluster has a default storage class with dynamic provisioning. If not, install a storage provisioner:

```bash
# Check for existing storage classes
kubectl get storageclass

# If no storage classes exist or none are marked as default, install local-path-provisioner
# This step is typically needed for single-node bare Kubernetes installations
# (Managed clusters like EKS/GKE/AKS already have storage classes configured)

# Install local-path-provisioner for automatic storage provisioning
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml

# Set it as default storage class
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Verify storage class is ready
kubectl get storageclass
```


## Install

```bash
cd health-and-life-sciences-ai-suite/multi_modal_patient_monitoring/helm/multi_modal_patient_monitoring

helm install multi-modal-patient-monitoring . \
  --namespace multi-modal-patient-monitoring \
  --create-namespace
```

## Upgrade (after changes)
```bash
helm upgrade multi-modal-patient-monitoring . -n multi-modal-patient-monitoring
``` 

## Verify Deployment
Pods
```bash
kubectl get pods -n multi-modal-patient-monitoring
``` 

All pods should be:
```bash
STATUS: Running
READY: 1/1
``` 
## Services
```bash
kubectl get svc -n multi-modal-patient-monitoring
``` 

## Check Logs (recommended)
```bash
kubectl logs -n multi-modal-patient-monitoring deploy/mdpnp
kubectl logs -n multi-modal-patient-monitoring deploy/dds-bridge
kubectl logs -n multi-modal-patient-monitoring deploy/aggregator
kubectl logs -n multi-modal-patient-monitoring deploy/ai-ecg
kubectl logs -n multi-modal-patient-monitoring deploy/pose
kubectl logs -n multi-modal-patient-monitoring deploy/metrics
kubectl logs -n multi-modal-patient-monitoring deploy/ui
``` 

Healthy services will show:

- Application startup complete
- Listening on expected ports
- No crash loops


## Ingress Configuration

The chart creates two Ingress resources when `ingress.enabled: true` (default):

| Value | Default | Description |
|---|---|---|
| `ingress.enabled` | `true` | Create Ingress resources for external access |
| `ingress.className` | `nginx` | IngressClass to use (requires a matching controller) |
| `ingress.annotations` | *(nginx-specific)* | Annotations applied to the main ingress |
| `ingress.hosts` | `multi-modal-patient-monitoring.local` | Hostname and path routing rules |

To disable ingress (e.g., for environments without an ingress controller):

```bash
helm install multi-modal-patient-monitoring . \
  --namespace multi-modal-patient-monitoring \
  --create-namespace \
  --set ingress.enabled=false
```

## Access the Frontend UI

### With Ingress (default)
#### 1. Check the Ingress Resource

Run the following command to view the ingress configuration:

```bash
kubectl get ingress -n multi-modal-patient-monitoring
```
This will show the hostname or IP and the path for the UI.

Example output:
```bash
NAME       HOSTS               PATHS   ADDRESS         PORTS
multi-modal-patient-monitoring  multi-modal-patient-monitoring.local       /       xx.xx.xx.xx   80
```
#### 2. If an IP Address Appears in ADDRESS

Add the hostname mapping to your local machine:
```bash
echo "<IP> multi-modal-patient-monitoring.local" | sudo tee -a /etc/hosts
```
Replace <IP> with the value shown in the ADDRESS column.

#### 3. If the ADDRESS Field is Empty (Common in Minikube)
Some local Kubernetes environments (such as Minikube) do not automatically populate the ingress IP.

Retrieve the Minikube cluster IP:
```bash
minikube ip
```
Then map the hostname to the IP:
```bash
echo "$(minikube ip) multi-modal-patient-monitoring.local" | sudo tee -a /etc/hosts
```

#### 4. Enable Ingress in Minikube (if not already enabled)
```bash
minikube addons enable ingress
```
Wait a few moments for the ingress controller to start.

#### 5.Open the Application
Open your browser and navigate to:
```bash
http://<host-or-ip>/
``` 
Example:
```bash
http://multi-modal-patient-monitoring.local/
``` 

This will open the Health AI Suite frontend dashboard.

From here you can access:

  - 3D Pose Estimation

  - ECG Monitoring

  - RPPG Monitoring

  - MdPnP service

  - Metrics Dashboard

### Access without Ingress Controller

If you deployed with `ingress.enabled: false` or do not have an NGINX Ingress Controller,
you can access the application using `kubectl port-forward`.

#### Step 1: Forward the UI service (primary access point)
```bash
kubectl port-forward -n multi-modal-patient-monitoring svc/ui 8080:80
```
Then open http://localhost:8080 in your browser.

#### Step 2: Forward the Pose Estimation stream (for video feed in GUI)
The UI includes a Live Video Feed widget for the 3D Pose Estimation workload. When deploying 
without an ingress controller, the application automatically detects this and configures 
the UI to access the pose video feed on a separate port. 

Forward the pose service in a **separate terminal**:
```bash
kubectl port-forward -n multi-modal-patient-monitoring svc/pose 8085:8085
```

The pose video feed is then available at http://localhost:8085/video_feed and will be 
automatically rendered within the UI's 3D Pose Estimation card.

> **Required for 3D Pose streaming:** Keep this `svc/pose 8085:8085` port-forward running.
> Without it, the Live Video Feed cannot be displayed in the UI.

#### Step 3: Forward the Aggregator API (required for UI health and workload controls)
```bash
kubectl port-forward -n multi-modal-patient-monitoring svc/aggregator 8001:80
```
The aggregator API is then available at http://localhost:8001.

#### Step 4: Start workloads (required to generate live frames)
If the video panel is visible but no live motion appears, start the workloads:
```bash
curl -X POST "http://localhost:8001/start?target=all"
```

> **Important:** When using port-forward without ingress, ensure all three `port-forward` 
> commands are running in separate terminal windows for the full application to function 
> correctly, especially to display the Live Video Feed in the GUI.

#### How it works

When `ingress.enabled: false` is set in the Helm values:
- The UI reads the aggregator API on `http://localhost:8001`
- The UI service is configured with `VITE_POSE_STREAM_URL=http://localhost:8085/video_feed`
- The frontend automatically uses this URL to access the pose video feed
- This allows the Live Video Feed widget to display correctly when accessed via 
  `localhost:8080`, even though the pose service is on `localhost:8085`

#### Alternative: NodePort access

You can also switch the services to NodePort type by overriding the service type:

```bash
helm install multi-modal-patient-monitoring . \
  --namespace multi-modal-patient-monitoring \
  --create-namespace \
  --set ingress.enabled=false \
  --set service.type=NodePort
```

Then find the assigned node ports:
```bash
kubectl get svc -n multi-modal-patient-monitoring
```

Access the services at `http://<node-ip>:<node-port>`.


## Uninstall
```bash
helm uninstall multi-modal-patient-monitoring -n multi-modal-patient-monitoring
``` 
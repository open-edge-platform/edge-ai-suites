# Multi modal patient monitoring – Helm Deployment

This Helm chart deploys the **Multi modal patient monitoring app** on Kubernetes.


## Prerequisites

- Kubernetes cluster (Minikube / Kind / Bare-metal)
- `kubectl`
- `helm` (v3+)
- A working PersistentVolume provisioner (required for PVC binding)

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
cd /health-and-life-sciences-ai-suite/multi_modal_patient_monitoring/helm/multi_modal_patient_monitoring

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


## Access the Frontend UI
### 1. Check the Ingress Resource

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
### 2. If an IP Address Appears in ADDRESS

Add the hostname mapping to your local machine:
```bash
echo "<IP> multi-modal-patient-monitoring.local" | sudo tee -a /etc/hosts
```
Replace <IP> with the value shown in the ADDRESS column.

### 3. If the ADDRESS Field is Empty (Common in Minikube)
Some local Kubernetes environments (such as Minikube) do not automatically populate the ingress IP.

Retrieve the Minikube cluster IP:
```bash
minikube ip
```
Then map the hostname to the IP:
```bash
echo "$(minikube ip) multi-modal-patient-monitoring.local" | sudo tee -a /etc/hosts
```

### 4. Enable Ingress in Minikube (if not already enabled)
```bash
minikube addons enable ingress
```
Wait a few moments for the ingress controller to start.

### 5.Open the Application
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


## Uninstall
```bash
helm uninstall multi-modal-patient-monitoring -n multi-modal-patient-monitoring
``` 
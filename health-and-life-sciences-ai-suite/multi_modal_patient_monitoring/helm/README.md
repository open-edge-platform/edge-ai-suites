# Health AI Suite – Helm Deployment

This Helm chart deploys the **Health & Life Sciences AI Suite** on Kubernetes.


## Prerequisites

- Kubernetes cluster (Minikube / Kind / Bare-metal)
- `kubectl`
- `helm` (v3+)


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
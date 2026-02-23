# Health AI Suite – Helm Deployment

This Helm chart deploys the **Health & Life Sciences AI Suite** on Kubernetes.


## Prerequisites

- Kubernetes cluster (Minikube / Kind / Bare-metal)
- `kubectl`
- `helm` (v3+)
- Docker images built locally

## Required Docker Images

The following images **must exist locally** before deploying the Helm chart.

Check available images:
```bash
docker images | grep intel/hl-ai
```


## Install

```bash
cd health-and-life-sciences-ai-suite/helm/multi_modal_patient_monitoring

helm install health-ai . \
  --namespace health-ai \
  --create-namespace
```

## Upgrade (after changes)
```bash
helm upgrade health-ai . -n health-ai
``` 

## Verify Deployment
Pods
```bash
kubectl get pods -n health-ai
``` 

All pods should be:
```bash
STATUS: Running
READY: 1/1
``` 
## Services
```bash
kubectl get svc -n health-ai
``` 

## Check Logs (recommended)
```bash
kubectl logs -n health-ai deploy/mdpnp
kubectl logs -n health-ai deploy/dds-bridge
kubectl logs -n health-ai deploy/aggregator
kubectl logs -n health-ai deploy/ai-ecg
kubectl logs -n health-ai deploy/pose
kubectl logs -n health-ai deploy/metrics
kubectl logs -n health-ai deploy/ui
``` 

Healthy services will show:

- Application startup complete
- Listening on expected ports
- No crash loops


## Access the Frontend UI
Check Ingress resource:

```bash
kubectl get ingress -n health-ai
```
This will show the hostname or IP and the path for the UI.

Example output:
```bash
NAME       HOSTS               PATHS   ADDRESS         PORTS
health-ai  health-ai.local       /       192.168.49.2   80
```
Open your browser and go to:
```bash
http://<host-or-ip>/
``` 
Example:
```bash
http://health-ai.local/
``` 
If using Minikube, you may need to enable the ingress addon:
```bash
minikube addons enable ingress
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
helm uninstall health-ai -n health-ai
``` 
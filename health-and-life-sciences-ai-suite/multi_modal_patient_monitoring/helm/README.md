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
The UI is exposed using a NodePort service.

Get the Minikube IP:
```bash
minikube ip
```
Get the UI NodePort:
```bash
kubectl get svc ui -n health-ai
```
Open your browser and go to:
```bash
http://<minikube-ip>:<nodeport>
``` 
Example:
```bash
http://192.168.49.2:30007/
``` 
This will open the Health AI Suite frontend dashboard.

From here you can access:

  - 3D Pose Estimation

  - ECG Monitoring

  - RPPG Monitoring

  - MdPnP service

  - Metrics Dashboard

## On Bare Metal Kubernetes (On-Prem)
NodePort still works.

User must access:
```bash
http://<Node-Internal-IP>:<nodePort>
``` 

## Uninstall
```bash
helm uninstall health-ai -n health-ai
``` 
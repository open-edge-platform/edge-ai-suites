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
## If Docker Images Are Missing

If the required images are **not present locally**, Kubernetes pods will fail with `ImagePullBackOff`.

### Build Images Locally

From the repository root, build each service image:

```bash
# MDPnP
docker build -t intel/hl-ai-mdpnp:1.0.0 mdpnp-service/

# DDS Bridge
docker build -t intel/hl-ai-dds-bridge:1.0.0 dds-bridge/

# Aggregator
docker build -t intel/hl-ai-aggregator-service:1.0.0 aggregator-service/

# AI ECG
docker build -t intel/hl-ai-ecg:1.0.0 ai-ecg/backend/

# 3D Pose
docker build -t intel/hl-ai-3dpose:1.0.0 3d-pose-estimation/src/

# Metrics
docker build -t intel/hl-ai-metrics-service:1.0.0 metrics-service/

# UI 
docker build -t intel/hl-ai-ui:1.0.0 ui/

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


## Uninstall
```bash
helm uninstall health-ai -n health-ai
``` 
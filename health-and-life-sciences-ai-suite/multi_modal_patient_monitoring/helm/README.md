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

```

## Install

```bash
cd health-and-life-sciences-ai-suite/helm

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
``` 

Healthy services will show:

- Application startup complete
- Listening on expected ports
- No crash loops


## Access Services (Port Forward)
AI ECG
```bash
kubectl port-forward svc/ai-ecg 8000:8000 -n health-ai
``` 
http://localhost:8000/docs

Aggregator
```bash
kubectl port-forward svc/aggregator 8001:50051 -n health-ai
``` 
http://localhost:8000/docs


Pose
```bash
kubectl port-forward svc/pose 8002:8001 -n health-ai
``` 
http://localhost:8002/docs



## Uninstall
```bash
helm uninstall health-ai -n health-ai
``` 
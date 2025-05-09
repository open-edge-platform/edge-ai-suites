# Deploy with Helm

Use Helm to deploy Smart Intersection to a Kubernetes cluster. This guide will help you:
- Add the Helm chart repository.
- Configure the Helm chart to match your deployment needs.
- Deploy and verify the application.

Helm simplifies Kubernetes deployments by streamlining configurations and enabling easy scaling and updates. For more details, see [Helm Documentation](https://helm.sh/docs/).


## Prerequisites

Before You Begin, ensure the following:

- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Tools Installed**: Install the required tools:
    - Kubernetes CLI (kubectl)
    - Helm 3 or later

## Steps to Deploy

To deploy the Smart Intersection Sample Application, copy and paste the entire block of commands below into your terminal and run them:

  ```bash
# change the permissions of the secrets folder
sudo chown -R $USER:$USER chart/files/secrets
sudo chown -R $USER:$USER src/secrets

# Create namespace
kubectl create namespace smart-intersection

# ==========================
# Apply PersistentVolumes
# ==========================
# Ensure the PersistentVolumes (PVs) are created before deploying the application.

kubectl apply -n smart-intersection -f ./chart/templates/grafana/pv.yaml  # PV for Grafana
kubectl apply -n smart-intersection -f ./chart/templates/influxdb/pv.yaml  # PV for InfluxDB
kubectl apply -n smart-intersection -f ./chart/templates/pgserver/pv.yaml  # PV for pgserver


# Install the chart with secrets injected via --set
helm upgrade --install smart-intersection ./chart \
  --create-namespace \
  --set grafana.service.type=NodePort \
  -n smart-intersection

# We need to run same command again (Known issue, fix will be available soon)

# Install the chart with secrets injected via --set
helm upgrade --install smart-intersection ./chart \
  --create-namespace \
  --set grafana.service.type=NodePort \
  -n smart-intersection

# Some containers in the deployment requires network access.
# If you are in a proxy environment, pass the proxy environment variables as follows:
# helm upgrade \
#     --install  smart-intersection ./chart \
#     --create-namespace \
#     --set httpProxy="http://proxy.example.com:8080" \
#     --set httpsProxy="http://proxy.example.com:8080" \
#     --set noProxy="localhost\,127.0.0.1" \
#     --set grafana.service.type=NodePort \
#     -n smart-intersection

# Provision data to DL Streamer Pipeline Server
# ======================

sleep 5 # Wait for the pods to be up

# Get the pod
DLS_PS_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-dlstreamer-pipeline-server -o jsonpath="{.items[0].metadata.name}")

# Copy data to the pod init containers
# > **⚠️ Note:** Sometimes init-dlstreamer-pipeline-server-models container gets created first and then init-dlstreamer-pipeline-server-videos. In that case, the order of copying data to the pod should be reversed.

kubectl cp ./src/dlstreamer-pipeline-server/videos smart-intersection/${DLS_PS_POD}:/data/ -c init-dlstreamer-pipeline-server-videos
kubectl -n smart-intersection exec $DLS_PS_POD -c init-dlstreamer-pipeline-server-videos -- touch /data/videos/.done
sleep 5 # Wait for the init container to finish
kubectl cp ./src/dlstreamer-pipeline-server/models/intersection smart-intersection/${DLS_PS_POD}:/data/models -c init-dlstreamer-pipeline-server-models
kubectl -n smart-intersection exec $DLS_PS_POD -c init-dlstreamer-pipeline-server-models -- touch /data/models/.done

sleep 5 # Wait for the init containers to finish

# Provision data to pgserver
# ==========================

# Get the pod
PGSERVER_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-pgserver -o jsonpath="{.items[0].metadata.name}")

# Copy data to the pod init container
kubectl cp ./src/webserver/smart-intersection-ri.tar.bz2 smart-intersection/${PGSERVER_POD}:/data/ -c init-smart-intersection-ri

# Signal the init container to start
kubectl -n smart-intersection exec $PGSERVER_POD -c init-smart-intersection-ri -- touch /data/.done

sleep 5 # Wait for the init container to finish

# Access Application Services
# ===========================
#
# Use kubectl port-forward to access the application services on <protocol>://localhost:<service-port>
# For more available options, see https://kubernetes.io/docs/reference/kubectl/generated/kubectl_port-forward/#options

# Access the Application UI
# =========================
WEB_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-web -o jsonpath="{.items[0].metadata.name}")
sudo -E kubectl -n smart-intersection port-forward $WEB_POD 443:443

# Access the Grafana UI
# =====================
GRAFANA_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-grafana -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $GRAFANA_POD 3000:3000

# Access the InfluxDB UI
# ======================
INFLUX_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-influxdb -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $INFLUX_POD 8086:8086

# Access the NodeRED UI
# =====================
NODE_RED_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-nodered -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $NODE_RED_POD 1880:1880

# Access the DL Streamer Pipeline Server
# =======================
DLS_PS_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-dlstreamer-pipeline-server -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $DLS_PS_POD 8080:8080
kubectl -n smart-intersection port-forward $DLS_PS_POD 8555:8555
  ```

### How to Delete the Namespace
To delete the namespace and all resources within it, run the following command:

```bash
kubectl delete namespace smart-intersection
```

## What to Do Next

- **[How to Use the Application](./how-to-use-application.md)**: Verify the application and access its features.
- **[Troubleshooting Helm Deployments](./support.md#troubleshooting-helm-deployments)**: Consolidated troubleshooting steps for resolving issues during Helm deployments.
- **[Get Started](./get-started.md)**: Ensure you have completed the initial setup steps before proceeding.

## Supporting Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Helm Documentation](https://helm.sh/docs/)

# Deploy with Helm

Use Helm to deploy Smart Intersection to a Kubernetes cluster.
This guide will help you:

- Add the Helm chart repository.
- Configure the Helm chart to match your deployment needs.
- Deploy and verify the application.

Helm simplifies Kubernetes deployments by streamlining configurations and
enabling easy scaling and updates. For more details, see
[Helm Documentation](https://helm.sh/docs/).

## Prerequisites

Before You Begin, ensure the following:

- **Kubernetes Cluster**: Ensure you have a properly installed and
configured Kubernetes cluster.
- **System Requirements**: Verify that your system meets the [minimum requirements](./system-requirements.md).
- **Tools Installed**: Install the required tools:
  - Kubernetes CLI (kubectl)
  - Helm 3 or later
- **cert-manager**: Will be installed as part of the deployment process (instructions provided below)

## Steps to Deploy

To deploy the Smart Intersection Sample Application, copy and paste the entire block of following commands into your terminal and run them:


### Step 1: Clone the Repository

Before you can deploy with Helm, you must clone the repository:

```bash
# Clone the repository
git clone https://github.com/open-edge-platform/edge-ai-suites.git

# Navigate to the Metro AI Suite directory
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
```

### Step 2: Configure Proxy Settings (If behind a proxy)

If you are deploying in a proxy environment, update the values.yaml file with your proxy settings before installation:

```bash
# Edit the values.yml file to add proxy configuration
nano ./smart-intersection/chart/values.yaml
```

Update the existing proxy configuration in your values.yaml with following values:

```yaml
http_proxy: "http://your-proxy-server:port"
https_proxy: "http://your-proxy-server:port"
no_proxy: "localhost,127.0.0.1,.local,.cluster.local"
```

Replace `your-proxy-server:port` with your actual proxy server details.

### Install cert-manager

The Smart Intersection application requires cert-manager for TLS certificate management. Install cert-manager before deploying the application:

```bash
# Install cert-manager
helm install \
  cert-manager oci://quay.io/jetstack/charts/cert-manager \
  --version v1.18.2 \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true
```

### Step 3: Deploy the application

Now you're ready to deploy the Smart Intersection application:

```bash
# Install the chart
helm upgrade --install smart-intersection ./smart-intersection/chart \
  --create-namespace \
  --set grafana.service.type=NodePort \
  -n smart-intersection
```

## Access Application Services using Node Port

### Access the Application UI using Node Port

- Get the Node Port Number using following command and use it to access the Application UI

```bash
kubectl get service smart-intersection-web -n smart-intersection -o jsonpath='{.spec.ports[0].nodePort}'
```

- Go to https://<HOST_IP>:<Node_PORT>
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: Stored in `supass` secret. To retrieve run the following command:

    ```bash
    kubectl get secret smart-intersection-supass-secret -n smart-intersection -o jsonpath='{.data.supass}' | base64 -d && echo
    ```

### Access the Grafana UI using Node Port

- Get the Node Port Number using following command and use it to access the Grafana UI

```bash
kubectl get service smart-intersection-grafana -n smart-intersection -o jsonpath='{.spec.ports[0].nodePort}'
```

- Go to http://<HOST_IP>:<Node_PORT>
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: `admin`

## Access Application Services using Port Forwarding (Optional)

### Access the Application UI

```bash
WEB_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-web -o jsonpath="{.items[0].metadata.name}")
sudo -E kubectl -n smart-intersection port-forward $WEB_POD 443:443 --address <HOST_IP>
```

- Go to https://<HOST_IP>
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: Stored in `supass` secret. To retrieve run the following command:

    ```bash
    kubectl get secret smart-intersection-supass-secret -n smart-intersection -o jsonpath='{.data.supass}' | base64 -d && echo
    ```

### Access the Grafana UI

```bash
GRAFANA_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-grafana -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $GRAFANA_POD 3000:3000
```

- Go to http://<HOST_IP>:<Node_PORT>
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: `admin`

### Access the InfluxDB UI

```bash
INFLUX_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-influxdb -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $INFLUX_POD 8086:8086
```

### Access the NodeRED UI

```bash
NODE_RED_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-nodered -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $NODE_RED_POD 1880:1880
```

### Access the DL Streamer Pipeline Server

```bash
DLS_PS_POD=$(kubectl get pods -n smart-intersection -l app=smart-intersection-dlstreamer-pipeline-server -o jsonpath="{.items[0].metadata.name}")
kubectl -n smart-intersection port-forward $DLS_PS_POD 8080:8080
kubectl -n smart-intersection port-forward $DLS_PS_POD 8555:8555
```

## Uninstall the Application

To uninstall the application, run the following command:

```bash
helm uninstall smart-intersection -n smart-intersection
```

## Delete the Namespace

To delete the namespace and all resources within it, run the following command:

```bash
kubectl delete namespace smart-intersection
```

## What to Do Next

- **[Troubleshooting Helm Deployments](./support.md#troubleshooting-helm-deployments)**: Consolidated troubleshooting steps for resolving issues during Helm deployments.
- **[Get Started](./get-started.md)**: Ensure you have completed the initial setup steps before proceeding.

## Supporting Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Helm Documentation](https://helm.sh/docs/)

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
- **Storage Provisioner**: A default storage class is required for persistent volumes

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

### Step 2: Configure External IP and Proxy Settings

#### Configure External IP (Required)

The Smart Intersection application needs to know your cluster's external IP address for proper certificate generation and CSRF security configuration. Update the external IP in the values.yaml file:

```bash
# Edit the values.yaml file to set your external IP
nano ./smart-intersection/chart/values.yaml
```

Find the `global.externalIP` section and update it with your actual external IP address:

```yaml
# Global configuration
global:
  # External IP address for certificate generation and CSRF configuration
  externalIP: "YOUR_EXTERNAL_IP_HERE"
```

Replace `YOUR_EXTERNAL_IP_HERE` with your actual external IP address where the application will be accessible.

#### Configure Proxy Settings (If behind a proxy)

If you are deploying in a proxy environment, also update the proxy settings in the same values.yaml file:

```yaml
http_proxy: "http://your-proxy-server:port"
https_proxy: "http://your-proxy-server:port"
no_proxy: "localhost,127.0.0.1,.local,.cluster.local"
```

Replace `your-proxy-server:port` with your actual proxy server details.



### Step 3: Setup Storage Provisioner (For Single-Node Clusters)

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

### Step 4: Deploy the application

Now you're ready to deploy the Smart Intersection application with nginx reverse proxy and self-signed certificates:

```bash
# Install the chart (works on both single-node and multi-node clusters)
helm upgrade --install smart-intersection ./smart-intersection/chart \
  --create-namespace \
  --set global.storageClassName="" \
  -n smart-intersection

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n smart-intersection --timeout=300s
```

> **Note**: Using `global.storageClassName=""` makes the deployment use whatever default storage class exists on your cluster.

## Access Application Services

### Smart Intersection Application UI
- **URL**: `https://<HOST_IP>:30443/`
- **Username**: `admin`
- **Password**: Get from secrets:
  ```bash
  kubectl get secret smart-intersection-supass-secret -n smart-intersection -o jsonpath='{.data.supass}' | base64 -d && echo
  ```

### Grafana Dashboard  
- **URL**: `https://<HOST_IP>:30443/grafana/`
- **Username**: `admin`
- **Password**: `admin`

### InfluxDB
- **URL**: `http://<HOST_IP>:30086/`
- **Username**: `admin`
- **Password**: Get from secrets:
  ```bash
  kubectl get secret smart-intersection-influxdb-secrets -n smart-intersection -o jsonpath='{.data.influxdb2-admin-password}' | base64 -d && echo
  ```

### NodeRED Editor
- **URL**: `https://<HOST_IP>:30443/nodered/`
- **No login required** - Visual programming interface

### DL Streamer Pipeline Server
- **URL**: `https://<HOST_IP>:30443/api/pipelines/status`
- **API Access**: No authentication required for status endpoints

> **Note**: For InfluxDB, use the direct access on port 30086 (`http://<HOST_IP>:30086/`) for login and full functionality. The proxy access through nginx (`https://<HOST_IP>:30443/influxdb/`) provides basic functionality and API access but is not recommended for the web UI login.

> **Security Note**: The application uses self-signed certificates for HTTPS. Your browser will show a security warning when first accessing the site. Click "Advanced" and "Proceed to site" (or equivalent) to continue. This is safe for local deployments.


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

## Complete Cleanup

If you want to completely remove all infrastructure components installed during the setup process:

```bash
# Remove local-path-provisioner (if installed)
kubectl delete -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml

# Delete all PVCs in the smart-intersection namespace
kubectl delete pvc --all -n smart-intersection

# Delete any remaining PVs (persistent volumes)
kubectl delete pv --all

# Force cleanup of stuck PVCs if needed (patch each PVC individually)
kubectl get pvc -n smart-intersection --no-headers | awk '{print $1}' | xargs -I {} kubectl patch pvc {} -n smart-intersection --type merge -p '{"metadata":{"finalizers":null}}'

# Remove additional storage classes (if created)
kubectl delete storageclass hostpath local-storage standard
```

> **Note**: This complete cleanup will remove storage provisioning from your cluster. You'll need to reinstall the storage provisioner for future deployments that require persistent volumes.

> **Run workload on GPU**: Set `gpuWorkload: true` in values.yaml file before deploying the helm chart.


## What to Do Next

- **[Troubleshooting Helm Deployments](./support.md#troubleshooting-helm-deployments)**: Consolidated troubleshooting steps for resolving issues during Helm deployments.
- **[Get Started](./get-started.md)**: Ensure you have completed the initial setup steps before proceeding.

## Supporting Resources

- [Kubernetes Documentation](https://kubernetes.io/docs/home/)
- [Helm Documentation](https://helm.sh/docs/)

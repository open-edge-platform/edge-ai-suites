# Deploy with Trusted Compute using Helm

Use Helm to deploy Smart Intersection with Trusted Compute to a k3s cluster.
This guide will help you:

- Install and configure Intel Trusted Compute on k3s cluster.
- Configure the Helm chart for Trusted Compute deployment.
- Deploy the application with hardware-isolated workloads.
- Verify Trusted Compute runtime is active.

Intel Trusted Compute runs workloads inside hardware-isolated VMs, protecting inference workloads and video data from untrusted co-tenants on the same host. For more details on Trusted Compute, see the [Trusted Compute Documentation](https://github.com/open-edge-platform/trusted-compute).

## Prerequisites

Before You Begin, ensure the following:

- **k3s Cluster**: Ensure you have a properly installed and configured k3s cluster.
- **System Requirements**:
  - Verify that your system meets the [minimum requirements](./system-requirements.md).
  - **Minimum RAM**: 32GB RAM is required for Trusted Compute deployments.
- **Tools Installed**: Install the required tools:
  - Kubernetes CLI (kubectl)
  - Helm 3 or later
- **Storage Provisioner**: A default storage class is required for persistent volumes.
- **Important:** Trusted Compute is not compatible with Docker version 29.5 or later. Docker version 29.4.x is required.

**Additional Prerequisites for GPU Deployment:**

- Intel CPU with VT-x and VT-d, integrated GPU, and IOMMU enabled in BIOS/UEFI
- Linux kernel with IOMMU, VFIO, and DRM/i915 or xe driver support

> **Note**: When GPU passthrough is enabled with Trusted Compute, the iGPU is exclusively bound to the Trusted Compute VM and is unavailable to the host or other workloads.

## 1. Install Trusted Compute

Follow the [Trusted Compute baremetal installation guide](https://github.com/open-edge-platform/trusted-compute/blob/main/docs/trusted_compute_baremetal.md) to install Trusted Compute version 1.5.3 or later. Complete the following sections:

1. Prerequisites
2. Download the Trusted Compute Package
3. K3s Option

## 2. Prepare for Deployment

### Step 1: Clone the Repository

Before you can deploy with Helm, you must clone the repository:

```bash
# Clone the repository
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b main

# Navigate to the Metro AI Suite directory
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
```

**Optional:** Pull the helm chart and replace the existing helm-chart folder with it.
> **Note:** The helm chart should be downloaded when you are not using the helm chart provided in `edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/chart`

```bash
# Navigate to Smart Intersection directory
cd smart-intersection

# Download helm chart with the following command
helm pull oci://registry-1.docker.io/intel/smart-intersection --version 1.19.0

# unzip the package using the following command
tar -xvf smart-intersection-1.19.0.tgz

# Replace the helm directory
rm -rf chart && mv smart-intersection chart

cd ..
```

### Step 2: Set Up Passwords

#### Set Admin and Postgres Passwords

These passwords need to be set before deployment. You can set them in the `values.yaml` file.
```bash
# Edit the values.yaml file to set your passwords
nano ./smart-intersection/chart/values.yaml
```
Find the following sections and update them with your desired passwords:

```yaml
supass: <YOUR_ADMIN_PASSWORD>  # Admin password for Smart Intersection
pgpass: <YOUR_POSTGRES_PASSWORD>  # Postgres password for Smart Intersection
```

### Step 3: Configure External IP and Proxy Settings

#### Configure External IP (Required)

The Smart Intersection application needs to know your cluster's external IP address for proper certificate generation and CSRF security configuration. Update the external IP in the `values.yaml` file:

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

If you are deploying in a proxy environment, also update the proxy settings in the same `values.yaml` file:

```yaml
http_proxy: "http://your-proxy-server:port"
https_proxy: "http://your-proxy-server:port"
no_proxy: "localhost,127.0.0.1,.local,.cluster.local"
```

Replace `your-proxy-server:port` with your actual proxy server details.

### Step 4: Setup Storage Provisioner(For Single-Node Clusters)

Check if your k3s cluster has a default storage class with dynamic provisioning. If not, install a storage provisioner:

```bash
# Check for existing storage classes
kubectl get storageclass

# If no storage classes exist or none are marked as default, install local-path-provisioner
# k3s typically comes with local-path provisioner by default, but if not present:

# Install local-path-provisioner for automatic storage provisioning
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml

# Set it as default storage class
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'

# Verify storage class is ready
kubectl get storageclass
```

## 3. Deploy the Application

Choose one of the following paths based on whether you need GPU acceleration.

---

### Option A: CPU Deployment

Deploy the Smart Intersection application with Trusted Compute enabled on CPU:

```bash
helm upgrade --install smart-intersection ./smart-intersection/chart \
  --create-namespace \
  --set global.storageClassName="" \
  --set trustedCompute.enabled=true \
  -n smart-intersection

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n smart-intersection --timeout=300s
```

> **Note:** Using `global.storageClassName=""` makes the deployment use whatever default storage class exists on your cluster.

---

### Option B: GPU Deployment

#### Step 1: Bind GPU to vfio-pci

> **Note:** Binding the GPU stops the display manager and disables the graphical display on the host. Run this step over SSH. The display is restored after running the `unbind` command.

Use the `intel-igpu-vfio-bind.sh` script from the `tools/` directory of the package installed in [Step 1](#1-install-trusted-compute) to bind the Intel iGPU to the `vfio-pci` driver on each GPU-enabled k3s host.

```bash
sudo ./tools/intel-igpu-vfio-bind.sh bind
```

Verify the GPU is bound correctly:

```bash
lspci -nnk -d 8086: | grep -A 3 "VGA\|Display"
```

The output should show `Kernel driver in use: vfio-pci` for your Intel GPU.

#### Step 2: Deploy with GPU Enabled

```bash
helm upgrade --install smart-intersection ./smart-intersection/chart \
  --create-namespace \
  --set global.storageClassName="" \
  --set trustedCompute.enabled=true \
  --set trustedCompute.tc_gpu_enabled=true \
  -n smart-intersection

# Wait for all pods to be ready
kubectl wait --for=condition=ready pod --all -n smart-intersection --timeout=300s
```

> **Note:** Using `global.storageClassName=""` makes the deployment use whatever default storage class exists on your cluster.

---

## 4. Verify Deployment

Verify that the pods are running with the Trusted Compute:

```bash
# Check that DL Streamer pods are using the trusted compute
kubectl get pods -n smart-intersection -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.runtimeClassName}{"\n"}{end}' | grep dlstreamer

# Verify the pods are running
kubectl get pods -n smart-intersection

# Check DL Streamer pod logs to ensure containers started successfully
kubectl logs -n smart-intersection -l app=smart-intersection-dlstreamer-pipeline-server --tail=30
```

You should see the DL Streamer Pipeline Server pods running with the Trusted Compute.

## 5. Access the Application

### Smart Intersection Application UI
- **URL**: `https://<HOST_IP>:30443/`
- **Username**: `admin`
- **Password**: <YOUR_ADMIN_PASSWORD> (set in `values.yaml`)

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

> **Note:** For InfluxDB, use the direct access on port 30086 (`http://<HOST_IP>:30086/`) for login and full functionality. The proxy access through nginx (`https://<HOST_IP>:30443/influxdb/`) provides basic functionality and API access but is not recommended for the web UI login.

> **Security Note:** The application uses self-signed certificates for HTTPS. Your browser will show a security warning when first accessing the site. Click "Advanced" and "Proceed to site" (or equivalent) to continue. This is safe for local deployments.

## 6. Clean Up Deployment

Follow the steps below in order to cleanly remove the deployment.

**Step 1. Uninstall the application and delete the namespace:**

```bash
helm uninstall smart-intersection -n smart-intersection
kubectl delete namespace smart-intersection
```

**Step 2. Revert GPU Binding** (if deployed with GPU):

On each k3s host where the GPU was bound, unbind it from vfio-pci:

```bash
sudo ./tools/intel-igpu-vfio-bind.sh unbind
```

This will restore the display manager and graphical display on the host.

**Step 3. Clean Up the Trusted Compute Deployment**

To uninstall Trusted Compute from the k3s nodes after you have removed the application, refer to the [Trusted Compute documentation](https://github.com/open-edge-platform/trusted-compute/blob/main/docs/trusted_compute_baremetal.md).

## Additional Cleanup (Optional)

For complete infrastructure cleanup, you can remove all infrastructure components installed during the setup process:

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
kubectl delete storageclass hostpath local-storage standard local-path
```

> **Note:** This complete cleanup will remove storage provisioning from your cluster. You will need to reinstall the storage provisioner for future deployments that require persistent volumes.

## Learn More

- [Trusted Compute Documentation](https://github.com/open-edge-platform/trusted-compute): Complete guide to Intel Trusted Compute
- [Troubleshooting Helm Deployments](../troubleshooting.md#troubleshooting-helm-deployments): Consolidated troubleshooting steps

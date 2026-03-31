# Secure Smart Intersection Agent Deployment with Trusted Compute

This guide describes how to deploy the **Smart Traffic Intersection Agent (STIA)** in a **Trusted Compute (TC)** environment. The application analyzes traffic scenarios at an intersection, provides driving suggestions, sends alerts, and exposes an interface that other agents can use to query intersection data.

---

## System prerequisites

Ensure your deployment environment meets these requirements before you begin:

- **Container orchestration**: **K3s** (lightweight Kubernetes distribution)
- **Package manager**: **Helm** (for Kubernetes application lifecycle management)
- **System memory**: **64GB**

---

## Implementation guide (K3s + Helm)

### Step 1: Set up the infrastructure (K3s and Helm)

#### 1.1: Deploy K3s Kubernetes platform

```bash
# Download and install K3s
curl -sfL https://get.k3s.io | sh -

# Verify the installation
sudo systemctl status k3s

# Check cluster readiness
sudo k3s kubectl get nodes

# Configure kubectl access
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config

# Set KUBECONFIG (recommended to point to your user kubeconfig)
export KUBECONFIG=$HOME/.kube/config
echo 'export KUBECONFIG=$HOME/.kube/config' >> ~/.bashrc
source ~/.bashrc
```

> **Note:** Avoid setting `KUBECONFIG=/etc/rancher/k3s/k3s.yaml` for everyday use. That file is root-owned and can cause permission issues. Copying it to `~/.kube/config` and pointing `KUBECONFIG` there is the recommended approach.

#### Install Helm package manager

```bash
# Download Helm installation script
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
chmod +x get_helm.sh

# Install Helm
./get_helm.sh

# Verify installation
helm version
```
#### 1.2 Install Trusted Compute

A fully operational TC environment is required for secure deployment.

> **Note:** If you already completed the K3s installation in step 1.1, skip that portion of the TC installation guide.

1. Pull the installation package, replacing `TAG` with `1.4.7`:

   ```bash
   oras pull registry-rs.edgeorchestration.intel.com/edge-orch/trusted-compute/baremetal/trusted-compute-installation-package:1.4.7
   ```

2. Follow the [TC Installation Guide](https://github.com/open-edge-platform/trusted-compute/blob/main/docs/trusted_compute_baremetal.md) to complete the setup.

---

### Step 2: Get the source code

Clone the Edge AI Suites repository and navigate to the application directory:

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git -b release-1.2.0 si_deploy
cd si_deploy/metro-ai-suite/metro-vision-ai-app-recipe/
```

---

### Step 3: Enable Trusted Compute security (Smart Intersection / DLSPS)

This step applies to the **Smart Intersection** Helm chart, which includes the **DL Streamer Pipeline Server (DLSPS)**.

1. Change to the DLSPS deployment template directory (the exact path may vary by release):

```bash
cd smart-intersection/chart/templates/dlstreamer-pipeline-server/
```

#### Option 1: Manual runtime configuration

Open `deployment.yaml` and add `runtimeClassName: kata-qemu` under the Pod template `spec`:

```bash
vi deployment.yaml
```

```yaml
spec:
  replicas: 1
  selector:
    matchLabels:
      app: {{ .Release.Name }}-dlstreamer-pipeline-server
  template:
    metadata:
      labels:
        app: {{ .Release.Name }}-dlstreamer-pipeline-server
    spec:
      runtimeClassName: kata-qemu
      securityContext:
        supplementalGroups: [109, 110, 992]
      volumes:
```

#### Option 2: Automated runtime configuration (use with care)

If the template contains a `template:` block followed by a `volumes:` block, you can insert `runtimeClassName` automatically:

```bash
sed -i '/template:/,/volumes:/ { /spec:/a\
      runtimeClassName: kata-qemu
}' deployment.yaml
```

> **Important:** `sed`-based edits depend on the exact YAML structure. Always review the file after applying this change.

#### Add resource configuration (DLSPS)

Open `deployment.yaml` and configure CPU and memory resources for the DLSPS container:

```bash
vi deployment.yaml
```

```yaml
resources:
  requests:
    memory: "16Gi"
    cpu: "4"
  limits:
    memory: "16Gi"
    cpu: "4"
```

---

### Step 4: Network configuration (WebRTC signaling server)

Update `configmap.yaml` to replace `localhost` with your host IP address to enable remote access.

#### Option 1: Manual update

```yaml
# Replace:
# WEBRTC_SIGNALING_SERVER: "ws://localhost:8443"

# With:
WEBRTC_SIGNALING_SERVER: "ws://<HOST_IP>:8443"
```

#### Option 2: Automated update

```bash
DEVICE_IP=$(hostname -I | awk '{print $1}') && sed -i "s|ws://localhost:8443|ws://$DEVICE_IP:8443|g" configmap.yaml
```

---

### Step 5: Deploy the Smart Intersection application (Helm)

From the `si_deploy/metro-ai-suite/metro-vision-ai-app-recipe/` directory, follow the [Smart Intersection Helm deployment guide](https://github.com/open-edge-platform/edge-ai-suites/blob/release-1.2.0/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/how-to-deploy-helm.md).

> **Note:** If you already cloned the repository in step 2, skip the `git clone` step in the linked guide and proceed with the remaining steps.

---

### Step 6: Verify Trusted Compute isolation and monitor logs

#### Confirm secure isolation (Kata/QEMU)

```bash
ps aux | grep qemu
```

A successful Trusted Compute deployment shows a QEMU process (started by Kata Containers) with VM parameters and a PID.

#### Monitor DL Streamer logs

```bash
kubectl logs <dl-streamer-pod-name> -n smart-intersection
```

---

## Application management

### Uninstall the Smart Intersection

Before deploying a new STIA instance, remove any existing deployment:

```bash
# Uninstall Helm releases (only run the ones that exist)
helm uninstall smart-intersection -n smart-intersection

# Remove the namespace and all associated resources
kubectl delete namespace smart-intersection
```

> **Tip:** If the namespace does not exist, `kubectl` returns an error that is safe to ignore.

---

## Enhanced security architecture (Trusted Compute)

Trusted Compute provides layered security benefits, including:

- **Workload isolation**: Workloads run inside hardware-isolated Kata VMs to reduce the blast radius between pods/workloads.
- **Memory encryption**: Protects sensitive data (e.g., video streams, inference artifacts) against certain physical and cold-boot style attacks (platform dependent).
- **Secure boot**: Ensures only verified components are used during boot (platform dependent).
- **Full disk encryption (FDE)**: Helps protect stored data if a device is lost or physically compromised (platform dependent).

This isolated execution environment helps protect traffic management workloads while maintaining application functionality and performance.


# Trusted Compute Smart City Intersection

The Smart Intersection is a sample application that unifies the analytics of a traffic intersection using Trusted Compute technology. Deep Learning Streamer Pipeline Server (DL Streamer Pipeline Server) utilizes a pre-trained object detection model to generate object detection metadata and a local NTP server for synchronized timestamps. This metadata is published to the MQTT broker. This example demonstrates the deployment of the DL Streamer Pipeline Server in a TC environment, facilitating the isolation of video analytics pipelines.

## Prerequisites

- Trusted Compute must be installed and running
- K3s (Kubernetes) installed on the system
- Helm package manager installed

## Step 1: Install Required Tools

**Install K3s if not already available:**

```bash
# Install K3s
curl -sfL https://get.k3s.io | sh -

# Verify K3s Installation
sudo systemctl status k3s

# Wait a moment for K3s to fully start, then check nodes
sudo k3s kubectl get nodes

# Set up Kubeconfig
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER:$USER ~/.kube/config
chmod 600 ~/.kube/config
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' >> ~/.bashrc
source ~/.bashrc
```

**Install Helm:**

```bash
curl -fsSL -o get_helm.sh https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3
chmod +x get_helm.sh
# Execute the script to install Helm
./get_helm.sh
# Verify the installation
helm version
```

## Step 2: Clone the Repository

Clone and navigate to the Smart Intersection Helm repository:

```bash
# Clone the repository
git clone https://github.com/open-edge-platform/edge-ai-suites.git

# Navigate to the Metro AI Suite directory
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
```

## Step 3: Replace the Deployment YAML

Inside the `smart-intersection/chart/templates/dlstreamer-pipeline-server/` directory, replace the deployment.yaml with the YAML file available [here](https://github.com/open-edge-platform/trusted-compute/blob/main/samples/ai/smart-intersection/deployment.yaml)

```bash
# Navigate to the templates directory
cd smart-intersection/chart/templates/dlstreamer-pipeline-server/

# Replace the deployment file with your custom version
# Copy the custom deployment.yaml to this location

# Update the WEBRTC_SIGNALING_SERVER configuration
# In configmap.yaml, change:
# WEBRTC_SIGNALING_SERVER: "ws://localhost:8443" 
# to:
# WEBRTC_SIGNALING_SERVER: "ws://<Host_IP>:8443"
# Where <Host_IP> is the Host IP of the machine where the application is running
```

## Step 4: Configure Resource Allocation

Configure resource allocation to allocate CPU cores and memory. You can adjust the resource requirements according to your specific needs by modifying the resource specifications in the deployment YAML file.

## Step 5: Deploy the Helm Chart

Follow the steps mentioned in the official documentation to run the Helm chart:

[Steps to Deploy the Helm Chart](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/metro-vision-ai-app-recipe/smart-intersection/docs/user-guide/how-to-deploy-helm.md)

## Step 6: Verify DL Streamer Launch

**1. Verify the DL Streamer Launch in TC**

To confirm that the DL Streamer has successfully launched in the Trusted Compute environment, check if the virtual machine associated with it is running:

```bash
ps aux | grep qemu
```

If DL Streamer is running correctly, you should see a process entry for the corresponding QEMU instance. This entry typically includes:
- The command used to launch the VM
- The amount of CPU/memory it is using
- The process ID (PID) of the VM

**2. Check DL Streamer Logs**

To monitor the DL Streamer and see the total frames per second (FPS) count, postdecode timestamp, check the logs of the DL Streamer pod:

```bash
kubectl logs <dl-streamer-deployment-name> -n smart-intersection
```

This trusted compute implementation adds an additional layer of security by isolating video analytics pipelines within secure virtual machines, ensuring that sensitive traffic analysis operations are protected from potential threats.


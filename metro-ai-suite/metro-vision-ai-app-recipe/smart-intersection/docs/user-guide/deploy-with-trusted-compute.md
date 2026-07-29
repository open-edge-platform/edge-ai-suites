# Deploy with Trusted Compute

This guide walks you through deploying the Smart Intersection Sample Application with Intel Trusted Compute, which runs workloads inside a hardware-isolated VM, protecting inference workloads and video data from untrusted co-tenants on the same host.

To get started:

- **Set up the sample application**: use Docker Compose with Trusted Compute to deploy the application in your environment with hardware isolation.
- **Run a predefined pipeline**: execute a sample pipeline to see real-time transportation monitoring and object detection in action within a trusted execution environment.
- **Access the application's features and user interfaces**: explore the Scenescape Web UI, Grafana dashboard, Node-RED interface, and DL Streamer Pipeline Server to monitor, analyze and customize workflows.
- **Consider Security features**: leverage hardware-based security measures including Trusted Compute to make your application safer.

## Prerequisites

Before you begin, ensure the following:

- Verify that your system meets the [minimum requirements](./get-started/system-requirements.md).
 - **Minimum RAM**: 32GB RAM is required for Trusted Compute deployments.
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
  - **Important:** Trusted Compute is not compatible with Docker version 29.5 or later. Docker version 29.4.x is required.
- Enable running docker without "sudo": [Post Install](https://docs.docker.com/engine/install/linux-postinstall/).
- Install Git: [Installing Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git).

**Additional Prerequisites for GPU Deployment:**

- Intel CPU with VT-x and VT-d, integrated GPU, and IOMMU enabled in BIOS/UEFI
- Linux kernel with IOMMU, VFIO, and DRM/i915 or xe driver support

## Setup and First Use

1. **Clone the Suite**:

   Go to the target directory of your choice and clone the suite.
   If you want to clone a specific release branch, replace `main` with the desired tag.
   To learn more on partial cloning, check the [Repository Cloning guide](https://docs.openedgeplatform.intel.com/dev/OEP-articles/contribution-guide.html#repository-cloning-partial-cloning).

   ```bash
   git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
   cd edge-ai-suites
   git sparse-checkout set metro-ai-suite
   cd metro-ai-suite/metro-vision-ai-app-recipe/
   ```

2. **Install Trusted Compute**

   Follow the [Trusted Compute baremetal installation guide](https://github.com/open-edge-platform/trusted-compute/blob/main/docs/trusted_compute_baremetal.md) to install Trusted Compute version 1.5.3 or later on your host system. Complete the following sections:

   - Prerequisites
   - Download the Trusted Compute Package
   - Docker Option

   > **Note:** Trusted Compute version 1.5.3 or later is recommended for this deployment. However, Trusted Compute 1.5.3 is not compatible with Docker version 29.5 or later. Docker version 29.4.x is required.

3. **Configure Network Settings (Optional)**

   By default, Trusted Compute uses the subnet `172.20.0.0/16` for isolated container networking. If this subnet conflicts with your existing networks, you can customize it before deployment.

   **Requirements:**

   - Subnet format must be exactly `172.X.0.0/16` where `X` is between 18–31 (RFC 1918 private IP range)
   - The subnet must not conflict with existing Docker networks on your system
   - DNS relay service will be automatically configured at `172.X.0.200`

   **Example:**

   ```bash
   # Optional: Customize the subnet if needed (default is 172.20.0.0/16)
   export TC_SUBNET=172.25.0.0/16  # DNS relay will be at 172.25.0.200
   ```

## Run the Application

Choose one of the following paths based on whether you need GPU acceleration.

---

### Option A: CPU Deployment

#### Step 1: Setup Application and Download Assets

Use the installation script to configure the application and download required models with Trusted Compute enabled:

```bash
export ENABLE_TC=true
./install.sh smart-intersection
```

> **Note:** For environments requiring a specific host IP address (for example, when deploying across different network interfaces), you can explicitly specify the IP address (Replace `<HOST_IP>` with your target IP address.):
> `./install.sh smart-intersection <HOST_IP>`

#### Step 2: Start the Application

Export admin password as environment variable:

```bash
export SUPASS=$(cat ./smart-intersection/src/secrets/supass)
```

Download container images with Application microservices and run with Docker Compose:

```bash
docker compose up -d
```

<details>
<summary>
Check Status of Microservices
</summary>

- The application starts the following microservices.
- To check if all microservices are in Running state:

  ```bash
  docker ps
  ```

**Expected Services:**
- Grafana Dashboard
- DL Streamer Pipeline Server
- MQTT Broker
- Node-RED (for applications without Scenescape)
- Scenescape services (for Smart Intersection only)

</details>

---

### Option B: GPU Deployment

> **Note:** When GPU passthrough is enabled, the iGPU is exclusively bound to the Trusted Compute VM and is unavailable to the host or other workloads.

#### Step 1: Bind GPU to vfio-pci

> **Warning:** Binding the GPU stops the display manager and disables the graphical display on the host. Run this step over SSH. The display is restored after running the `unbind` command.

Use the `intel-igpu-vfio-bind.sh` script from the `tools/` directory of the Trusted Compute package installed in [Setup and First Use, step 2](#setup-and-first-use) to bind the Intel iGPU to the `vfio-pci` driver.

```bash
sudo ./tools/intel-igpu-vfio-bind.sh bind
```

Verify the GPU is bound correctly:

```bash
lspci -nnk -d 8086: | grep -A 3 "VGA\|Display"
```

The output should show `Kernel driver in use: vfio-pci` for your Intel GPU.

#### Step 2: Configure GPU for Inference

Follow the [How to Use GPU for Inference](./how-to-use-gpu-for-inference.md) guide to properly configure your GPU settings for optimal inference performance with Trusted Compute.

#### Step 3: Setup Application and Download Assets

Use the installation script to configure the application and download required models with Trusted Compute and GPU enabled:

```bash
export ENABLE_TC=true
export TC_SI_TARGET_DEVICE=GPU
./install.sh smart-intersection
```

> **Note:** For environments requiring a specific host IP address (for example, when deploying across different network interfaces), you can explicitly specify the IP address (Replace `<HOST_IP>` with your target IP address.):
> `export ENABLE_TC=true && export TC_SI_TARGET_DEVICE=GPU && ./install.sh smart-intersection <HOST_IP>`

#### Step 4: Start the Application

Export admin password as environment variable:

```bash
export SUPASS=$(cat ./smart-intersection/src/secrets/supass)
```

Download container images with Application microservices and run with Docker Compose:

```bash
docker compose up -d
```

<details>
<summary>
Check Status of Microservices
</summary>

- The application starts the following microservices.
- To check if all microservices are in Running state:

  ```bash
  docker ps
  ```

**Expected Services:**
- Grafana Dashboard
- DL Streamer Pipeline Server
- MQTT Broker
- Node-RED (for applications without Scenescape)
- Scenescape services (for Smart Intersection only)

</details>

---

## Access the Application and Components

### Application UI

Open a browser and go to the following endpoints to access the application. Use `<actual_ip>` instead of `localhost` for external access:

> **Note:**
>
> - All services are accessed through the nginx reverse proxy at `https://localhost` with appropriate paths.
> - For passwords stored in files (e.g., `supass` or `influxdb2-admin-token`), refer to the respective secret files in your deployment under ./src/secrets (Docker) or chart/files/secrets (Helm).
> - Since the application uses HTTPS with self-signed certificates, your browser may display a certificate warning. For the best experience, use **Google Chrome** and accept the certificate.

- **URL**: [https://localhost](https://localhost)
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: Stored in `supass`. (Check `./smart-intersection/src/secrets/supass`)

> **Note**:
>
> - After starting the application, wait approximately 1 minute for the MQTT broker to initialize. You can confirm it is ready when green arrows appear for MQTT in the application interface. Since the application uses HTTPS, your browser may display a self-signed certificate warning. For the best experience, use **Google Chrome**.

### Grafana UI

- **URL**: [https://localhost/grafana/](https://localhost/grafana/)
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: `admin` (You will be prompted to change it on first login.)

### InfluxDB UI

- **URL**: [http://localhost:8086](http://localhost:8086)
- **Log in with credentials**:
  - **Username**: `<your_influx_username>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-username`)
  - **Password**: `<your_influx_password>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-password`).

### NodeRED UI

- **URL**: [https://localhost/nodered/](https://localhost/nodered/)

### DL Streamer Pipeline Server

- **REST API**: [https://localhost/api/pipelines/status](https://localhost/api/pipelines/status)
  - **Check Pipeline Status**:

    ```bash
    curl -k https://localhost/api/pipelines/status
    ```

## Verify the Application

- **Fused object tracks**: in Scene Management UI, click on the Intersection-Demo card to navigate to the Scene. On the Scene page, you will see fused tracks moving on the map. You will also see greyed out frames from each camera. Toggle the "Live View" button to see the incoming camera frames. The object detections in the camera feeds will correlate to the tracks on the map.

  ![Intersection Scene Homepage](./_assets/scenescape.png "intersection scene homepage")

- **Grafana Dashboard**: In Grafana UI, observe aggregated analytics of different regions of interests in the grafana dashboard. After navigating to Grafana home page, click on "Dashboards" and click on item "Anthem-ITS-Data".

  ![Intersection Grafana Dashboard](./_assets/grafana.png "intersection grafana dashboard")

## Stop the Application

To stop the application microservices, use the following command:

```bash
docker compose down
```

### Additional Cleanup Steps

If you deployed with **GPU**, you should also unbind the GPU from vfio-pci to restore it to the host:

```bash
sudo ./tools/intel-igpu-vfio-bind.sh unbind
```

This will restore the display manager and graphical display on the host.

### Uninstall Trusted Compute (Optional)

To uninstall Trusted Compute from the host, refer to the [Trusted Compute documentation](https://github.com/open-edge-platform/trusted-compute/blob/main/docs/trusted_compute_baremetal.md).

## Other Deployment Options

For Kubernetes-based deployments with Trusted Compute:

- **[Deploy with Helm and Trusted Compute](./get-started/deploy-with-trusted-compute-helm.md)**: Use Helm to deploy the application with Trusted Compute to a Kubernetes cluster for scalable and production-ready deployments with hardware isolation.

## Learn More

- [Troubleshooting](./troubleshooting.md): Find detailed steps to resolve common issues
- [Trusted Compute Documentation](https://github.com/open-edge-platform/trusted-compute): Complete guide to Intel Trusted Compute

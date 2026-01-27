# Health-and-Life-Sciences AI Suite (Preview)

The **Health-and-Life-Sciences AI Suite** is a preview collection of healthcare-focused AI applications, libraries, and benchmarking tools to help developers build intelligent patient monitoring solutions faster.

The suite provides **multi-modal AI pipelines** accelerated with the **OpenVINO™ toolkit**, enabling high-performance deployment on **Intel® Core™ Ultra platforms** using **CPU, integrated GPU (iGPU), and NPU**.

This suite organizes workflows tailored for healthcare and life sciences, with initial support for a **Multi-Modal Patient Monitoring** application.

---

## Initial Application: Multi-Modal Patient Monitoring

The Multi-Modal Patient Monitoring application demonstrates how multiple AI workloads can run **simultaneously on a single platform**, enabling consolidated patient monitoring.

---

## Prerequisites
```
• MDPnP and DDS-Bridge components require Java 17.

• Ensure Java is installed and JAVA_HOME is set correctly.
  Example:
    export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
    export PATH=$JAVA_HOME/bin:$PATH

• If you are behind a corporate proxy, configure Gradle:
    mkdir -p ~/.gradle
    nano ~/.gradle/gradle.properties

  Add proxy details in gradle.properties:
    systemProp.http.proxyHost=<PROXY_HOST>
    systemProp.http.proxyPort=<PROXY_PORT>
    systemProp.https.proxyHost=<PROXY_HOST>
    systemProp.https.proxyPort=<PROXY_PORT>
```
---

## 🐳 Run Health-AI-Suite Using Pre-Built Images

```
make run

```
---
## 🚀 Run Health-AI-Suite (Local Build)
```
# Initialize MDPnP submodules and dependencies
make init-mdpnp

# Build MDPnP services locally
make build-mdpnp

# Build DDS bridge locally
make build-dds-bridge

# Run the full Health-AI-Suite using locally built images
# Set REGISTRY=false to avoid pulling images from a remote registry
make run REGISTRY=false

# Stop and clean up all running containers
make down

```
---

## Disclaimer

This software is provided for **development and evaluation purposes only** and is **not intended for clinical or diagnostic use**.


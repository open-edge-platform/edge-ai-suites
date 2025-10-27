# Offline Package Generator - User Guide

## Overview

The Offline Package Generator creates self-contained deployment packages for Metro Vision AI applications that can be deployed in environments without internet connectivity. This tool is specifically designed for Denied, Disrupted, Intermittent, and Limited (DDIL) environments where traditional cloud-dependent deployments are not feasible.

## Prerequisites

### System Requirements
- **Operating System**: Linux (Ubuntu 20.04 or later)
- **Docker**: Version 20.10.0 or higher
- **Docker Compose**: Version 2.0.0 or higher
- **Storage Space**: Minimum 15 GB available disk space
- **Memory**: 8 GB RAM recommended
- **Internet Connection**: Required for package generation only


> **Important**: This process requires two environments - a connected system for package generation and an offline target system for deployment.

*Perform this step on a system with internet connectivity*

**Objective**: Create a complete offline deployment package containing all necessary components for the Smart Parking application.

```bash
# Navigate to the Smart Parking application directory
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/smart-parking

# Execute the offline package generator
./offline-package-generator.sh
```

**What happens during generation:**
- Downloads and packages all Docker images (~2-3 GB)
- Collects AI models and sample videos (~500 MB)
- Gathers Grafana plugins and configurations (~100 MB)
- Prepares deployment scripts and documentation
- Creates a complete `offline-package/` directory

**Success indicator**: You should see:
```
✓ Docker is available and running
✓ Docker Compose is available
...
Offline package generation completed successfully!
Package location: ./offline-package
```

---

### Step 2: Prepare Package for Transfer
*Package the generated files for secure transport to offline environment*

**Objective**: Create a compressed, transferable archive optimized for DDIL environments.

```bash
# Create a timestamped compressed package for easy identification
tar -czf smart-parking-offline-$(date +%Y%m%d-%H%M).tar.gz offline-package/

# Verify package integrity and size
ls -lh smart-parking-offline-*.tar.gz
tar -tzf smart-parking-offline-*.tar.gz | head -10

# Generate checksum for integrity verification
sha256sum smart-parking-offline-*.tar.gz > package-checksum.txt
```

**Transfer options for DDIL environments:**
- **USB/External drive**: Copy files to removable media
- **Secure network**: Use SCP, SFTP, or approved file transfer protocols
- **Physical media**: Burn to DVD/Blu-ray for highly secure environments
- **Satellite/RF links**: For remote locations with limited connectivity

---

### Step 3: Deploy in Offline Environment
*Execute deployment on the target system without internet connectivity*

**Objective**: Deploy and start the Smart Parking application in a completely offline environment.

#### 3.1 Extract and Prepare
```bash
# Extract the package on target system
tar -xzf smart-parking-offline-*.tar.gz

# Verify extraction integrity
sha256sum -c package-checksum.txt

# Navigate to extracted package
cd offline-package/

# Verify all components are present
ls -la
```

#### 3.2 Load Docker Components
```bash
# Make scripts executable
chmod +x load-images.sh

# Load all Docker images (this may take 10-15 minutes)
./load-images.sh

# Verify images loaded successfully
docker images | grep -E "(grafana|influxdb|nginx|dlstreamer)"
```

#### 3.3 Start the Application
```bash
# Start all services using Docker Compose
docker compose up -d

# Monitor startup progress
docker ps
```

**Next Steps**: Proceed with steps to run the application using the [get-started-guide](get-started.md#run-the-application) for detailed instructions. 

# Get Started

<!--
**Sample Description**: Provide a brief overview of the application and its purpose.
-->
The Smart Transportation Applications suite is a modular sample application designed to help developers create intelligent transportation monitoring solutions. By leveraging AI and real-time video analytics, this sample application demonstrates how to achieve accurate traffic detection, behavior analysis, and automated monitoring across various transportation scenarios.

<!--
**What You Can Do**: Highlight the developer workflows supported by the guide.
-->
By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to quickly deploy the application in your environment.
- **Run a predefined pipeline**: Execute a sample pipeline to see real-time transportation monitoring and object detection in action.
- **Modify application parameters**: Customize settings like input sources, detection thresholds, and regions of interest to adapt the application to your specific requirements.

## Prerequisites
- Verify that your system meets the [minimum requirements](./system-requirements.md).
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).
- Enable running docker without "sudo": [Post Install](https://docs.docker.com/engine/install/linux-postinstall/)
- Install Git: [Installing Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)

<!--
**Setup and First Use**: Include installation instructions, basic operation, and initial validation.
-->
## Set up and First Use

<!--
**User Story 1**: Setting Up the Application  
- **As a developer**, I want to set up the application in my environment, so that I can start exploring its functionality.

**Acceptance Criteria**:
1. Step-by-step instructions for downloading and installing the application.
2. Verification steps to ensure successful setup.
3. Troubleshooting tips for common installation issues.
-->

1. **Clone the Repository**:
   - Run:
     ```bash
     git clone https://github.com/open-edge-platform/edge-ai-suites.git
     cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
     ```

2. **Setup Application and Download Assets**:
   - Use the installation script to configure the application and download required models:
     ```bash
     ./install.sh <smart-parking|loitering-detection|smart-intersection|smart-tolling>
     ```

   **Available Applications:**
   
   | **Application** | **Command** | **Description** | **Models** | **Scenescape Components** |
   |------------|---------|-------------|-------------|-------------|
   | Smart Intersection Management | `smart-intersection` | Traffic flow optimization and intersection monitoring | Custom Intersection Model | Included |
   | Loitering Detection | `loitering-detection` | Real-time detection of loitering behavior in transportation hubs | pedestrian-and-vehicle-detector-adas-0001 | Not included |
   | Smart Parking | `smart-parking` | Automated parking space monitoring and management | YOLO v10s | Not included |
   | Smart Tolling | `smart-tolling` | Intelligent toll collection and vehicle classification | YOLO v10s | Not included |

   **Example**:
   ```bash
   # Install loitering detection with auto-detected IP
   ./install.sh loitering-detection
   ```

## Run the Application

1. **Start the Application**:
   - Download container images with Application microservices and run with Docker Compose:
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

2. **Run Predefined Pipelines**:
   - Pipeline startup depends on your application type:
   
   **For Applications WITHOUT Scenescape Components** *(Loitering Detection, Smart Parking, Smart Tolling)*:
   - Start video streams to run video inference pipelines:
     ```bash
     ./sample_start.sh
     ```
     
     <details>
     <summary>
     Check Status and Stop pipelines
     </summary>
     
     - To check the status:
       ```bash
       ./sample_status.sh
       ```
     
     - To stop the pipelines without waiting for video streams to finish replay:
       ```bash
       ./sample_stop.sh
       ```
     </details>
   
   **For Applications WITH Scenescape Components** *(Smart Intersection)*:
   - No action required! The inference pipeline starts automatically when the services launch.

3. **View the Application Output**:
   - Open a browser and go to `http://localhost:3000` to access the Grafana dashboard.
     - Change the localhost to your host IP if you are accessing it remotely.
   - Log in with the following credentials:
     - **Username**: `admin`
     - **Password**: `admin`
   - Check under the Dashboards section for the application-specific preloaded dashboard.
   - **Expected Results**: The dashboard displays real-time video streams with AI overlays and detection metrics.

## **Access the Application and Components** ##

### **Grafana UI** ###
- **URL**: [http://localhost:3000](http://localhost:3000)
- **Log in with credentials**:
    - **Username**: `admin`
    - **Password**: `admin` (You will be prompted to change it on first login.)

### **NodeRED UI** ###
- **URL**: [http://localhost:1880](http://localhost:1880)

### **DL Streamer Pipeline Server** ###
- **REST API**: [http://localhost:8080](http://localhost:8080)
  - **Check Pipeline Status**:
    ```bash
    curl http://localhost:8080/pipelines
    ```
- **WebRTC**: [http://localhost:8555](http://localhost:8555) [Only available for Non Scenescape Applications]

### **Scenescape UI** ### [Only available for Scenescape Application]

- **URL**: [https://localhost](https://localhost)
- **Log in with credentials**:
    - **Username**: `admin`
    - **Password**: Stored in `supass`. (Check `./smart-intersection/src/secrets/supass`)

### **InfluxDB UI** ### [Only available for Scenescape Application]
- **URL**: [http://localhost:8086](http://localhost:8086)
- **Log in with credentials**:
    - **Username**: `<your_influx_username>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-username`)
    - **Password**: `<your_influx_password>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-password`).


## **Stop the Application**:
  - To stop the application microservices, use the following command:
    ```bash
    docker compose down
    ```

## Supporting Resources
- [DL Streamer Pipeline Server](https://docs.edgeplatform.intel.com/dlstreamer-pipeline-server/3.0.0/user-guide/Overview.html)

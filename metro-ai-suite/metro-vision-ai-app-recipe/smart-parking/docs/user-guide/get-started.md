
# Get Started

The Smart Parking application uses AI-driven video analytics to optimize parking management. It provides a modular architecture that integrates seamlessly with various input sources and leverages AI models to deliver accurate and actionable insights.

By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to quickly deploy the application in your environment.
- **Run a predefined pipeline**: Execute a pipeline to see smart parking application in action.
- **Access the application's features and user interfaces**: Explore the Grafana dashboard, Node-RED interface, and DL Streamer Pipeline Server to monitor, analyze and customize workflows.

## Prerequisites
- Verify that your system meets the [minimum requirements](./system-requirements.md).
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).

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
     ./install.sh smart-parking
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
- In Grafana UI, the dashboard displays the detected cars in the parking lot.
      ![Grafana Dashboard](_images/grafana-smart-parking.jpg)

### **NodeRED UI** ###
- **URL**: [http://localhost:1880](http://localhost:1880)

### **DL Streamer Pipeline Server** ###
- **REST API**: [http://localhost:8080](http://localhost:8080)
  -   - **Check Pipeline Status**:
    ```bash
    curl http://localhost:8080/pipelines
    ```
- **WebRTC**: [http://localhost:8889](http://localhost:8889)

## **Stop the Application**:

- To stop the application microservices, use the following command:
  ```bash
  docker compose down
  ```

## Other Deployment Option

Choose one of the following methods to deploy the Smart Parking Sample Application:

- **[Deploy Using Helm](./how-to-deploy-with-helm.md)**: Use Helm to deploy the application to a Kubernetes cluster for scalable and production-ready deployments.

## Supporting Resources
- [Troubleshooting Guide](./support.md): Find detailed steps to resolve common issues during deployments.
- [DL Streamer Pipeline Server](https://docs.edgeplatform.intel.com/dlstreamer-pipeline-server/3.0.0/user-guide/Overview.html)
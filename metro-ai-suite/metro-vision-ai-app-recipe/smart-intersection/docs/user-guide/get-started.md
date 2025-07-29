# Get Started

<!--
**Sample Description**: Provide a brief overview of the application and its purpose.
-->
The Smart Intersection Sample Application is a modular sample application designed to help developers create intelligent intersection monitoring solutions. By leveraging AI and sensor fusion, this sample application demonstrates how to achieve accurate traffic detection, congestion management, and real-time alerting.

<!--
**What You Can Do**: Highlight the developer workflows supported by the guide.
-->
By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to quickly deploy the application in your environment.
- **Run a predefined pipeline**: Execute a sample pipeline to see real-time transportation monitoring and object detection in action.
- **Access the application's features and user interfaces**: Explore the Scenescape Web UI, Grafana dashboard, Node-RED interface, and DL Streamer Pipeline Server to monitor, analyze and customize workflows.

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
     ./install.sh smart-intersection
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

2. **View the Application Output**:
   - Open a browser and go to `http://localhost:3000` to access the Grafana dashboard.
     - Change the localhost to your host IP if you are accessing it remotely.
   - Log in with the following credentials:
     - **Username**: `admin`
     - **Password**: `admin`
   - Check under the Dashboards section for the application-specific preloaded dashboard.
   - **Expected Results**: The dashboard displays real-time video streams with AI overlays and detection metrics.


## **Access the Application and Components** ##

### **Application UI** ###

Open a browser and go to the following endpoints to access the application. Use `<actual_ip>` instead of `localhost` for external access:

> **Notes**
> - For passwords stored in files (e.g., `supass` or `influxdb2-admin-token`), refer to the respective secret files in your deployment under ./src/secrets (Docker) or chart/files/secrets (Helm).


- **URL**: [https://localhost](https://localhost)
- **Log in with credentials**:
    - **Username**: `admin`
    - **Password**: Stored in `supass`. (Check `./smart-intersection/src/secrets/supass`)

> **Notes**:
> - After starting the application, wait approximately 1 minute for the MQTT broker to initialize. You can confirm it is ready when green arrows appear for MQTT in the application interface. Since the application uses HTTPS, your browser may display a self-signed certificate warning. For the best experience, it is recommended to use **Google Chrome**.

### **Grafana UI** ###
- **URL**: [http://localhost:3000](http://localhost:3000)
- **Log in with credentials**:
    - **Username**: `admin`
    - **Password**: `admin` (You will be prompted to change it on first login.)

### **InfluxDB UI** ###
- **URL**: [http://localhost:8086](http://localhost:8086)
- **Log in with credentials**:
    - **Username**: `<your_influx_username>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-username`)
    - **Password**: `<your_influx_password>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-password`).

### **NodeRED UI** ###
- **URL**: [http://localhost:1880](http://localhost:1880)

### **DL Streamer Pipeline Server** ###
- **REST API**: [http://localhost:8080](http://localhost:8080)
  - **Check Pipeline Status**:
    ```bash
    curl http://localhost:8080/pipelines
    ```
- **WebRTC**: [http://localhost:8555](http://localhost:8555)

## Verify the Application

- **Fused object tracks**: In Scene Management UI, click on the Intersection-Demo card to navigate to the Scene. On the Scene page, you will see fused tracks moving on the map. You will also see greyed out frames from each camera. Toggle the "Live View" button to see the incoming camera frames. The object detections in the camera feeds will correlate to the tracks on the map.
      ![Intersection Scene Homepage](_images/scenescape.png)
- **Grafana Dashboard**: In Grafana UI, observe aggregated analytics of different regions of interests in the grafana dashboard. After navigating to Grafana home page, click on "Dashboards" and click on item "Anthem-ITS-Data".
      ![Intersection Grafana Dashboard](_images/grafana.png)

## **Stop the Application**:
  - To stop the application microservices, use the following command:
    ```bash
    docker compose down
    ```

## Other Deployment Option

Choose one of the following methods to deploy the Smart Intersection Sample Application:

- **[Deploy Using Helm](./how-to-deploy-helm.md)**: Use Helm to deploy the application to a Kubernetes cluster for scalable and production-ready deployments.

## Resources

- [Troubleshooting Guide](./support.md): Find detailed steps to resolve common issues during deployments.
- [DL Streamer Pipeline Server](https://docs.edgeplatform.intel.com/dlstreamer-pipeline-server/3.0.0/user-guide/Overview.html)

# Get Started

Loitering Detection leverages advanced AI algorithms to monitor and analyze real-time video feeds, identifying individuals lingering in designated areas. It provides a modular architecture that integrates seamlessly with various input sources and leverages AI models to deliver accurate and actionable insights.

By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to quickly deploy the application in your environment.
- **Run a predefined pipeline**: Execute a pipeline to see loitering detection in action.

## Prerequisites
- Verify that your system meets the [minimum requirements](./system-requirements.md).
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).

## Set up and First Use

1. **Download the Application**:
    - Download the Docker Compose file and configuration:
      ```bash
      git clone https://github.com/open-edge-platform/edge-ai-suites.git
      cd edge-ai-suites/metro-ai-suite/loitering-detection/
      ```

2. **Configure the Application and Download Assets**
   - Download the Models and Video files.
   - Configure the provided application IP address. If omitted, the application uses the primary IP address.

     ```bash
     ./install.sh [<IP_address>]
     ```
      <details>
      <summary>
      Check installed assets.
      </summary>

      The `install.sh` script downloads the following assets:

      **Models**
      - **pedestrian-and-vehicle-detector-adas-0001**: This model is obtained from the Open Model Zoo.

      **Videos**

      | **Video Name**       | **Download URL**         |
      |-----------------------|--------------------------|
      | VIRAT_S_000101.mp4    | [VIRAT_S_000101.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000101.mp4) |
      | VIRAT_S_000102.mp4    | [VIRAT_S_000102.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000102.mp4) |
      | VIRAT_S_000103.mp4    | [VIRAT_S_000103.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000103.mp4) |
      | VIRAT_S_000104.mp4    | [VIRAT_S_000104.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/VIRAT_S_000104.mp4) |

      </details>

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

      - The application starts the following microservices, see also [How it Works](./Overview.md#how-it-works).

      ![Architecture Diagram](./_images/loitering-detection-architecture.drawio.svg)

      - To check if all microservices are in Running state:
        ```bash
        docker ps
        ```
      </details>

2. **Run Predefined Loitering Detection Pipelines**:
    - Start video streams to run Loitering Detection pipelines:
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
        - **Username:** `admin`
        - **Password:** `admin`
    - Check under the Dashboards section for the default dashboard named "Video Analytics Dashboard".

    - **Expected Results**: The dashboard displays detected people and cars.
    - ![Dashboard Example](_images/grafana.png)

4. **Stop the Application**:
    - To stop the application microservices, use the following command:
      ```bash
      docker compose down -v
      ```

## Next Steps
- [How to Customize the Application](how-to-customize-application.md)

## Troubleshooting

1. **Changing the Host IP Address**

    - If you need to use a specific Host IP address instead of the one automatically detected during installation, you can explicitly provide it using the following command. Replace `<HOST_IP>` with your desired IP address:

      ```bash
      ./install.sh <HOST_IP>
      ```

2. **Containers Not Starting**:
   - Check the Docker logs for errors:
     ```bash
     docker compose logs
     ```

3. **No Video Streaming on Grafana Dashboard**
    - Go to the Grafana "Video Analytics Dashboard".
    - Click on the Edit option (located on the right side) under the WebRTC Stream panel.
    - Update the URL from `http://localhost:8083` to `http://host-ip:8083`.

4. **Failed Grafana Deployment**
    - If unable to deploy grafana container successfully due to fail to GET "https://grafana.com/api/plugins/yesoreyeram-infinity-datasource/versions": context deadline exceeded, please ensure the proxy is configured in the ~/.docker/config.json as shown below:

      ```bash
              "proxies": {
                      "default": {
                              "httpProxy": "<Enter http proxy>",
                              "httpsProxy": "<Enter https proxy>",
                              "noProxy": "<Enter no proxy>"
                      }
              }
      ```

    - After editing the file, remember to reload and restart docker before deploying the microservice again.

      ```bash
      systemctl daemon-reload
      systemctl restart docker
      ```

## Supporting Resources
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [DL Streamer Pipeline Server](https://docs.edgeplatform.intel.com/dlstreamer-pipeline-server/3.0.0/user-guide/Overview.html)

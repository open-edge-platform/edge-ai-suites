
# Get Started

The Smart Parking application uses AI-driven video analytics to optimize parking management. It provides a modular architecture that integrates seamlessly with various input sources and leverages AI models to deliver accurate and actionable insights.

By following this guide, you will learn how to:
- **Set up the sample application**: Use Docker Compose to quickly deploy the application in your environment.
- **Run a predefined pipeline**: Execute a pipeline to see smart parking application in action.

## Prerequisites
- Verify that your system meets the [minimum requirements](./system-requirements.md).
- Install Docker: [Installation Guide](https://docs.docker.com/get-docker/).

## Set up and First Use

1. **Download the Application**:
    - Download the Docker Compose file and configuration:
      ```bash
      git clone https://github.com/open-edge-platform/edge-ai-suites.git
      cd edge-ai-suites/metro-ai-suite/smart-parking/
      ```

2. **Configure the Application and Download Assets**
   - Download the Models and Video files.
   - Configure the provided application IP address. If omitted, the application uses the primary IP address.

     ```bash
     ./install.sh
     ```
      <details>
      <summary>
      Check installed assets.
      </summary>

      The `install.sh` script downloads the following assets:

      **Models**
      - **YOLO v10s**: YOLO Model for object detection.

      **Videos**

      | **Video Name**       | **Download URL**         |
      |-----------------------|--------------------------|
      | new_video_1.mp4    | [smart_parking_1.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_1.mp4) |
      | new_video_2.mp4    | [smart_parking_2.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_2.mp4) |
      | new_video_3.mp4    | [smart_parking_3.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_3.mp4) |
      | new_video_4.mp4    | [smart_parking_4.mp4](https://github.com/intel/metro-ai-suite/raw/refs/heads/videos/videos/smart_parking_4.mp4) |

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

      ![Architecture Diagram](./_images/smart-parking-architecture.drawio.svg)

      - To check if all microservices are in Running state:
        ```bash
        docker ps
        ```
      </details>

2. **Run Predefined Smart Parking Pipelines**:
    - Start video streams to run Smart Parking pipelines:
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

    - **Expected Results**: The dashboard displays detected cars in the parking lot.
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

5. **Not all streams are visible on Grafana**

    - MediaMTX may fail to stream if the pipeline initialization (of any of the webrtc streaming pipeline) takes longer than 10 seconds. This would be evident from the "deadline exceeded" log in "mediamtx-server" docker container. To resolve this, you can increase the MTX_WEBRTCTRACKGATHERTIMEOUT value in the "environment" section of the docker-compose.yml file.

## Supporting Resources
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [DL Streamer Pipeline Server](https://docs.edgeplatform.intel.com/dlstreamer-pipeline-server/3.0.0/user-guide/Overview.html)

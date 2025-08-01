# Smart Parking

Smart Parking provides information on which parking spaces are occupied based on video feeds
from multiple cameras, each monitoring a specific section of a parking lot. It is an
end-to-end solution offering an analytics dashboard with both real-time and historical results.

It is a cloud-native application composed of microservices, using pre-trained deep learning
models for video analysis. The app is modular and highly configurable, enabling you to adjust
its parameters, such as detection thresholds and object types, without the need for extensive
coding or deep learning expertise. Its key features are:

- **Vision Analytics Pipeline:** detects and classifies objects using pre-configured AI models.
- **Integration with MQTT, Node-RED, and Grafana:** facilitates efficient message handling,
  real-time monitoring, and insightful data visualization.
- **User-Friendly:** prebuilt scripts and configuration files facilitate ease of use.

![Grafana Dashboard](./docs/user-guide/_images/grafana-smart-parking.jpg)


## Get Started

- [System Requirements](./docs/user-guide/system-requirements.md)
- [Deploy with Docker Compose](./docs/user-guide/get-started.md)
- [Deploy with Helm](./docs/user-guide/how-to-deploy-with-helm.md)


## How It Works

Here is an overview of the architecture and logic of the application.

![Architecture Diagram](./docs/user-guide/_images/smart-parking-architecture.drawio.svg)


- **DL Streamer Pipeline Server** is a core component of the app. It receives video feed from
multiple cameras (four by default, simulated with a video recording). With pre-trained deep
learning models, it performs real-time object detection, classification, and tracking.
It recognizes vehicles in the parking lot and sends their 2D bounding boxes to Node-Red,
through the MQTT Broker. It also adds the detected bounding boxes on top of the video input,
consumed by the WebRTC Server.
- **Mosquitto MQTT Broker** is a message distribution service, passing data between these sends the raw coordinates of detected vehicles to Node-RED. The
feedback it receives is moved to Grafana to display.
- **Node-RED,** is a low-code platform for setting up application-specific rules and triggering
MQTT-based events. It takes the 2D bounding boxes of detected cars and matches them with
predefined parking slot positions, thus determining if a slot is free or occupied.
- **Grafana Dashboard** provides a monitoring and visualization dashboard indicating which
and how many parking spaces are occupied. It also displays the original video feed coming
from the WebRTC Server.
- **WebRTC Server** serves video streams processed by the pipeline for
end-user visualization. It is supplemented by the Coturn signaling server and passes the feed
for display in Grafana.


## Learn More

- [Release Notes](./docs/user-guide/release-notes.md)
- [How to customize the application](./docs/user-guide/how-to-customize-application.md)
- [Support and Troubleshooting](./docs/user-guide/support.md)

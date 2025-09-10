# Smart Intersection

The **Smart Intersection** is a sample application that unifies the analytics of a traffic intersection.

It demonstrates how edge AI technologies can address traffic management challenges using scene-based analytics. It combines analytics from multiple traffic cameras to provide a unified intersection view, enabling advanced use cases such as object tracking across multiple viewpoints, motion vector analysis (e.g., speed and heading), and understanding object interactions in three-dimensional space. This application highlights how existing camera infrastructure can be leveraged for real-time, multi-camera scene analytics, showcasing a shift from frame-based analysis to integrated, edge AI-driven solutions for smarter traffic management.

The following are some example use cases:

- **Use Case 1**: Pedestrian Safety - Enhance the safety for vulnerable road users (VRUs) at crosswalks.
  - Example: Scene-based region of interest (ROI) analytics help identify VRUs actively using crosswalks and detect unsafe situations, such as pedestrians walking outside the designated crosswalk areas.
- **Use Case 2**: Measure average vehicle count and average dwell time in each lane. Dwell time refers to the amount of time a vehicle spends at a stop, such as a bus stop or train station, without moving.
  - Example: Vehicles spending too much time in a lane indicates anomalies such as stalled vehicles, accidents, and congestion.

The key benefits are as follows:

- **Multi-camera multi-object tracking**: Enables tracking of objects across multiple camera views.
- **Scene based analytics**: Regions of interest that span multiple views can be easily defined on the map rather than independently on each camera view. This greatly simplifies business logic, enables more flexibility in defining regions, and allows various types of sensors to be used to track vehicles and people such as lidar and radar in addition to cameras.
- **Improved Urban Management**: Object tracks and analytics are available near-real-time on the MQTT broker to enable actionable insights for traffic monitoring and safety applications.
- **Reduced TCO**: Works with existing cameras, simplifies business logic development, and future-proofs the solution by enabling additional sensors and cameras as needed without changing the business logic.

## Get Started

To see the system requirements and other installations, see the following guides:

- [System Requirements](./docs/user-guide/system-requirements.md): Check the hardware and software requirements for deploying the application.
- [Get Started](./docs/user-guide/get-started.md): Follow step-by-step instructions to set up the application.

## How It Works
This section provides a high-level view of how the application integrates with a typical system architecture.

![High-Level System Diagram](./docs/user-guide/_images/architecture.png)

### Example Content for Diagram Description
- **Inputs**:
  - **Video Files** - Four traffic intersection cameras that capture videos simultaneously.
  - **Scene Database** - Pre-configured intersection scene with satellite view of intersection, calibrated cameras, and regions of interest.

  The video recordings are used to simulate the live feed from cameras deployed at a traffic intersection. The application can be configured to work with live cameras.
- **Processing**:
  - **Video Analytics** - Deep Learning Streamer Pipeline Server (DL Streamer Pipeline Server) utilizes a pre-trained object detection model to generate object detection metadata and and a local NTP server for synchronized timestamps. This metadata is published to the MQTT broker
  - **Sensor Fusion** - Scene Controller Microservice fuses the metadata from video analytics utilizing scene data obtained through the Scene Management API. It uses the fused tracks and the configured analytics (regions of interest) to generate events that are published to the MQTT broker.
  - **Aggregate Scene Analytics** - Region of interest analytics are read from the MQTT broker and stored in an InfluxDB bucket which enables time series analysis through Flux queries.
- **Outputs**:
  - Fused object tracks are available on the MQTT broker and visualized through the Scene Management UI.
  - Aggregate scene analytics are visualized through a Grafana dashboard.

For more details, see [Overview ](./docs/user-guide/Overview.md)

## Learn More

- [How to Deploy with Helm](./docs/user-guide/how-to-deploy-helm.md): How to deploy the application using Helm on a Kubernetes cluster.
- [Support and Troubleshooting](./docs/user-guide/support.md): Find solutions to common issues and troubleshooting steps.

## License

The application is licensed under the [LIMITED EDGE SOFTWARE DISTRIBUTION LICENSE AGREEMENT](LICENSE.txt).
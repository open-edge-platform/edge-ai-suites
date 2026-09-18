# Industrial Edge Insights - Time Series

Time Series predictive maintenance apps allow for detecting anomalous patterns across time, such as power generation patterns relative to wind speed for the wind turbines.

In the Energy Sector unexpected equipment failures result in costly downtime and operational inefficiencies. Using AI-driven predictive analytics, edge devices can monitor equipment health through sensor data (for example, power output) detect anomalous trends indicative of wear or failure, and alert operators to schedule maintenance proactively. This enhances productivity, reduces costs, and extends equipment lifespan.

[Wind Turbine Anomaly Detection](./wind-turbine-anomaly-detection/index.md) demonstrates a time series use case by detecting anomalous power generation patterns in wind turbines,
relative to wind speed.


They demonstrate how AI driven analytics can improve safety and preventive maintenance in industrial environments.

## Architecture

The Time-series sample apps, at a high-level, are based on a generic Time Series AI stack.
It comprises typical **TICK Stack** components, such as Telegraf, InfluxDB, and Kapacitor
(used by the Time Series Analytics microservice) and Grafana for visualization. Data
simulators (can act as data destinations if configured) would, of course, be replaced with
physical devices, in a real deployment scenario. If you are interested, documents for each
sample application provide detailed architectural descriptions.

<!--hide_directive
::::{grid} 1 2 2 2
:::{grid-item-card} Wind Turbine Anomaly Detection
:class-card: homepage-card-container-big
:link: ./wind-turbine-anomaly-detection/index.html

Monitoring power generation anomalies for preventive maintenance.
:::
::::
hide_directive-->

## Blueprint

This section documents the minimum software stack that **Wind Turbine Anomaly Detection** uses
from the broader Open Edge Platform (Edge AI Libraries, tools, and microservices), so you can
see exactly what is required to run this sample application versus what the platform
additionally offers.

### Core Stack

The following components are deployed by default through `docker-compose.yml` (or the
equivalent Helm chart in `helm/`):

| Category | Component | Role in this sample application |
|---|---|---|
| Data ingestion | Telegraf | Collects/forwards simulated turbine sensor data (power, wind speed) |
| Data storage | InfluxDB | Time-series database used by the TICK stack |
| AI microservice | Time Series Analytics Microservice (built on Kapacitor) | Runs the anomaly-detection UDF (scikit-learn `RandomForestClassifier`) against streaming data |
| Visualization | Grafana | Dashboards for turbine data and detected anomalies |
| Microservice | Eclipse Mosquitto (MQTT broker) | Transports sensor data and alert messages |
| Microservice | OPC UA server, MQTT publisher | Simulate/publish turbine data over OPC-UA and MQTT protocols |
| Microservice | nginx | Reverse proxy for the application endpoints |

### Optional Add-ons

| Component | Role | Enabled via |
|---|---|---|
| Visual Pipeline and Platform Evaluation Tool (ViPPET) | Deploys and benchmarks the Time Series Analytics Microservice as part of the ViPPET stack | ViPPET integration (see [Release Notes](./release-notes.md)) |
| Helm / Kubernetes | Alternative deployment path for the same microservices on a Kubernetes cluster | [Deploy with Helm](./get-started/deploy-with-helm.md) |

> **Note:** This sample application uses a classical machine learning model
> (scikit-learn `RandomForestClassifier`), not OpenVINO™ or DL Streamer — there is no
> vision/inference-accelerator component in this stack.

### Stack Component System Requirements

Each shared component brings its own hardware/software requirements, documented at the
source rather than repeated here:

| Component | System Requirements |
|---|---|
| Time Series Analytics Microservice | [Overview](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/time-series-analytics/index.html) (no dedicated hardware requirements beyond the Docker Compose baseline below) |
| Visual Pipeline and Platform Evaluation Tool (ViPPET) | [Overview](https://docs.openedgeplatform.intel.com/dev/edge-ai-libraries/visual-pipeline-and-platform-evaluation-tool/index.html) |

### Not Used by This Sample Application

The following platform capabilities are available on Open Edge Platform but are **not** part
of this sample application's stack: OpenVINO™, DL Streamer, Intel® Geti™, Generative AI / LLM
models, RAG or chat microservices, and ROS-based robotics middleware.

<!--hide_directive
:::{toctree}
:hidden:

get-started
how-to-guides
wind-turbine-anomaly-detection/index
troubleshooting
Release Notes <release-notes>

:::
hide_directive-->

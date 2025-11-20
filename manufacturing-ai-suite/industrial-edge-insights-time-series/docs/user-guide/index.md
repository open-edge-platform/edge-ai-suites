# Industrial Edge Insights - Time Series

Time Series predictive maintenance apps allow for detecting anomalous patterns across time, such as power generation patterns relative to wind speed for the wind turbines.

In the Energy Sector unexpected equipment failures result in costly downtime and operational inefficiencies. Using AI-driven predictive analytics, edge devices can monitor equipment health through sensor data (for example, power output) detect anomalous trends indicative of wear or failure, and alert operators to schedule maintenance proactively. This enhances productivity, reduces costs, and extends equipment lifespan.

[Wind Turbine Anomaly Detection](./wind-turbine-anomaly-detection/index.md) demonstrates a time series use case by detecting anomalous power generation patterns
in wind turbines, relative to wind speed.

[Weld Anomaly Detection](./weld-anomaly-detection/index.md) demonstrates how AI-driven analytics enable edge devices to monitor weld quality.

They demonstrate how AI driven analytics can improve safety and preventive maintenance in industrial environments.


## Architecture

The Time-series sample apps, at a high-level, are based on a generic Time Series AI stack.
It comprises of typical **TICK Stack** components, such as Telegraf, InfluxDB, and Kapacitor
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
:::{grid-item-card} Weld Anomaly Detection
:class-card: homepage-card-container-big
:link: ./weld-anomaly-detection/index.html

Monitoring weld anomalies for preventive maintenance.
:::
::::
hide_directive-->

<!--hide_directive
:::{toctree}
:hidden:

get-started
system-requirements
how-to-guides/index
weld-anomaly-detection/index
wind-turbine-anomaly-detection/index
Release Notes <release_notes>
troubleshoot-guide
:::
hide_directive-->


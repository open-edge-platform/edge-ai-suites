# Industrial Edge Insights - Time Series

Time Series predictive maintenance apps allow for detecting anomalous patterns across time,
such as power generation patterns relative to wind speed for the wind turbines.

In the Energy Sector unexpected equipment failures result in costly downtime and operational
inefficiencies. Using AI-driven predictive analytics, edge devices can monitor equipment
health through sensor data (for example, power output) detect anomalous trends indicative
of wear or failure, and alert operators to schedule maintenance proactively.
This enhances productivity, reduces costs, and extends equipment lifespan.

[Wind turbine anomaly detection](./wind-turbine-anomaly/user-guide/get-started.md) sample app
demonstrates a time series use case by detecting anomalous power generation patterns
in wind turbines, relative to wind speed. By identifying deviations, it helps
optimize maintenance schedules and prevent potential turbine failures, enhancing
operational efficiency.

[Weld Anomaly Detection](./weld-anomaly-detection/index.md) sample app demonstrates how AI-driven analytics enable edge devices to monitor weld quality.
They detect anomalous weld patterns and alert operators for timely intervention,
ensuring proactive maintenance, safety, and operational efficiency. No more failures
and unplanned downtime.

<!--hide_directive
::::{grid} 1 2 3 4
:::{grid-item-card} Wind Turbine Anomaly Detection
:class-card: homepage-card-container-big
:link: ./wind-turbine-anomaly/get-started.html

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

wind-turbine-anomaly/how-it-works.md
wind-turbine-anomaly/system-requirements
wind-turbine-anomaly/get-started
wind-turbine-anomaly/how-to-build-from-source
wind-turbine-anomaly/how-to-deploy-with-helm
wind-turbine-anomaly/how-to-configure-custom-udf
wind-turbine-anomaly/how-to-configure-alerts
wind-turbine-anomaly/how-to-enable-system-metrics
wind-turbine-anomaly/how-to-update-config
wind-turbine-anomaly/how-to-create-a-new-sample-app
wind-turbine-anomaly/how-to-connect-to-secure-mqtt-broker
wind-turbine-anomaly/release_notes
weld-anomaly-detection/index
:::
hide_directive-->

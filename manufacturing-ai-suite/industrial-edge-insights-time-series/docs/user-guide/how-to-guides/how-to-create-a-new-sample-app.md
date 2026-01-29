# How to create a new sample app

This guide provides step-by-step instructions on how you can create a new sample app by taking
`Wind Turbine Anomaly Detection` OR `Weld Anomaly Detection` sample app as a reference
by configuring the generic `Time Series AI Stack`. Create a copy of the
`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection`
folder and replace the folder name with the sample app name to be created.

## Steps to follow

### Configuration

#### 1. **Data Simulators/Destinations**:

   Options available:
   1. Update the OPC-UA/MQTT simulator containers (`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/simulator`) as needed
      to ingest the needed dataset to analyze via a CSV file
   2. If you have existing `OPC-UA/MQTT` simulators, you can use that too. Just adjust the Compose and Helm template files similar to
      the above existing OPC-UA/MQTT simulators
   3. Directly configure `Telegraf` to connect to the device acting as `OPC-UA` server OR `MQTT publisher/broker`.
      Refer to the [Telegraf plugin documentation](https://docs.influxdata.com/telegraf/v1/plugins/#input-plugins/) for more details

#### 2. **Generic Time Series AI stack**

- **Data Ingestion - Telegraf**

    Update the `[[inputs.mqtt_consumer]]` and `[[inputs.opcua]]` sections in `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/<new-app-name>/telegraf-config/Telegraf.conf`, based on the MQTT/OPC-UA configuration, the input
    would be read and the topics in MQTT input plugin and name_override in OPC-UA
    input plugin is used for writing this as measurement in InfluxDB.

    In the above configuration file, the two `[[outputs.influxdb]]` plugins publish the
    data to InfluxDB and Time Series Analytics microservice.

- **Data Processing - Time Series Analytics Microservice**

    The `tick_scripts`, `models` and `udfs` folders at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/<new-app-name>/time-series-analytics-config` constitutes the User Defined Function (UDF) deployment package. The `config.json` at the same location is the Time Series microservice configuration.

    More details at [how-to-configure-custom-udf](./how-to-configure-custom-udf.md)

- **Data Visualization - Grafana**

    Prepare the custom Grafana dashboard (`edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/<new-app-name>/grafana-dashboard.yml`) which gets volume mounted in the Grafana microservice at `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/docker-compose.yml`.

### Deployment

> **Note:** Adjust the `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/Makefile` to add the support for the new sample
> app name for both Docker Compose and Helm deployments.

1. For docker compose deployment, follow the [Get Started](../get-started.md) guide/
2. For helm deployment, follow the [How to deploy with helm](./how-to-deploy-with-helm.md)

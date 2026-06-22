# Deploy with Custom UDF

This guide provides instructions for setting up a custom UDF deployment package (UDFs, TICKscripts, models) and `config.json` in **Time Series Analytics Microservice**.

## Configuration

- **`config.json`**:
   - Review the [configuration reference](../wind-turbine-anomaly-detection/index.md#configjson) and update it as needed for your custom UDF deployment package.

- **`UDF Deployment Package`**:

  1. **`udfs/`**:
     - Contains Python scripts for UDFs.
     - If additional Python packages are required, list them in `requirements.txt` using pinned versions.
     - For detailed instructions on writing UDFs, see the [How to Write a UDF](./write-user-defined-function.md) guide.

  2. **`tick_scripts/`**:
     - Contains TICKscripts for data processing, analytics, and alerts.
     - More details on writing TICKscripts are available at <https://docs.influxdata.com/kapacitor/v1/reference/tick/introduction/>

     - Example TICKscript:

      ```bash
      dbrp "datain"."autogen"

      var data0 = stream
          |from()
              .database('datain')
              .retentionPolicy('autogen')
              .measurement('opcua')
          @windturbine_anomaly_detector()
          |alert()
              .crit(lambda: "anomaly_status" > 0)
              .message('Anomaly detected: Wind Speed: {{ index .Fields "wind_speed" }}, Grid Active Power: {{ index .Fields "grid_active_power" }}, Anomaly Status: {{ index .Fields "anomaly_status" }}')
              .mqtt('my_mqtt_broker')
              .topic('alerts/wind_turbine')
              .qos(1)
          |log()
              .level('INFO')
          |influxDBOut()
              .buffer(0)
              .database('datain')
              .measurement('opcua')
              .retentionPolicy('autogen')
      ```
       - Key sections:
         - **Input**: Fetch data from Telegraf (stream).
         - **Processing**: Apply UDFs for analytics.
         - **Alerts**: Configuration for publishing alerts (e.g., MQTT). Refer to the [document](./configure-alerts.md#helm---publish-mqtt-alerts)
         - **Logging**: Set log levels (`INFO`, `DEBUG`, `WARN`, `ERROR`).
         - **Output**: Publish processed data.

          For more details, refer to the [Kapacitor TICK Script Documentation](https://docs.influxdata.com/kapacitor/v1/reference/tick/introduction/).

  3. **`models/`**:
     - Contains model files (e.g., `.pkl`) used by UDF Python scripts.

### Docker Compose Deployment

> **Note:** Follow the [Get started](../get-started.md) guide to deploy the `Wind Turbine Anomaly Detection` and `Weld Defect Detection` sample apps.

The UDF deployment package (UDFs, TICKscripts, models) and `config.json` for each sample app are uploaded into the Time Series Analytics Microservice container via `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/Makefile`:

- **Wind Turbine Anomaly Detection**: `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config`
- **Weld Defect Detection**: `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/weld-defect-detection/time-series-analytics-config`

To apply changes to the UDF deployment package or `config.json`, update the files at the relevant path above, then follow the steps below to upload the updated package:

1. Create the UDF deployment package tar file:

   ```sh
   export SAMPLE_APP="<wind-turbine-anomaly-detection or weld-defect-detection>"
   # Navigate to the directory containing your UDF deployment package files
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/${SAMPLE_APP}/time-series-analytics-config/
   rm -f ${SAMPLE_APP}.tar
   tar cf ${SAMPLE_APP}.tar models/ tick_scripts/ udfs/
   ```

2. Upload the UDF deployment package to the Time Series Analytics Microservice:

   ```sh
   curl -X POST https://localhost:3000/ts-api/udfs/package -F "file=@${SAMPLE_APP}.tar" -k
   ```

3. Upload the `config.json` to activate the custom UDF:

   ```sh
   curl -s -X POST https://localhost:3000/ts-api/config \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d @config.json \
     -k
   ```

### Helm Deployment

1. Update the UDF deployment package by following the instructions in [Configure Time Series Analytics Microservice with Custom UDF Deployment Package](./configure-custom-udf.md#configuration).

2. Install the Helm chart by following [Step 3: Install Helm Charts](../get-started/deploy-with-helm.md#step-3-install-helm-charts).

3. Create the UDF deployment package tar file:

   ```sh
   export SAMPLE_APP="<wind-turbine-anomaly-detection or weld-defect-detection>"
   # Navigate to the directory containing your UDF deployment package files
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/${SAMPLE_APP}/time-series-analytics-config/
   rm -f ${SAMPLE_APP}.tar
   tar cf ${SAMPLE_APP}.tar models/ tick_scripts/ udfs/
   ```

4. Upload the UDF deployment package to the Time Series Analytics Microservice:

   ```sh
   curl -X POST https://localhost:30001/ts-api/udfs/package -F "file=@${SAMPLE_APP}.tar" -k
   ```

5. Upload the `config.json` to activate the custom UDF:

   ```sh
   curl -s -X POST https://localhost:30001/ts-api/config \
     -H 'accept: application/json' \
     -H 'Content-Type: application/json' \
     -d @config.json \
     -k
   ```

6. Verify the logs of the Time Series Analytics Microservice:

   ```sh
   POD_NAME=$(kubectl get pods -n ts-sample-app -o jsonpath='{.items[*].metadata.name}' | tr ' ' '\n' | grep deployment-time-series-analytics-microservice | head -n 1)
   kubectl logs -f -n ts-sample-app $POD_NAME
   ```

For more details, refer to the Time Series Analytics Microservice API documentation on [updating the config](./update-config.md).

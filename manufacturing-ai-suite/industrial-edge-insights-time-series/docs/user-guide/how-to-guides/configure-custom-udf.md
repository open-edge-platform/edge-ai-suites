# Deploy with Custom UDF

This guide provides instructions for setting up a custom InfluxDB 3 Core plugin package (plugin code, requirements, and models) and `config.json` in **Time Series Analytics Microservice**.

## Configuration

- **`config.json`**:

  Review the [configuration reference](../wind-turbine-anomaly-detection/index.md#configjson) and update it as needed for your custom UDF deployment package.

- **`UDF Deployment Package`**:

  1. **`udfs/<plugin-name>/`**:
    - Contains the Core Processing Engine plugin in `__init__.py`.
    - If additional Python packages are required, list pinned versions in `requirements.txt`.
    - The plugin defines `process_writes` for stream triggers and `process_scheduled_call` for scheduled batch triggers.

  2. **`models/`**:
     - Contains model files (e.g., `.pkl`) used by UDF Python scripts.

### Docker Compose Deployment

> [!NOTE]
> Follow the [Get started](../get-started.md) guide to deploy the `Wind Turbine Anomaly Detection` sample app.

The Core plugin package and `config.json` are uploaded through the Time Series Analytics Microservice API. The Wind Turbine sample Makefile handles this automatically:

- **Wind Turbine Anomaly Detection**: `edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config`

To apply changes to the UDF deployment package or `config.json`, update the files at the relevant path above, then follow the steps below to upload the updated package:

1. Create the UDF deployment package tar file:

   ```sh
   export SAMPLE_APP="wind-turbine-anomaly-detection"
   # Navigate to the directory containing your UDF deployment package files
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/${SAMPLE_APP}/time-series-analytics-config/
   rm -f ${SAMPLE_APP}.tar
   tar --exclude='__pycache__' --exclude='*.pyc' -cf ${SAMPLE_APP}.tar models/ udfs/influx3_windturbine/
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
   export SAMPLE_APP="wind-turbine-anomaly-detection"
   # Navigate to the directory containing your UDF deployment package files
   cd edge-ai-suites/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/${SAMPLE_APP}/time-series-analytics-config/
   rm -f ${SAMPLE_APP}.tar
   tar --exclude='__pycache__' --exclude='*.pyc' -cf ${SAMPLE_APP}.tar models/ udfs/influx3_windturbine/
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

# Write a User Defined Function (UDF)

User Defined Functions (UDFs) are custom Python scripts that allow you to implement domain-specific analytics and anomaly detection algorithms in the Time Series Analytics Microservice. UDFs process streaming data from Kapacitor and can perform complex computations, machine learning inference, or custom business logic on time-series data.

This guide provides step-by-step instructions for writing your own UDFs for the Time Series Analytics Microservice.

## Overview

Kapacitor spawns a UDF process (called an **agent**) that communicates with Kapacitor over STDIN/STDOUT using protocol buffers. The agent:

1. Describes its capabilities and configuration options.
2. Initializes itself with provided options.
3. Processes incoming data points or batches.
4. Returns results back to Kapacitor.

The Python Kapacitor agent handles all communication details and exposes a simple `Handler` interface for implementing your custom logic.

## UDF Architecture

```text
┌─────────────┐          Protocol Buffers         ┌──────────────────┐
│             │  ◄────── (STDIN/STDOUT) ────────► │                  │
│  Kapacitor  │                                   │   UDF Agent      │
│             │          Data Points              │   (Your Python   │
│             │   ─────────────────────────────►  │    Handler)      │
└─────────────┘                                   └──────────────────┘
```

## The Handler Interface

All UDFs must implement the `Handler` interface from `kapacitor.udf.agent`. The Handler receives callbacks as Kapacitor sends data and requests.

**Basic Implementation Template:**

```python
#!/usr/bin/env python3
import os
import logging
import time
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2

log_level = os.getenv('KAPACITOR_LOGGING_LEVEL', 'INFO').upper()
logging_level = getattr(logging, log_level, logging.INFO)

# Configure logging
logging.basicConfig(
    level=logging_level,  # Set the log level to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Log format
)

# Create a logger instance for this module
# This logger will be used throughout the UDF to record events, errors, and debug information
# All log messages will be captured by Kapacitor and written to its log files
logger = logging.getLogger()

class MyHandler(Handler):
    """ Handler for the UDF. It processes incoming points
    and uses the loaded model to analyze and process the point.
    """
    def __init__(self, agent):
        self._agent = agent
        # Need to enable after model training
        model_name = (os.path.basename(__file__)).replace('.py', '<model_type_extension>')
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "../models/" + model_name)
        model_path = os.path.abspath(model_path)

        # Initialize model for analysis.
        # Load the model using your algorithm's import method and assign it to self.model.
        # Example: self.model = cb.CatBoostClassifier(...), then self.model.load_model(model_path)
        self.model = None  # Replace None with your actual model instance

        self.model.load_model(model_path)

    def info(self):
        """Describe the UDF's capabilities and configuration options
        Note: Time Series Analytics only supports STREAM processing.
        """
        response = udf_pb2.Response()
        response.info.wants = udf_pb2.STREAM
        response.info.provides = udf_pb2.STREAM
        return response

    def init(self, init_req):
        """ Initialize the Handler with the provided options"""
        response = udf_pb2.Response()
        response.init.success = True
        return response

    def snapshot(self):
        """Create a snapshot of the current state"""
        response = udf_pb2.Response()
        response.snapshot.snapshot = b''
        return response

    def restore(self, restore_req):
        """Restore from a previous snapshot"""
        response = udf_pb2.Response()
        response.restore.success = False
        response.restore.error = 'not implemented'
        return response

    def point(self, point):
        """Process a single data point"""
        # Your custom logic goes here
        # Extract field values, perform analysis, and emit results
        self._agent.write_response(udf_pb2.Response(point=point))

    def begin_batch(self, begin_req):
        """ A batch has begun.
        """
        raise Exception("not supported")

    def end_batch(self, end_req):
        """ The batch is complete.
        """
        raise Exception("not supported")

if __name__ == '__main__':
    # Create an agent
    agent = Agent()

    # Create a handler and pass it an agent so it can write points
    h = MyHandler(agent)

    # Set the handler on the agent
    agent.handler = h

    # Anything printed to STDERR from a UDF process gets captured
    # into the Kapacitor logs.
    logger.info("Starting UDF agent")
    agent.start()
    agent.wait()
    logger.info("UDF agent finished")

```

## Implementing UDF with *Basic Implementation Template*

### Import and initialize the model in the `__init__(self, agent)`

Load ML models, thresholds, or external resources only once during initialization.

### Implement custom logic in the point() function

The point() method is called for every incoming data point.
Use it to extract fields, run inference or business logic, and emit results.

```python
    def point(self, point):

        # Extract field values from the incoming data point
        # Double fields (numeric values) - floating-point numbers like temperature, pressure
        temperature = point.fieldsDouble.get("temperature", 0.0)
        pressure = point.fieldsDouble.get("pressure", 0.0)
        humidity = point.fieldsDouble.get("humidity", 0.0)

        # String fields (text values) - textual data like IDs, locations, status messages
        sensor_id = point.fieldsString.get("sensor_id", "unknown")
        location = point.fieldsString.get("location", "default")
        status = point.fieldsString.get("status", "normal")

        # Boolean fields (true/false values) - binary states like active/inactive, enabled/disabled
        is_active = point.fieldsBool.get("is_active", False)
        is_calibrated = point.fieldsBool.get("is_calibrated", True)

        # Integer fields (whole numbers) - counts, codes, or discrete numeric values
        sample_count = point.fieldsInt.get("sample_count", 0)
        error_code = point.fieldsInt.get("error_code", 0)

        # Tags (metadata - always strings) - used for grouping and filtering, not for computation
        device_name = point.tags.get("device", "")
        site = point.tags.get("site", "")

        # Log the extracted values for debugging and monitoring
        logger.debug(f"Processing point - Sensor: {sensor_id}, Temp: {temperature}, Active: {is_active}")

        # Perform your analysis using the extracted values
        # Example: Run model inference, apply thresholds, calculate derived metrics
        # Add your custom logic here

        # Example: Set output fields based on analysis results
        # point.fieldsDouble["anomaly_score"] = calculated_score
        # point.fieldsString["analysis_result"] = "normal" or "anomaly"

        # Write the processed point back to Kapacitor
        self._agent.write_response(udf_pb2.Response(point=point))
```

## Best Practices

1. **Error Handling**: Always validate input data and handle missing fields gracefully.

   ```python
   if field_name not in point.fieldsDouble:
       logger.warning(f"Field {field_name} not found")
       return
   ```

2. **Logging**: Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)

   ```python
   logger.info("Processing point for source %s", source)
   logger.debug("Detailed debug information")
   logger.error("Critical error occurred")
   ```

3. **Default Values**: Always set default values for output fields.

   ```python
   if "anomaly_status" not in point.fieldsDouble:
       point.fieldsDouble["anomaly_status"] = 0.0
   ```

4. **Environment Variables**: Use environment variables for configuration.

   ```python
   model_path = os.getenv('MODEL_PATH', '/default/path')
   log_level = os.getenv('KAPACITOR_LOGGING_LEVEL', 'INFO').upper()
   ```

5. **Model Files**: Store models in the `models/` directory alongside UDF scripts.

   ```python
   model_name = os.path.basename(__file__).replace('.py', '.pkl')
   model_path = os.path.join(os.path.dirname(__file__), "../models/", model_name)
   ```

6. **Performance**: Minimize processing time in the `point()` method
   - Load models and resources in `init()`, not `point()`
   - Use vectorized operations when possible
   - Consider batching for heavy computations

7. **Dependencies**: List all Python dependencies in `requirements.txt` with pinned versions.

   ```text
   numpy==1.24.0
   scikit-learn==1.3.0
   pandas==2.0.0
   catboost==1.2.0
   ```

## Using Your UDF in TICKscripts

Once your UDF is written, reference it in TICKscripts:

```text
// Stream processing example
var data = stream
    |from()
        .measurement('sensor_data')
    @my_udf()
        .field('temperature')
        .threshold(50.0)
    |alert()
        .crit(lambda: "anomaly_status" > 0)
        .message('Anomaly detected: {{ index .Fields "temperature" }}')
        .mqtt('my_mqtt_broker')
        .topic('alerts/sensor')
    |influxDBOut()
        .database('results')
        .measurement('sensor_data')
```

## References

- [Kapacitor UDF Documentation](https://docs.influxdata.com/kapacitor/v1/guides/anomaly_detection/#writing-a-user-defined-function-udf)
- [Example UDFs in Repository](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/)
  - [Wind Turbine Anomaly Detection](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/windturbine_anomaly_detector.py)
  - [Weld Anomaly Detection](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/weld_anomaly_detector.py)
- [Kapacitor TICKscript Reference](https://docs.influxdata.com/kapacitor/v1/reference/tick/introduction/)
  - [Wind Turbine Anomaly Detection](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/windturbine_anomaly_detector.tick)
  - [Weld Anomaly Detection](https://github.com/open-edge-platform/edge-ai-suites/blob/main/manufacturing-ai-suite/industrial-edge-insights-time-series/apps/wind-turbine-anomaly-detection/time-series-analytics-config/tick_scripts/weld_anomaly_detector.tick)
- [Configure Custom UDF Deployment](./configure-custom-udf.md)

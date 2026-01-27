# Write a User Defined Function (UDF)

User Defined Functions (UDFs) are custom Python scripts that allow you to implement domain-specific analytics and anomaly detection algorithms in the Time Series Analytics Microservice. UDFs process streaming data from Kapacitor and can perform complex computations, machine learning inference, or custom business logic on time-series data.

This guide provides step-by-step instructions for writing your own UDFs for the ia-time-series-analytics microservice, based on the Kapacitor UDF framework.

## Overview

Kapacitor spawns a UDF process (called an **agent**) that communicates with Kapacitor over STDIN/STDOUT using protocol buffers. The agent:
1. Describes its capabilities and configuration options
2. Initializes itself with provided options
3. Processes incoming data points or batches
4. Returns results back to Kapacitor

The Python Kapacitor agent handles all communication details and exposes a simple `Handler` interface for implementing your custom logic.

## UDF Architecture

```
┌─────────────┐          Protocol Buffers         ┌──────────────────┐
│             │  ◄────── (STDIN/STDOUT) ────────► │                  │
│  Kapacitor  │                                   │   UDF Agent      │
│             │          Data Points              │   (Your Python   │
│             │   ─────────────────────────────►  │    Handler)      │
└─────────────┘                                   └──────────────────┘
```

## The Handler Interface

All UDFs must implement the `Handler` interface from `kapacitor.udf.agent`. The Handler receives callbacks as Kapacitor sends data and requests.

**Required Methods:**

```python
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2

class MyHandler(Handler):
    def info(self):
        """Describe the UDF's capabilities and configuration options"""
        pass
    
    def init(self, init_req):
        """Initialize the handler with provided options"""
        pass
    
    def snapshot(self):
        """Create a snapshot of the current state"""
        pass
    
    def restore(self, restore_req):
        """Restore from a previous snapshot"""
        pass
    
    def point(self, point):
        """Process a single data point"""
        pass
```

## Step-by-Step UDF Implementation

### Step 1: Import Required Libraries

```python
import os
import logging
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2

# Add your domain-specific imports
import numpy as np
import pickle
# etc.

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger()
```

### Step 2: Implement the `info()` Method

The `info()` method tells Kapacitor what type of data your UDF accepts and provides. You can also define configuration options.

**Key Concepts:**
- **`wants`**: Type of data the UDF expects (use `STREAM` for real-time point-by-point processing)
- **`provides`**: Type of data the UDF outputs (use `STREAM` for real-time analytics)
- **`options`**: Configuration parameters that can be set in TICKscripts

**Example: Stream Processing UDF**

```python
def info(self):
    """Return the InfoResponse describing the UDF properties"""
    response = udf_pb2.Response()
    
    # Process individual points as they arrive
    response.info.wants = udf_pb2.STREAM
    # Output individual points
    response.info.provides = udf_pb2.STREAM
    
    # Define optional configuration options
    # These can be set in TICKscript: @my_udf().field('temperature').threshold(50.0)
    
    # Option for specifying which field to process
    response.info.options['field'].valueTypes.append(udf_pb2.STRING)
    
    # Option for setting a numeric threshold
    response.info.options['threshold'].valueTypes.append(udf_pb2.DOUBLE)
    
    # Option for setting a window size
    response.info.options['window_size'].valueTypes.append(udf_pb2.INT)
    
    return response
```

**Available Option Types:**
- `udf_pb2.STRING` - String values
- `udf_pb2.INT` - Integer values
- `udf_pb2.DOUBLE` - Float/double values
- `udf_pb2.BOOL` - Boolean values

### Step 3: Implement the `init()` Method

The `init()` method is called once when the task starts. Parse options from the TICKscript and initialize your handler.

```python
def __init__(self, agent):
    self._agent = agent
    
    # Initialize instance variables
    self.field_name = ''
    self.threshold = 0.0
    self.model = None
    # etc.

def init(self, init_req):
    """Initialize the handler with options from TICKscript"""
    success = True
    msg = ''
    
    # Parse options provided in TICKscript
    for opt in init_req.options:
        if opt.name == 'field':
            self.field_name = opt.values[0].stringValue
        elif opt.name == 'threshold':
            self.threshold = opt.values[0].doubleValue
        elif opt.name == 'window_size':
            self.window_size = opt.values[0].intValue
    
    # Validate required options
    if not self.field_name:
        success = False
        msg += ' must supply a field name'
    
    if self.threshold <= 0:
        success = False
        msg += ' must supply a positive threshold'
    
    # Load models or initialize resources
    try:
        model_path = os.getenv('MODEL_PATH', '/path/to/model.pkl')
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        logger.info(f"Model loaded from {model_path}")
    except Exception as e:
        success = False
        msg += f' failed to load model: {str(e)}'
    
    # Return initialization response
    response = udf_pb2.Response()
    response.init.success = success
    response.init.error = msg.lstrip()
    
    return response
```

### Step 4: Implement the `point()` Method

Process each point as it arrives in real-time:

```python
def point(self, point):
    """Process a single data point"""
    
    # Extract field values
    # Points have multiple field dictionaries by type:
    # - point.fieldsDouble: float/double fields
    # - point.fieldsInt: integer fields
    # - point.fieldsString: string fields
    # - point.fieldsBool: boolean fields
    
    # Extract the field we're interested in
    if self.field_name in point.fieldsDouble:
        value = point.fieldsDouble[self.field_name]
    elif self.field_name in point.fieldsInt:
        value = point.fieldsInt[self.field_name]
    else:
        logger.warning(f"Field {self.field_name} not found in point")
        return
    
    # Perform your custom analysis
    result = self.analyze(value)
    
    # Add results to the point
    point.fieldsDouble["anomaly_score"] = result['score']
    point.fieldsDouble["anomaly_status"] = 1.0 if result['is_anomaly'] else 0.0
    
    # Send the modified point back to Kapacitor
    response = udf_pb2.Response()
    response.point.CopyFrom(point)
    self._agent.write_response(response, True)

def analyze(self, value):
    """Your custom analysis logic"""
    # Example: Simple threshold check
    is_anomaly = value > self.threshold
    return {
        'score': abs(value - self.threshold),
        'is_anomaly': is_anomaly
    }
```

### Step 5: Implement Snapshot and Restore (Optional but Recommended)

Kapacitor can snapshot the UDF state for recovery:

```python
def snapshot(self):
    """Create a snapshot of the current state"""
    response = udf_pb2.Response()
    # For simple UDFs, an empty snapshot is fine
    response.snapshot.snapshot = b''
    return response

def restore(self, restore_req):
    """Restore from a previous snapshot"""
    response = udf_pb2.Response()
    # Implement if you need state recovery
    response.restore.success = False
    response.restore.error = 'not implemented'
    return response
```

### Step 6: Create the Main Entry Point

```python
if __name__ == '__main__':
    # Create the agent
    agent = Agent()
    
    # Create your handler and pass the agent
    h = MyHandler(agent)
    
    # Set the handler on the agent
    agent.handler = h
    
    # Start the agent (blocks until Kapacitor closes the connection)
    logger.info("Starting UDF agent")
    agent.start()
    agent.wait()
    logger.info("UDF agent finished")
```

## Complete Example: Wind Turbine Anomaly Detection

Here's a simplified example based on the wind turbine UDF:

```python
#!/usr/bin/env python3
import os
import logging
import pickle
from kapacitor.udf.agent import Agent, Handler
from kapacitor.udf import udf_pb2
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger()

class WindTurbineAnomalyDetector(Handler):
    """Detect anomalies in wind turbine data based on wind speed vs power output"""
    
    def __init__(self, agent):
        self._agent = agent
        
        # Load pre-trained model
        model_path = os.getenv('MODEL_PATH')
        with open(model_path, 'rb') as f:
            self.model = pickle.load(f)
        
        # Configuration
        self.wind_speed_field = "wind_speed"
        self.power_field = "grid_active_power"
        self.error_threshold = 0.15
        self.cut_in_speed = 3.0
        self.cut_out_speed = 14.0
    
    def info(self):
        response = udf_pb2.Response()
        response.info.wants = udf_pb2.STREAM
        response.info.provides = udf_pb2.STREAM
        return response
    
    def init(self, init_req):
        response = udf_pb2.Response()
        response.init.success = True
        return response
    
    def snapshot(self):
        response = udf_pb2.Response()
        response.snapshot.snapshot = b''
        return response
    
    def restore(self, restore_req):
        response = udf_pb2.Response()
        response.restore.success = False
        response.restore.error = 'not implemented'
        return response
    
    def point(self, point):
        """Process wind turbine data point"""
        
        # Extract wind speed and power
        wind_speed = point.fieldsDouble.get(self.wind_speed_field)
        power = point.fieldsDouble.get(self.power_field)
        
        if wind_speed is None or power is None:
            logger.warning("Missing required fields")
            return
        
        # Skip if outside operational range
        if wind_speed <= self.cut_in_speed or wind_speed > self.cut_out_speed:
            point.fieldsDouble["anomaly_status"] = 0.0
        else:
            # Predict expected power based on wind speed
            expected_power = self.model.predict(np.array([[wind_speed]]))[0]
            
            # Calculate relative error
            error = abs(expected_power - power) / power if power > 0 else 0
            
            # Classify as anomaly if error exceeds threshold
            if error > self.error_threshold:
                if error < 0.3:
                    point.fieldsDouble["anomaly_status"] = 0.3  # LOW
                elif error < 0.6:
                    point.fieldsDouble["anomaly_status"] = 0.6  # MEDIUM
                else:
                    point.fieldsDouble["anomaly_status"] = 1.0  # HIGH
                
                logger.info(f"Anomaly detected: wind_speed={wind_speed}, "
                          f"power={power}, expected={expected_power}, error={error}")
            else:
                point.fieldsDouble["anomaly_status"] = 0.0
        
        # Send the point back
        response = udf_pb2.Response()
        response.point.CopyFrom(point)
        self._agent.write_response(response, True)

if __name__ == '__main__':
    agent = Agent()
    h = WindTurbineAnomalyDetector(agent)
    agent.handler = h
    logger.info("Starting Wind Turbine Anomaly Detector UDF")
    agent.start()
    agent.wait()
```

## Working with Point Data

Points contain multiple field dictionaries organized by data type:

```python
# Accessing fields by type
value_double = point.fieldsDouble.get("temperature", 0.0)
value_int = point.fieldsInt.get("count", 0)
value_string = point.fieldsString.get("status", "")
value_bool = point.fieldsBool.get("active", False)

# Setting fields
point.fieldsDouble["result"] = 42.5
point.fieldsString["status"] = "anomaly"

# Accessing tags (metadata)
source = point.tags.get("source", "unknown")

# Accessing timestamp (nanoseconds since epoch)
timestamp_ns = point.time
```

## Using Machine Learning Models

Both example UDFs demonstrate ML model integration:

### Example 1: Scikit-learn Model (Wind Turbine)
```python
import pickle
from sklearn.linear_model import LinearRegression

# Load during init
with open(model_path, 'rb') as f:
    self.model = pickle.load(f)

# Use in point()
prediction = self.model.predict(np.array([[wind_speed]]))[0]
```

### Example 2: CatBoost Model (Weld Defect)
```python
import catboost as cb
import pandas as pd

# Load during init
self.model = cb.CatBoostClassifier()
self.model.load_model(model_path)

# Use in point()
fields = {key: value for key, value in point.fieldsDouble.items()}
point_series = pd.Series(fields)
probabilities = self.model.predict_proba(point_series)
```

## Best Practices

1. **Error Handling**: Always validate input data and handle missing fields gracefully
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

3. **Default Values**: Always set default values for output fields
   ```python
   if "anomaly_status" not in point.fieldsDouble:
       point.fieldsDouble["anomaly_status"] = 0.0
   ```

4. **Environment Variables**: Use environment variables for configuration
   ```python
   model_path = os.getenv('MODEL_PATH', '/default/path')
   log_level = os.getenv('KAPACITOR_LOGGING_LEVEL', 'INFO').upper()
   ```

5. **Model Files**: Store models in the `models/` directory alongside UDF scripts
   ```python
   model_name = os.path.basename(__file__).replace('.py', '.pkl')
   model_path = os.path.join(os.path.dirname(__file__), "../models/", model_name)
   ```

6. **Performance**: Minimize processing time in the `point()` method
   - Load models and resources in `init()`, not `point()`
   - Use vectorized operations when possible
   - Consider batching for heavy computations

7. **Dependencies**: List all Python dependencies in `requirements.txt` with pinned versions
   ```
   numpy==1.24.0
   scikit-learn==1.3.0
   pandas==2.0.0
   catboost==1.2.0
   ```

## Testing Your UDF

1. **Local Testing**: Test the UDF standalone before integration
   ```python
   # Add test code at the end
   if __name__ == '__main__':
       # Test with sample data
       import sys
       if len(sys.argv) > 1 and sys.argv[1] == 'test':
           # Run tests
           pass
       else:
           # Normal execution
           agent = Agent()
           # ...
   ```

2. **Logging**: Use extensive logging during development
3. **Unit Tests**: Create unit tests for your analysis logic

## Using Your UDF in TICKscripts

Once your UDF is written, reference it in TICKscripts:

```javascript
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

## Troubleshooting

### Common Issues

1. **UDF Process Not Starting**: Check Kapacitor logs for Python errors
2. **Missing Fields**: Verify field names match your TICKscript and data source
3. **Import Errors**: Ensure all dependencies are listed in `requirements.txt`
4. **Model Loading Failures**: Verify model paths and file permissions
5. **Performance Issues**: Profile your `point()` method and optimize hot paths

### Debugging Tips
- Enable DEBUG logging: `logging.basicConfig(level=logging.DEBUG)`
- Print to stderr (captured in Kapacitor logs): `print(msg, file=sys.stderr)`
- Test with minimal data first, then scale up
- Check that your UDF properly initializes all required fields

## References

- [Kapacitor UDF Documentation](https://docs.influxdata.com/kapacitor/v1/guides/anomaly_detection/#writing-a-user-defined-function-udf)
- [Example UDFs in Repository](../../../apps/)
  - [Wind Turbine Anomaly Detector](../../../apps/wind-turbine-anomaly-detection/time-series-analytics-config/udfs/windturbine_anomaly_detector.py)
  - [Weld Anomaly Detector](../../../apps/weld-anomaly-detection/time-series-analytics-config/udfs/weld_anomaly_detector.py)
- [Kapacitor TICKscript Reference](https://docs.influxdata.com/kapacitor/v1/reference/tick/introduction/)
- [Configure Custom UDF Deployment](./how-to-configure-custom-udf.md)

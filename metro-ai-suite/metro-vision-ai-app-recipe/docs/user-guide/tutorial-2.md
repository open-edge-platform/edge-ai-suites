# Customizing Node-RED Flows for Metro Vision AI Applications

<!--
**Sample Description**: This tutorial demonstrates how to customize Node-RED flows to process and enhance AI inference data from metro vision applications, enabling real-time data manipulation and custom business logic implementation.
-->

This tutorial guides you through customizing Node-RED flows to process AI inference data from metro vision applications. You'll learn how to connect to MQTT data streams, manipulate inference results, add custom business logic, and create enhanced data outputs for downstream systems.

<!--
**What You Can Do**: This guide covers the complete workflow for customizing Node-RED flows in metro vision AI applications.
-->

By following this guide, you will learn how to:
- **Access and Launch Node-RED**: Connect to the Node-RED interface and understand the flow-based programming environment
- **Clear and Reset Flows**: Remove existing flows and start with a clean workspace for custom development
- **Connect to MQTT Data Streams**: Establish connections to receive real-time AI inference data from metro vision applications
- **Implement Custom Data Processing**: Add custom names, metadata, and business logic to AI inference results using function nodes
- **Publish Enhanced Data**: Send processed data back to MQTT topics for consumption by other applications

## Prerequisites

- Complete [Tutorial 1 - AI Tolling System](./tutorial-1.md) to have a running metro vision AI application
- Verify that your metro vision AI application is running and producing MQTT data
- Basic understanding of Node-RED flow-based programming concepts
- Familiarity with MQTT messaging protocol and JSON data structures
- Web browser access to the Node-RED interface

## Node-RED Flow Architecture Overview

<!--
**Architecture Image Placeholder**: Add flow diagram showing MQTT input, function processing, and MQTT output nodes
-->
*[Image placeholder: Node-RED Flow Architecture - showing MQTT subscriber → Function Node → Data Enhancement → MQTT Publisher workflow]*

The custom Node-RED flow consists of:
- **MQTT Input Node**: Subscribes to AI inference data topics
- **Function Nodes**: Processes and enhances the incoming data with custom logic
- **Debug Nodes**: Provides real-time monitoring of data flow
- **MQTT Output Node**: Publishes enhanced data to new or existing topics

## Set up and First Use

### 1. **Access the Node-RED Interface**

Launch Node-RED in your web browser using your host system's IP address:

```bash
# Find your host IP address if needed
hostname -I | awk '{print $1}'
```

Open your web browser and navigate to the Node-RED interface:
```
http://<HOST_IP>:1880
```

Replace `<HOST_IP>` with your actual system IP address.

<details>
<summary>
Troubleshooting Node-RED Access
</summary>

If you cannot access Node-RED:
1. Verify the metro vision AI application is running:
   ```bash
   docker ps | grep node-red
   ```
2. Check that port 1880 is exposed and accessible
3. Ensure no firewall is blocking the connection
4. Try accessing via localhost if running on the same machine: `http://localhost:1880`

</details>

### 2. **Clear Existing Node-RED Flows**

Remove any existing flows to start with a clean workspace:

1. **Select All Flows**: Press `Ctrl+A` (or `Cmd+A` on Mac) to select all nodes in the current flow
2. **Delete Selected Nodes**: Press the `Delete` key to remove all selected nodes
3. **Deploy Changes**: Click the red **Deploy** button in the top-right corner to save the changes

- Go to the URL http://<HOST_IP>:1880.
- Select everything inside the flow and delete it.
- This clears the your node red flow.

### 3. **Create MQTT Input Connection**

Set up an MQTT subscriber node to receive AI inference data:

1. **Add MQTT Input Node**:
   - Drag an `mqtt in` node from the **network** section in the left palette
   - Double-click the node to configure it

2. **Configure MQTT Broker**:
   - **Server**: `broker:1883` (or your MQTT broker address)
   - **Topic**: `object_detection_1` (or your specific AI data topic)
   - **QoS**: `0`
   - **Output**: `auto-detect (string or buffer)`

3. **Set Node Properties**:
   - **Name**: `AI Inference Input`
   - Click **Done** to save the configuration

<details>
<summary>
Common MQTT Topics for Metro Vision AI
</summary>

| **Topic** | **Description** | **Data Format** |
|-----------|-----------------|-----------------|
| `inference/results` | Raw AI model inference results | JSON |
| `vehicle/detection` | Vehicle detection events | JSON |
| `person/count` | Person counting data | JSON |
| `analytics/summary` | Aggregated analytics data | JSON |

</details>

### 4. **Add Debug Output for Monitoring**

Create a debug node to monitor incoming data:

1. **Add Debug Node**:
   - Drag a `debug` node from the **common** section
   - Connect the output of the MQTT input node to the debug node input

2. **Configure Debug Node**:
   - **Output**: `msg.payload`
   - **To**: `debug tab and console`
   - **Name**: `Raw Data Monitor`

3. **Deploy and Test**:
   - Click **Deploy**
   - Check the debug panel (bug icon in the right sidebar) for incoming messages

### 5. **Implement Custom Data Processing Function**

Add a function node to enhance the AI inference data with custom metadata:

1. **Add Function Node**:
   - Drag a `function` node from the **function** section
   - Position it between the MQTT input and a new MQTT output node

2. **Configure the Function Node**:
   - **Name**: `Add Custom Metadata`
   - **Function Code**:

```javascript
// Parse incoming AI inference data
let inferenceData = msg.payload;

// Handle string JSON data
if (typeof inferenceData === 'string') {
    try {
        inferenceData = JSON.parse(inferenceData);
    } catch (e) {
        node.error("Invalid JSON data received", msg);
        return null;
    }
}

// Add custom metadata and enhancements
const enhancedData = {
    ...inferenceData,
    processed_timestamp: new Date().toISOString(),
    processing_node: "custom-node-red-flow",
    location: {
        site_name: "Metro Station Alpha",
        camera_id: inferenceData.camera_id || "unknown",
        zone: "entrance-01"
    },
    custom_attributes: {
        confidence_threshold: 0.7,
        alert_enabled: inferenceData.confidence > 0.8,
        priority: inferenceData.confidence > 0.9 ? "high" : "normal"
    }
};

// Add custom naming based on object type
if (enhancedData.objects) {
    enhancedData.objects = enhancedData.objects.map(obj => {
        return {
            ...obj,
            display_name: `${obj.class_name}_${Date.now()}`,
            tracking_id: `track_${Math.random().toString(36).substr(2, 9)}`
        };
    });
}

// Set the enhanced data as the new payload
msg.payload = enhancedData;
msg.topic = "inference/enhanced";

return msg;
```

3. **Add Error Handling**:
   - Click the **On Error** tab in the function node configuration
   - Enable error handling for robust data processing

### 6. **Configure MQTT Output for Enhanced Data**

Set up an MQTT publisher to send the enhanced data:

1. **Add MQTT Output Node**:
   - Drag an `mqtt out` node from the **network** section
   - Connect the function node output to this MQTT output node

2. **Configure MQTT Publisher**:
   - **Server**: Same as input (`broker:1883`)
   - **Topic**: `inference/enhanced` (or use `msg.topic` for dynamic topics)
   - **QoS**: `0`
   - **Retain**: `false`
   - **Name**: `Enhanced Data Publisher`

3. **Add Debug Output**:
   - Add another debug node connected to the MQTT output
   - **Name**: `Enhanced Data Monitor`

### 7. **Deploy and Validate the Custom Flow**

Test your custom Node-RED flow:

1. **Deploy the Complete Flow**:
   ```bash
   # Click the Deploy button in Node-RED interface
   ```

2. **Monitor Data Flow**:
   - Open the debug panel in Node-RED
   - Verify that both raw and enhanced data are flowing through the system
   - Check timestamps and custom metadata are being added correctly

3. **Validate MQTT Output**:
   ```bash
   # Subscribe to the enhanced data topic to verify output
   docker exec -it <mqtt-container> mosquitto_sub -h localhost -t "inference/enhanced"
   ```

<details>
<summary>
Verify Enhanced Data Structure
</summary>

Your enhanced data should include:
- Original AI inference results
- Added `processed_timestamp`
- Custom `location` metadata
- `custom_attributes` with confidence-based logic
- Enhanced `objects` array with `display_name` and `tracking_id`

Sample enhanced output:
```json
{
  "original_inference_data": "...",
  "processed_timestamp": "2025-07-25T10:30:00.000Z",
  "processing_node": "custom-node-red-flow",
  "location": {
    "site_name": "Metro Station Alpha",
    "camera_id": "cam_01",
    "zone": "entrance-01"
  },
  "custom_attributes": {
    "confidence_threshold": 0.7,
    "alert_enabled": true,
    "priority": "high"
  }
}
```

</details>

## Running Advanced Customizations

### **Adding Conditional Logic**

Enhance your function node with conditional processing based on AI inference results:

```javascript
// Example: Alert generation based on person count
if (enhancedData.person_count > 50) {
    msg.alert = {
        type: "crowding_detected",
        severity: "high",
        message: "High crowd density detected in entrance area",
        timestamp: new Date().toISOString()
    };
    msg.topic = "alerts/crowding";
} else {
    msg.topic = "inference/enhanced";
}
```

### **Data Aggregation and Filtering**

Implement data aggregation for analytics:

```javascript
// Store in context for aggregation
let hourlyCount = context.get('hourlyCount') || 0;
let lastHour = context.get('lastHour') || new Date().getHours();
let currentHour = new Date().getHours();

if (currentHour !== lastHour) {
    // Reset counter for new hour
    context.set('hourlyCount', 0);
    context.set('lastHour', currentHour);
    hourlyCount = 0;
}

// Increment counter
hourlyCount++;
context.set('hourlyCount', hourlyCount);

// Add aggregation data
enhancedData.analytics = {
    hourly_count: hourlyCount,
    current_hour: currentHour
};
```

## Expected Results

After completing this tutorial, you should have:

1. **Custom Node-RED Flow**: A working flow that processes AI inference data with custom enhancements
2. **Enhanced Data Stream**: MQTT topics publishing enriched data with custom metadata
3. **Real-time Monitoring**: Debug panels showing data flow and transformations
4. **Flexible Architecture**: A foundation for adding more complex business logic and data processing

## Next Steps

- **Explore Advanced Nodes**: Integrate with external APIs, databases, or notification systems
- **Implement Data Storage**: Add nodes to store enhanced data in databases or file systems
- **Create Dashboards**: Use Node-RED Dashboard nodes to visualize real-time data
- **Add Machine Learning**: Integrate additional ML models for further data enhancement
- **Scale the Solution**: Deploy multiple Node-RED instances for distributed processing

## Troubleshooting

### **Node-RED Interface Not Accessible**
- **Problem**: Cannot access Node-RED at the specified URL
- **Solution**: 
  ```bash
  # Check if Node-RED container is running
  docker ps | grep node-red
  # Restart the metro vision AI application if needed
  ./sample_stop.sh && ./sample_start.sh
  ```

### **MQTT Connection Issues**
- **Problem**: MQTT nodes show "disconnected" status
- **Solution**: Verify MQTT broker is running and accessible:
  ```bash
  # Test MQTT broker connectivity
  docker exec -it <mqtt-container> mosquitto_pub -h localhost -t "test" -m "test message"
  ```

### **No Data in Debug Panel**
- **Problem**: Debug nodes show no incoming data
- **Solution**: 
  - Verify the AI application is running and generating inference data
  - Check MQTT topic names match your application's output topics
  - Ensure proper JSON parsing in function nodes

### **Function Node Errors**
- **Problem**: Function node shows errors in the debug panel
- **Solution**: 
  - Add try-catch blocks around JSON parsing
  - Use `node.warn()` or `node.error()` for debugging
  - Validate input data structure before processing

## Supporting Resources

- [Node-RED Official Documentation](https://nodered.org/docs/)
- [MQTT Protocol Specification](https://mqtt.org/)
- [Intel DLStreamer Documentation](https://dlstreamer.github.io/)
- [Metro AI Solutions](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite)
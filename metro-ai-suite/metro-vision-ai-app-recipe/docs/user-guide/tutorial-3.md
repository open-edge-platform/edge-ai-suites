# Customize Grafana Dashboard for Real-Time Object Detection

<!--
**Sample Description**: Learn how to create custom Grafana dashboards that integrate real-time video streams and MQTT data visualization for metro vision AI applications.
-->
This tutorial guides you through creating a custom Grafana dashboard that displays real-time object detection video streams and data analytics. You'll build an integrated monitoring solution that combines visual feeds with data tables for comprehensive metro vision monitoring.

<!--
**What You Can Do**: Highlight the developer workflows supported by the guide.
-->
By following this guide, you will learn how to:
- **Create Custom Dashboards**: Build new Grafana dashboards tailored for metro vision applications
- **Integrate Video Streams**: Embed real-time WebRTC video feeds using HTML panels
- **Visualize MQTT Data**: Create dynamic tables that display live object detection data from MQTT streams

## Prerequisites

- Verify that your metro vision AI application is running: [Setup Guide](./tutorial-1.md)
- Access to Grafana dashboard (typically at `http://localhost:3000`)
- WebRTC streaming service configured and operational
- MQTT broker running with object detection data feed

## Set up and First Use

### 1. **Create a New Dashboard**

1. **Access Grafana Interface**:
   - Open your web browser and navigate to `http://localhost:3000`
   - Log in with your Grafana credentials

2. **Create New Dashboard**:
   - Click the "+" icon in the left sidebar
   - Select "Dashboard" from the dropdown menu
   - Click "Add new panel"

### 2. **Add Real-Time Video Stream Panel**

1. **Create HTML Panel**:
   - In the panel editor, change the visualization type to "Text"
   - Switch to "HTML" mode
   - Add the following iframe code:

   ```html
   <iframe 
     src="${WEBRTC_URL}/object_detection_1" 
     style="width:100%;height:500px;" 
     allow="autoplay; encrypted-media"
     frameborder="0">
   </iframe>
   ```

2. **Configure Panel Settings**:
   - Set panel title to "Live Object Detection Feed"
   - Adjust panel size as needed
   - Click "Apply" to save the panel

   <details>
   <summary>
   Understanding WebRTC URL Variables
   </summary>
   
   The `${WEBRTC_URL}` variable should be configured in your Grafana environment variables or replaced with your actual WebRTC server URL (e.g., `http://localhost:8889`).
   
   | **Parameter** | **Description** |
   |---------------|-----------------|
   | `src` | WebRTC stream endpoint URL |
   | `style` | CSS styling for responsive design |
   | `allow` | Browser permissions for media playback |
   
   </details>

### 3. **Create MQTT Data Table**

1. **Add New Panel**:
   - Click "Add panel" to create another visualization
   - Select "Table" as the visualization type

2. **Configure Data Source**:
   - Set your MQTT data source (InfluxDB, Prometheus, or direct MQTT connection)
   - Configure query to fetch object detection metrics

   ```bash
   # Example InfluxDB query for object detection data
   SELECT "object_type", "confidence", "timestamp", "coordinates" 
   FROM "object_detection" 
   WHERE $timeFilter
   ```

3. **Format Table Display**:
   - Configure column headers: Object Type, Confidence Score, Detection Time, Location
   - Set auto-refresh interval (e.g., 5 seconds)
   - Apply appropriate data formatting

   <details>
   <summary>
   Sample MQTT Data Structure
   </summary>
   
   Your MQTT messages should follow this structure for optimal table display:
   
   ```json
   {
     "timestamp": "2025-07-25T10:30:00Z",
     "object_type": "person",
     "confidence": 0.92,
     "coordinates": {
       "x": 245,
       "y": 180,
       "width": 85,
       "height": 120
     },
     "camera_id": "metro_cam_01"
   }
   ```
   
   </details>

### 4. **Configure Dashboard Layout**

1. **Arrange Panels**:
   - Drag and resize panels for optimal viewing
   - Position video feed in the upper section
   - Place data table below or alongside the video

2. **Save Dashboard**:
   - Click the save icon (disk symbol)
   - Name your dashboard "Metro Vision Object Detection"
   - Add appropriate tags for organization

## Expected Results

After completing this tutorial, you should have:

- **Interactive Dashboard**: A custom Grafana dashboard displaying real-time video and data
- **Live Video Feed**: WebRTC stream showing object detection overlay
- **Dynamic Data Table**: Real-time MQTT data updates with detection information
- **Integrated Monitoring**: Combined visual and analytical view of metro vision system

## Troubleshooting

1. **Video Stream Not Loading**
   - Verify WebRTC service is running: `docker ps | grep webrtc`
   - Check WEBRTC_URL environment variable configuration
   - Ensure browser permissions allow autoplay and camera access

2. **MQTT Data Not Appearing**
   - Confirm MQTT broker connection in Grafana data sources
   - Validate MQTT topic subscription and message format
   - Check query syntax for your specific data source

3. **Dashboard Performance Issues**
   - Reduce refresh intervals if system is slow
   - Limit data query time ranges
   - Consider using data aggregation for high-volume streams

## Next Steps

- **Advanced Analytics**: Add statistical panels for detection trends and patterns
- **Alert Configuration**: Set up notifications for specific detection events
- **Multi-Camera Support**: Extend dashboard to handle multiple camera feeds
- **Custom Plugins**: Explore Grafana plugins for enhanced visualization options

## Supporting Resources

- [Grafana HTML Panel Documentation](https://grafana.com/docs/grafana/latest/panels/visualizations/text/)
- [MQTT Data Source Configuration](https://grafana.com/docs/grafana/latest/datasources/)
- [Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)

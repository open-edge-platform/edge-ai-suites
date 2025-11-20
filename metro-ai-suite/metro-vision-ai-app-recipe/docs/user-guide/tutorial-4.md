# AI Crowd Analytics Tutorial

This tutorial walks you through creating an AI-powered crowd analytics system that automatically detects vehicles and identifies whether they form a "crowd" (closely grouped vehicles) or are scattered individually. The system leverages Intel's DLStreamer framework with pre-trained AI models to process video streams and analyze vehicle clustering patterns in real-time.


By following this guide, you will learn how to:
- **Set up the Crowd Analytics Application**: Create a new application based on the Smart Parking template and configure it for crowd detection use cases
- **Download and Configure AI Models**: Install YOLO object detection models and custom vehicle classification models
- **Configure Video Processing Pipeline**: Set up the DLStreamer pipeline for real-time vehicle detection and crowd analysis
- **Deploy and Run the System**: Launch the containerized application and monitor crowd detection performance

## Prerequisites

- Verify that your system meets the [minimum system requirements](./system-requirements.md) for running edge AI applications
- Install Docker: [Docker Installation Guide](https://docs.docker.com/get-docker/)
- Enable running Docker without "sudo": [Post-installation steps for Linux](https://docs.docker.com/engine/install/linux-postinstall/)
- Ensure you have at least 8GB of available disk space for AI models and video files
- Basic understanding of containerized applications and video processing concepts

## Application Architecture Overview

![Crowd Analytics System Diagram](_images/metro-vision-ai-app-recipe-architecture.drawio.svg)


The AI Crowd Analytics system consists of several key components:
- **Video Input**: Processes live camera feeds or video files from parking lot cameras
- **Vehicle Detection**: Uses YOLO11s model to detect and track vehicles in the parking lot
- **Vehicle Tracking**: Maintains consistent vehicle identification across video frames
- **Crowd Detection Algorithm**: Analyzes vehicle positions using Euclidean distance calculations in Node-RED to identify clusters
- **Data Processing**: Determines whether detected vehicles form a "crowd" (closely grouped) or are scattered individually
- **Real-time Analytics**: Provides live updates on crowd formation and dispersal patterns

## Set up and First Use

### 1. **Create the Crowd Analytics Application Directory**

Navigate to the metro vision AI recipe directory and create the crowd-analytics application by copying the Smart Parking template:

```bash
cd ./edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe
cp -r smart-parking/ crowd-analytics/
```

This creates a new `crowd-analytics` directory with all the necessary application structure and configuration files.

### 2. **Download Sample Video File**

Download a sample video file containing vehicle traffic for testing the AI tolling system:

```bash
mkdir -p ./crowd-analytics/src/dlstreamer-pipeline-server/videos/
wget -O ./crowd-analytics/src/dlstreamer-pipeline-server/videos/easy1.mp4 \
  https://github.com/freedomwebtech/yolov8-advance-parkingspace-detection/raw/main/easy1.mp4

```

<details>
<summary>
Video File Details
</summary>

The sample video contains:
- Multiple vehicles in various parking scenarios
- Examples of both clustered (crowded) and scattered vehicle arrangements
- Duration: Approximately 21 seconds of footage

</details>

### 3. **Download and Setup AI Models**

Create and run the model download script to install all required AI models:

```bash
docker run --rm --user=root \
  -e http_proxy -e https_proxy -e no_proxy \
  -v "$PWD:/home/dlstreamer/metro-suite" \
  intel/dlstreamer:2025.1.2-ubuntu24 bash -c "$(cat <<EOF

cd /home/dlstreamer/metro-suite/

mkdir -p crowd-analytics/src/dlstreamer-pipeline-server/models/public
export MODELS_PATH=/home/dlstreamer/metro-suite/crowd-analytics/src/dlstreamer-pipeline-server/models
/home/dlstreamer/dlstreamer/samples/download_public_models.sh yolo11s coco128

# mkdir -p crowd-analytics/src/dlstreamer-pipeline-server/models/intel

echo "Fix ownership..."
chown -R "$(id -u):$(id -g)" crowd-analytics/src/dlstreamer-pipeline-server/models crowd-analytics/src/dlstreamer-pipeline-server/videos 2>/dev/null || true
EOF
)"
```

The installation script downloads and sets up essential AI models:

| **Model Name** | **Purpose** | **Framework** | **Size** |
|----------------|-------------|---------------|----------|
| YOLO11s | Vehicle detection and localization | PyTorch/OpenVINO | ~65MB |

<details>
<summary>
Model Download Process Details
</summary>

The installation script performs the following operations:
1. Creates the required directory structure under `src/dlstreamer-pipeline-server/models/`
2. Runs a DLStreamer container to access model download tools
3. Downloads public YOLO models using the built-in download scripts
4. Sets up proper file permissions for container access

Expected download time: 5-10 minutes depending on internet connection.

</details>

### 4. **Configure the AI Processing Pipeline**

Update the pipeline configuration to use the crowd analytics AI models. Create or update the configuration file:

```bash
cat > ./crowd-analytics/src/dlstreamer-pipeline-server/config.json << 'EOF'
{
    "config": {
        "pipelines": [
            {
                "name": "yolov11s_crowd_analytics",
                "source": "gstreamer",
                "queue_maxsize": 50,
                "pipeline": "{auto_source} name=source ! decodebin ! gvaattachroi roi=1000,550,1800,800 ! gvadetect model=/home/pipeline-server/models/public/yolo11s/FP16/yolo11s.xml device=CPU pre-process-backend=opencv name=detection inference-region=1 ! queue ! gvatrack tracking-type=short-term-imageless ! queue ! gvametaconvert add-empty-results=true name=metaconvert ! gvametapublish file-format=2 file-path=/tmp/easy1_test1.jsonl ! queue ! gvafpscounter ! appsink name=destination",
                "description": "Vehicle detection and tracking for crowd analytics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "detection-properties": {
                            "element": {
                                "name": "detection",
                                "format": "element-properties"
                            }
                        }
                    }
                },
                "auto_start": false
            }
        ]
    }
}
EOF
```
<details>
<summary>
Pipeline Configuration Explanation
</summary>
The GStreamer pipeline configuration defines the crowd analytics AI processing workflow:

- **Source**: Accepts video input from parking lot camera feeds or video files
- **Decode**: Converts video format to raw frames for processing  
- **gvaattachroi**: Defines a region of interest (ROI) with coordinates thus improving performance by processing only the relevant portion of the frame
- **gvadetect**: Runs the YOLO11s object detection model (FP16 optimized) on CPU to identify and locate vehicles in each frame
- **gvatrack**: Tracks detected vehicles across frames using imageless tracking, assigning persistent IDs to each vehicle without storing frame images
- **gvametaconvert**: Converts inference results to structured metadata with vehicle positions
- **gvafpscounter**: Monitors processing performance

</details>


### 5. **Configure Application Environment**

Update the environment configuration to use the Crowd Analytics application and create self-signed certificates for nginx:

```bash
# Update the .env file to specify the crowd-analytics application and HOST IP Address
sed -i 's/^SAMPLE_APP=.*/SAMPLE_APP=crowd-analytics/' .env
sed -i "s/^HOST_IP=.*/HOST_IP=$(hostname -I | cut -f1 -d' ')/" .env


# Create self signed certificate for nginx
mkdir -p crowd-analytics/src/nginx/ssl
cd crowd-analytics/src/nginx/ssl
if [ ! -f server.key ] || [ ! -f server.crt ]; then
    echo "Generate self-signed certificate..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout server.key -out server.crt -subj "/C=US/ST=CA/L=San Francisco/O=Intel/OU=Edge AI/CN=localhost"
    chown -R "$(id -u):$(id -g)" server.key server.crt 2>/dev/null || true

fi
cd ../../../../

# Verify the configuration
grep SAMPLE_APP= .env
grep HOST_IP= .env
```

### 6. **Deploy the Application**

Set up the Docker Compose configuration and start the application:

```bash
# Copy the compose file for deployment
cp compose-without-scenescape.yml docker-compose.yml

# Start all services in detached mode
docker compose up -d
```

The deployment process will:
- Pull required container images
- Start the DLStreamer pipeline server
- Initialize the Node-RED flow management
- Launch the Grafana dashboard
- Set up the MQTT message broker

## Validation and Expected Results

### 1. **Verify Service Status**

Check that all services are running correctly:

```bash
docker ps
```

Expected output should show containers for:
- `dlstreamer-pipeline-server`
- `node-red`
- `grafana`
- `mosquitto` (MQTT broker)
- `nginx` (reverse proxy)
### 2. **Access the Application Interface**

Open your web browser and navigate to:
- **Main Dashboard**: `https://<HOST_IP>/grafana` (Grafana)
    - Username: admin
    - Password: admin
- **Node-RED Flow Editor**: `https://<HOST_IP>/nodered/`

### 3. **Test Video Processing**

Start the AI pipeline and process the sample video:

```bash
# Start the crowd analytics pipeline with the sample video
curl -k -s https://localhost/api/pipelines/user_defined_pipelines/yolov11s_crowd_analytics -X POST -H 'Content-Type: application/json' -d '
{
    "source": {
        "uri": "file:///home/pipeline-server/videos/easy1.mp4",
        "type": "uri"
    },
    "destination": {
        "metadata": {
            "type": "mqtt",
            "topic": "object_detection_1",
            "timeout": 1000
        },
        "frame": {
            "type": "webrtc",
            "peer-id": "object_detection_1"
        }
    },
    "parameters": {
        "detection-device": "CPU"
    }
}'
```

### 4. **View Live Video Stream**

Access the processed video stream with AI annotations through WebRTC:

```bash
# Open in your web browser (replace <HOST_IP> with your actual IP address)
# For local testing, typically use localhost or 127.0.0.1
https://<HOST_IP>/mediamtx/object_detection_1/
```

For local testing, you can use: `https://localhost/mediamtx/object_detection_1/`

![Crowd Analytics Live Detection](_images/crowd_analytics_detection.png)

Expected results:
- Accurate vehicle detection in parking lot scenario
- Real-time vehicle tracking with consistent IDs across frames

## Troubleshooting

### 1. **Container Startup Issues**

If containers fail to start:
```bash
# Check container logs for specific errors
docker logs <container_name>

# Common issues:
# - Port conflicts: Ensure ports 3000, 1880, 8080 are available
# - Permission issues: Verify Docker permissions
# - Resource constraints: Check available memory and disk space
```

### 2. **Pipeline Processing Errors**

If video processing fails or shows poor accuracy:
```bash
# Check pipeline server logs
docker logs dlstreamer-pipeline-server

# Verify model files are properly installed
ls -la ./crowd-analytics/src/dlstreamer-pipeline-server/models/

# Test with different video source
# Replace the video file with a different sample
```

### 3. **Performance Issues**

For slow processing or high CPU usage:
- **Reduce video resolution**: Use lower resolution input videos
- **Adjust inference device**: Change from CPU to GPU if available
- **Optimize pipeline**: Reduce queue sizes or disable unnecessary features

-------------------------------

# Customizing Node-RED Flows for Crowd Analytics Applications

The following steps guides you through customizing Node-RED flows to implement crowd analytics logic for vehicle detection data. You'll learn how to connect to MQTT data streams from the crowd analytics pipeline, calculate vehicle proximities using Euclidean distances, detect crowd formations (clusters of vehicles in close proximity), and create enhanced analytics outputs.


By following these steps, you will learn how to:
- **Access and Launch Node-RED**: Connect to the Node-RED interface and understand the flow-based programming environment
- **Clear and Reset Flows**: Remove existing flows and start with a clean workspace for custom development
- **Connect to MQTT Data Streams**: Establish connections to receive real-time AI inference data from metro vision applications
- **Implement Custom Data Processing**: Add custom names, metadata, and business logic to AI inference results using function nodes
- **Publish Enhanced Data**: Send processed data back to MQTT topics for consumption by other applications

## Prerequisites

- Complete the previous steps mentioned above to have a running crowd analytics application
- Verify that your crowd analytics application is running and producing MQTT vehicle detection data
- Basic understanding of Node-RED flow-based programming concepts
- Familiarity with MQTT messaging protocol and JSON data structures
- Web browser access to the Node-RED interface

## Crowd Analytics Flow Architecture Overview

The custom Node-RED flow implements crowd detection algorithms:
- **MQTT Input Node**: Subscribes to vehicle detection data from YOLO11s pipeline
- **Vehicle Position Extractor**: Parses bounding box coordinates (x, y, w, h format) to calculate centroids
- **Distance Calculator**: Computes Euclidean distances between all vehicle pairs
- **Hotspot Detector**: Applies proximity thresholds to identify crowd formations (2+ vehicles in close proximity)
- **Analytics Generator**: Creates crowd metrics, density maps, crowd length measurements, and alerts
- **MQTT Output Node**: Publishes crowd analytics data to visualization systems

## Set up and First Use

### 1. **Access the Node-RED Interface**

Launch Node-RED in your web browser using your host system's IP address:

```bash
# Find your host IP address if needed
hostname -I | awk '{print $1}'
```

Open your web browser and navigate to the Node-RED interface:
```
https://<HOST_IP>/nodered/
```
Replace `<HOST_IP>` with your actual system IP address.

<details>
<summary>
Troubleshooting Node-RED Access
</summary>

If you cannot access Node-RED:
1. Verify the crowd analytics application is running:
   ```bash
   docker ps | grep node-red
   ```
2. Check that port 1880 is exposed and accessible
3. Ensure no firewall is blocking the connection
4. Try accessing via localhost if running on the same machine: https://localhost/nodered/

</details>

### 2. **Clear Existing Node-RED Flows**

Remove any existing flows to start with a clean workspace:

1. **Select All Flows**: Press `Ctrl+A` (or `Cmd+A` on Mac) to select all nodes in the current flow
2. **Delete Selected Nodes**: Press the `Delete` key to remove all selected nodes
3. **Deploy Changes**: Click the red **Deploy** button in the top-right corner to save the changes

### 3. **Create MQTT Input Connection for Vehicle Data**

Set up an MQTT subscriber node to receive vehicle detection data:

1. **Add MQTT Input Node**:
   - Drag an `mqtt in` node from the **network** section in the left palette
   - Double-click the node to configure it

2. **Configure MQTT Broker**:
   - **Server**: `broker:1883` (or your MQTT broker address)
   - **Topic**: `object_detection_1` (crowd analytics data topic)
   - **QoS**: `0`
   - **Output**: `auto-detect (string or buffer)`

3. **Set Node Properties**:
   - **Name**: `Vehicle Detection Input`
   - Click **Done** to save the configuration

### 4. **Add Debug Output for Vehicle Data Monitoring**

Create a debug node to monitor incoming vehicle detection data:

1. **Add Debug Node**:
   - Drag a `debug` node from the **common** section
   - Connect the output of the MQTT input node to the debug node input

2. **Configure Debug Node**:
   - **Output**: `msg.payload`
   - **To**: `debug tab and console`
   - **Name**: `Vehicle Data Monitor`

3. **Deploy and Test**:
   - Click **Deploy**
   - Check the debug panel (bug icon in the right sidebar) for incoming vehicle detection messages

4. **Start the Crowd Analytics Pipeline** (if needed):
   If you don't see data in the debug panel, execute the crowd analytics pipeline using this curl command:

   ```bash
   curl -k -s https://localhost/api/pipelines/user_defined_pipelines/yolov11s_crowd_analytics -X POST -H 'Content-Type: application/json' -d '
   {
       "source": {
           "uri": "file:///home/pipeline-server/videos/easy1.mp4",
           "type": "uri"
       },
       "destination": {
           "metadata": {
               "type": "mqtt",
               "topic": "object_detection_1",
               "timeout": 1000
           },
           "frame": {
               "type": "webrtc",
               "peer-id": "object_detection_1"
           }
       },
       "parameters": {
           "detection-device": "CPU"
       }
   }'
   ```

### 5. **Implement Vehicle Position Extraction Function**

Add a function node to extract vehicle positions from detection data:

1. **Add Function Node**:
   - Drag a `function` node from the **function** section
   - Position it after the MQTT input node

2. **Configure the Vehicle Position Extractor**:
   - **Name**: `Extract Vehicle Positions`
   - **Function Code**:

```javascript
// Extract vehicle positions from YOLOv10s detection data
// Calculate centroid coordinates for each detected vehicle

// Parse JSON if payload is a string
if (typeof msg.payload === 'string') {
    try {
        msg.payload = JSON.parse(msg.payload);
    } catch (e) {
        node.warn("Failed to parse JSON: " + e.message);
        return null;
    }
}

// Check if payload exists and has metadata.objects array
if (!msg.payload || !msg.payload.metadata || !msg.payload.metadata.objects ||
    !Array.isArray(msg.payload.metadata.objects)) {
    return null; // Ignore frames without vehicle data
}

let vehicles = [];
let frameTimestamp = Date.now();
let metadata = msg.payload.metadata;

// Get frame dimensions for calculations
let frameWidth = metadata.width || 1920;
let frameHeight = metadata.height || 1080;

// Process each detected object
for (let i = 0; i < metadata.objects.length; i++) {
    let obj = metadata.objects[i];

    // Filter for cars only (you can add more vehicle types if needed)
    let vehicleTypes = ['car', 'truck', 'bus', 'motorcycle', 'vehicle'];
    if (!obj.detection || !obj.detection.label ||
        !vehicleTypes.includes(obj.detection.label.toLowerCase())) {
        continue; // Skip non-vehicle objects
    }

    // Extract bounding box coordinates (x, y, w, h format)
    let x = obj.x || 0;
    let y = obj.y || 0;
    let w = obj.w || 0;
    let h = obj.h || 0;

    if (w === 0 || h === 0) {
        continue; // Skip objects without valid dimensions
    }

    // Calculate centroid coordinates (center of bounding box)
    let centerX = x + (w / 2);
    let centerY = y + (h / 2);

    // Calculate bounding box area
    let area = w * h;

    // Get normalized coordinates from detection bounding_box
    let bbox = obj.detection.bounding_box || {};

    // Create vehicle object
    let vehicle = {
        id: obj.id || `vehicle_${i}`,
        type: obj.detection.label,
        confidence: obj.detection.confidence || 0,
        position: {
            x: centerX,      // Pixel coordinates
            y: centerY,
            x_norm: (centerX / frameWidth),     // Normalized [0-1]
            y_norm: (centerY / frameHeight)
        },
        bbox: {
            x: x,            // Top-left x in pixels
            y: y,            // Top-left y in pixels
            width: w,        // Width in pixels
            height: h,       // Height in pixels
            area: area,      // Area in square pixels
            x_min_norm: bbox.x_min || 0,        // Normalized coordinates
            y_min_norm: bbox.y_min || 0,
            x_max_norm: bbox.x_max || 0,
            y_max_norm: bbox.y_max || 0
        },
        timestamp: frameTimestamp
    };

    vehicles.push(vehicle);
}

// Only process frames with vehicles
if (vehicles.length === 0) {
    return null;
}

// Create output message with vehicle positions
msg.payload = {
    timestamp: frameTimestamp,
    frame_dimensions: {
        width: frameWidth,
        height: frameHeight
    },
    vehicle_count: vehicles.length,
    vehicles: vehicles
};

return msg;
```

### 6. **Implement Hotspot Detection Algorithm**

Add a function node to calculate inter-vehicle distances and detect hotspots:

1. **Add Function Node**:
   - Drag another `function` node from the **function** section
   - Connect it after the `Extract Vehicle Positions` node

2. **Configure the Hotspot Detection Logic**:
   - **Name**: `Hotspot Detection Algorithm`
   - **Function Code**:

```javascript
// Hotspot Detection Algorithm for PARKED Vehicles
// Tracks vehicle positions across frames to identify stationary (parked) vehicles
// Calculates hotspots only for parked vehicles

// Initialize persistent storage
if (!context.vehicleHistory) context.vehicleHistory = {};
if (!context.previousHotspots) context.previousHotspots = {};

// If no vehicles detected, return early
if (!msg.payload || !msg.payload.vehicles || msg.payload.vehicles.length === 0) {
    msg.payload = {
        ...msg.payload,
        hotspot_count: 0,
        hotspots: [],
        parked_vehicles: []
    };
    return msg;
}

// Extract vehicle list and current timestamp
let vehicles = msg.payload.vehicles;
let currentTimestamp = msg.payload.timestamp;

// Configuration parameters
const DISTANCE_THRESHOLD = 150;       // Maximum distance (pixels) to consider vehicles part of same hotspot
const MIN_HOTSPOT_SIZE = 2;           // Minimum number of parked vehicles to form a hotspot
const PARKED_THRESHOLD = 150;         // Maximum movement (pixels) to consider a vehicle stationary
const PARKED_FRAMES_REQUIRED = 15;    // Frames vehicle must stay stationary to be marked as parked
const MOVING_FRAMES_GRACE = 30;       // Allowed consecutive moving frames before resetting parked status
const HISTORY_TIMEOUT = 5000;         // Time (ms) to keep vehicle history without updates
const DISTANCE_MODE = "euclidean";    // Distance calculation method: "euclidean", "manhattan", etc.
const INCLUDE_OVERLAPPING = true;     // Whether overlapping vehicles are allowed in same hotspot
const OVERLAP_THRESHOLD = 0.3;        // Maximum allowed bounding box overlap fraction for separate hotspots
const HOTSPOT_STABILITY_FRAMES = 20;  // Frames a hotspot must persist to be considered stable


// Calculate distance between two positions
function calculateDistance(pos1, pos2, mode = DISTANCE_MODE) {
    let dx = Math.abs(pos1.x - pos2.x);
    let dy = Math.abs(pos1.y - pos2.y);
    switch (mode) {
        case "horizontal": return dx;
        case "vertical": return dy;
        case "manhattan": return dx + dy;
        case "euclidean":
        default: return Math.sqrt(dx * dx + dy * dy);
    }
}

// Calculate intersection over union (IoU) of two bounding boxes
function calculateBBoxOverlap(b1, b2) {
    let xLeft = Math.max(b1.x, b2.x);
    let yTop = Math.max(b1.y, b2.y);
    let xRight = Math.min(b1.x + b1.width, b2.x + b2.width);
    let yBottom = Math.min(b1.y + b1.height, b2.y + b2.height);
    if (xRight < xLeft || yBottom < yTop) return 0;
    let intersectionArea = (xRight - xLeft) * (yBottom - yTop);
    let union = b1.area + b2.area - intersectionArea;
    return intersectionArea / union;
}

// Cleanup old vehicles from history
for (let id of Object.keys(context.vehicleHistory)) {
    if (currentTimestamp - context.vehicleHistory[id].lastSeen > HISTORY_TIMEOUT) {
        delete context.vehicleHistory[id];
    }
}

// Track parked vehicles
let parkedVehicles = [];

for (let vehicle of vehicles) {
    let id = vehicle.id;
    let pos = vehicle.position || { x: vehicle.x, y: vehicle.y };

    if (!context.vehicleHistory[id]) {
        // New vehicle: initialize history
        context.vehicleHistory[id] = {
            id,
            positions: [pos],
            firstSeen: currentTimestamp,
            lastSeen: currentTimestamp,
            isParked: false,
            stationaryFrames: 1,
            movingFrames: 0
        };
    } else {
        // Existing vehicle: update history
        let history = context.vehicleHistory[id];
        history.positions.push(pos);
        history.lastSeen = currentTimestamp;

        if (history.positions.length > PARKED_FRAMES_REQUIRED)
            history.positions.shift();

        let totalFrames = history.positions.length;

        if (totalFrames >= PARKED_FRAMES_REQUIRED) {
            let firstPos = history.positions[0];
            let lastPos = history.positions[totalFrames - 1];
            let totalMovement = calculateDistance(firstPos, lastPos);

            if (totalMovement <= PARKED_THRESHOLD) {
                history.stationaryFrames++;
                if (history.stationaryFrames >= PARKED_FRAMES_REQUIRED) {
                    history.isParked = true;
                }
            } else {
                history.stationaryFrames = 0;
                history.isParked = false;
                history.movingFrames++;
            }
        }
    }

    // Add to parked list if currently parked
    if (context.vehicleHistory[id].isParked) {
        parkedVehicles.push({
            ...vehicle,
            parked_duration_ms: currentTimestamp - context.vehicleHistory[id].firstSeen,
            parked_frames: context.vehicleHistory[id].stationaryFrames
        });
    }
}

// Skip hotspot computation if not enough parked vehicles
if (parkedVehicles.length < MIN_HOTSPOT_SIZE) {
    msg.payload = {
        ...msg.payload,
        total_vehicles: vehicles.length,
        parked_vehicles_count: parkedVehicles.length,
        hotspot_count: 0,
        hotspots: [],
        parked_vehicles: parkedVehicles
    };
    return msg;
}

// Compute distance matrix and proximity pairs between parked vehicles
let distanceMatrix = [];
let proximityPairs = [];

for (let i = 0; i < parkedVehicles.length; i++) {
    distanceMatrix[i] = [];
    for (let j = 0; j < parkedVehicles.length; j++) {
        if (i === j) distanceMatrix[i][j] = 0;
        else {
            let d = calculateDistance(parkedVehicles[i].position, parkedVehicles[j].position);
            distanceMatrix[i][j] = d;
            if (d <= DISTANCE_THRESHOLD) {
                let overlap = calculateBBoxOverlap(parkedVehicles[i].bbox, parkedVehicles[j].bbox);
                let isClose = INCLUDE_OVERLAPPING || overlap < OVERLAP_THRESHOLD;
                if (isClose) {
                    proximityPairs.push({
                        vehicle1_id: parkedVehicles[i].id,
                        vehicle2_id: parkedVehicles[j].id,
                        distance: Math.round(d * 100) / 100,
                        overlap: Math.round(overlap * 1000) / 1000
                    });
                }
            }
        }
    }
}

// Cluster parked vehicles into hotspots
let visited = new Array(parkedVehicles.length).fill(false);
let hotspots = [];

function findHotspot(i, currentHotspot) {
    // Recursive DFS to find connected parked vehicles
    visited[i] = true;
    currentHotspot.push(i);
    for (let j = 0; j < parkedVehicles.length; j++) {
        if (!visited[j] && distanceMatrix[i][j] <= DISTANCE_THRESHOLD) {
            if (INCLUDE_OVERLAPPING || calculateBBoxOverlap(parkedVehicles[i].bbox, parkedVehicles[j].bbox) < OVERLAP_THRESHOLD) {
                findHotspot(j, currentHotspot);
            }
        }
    }
}

// Identify all hotspots
for (let i = 0; i < parkedVehicles.length; i++) {
    if (!visited[i]) {
        let cluster = [];
        findHotspot(i, cluster);
        if (cluster.length >= MIN_HOTSPOT_SIZE) {
            let members = cluster.map(idx => parkedVehicles[idx]);
            let centroidX = members.reduce((sum, v) => sum + v.position.x, 0) / members.length;
            let centroidY = members.reduce((sum, v) => sum + v.position.y, 0) / members.length;

            let minX = Math.min(...members.map(v => v.bbox.x));
            let minY = Math.min(...members.map(v => v.bbox.y));
            let maxX = Math.max(...members.map(v => v.bbox.x + v.bbox.width));
            let maxY = Math.max(...members.map(v => v.bbox.y + v.bbox.height));
            let hotspotWidth = maxX - minX;
            let hotspotHeight = maxY - minY;

            let maxDistance = 0;
            for (let m = 0; m < members.length; m++)
                for (let n = m + 1; n < members.length; n++)
                    maxDistance = Math.max(maxDistance, distanceMatrix[cluster[m]][cluster[n]]);

            let area = Math.PI * Math.pow(maxDistance / 2, 2);
            let density = members.length / (area || 1);

            let vehicleIds = members.map(v => v.id).sort((a, b) => a - b).join('_');
            hotspots.push({
                id: "hotspot_" + vehicleIds,
                vehicle_count: members.length,
                vehicle_ids: vehicleIds,
                centroid: { x: Math.round(centroidX), y: Math.round(centroidY) },
                bounding_box: { x: Math.round(minX), y: Math.round(minY), width: Math.round(hotspotWidth), height: Math.round(hotspotHeight) },
                density: Math.round(density * 1000) / 1000,
                vehicles: members.map(v => ({ id: v.id, type: v.type, parked_duration_ms: v.parked_duration_ms }))
            });
        }
    }
}

// Track hotspot stability across frames
let currentHotspotIds = new Set();
let stableHotspots = [];

for (let hs of hotspots) {
    let key = hs.vehicle_ids;
    currentHotspotIds.add(key);

    if (!context.previousHotspots[key]) {
        context.previousHotspots[key] = { frameCount: 1, published: false, data: hs };
    } else {
        context.previousHotspots[key].frameCount++;
        context.previousHotspots[key].data = hs;
    }

    if (context.previousHotspots[key].frameCount >= HOTSPOT_STABILITY_FRAMES) {
        stableHotspots.push(hs);
        if (!context.previousHotspots[key].published) {
            node.warn("NEW STABLE HOTSPOT: [" + key.replace(/_/g, ", ") + "]");
            context.previousHotspots[key].published = true;
        }
    }
}

// Remove hotspots that no longer exist
for (let key in context.previousHotspots) {
    if (!currentHotspotIds.has(key)) {
        if (context.previousHotspots[key].published)
            node.warn("HOTSPOT ENDED: [" + key.replace(/_/g, ", ") + "]");
        delete context.previousHotspots[key];
    }
}

// Return final output
msg.payload = {
    ...msg.payload,
    total_vehicles: vehicles.length,
    parked_vehicles_count: parkedVehicles.length,
    hotspot_count: stableHotspots.length,
    hotspots: stableHotspots,
    parked_vehicles: parkedVehicles,
    proximity_pairs: proximityPairs,
    distance_threshold: DISTANCE_THRESHOLD,
    distance_mode: DISTANCE_MODE,
    parked_threshold: PARKED_THRESHOLD,
    parked_frames_required: PARKED_FRAMES_REQUIRED
};

return msg;
```


### 7. **Add Hotspot Analytics Output Processing**

Create a function node to generate hotspot analytics summaries and alerts:

1. **Add Function Node**:
   - Drag another `function` node from the **function** section
   - Connect it after the `Hotspot Detection Algorithm` node

2. **Configure Analytics Generator**:
   - **Name**: `Generate Hotspot Analytics`
   - **Function Code**:

```javascript
// Generate Hotspot Analytics for PARKED Vehicles

if (!msg.payload || !msg.payload.hotspots) {
    return null;
}

let hotspots = msg.payload.hotspots || [];
let timestamp = msg.payload.timestamp;

// Create table-friendly output with one row per hotspot
let tableData = hotspots.map((hotspot, index) => {
    // Calculate average parked duration and frames for vehicles in this hotspot
    let totalDuration = 0;
    let totalFrames = 0;
    let vehicleIds = [];

    // hotspot.vehicles is an array of vehicle objects with parked_duration_ms
    for (let vehicle of hotspot.vehicles) {
        vehicleIds.push(vehicle.id);
        totalDuration += vehicle.parked_duration_ms || 0;

        // Calculate frames from duration if not available (assuming 30fps)
        let frames = vehicle.parked_frames || Math.round((vehicle.parked_duration_ms || 0) / 33.33);
        totalFrames += frames;
    }

    let vehicleCount = hotspot.vehicles.length;
    let avgDurationSec = vehicleCount > 0 ? Math.round(totalDuration / vehicleCount / 1000) : 0;
    let avgFrames = vehicleCount > 0 ? Math.round(totalFrames / vehicleCount) : 0;

    return {
        timestamp: timestamp,
        hotspot_id: hotspot.id,
        hotspot_number: index + 1,
        vehicle_count: hotspot.vehicle_count,
        centroid_x: Math.round(hotspot.centroid.x),
        centroid_y: Math.round(hotspot.centroid.y),
        avg_distance_px: Math.round(hotspot.avg_distance),
        max_distance_px: Math.round(hotspot.max_distance),
        vehicle_ids: hotspot.vehicle_ids.replace(/_/g, ', '),
        avg_parked_duration_sec: avgDurationSec,
        avg_parked_frames: avgFrames
    };
});

// If no hotspots, don't send anything
if (tableData.length === 0) {
    return null;
}

// Split array into individual messages (one per hotspot)
// Each hotspot becomes a separate MQTT message for proper Grafana table visualization
return tableData.map(hotspot => {
    return { payload: hotspot };
});
```

### 8. **Configure MQTT Output for Hotspot Analytics**

Set up a single MQTT publisher for hotspot analytics data:

1. **Add MQTT Output Node**:
   - Drag an `mqtt out` node from the **network** section
   - Connect the output of the analytics generator to this node
   - **Configure**:
     - **Server**: Same as input (`broker:1883`)
     - **Topic**: `hotspot_analytics` (or use `msg.topic` for dynamic topics)
     - **QoS**: `0`
     - **Retain**: `false`
     - **Name**: `Hotspot Analytics Publisher`

### 9. **Add Debug Monitoring**

Create debug nodes to monitor the hotspot analytics pipeline:

1. **Add Debug Nodes**:
   - Add debug nodes after each function node
   - **Names**: 
     - `Vehicle Positions Debug`
     - `Hotspot Detection Debug`
     - `Analytics Output Debug`

2. **Configure Debug Outputs**:
   - Set each debug node to output `msg.payload`
   - Enable console output for troubleshooting

### Expected Node-RED Flow

![Crowd Analytics Node-RED Flow](_images/crowd-analytics-node-red-flow.png)

### 10. **Deploy and Validate the Crowd Analytics Flow**

Test your complete crowd analytics Node-RED flow:

1. **Deploy the Complete Flow**:
   - Click the Deploy button on the Top Right side in Node-RED interface

2. **Monitor Crowd Analytics**:
   - Open the debug panel in Node-RED
   - Start the crowd analytics pipeline using the curl command:
    ```bash
   curl -k -s https://localhost/api/pipelines/user_defined_pipelines/yolov11s_crowd_analytics -X POST -H 'Content-Type: application/json' -d '
   {
       "source": {
           "uri": "file:///home/pipeline-server/videos/easy1.mp4",
           "type": "uri"
       },
       "destination": {
           "metadata": {
               "type": "mqtt",
               "topic": "object_detection_1",
               "timeout": 1000
           },
           "frame": {
               "type": "webrtc",
               "peer-id": "object_detection_1"
           }
       },
       "parameters": {
           "detection-device": "CPU"
       }
   }'
   ```
   - Verify that vehicle detection data flows through each stage
   - Vehicle crowd alert generation for different congestion scenarios
   - Review hotspot length calculations in the output

## Troubleshooting

### 1. **No Data in Debug Panel**
- **Problem**: Debug nodes show no incoming data
- **Solution**: 
  - Verify the AI application is running and generating inference data
  - Check MQTT topic names match your application's output topics
  - Ensure proper JSON parsing in function nodes

### 2. **Function Node Errors**
- **Problem**: Function node shows errors in the debug panel
- **Solution**: 
  - Add try-catch blocks around JSON parsing
  - Use `node.warn()` or `node.error()` for debugging
  - Validate input data structure before processing


After successfully implementing hotspot analytics with Node-RED, follow the following steps to set up Grafana dashboards for visualizing the hotspot data and metrics. This will allow you to monitor vehicle congestion and hotspot formations in real-time, providing valuable insights.


---------------------------------------
# Visualizing Hotspot Analytics in Grafana

The hotspot analytics data published to `hotspot_analytics` can be visualized in real-time using Grafana.

#### **Quick Setup Steps**

1. **Access Grafana**: Navigate to `https://<HOST_IP>/grafana` (Username: `admin`, Password: `admin`)

2. **Create New Dashboard**:
   - Click the "+" icon in the right sidebar
   - Select "New Dashboard" from the top right menu
   - Click "Add Visualization"

### 2. **Add Real-Time Video Stream Panel**

1. **Create HTML Panel for Live Feed**:
   - In the panel editor, change the visualization type to "Text" (On Right side of Visualization Editor)
   - Switch to "HTML" mode
   - Add the following iframe code:
   - In the below code update <HOST_IP> to your host IP address. If you are testing on localhost, update it to localhost.

   ```html
   <iframe 
     src="https://<HOST_IP>/mediamtx/object_detection_1/" 
     style="width:100%;height:500px;" 
     allow="autoplay; encrypted-media"
     frameborder="0">
   </iframe>
   ```

2. **Configure Video Panel Settings**:
   - Set panel title to "Live Vehicle Crowd Detection Feed"
   - Click "Apply" to save the panel
   - Adjust panel size as needed

### 3. **Create Crowd Analytics Data Table**

1. **Add New Panel**:
   - Click "Add Visualization" to create another visualization
   - Select "Table" as the visualization type (On Right side of Visualization Editor)
   - Set panel title to "Real-time Vehicle Hotspot Analytics"

2. **Configure Data Source**:
   - Set your MQTT data source as "grafana-mqtt-datasource"
   - Configure topic to fetch hotspot analytics data
   - Update Topic to "hotspot_analytics"

3. **Add Transformations** (Transform tab at bottom):   
   a. **Sort by**:
      - Click **"+ Add transformation"** → Select **"Sort by"**
      - **Field**: Select **"Time"**
      - **Reverse**: Toggle to **On** (newest first)
      - Click **Apply**
      
      **Purpose**: Ensures the most recent data for each hotspot appears first
   
   b. **Group by**:
      - Click **"+ Add transformation"** → Select **"Group by"**
      - **Group by**: Select **"hotspot_id"**
      - **Calculations** (configure for each field):
        - `timestamp`: Select **"Last"**
        - `hotspot_number`: Select **"Last"**
        - `vehicle_count`: Select **"Last"**
        - `centroid_x`: Select **"Last"**
        - `centroid_y`: Select **"Last"**
        - `avg_distance_px`: Select **"Last"**
        - `max_distance_px`: Select **"Last"**
        - `vehicle_ids`: Select **"Last"**
        - `avg_parked_duration_sec`: Select **"Last"**
        - `avg_parked_frames`: Select **"Last"**
      - Click **Apply**

    You can add more transformations as needed for additional fields.

4. **Configure Time Window and Refresh** (for real-time display):
   - **Time Range** (top-right corner): Set to **"Last 5 seconds"**
   - **Auto-refresh**: Select **"5s"** from dropdown
   - Click **Save**

5. **Save Dashboard**
   - Click the save icon at the top of the dashboard
   - Name your dashboard "Vehicle Crowd Analytics Dashboard"

6. **Run the pipeline** (if not already running):
   - Use the curl command to start the crowd analytics pipeline to see the expected results:
   
   ```bash
   curl -k -s https://localhost/api/pipelines/user_defined_pipelines/yolov11s_crowd_analytics -X POST -H 'Content-Type: application/json' -d '
   {
       "source": {
           "uri": "file:///home/pipeline-server/videos/easy1.mp4",
           "type": "uri"
       },
       "destination": {
           "metadata": {
               "type": "mqtt",
               "topic": "object_detection_1",
               "timeout": 1000
           },
           "frame": {
               "type": "webrtc",
               "peer-id": "object_detection_1"
           }
       },
       "parameters": {
           "detection-device": "CPU"
       }
   }'
   ```

## Expected Results

![Crowd Analytics Grafana](_images/crowd-analytics-grafana.png)

After completing this tutorial, you should have:

- **Interactive Dashboard**: A custom Grafana dashboard displaying real-time video and data
- **Live Video Feed**: WebRTC stream showing object detection overlay
- **Dynamic Data Table**: Real-time MQTT data updates with detection information
- **Integrated Monitoring**: Combined visual and analytical view of the crowd detection

**Troubleshooting**:
- **No data appearing**: Verify Node-RED flow is deployed and pipeline is running
- **Same hotspot appearing multiple times**: Add the **"Sort by"** and **"Group by hotspot_id"** transformations to deduplicate
- **Only 1 row shown when 3 hotspots exist**: Verify all transformations are applied in correct order: Sort by → Group by


## Troubleshooting

### **No Vehicle Detection Data**
- **Problem**: Debug nodes show no incoming vehicle data
- **Solution**: 
  ```bash
  # Verify crowd analytics pipeline is running
  curl -k -s https://localhost/api/pipelines/user_defined_pipelines/yolov11s_crowd_analytics
  # Check MQTT broker connectivity
  docker logs <mqtt-container-name>
  ```

### **Incorrect Distance Calculations**
- **Problem**: Crowd detection not working properly
- **Solution**: 
  - Verify bounding box coordinates are valid (x, y, w, h format)
  - Check centroid calculations in vehicle position extractor
  - Adjust `DISTANCE_THRESHOLD` for your specific video resolution (default: 150 pixels for 1920x1080)

### **No Hotspots Detected**
- **Problem**: Vehicles are present but no hotspots detected
- **Solution**: 
  - Increase the `DISTANCE_THRESHOLD` value (try 200-300 pixels)
  - Verify `MIN_HOTSPOT_SIZE` is set to 2 vehicles
  - Check vehicle filtering logic (car, truck, bus types)
  - Review proximity_pairs in debug output to see actual distances

### **Function Node Errors**
- **Problem**: JavaScript errors in hotspot detection functions
- **Solution**: 
  - Add error handling with try-catch blocks
  - Use `node.warn()` for debugging intermediate values
  - Validate input data structure before processing
  - Check that msg.payload.metadata.objects exists

### **Hotspot Length Not Calculated**
- **Problem**: Hotspot length shows as 0 or undefined
- **Solution**:
  - Verify that multiple vehicles are detected in the hotspot
  - Check that distance_mode used for calculations are working
  - Review the `max_distance` field in hotspot output
  - Ensure distanceMatrix is populated correctly

## Supporting Resources

- [DLStreamer Documentation](https://dlstreamer.github.io/)
- [Metro AI Solutions](https://github.com/open-edge-platform/edge-ai-suites/tree/main/metro-ai-suite)
- [Node-RED Official Documentation](https://nodered.org/docs/)
- [MQTT Protocol Specification](https://mqtt.org/)
- [Euclidean Distance Algorithms](https://en.wikipedia.org/wiki/Euclidean_distance)
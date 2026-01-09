# Traffic Intelligence Service

A lightweight microservice for real-time traffic analysis at individual intersections. This service provides weather-aware traffic intelligence with VLM-powered insights and structured alerts.

## Features

### 🚦 Real-time Traffic Monitoring
- Subscribes to MQTT camera data from intersection cameras
- Monitors traffic density across multiple directions (North, South, East, West)
- Provides real-time traffic snapshots and historical data

### 🌤️ Weather Integration
- Fetches real-time weather data from National Weather Service API
- Analyzes weather impact on traffic patterns
- Correlates road conditions with traffic congestion

### 🤖 AI-Powered Analysis
- Enhanced VLM (Vision Language Model) integration for traffic analysis
- Structured prompts for traffic pattern recognition
- Weather-aware alert generation with confidence scoring
- Contextual recommendations for traffic management

### 📊 Structured Data Output
- API responses match the existing `data.json` schema
- Real-time camera image synchronization
- Comprehensive traffic intelligence reports

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   MQTT Broker   │────│ Traffic Intel    │────│   VLM Service   │
│  (Camera Data)  │    │     Service      │    │  (Analysis)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                                │
                       ┌──────────────────┐    ┌─────────────────┐
                       │ Weather Service  │────│    NWS API      │
                       │   (Conditions)   │    │  (gov data)     │
                       └──────────────────┘    └─────────────────┘
```

## Quick Start

### UV Development (Recommended)

1. **Install uv (if not already installed):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Quick setup and run:**
```bash
git clone <repository-url>
cd traffic-intelligence

# Using the development script
./dev.sh setup    # Create venv and install dependencies
./dev.sh run      # Start the service

# Or using Make
make setup        # Setup environment
make run          # Start the service
make help         # Show all available commands
```

3. **Development mode:**
```bash
./dev.sh dev      # Run with debug logging
./dev.sh test     # Run tests
./dev.sh example  # Run example client

# Or with Make
make dev          # Development mode
make test         # Run tests
make example      # Run example client
make lint         # Run linting
```

### Docker Deployment

1. **Clone the repository:**
```bash
git clone <repository-url>
cd traffic-intelligence
```

2. **Configure environment:**
```bash
cp config/traffic_intelligence.json.example config/traffic_intelligence.json
# Edit configuration for your intersection
```

3. **Start with Docker Compose:**
```bash
docker-compose up -d
```

4. **Verify service:**
```bash
curl http://localhost:8081/health
curl http://localhost:8081/api/v1/traffic/current
```

### Local Development with UV

1. **Install uv (if not already installed):**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# or
pip install uv
```

2. **Create virtual environment and install dependencies:**
```bash
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -r requirements.tx
```

3. **Set environment variables:**
```bash
export INTERSECTION_ID="97781c36-b53a-4749-87e6-8815da99bac7"
export INTERSECTION_NAME="Intersection-Demo"
export MQTT_HOST="broker.scenescape.intel.com"
export VLM_BASE_URL="http://vlm-service:8080"
```

4. **Run the service:**
```bash
uv run python -m traffic_intelligence.main
# or with activated venv:
python -m traffic_intelligence.main
```

## API Documentation

### Base URL
- Local: `http://localhost:8081/api/v1`
- Docker: `http://localhost:8081/api/v1`

### Endpoints

#### Get Current Traffic Intelligence
```http
GET /traffic/current
```

Returns complete traffic intelligence data matching the `data.json` schema:

```json
{
  "timestamp": "2025-09-16T10:30:00.123456",
  "intersection_id": "cb1cf1a0-b936-4d47-9221-3fd5cf24857d",
  "data": {
    "intersection_id": "cb1cf1a0-b936-4d47-9221-3fd5cf24857d",
    "intersection_name": "Intersection-1",
    "latitude": 37.55336,
    "longitude": -122.29627,
    "timestamp": "2025-09-16T10:30:00.123456",
    "north_camera": 3,
    "south_camera": 7,
    "east_camera": 2,
    "west_camera": 4,
    "total_density": 16
  },
  "camera_images": {
    "north_camera": {
      "camera_id": "intersection-1-cam1",
      "direction": "north",
      "timestamp": "2025-09-16T10:29:45.000000",
      "image_base64": "...",
      "image_size_bytes": 45678
    }
  },
  "weather_data": {
    "name": "This Afternoon",
    "temperature": 72,
    "temperature_unit": "F",
    "detailed_forecast": "Partly cloudy with light winds",
    "fetched_at": "2025-09-16T10:25:00.000000",
    "is_precipitation": false,
  },
  "vlm_analysis": {
    "traffic_summary": "Moderate traffic with high density in south direction",
    "alerts": [
      {
        "alert_type": "congestion",
        "level": "warning",
        "description": "High traffic density detected in south direction",
        "weather_related": false
      }
    ],
    "recommendations": [
      "Monitor south-bound signal timing",
      "Consider traffic flow optimization"
    ],
    "analysis_timestamp": "2025-09-16T10:30:00.000000"
  }
}
```

#### Get Traffic History
```http
GET /traffic/history?minutes=30
```

Returns historical traffic data for the specified time period.

#### Get Current Weather
```http
GET /weather/current
```

Returns current weather conditions for the intersection location.

#### Get VLM Analysis
```http
GET /analysis/current
```

Returns the latest VLM traffic analysis with structured alerts.

#### Trigger Manual Analysis
```http
POST /analysis/trigger
```

Manually triggers VLM analysis of current traffic conditions.

#### Service Status
```http
GET /status
```

Returns service health and operational statistics.

#### Configuration
```http
GET /config
PUT /config/threshold?threshold=10
```

Get/update service configuration parameters.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INTERSECTION_ID` | `cb1cf1a0-b936-4d47-9221-3fd5cf24857d` | Unique intersection identifier |
| `INTERSECTION_NAME` | `Intersection-1` | Human-readable intersection name |
| `INTERSECTION_LATITUDE` | `37.55336` | Intersection GPS latitude |
| `INTERSECTION_LONGITUDE` | `-122.29627` | Intersection GPS longitude |
| `MQTT_HOST` | `broker.scenescape.intel.com` | MQTT broker hostname |
| `MQTT_PORT` | `1883` | MQTT broker port |
| `CAMERA_1_TOPIC` | `scenescape/data/camera/camera1` | MQTT topic for camera 1 |
| `CAMERA_2_TOPIC` | `scenescape/data/camera/camera2` | MQTT topic for camera 2 |
| `CAMERA_3_TOPIC` | `scenescape/data/camera/camera3` | MQTT topic for camera 3 |
| `VLM_BASE_URL` | `http://vlm-service:8080` | VLM service endpoint |
| `HIGH_DENSITY_THRESHOLD` | `5` | Vehicle count threshold for high density |
| `WEATHER_CACHE_MINUTES` | `15` | Weather data cache duration |

### Configuration File

Create `config/traffic_intelligence.json`:

```json
{
  "intersection": {
    "id": "cb1cf1a0-b936-4d47-9221-3fd5cf24857d",
    "name": "Intersection-1",
    "latitude": 37.55336,
    "longitude": -122.29627
  },
  "mqtt": {
    "host": "broker.scenescape.intel.com",
    "port": 1883,
    "use_tls": true,
    "camera_topics": [
      "scenescape/data/camera/camera1",
      "scenescape/data/camera/camera2",
      "scenescape/data/camera/camera3",
      "scenescape/data/camera/camera4"
    ]
  },
  "traffic": {
    "high_density_threshold": 5,
    "analysis_window_seconds": 30,
  }
}
```

## MQTT Data Format

The service expects camera data on MQTT topics in this format:

```json
{
  "camera_id": "camera1",
  "vehicle_count": 5,
  "pedestrian_count": 2,
  "timestamp": "2025-09-16T10:30:00.000000Z",
  "image_data": "base64-encoded-image-data"
}
```

### Camera-to-Direction Mapping

| Camera | MQTT Topic | Direction |
|--------|------------|-----------|
| Camera 1 | `scenescape/data/camera/camera1` | North |
| Camera 2 | `scenescape/data/camera/camera2` | South |
| Camera 3 | `scenescape/data/camera/camera3` | East |

## VLM Integration

### Enhanced Prompts

The service uses structured prompts that include:
- Real-time traffic density by direction
- Current weather conditions and road impact
- Historical traffic patterns
- Request for structured JSON responses

### Alert Types

- `congestion`: Traffic density alerts
- `weather_related`: Weather-impacted traffic
- `road_condition`: Road surface/visibility issues
- `accident`: Detected incidents
- `maintenance`: Construction/maintenance impacts

### Alert Levels

- `info`: Informational notices
- `warning`: Elevated traffic conditions
- `critical`: Severe congestion or safety issues

## Weather Analysis

### Road Condition Detection

The service analyzes weather data to determine:
- **Dry**: Normal conditions
- **Wet**: Rain or recent precipitation
- **Icy**: Freezing conditions or ice formation
- **Low Visibility**: Fog or severe weather

### Traffic Correlation

Weather impact analysis includes:
- Precipitation effects on traffic flow
- Temperature impacts on vehicle performance
- Visibility conditions affecting driver behavior
- Road surface conditions and safety

## Monitoring and Observability

### Health Checks

```bash
# Service health
curl http://localhost:8081/health

# Service status with metrics
curl http://localhost:8081/api/v1/status
```

### Logging

Structured JSON logging with configurable levels:
- Service operations and errors
- MQTT message processing
- VLM analysis triggers and results
- Weather data updates

### Metrics

Key operational metrics available via `/status`:
- Current traffic density
- Active camera count
- VLM analysis frequency
- Data processing rates

## Development

### Project Structure

```
traffic-intelligence/
├── main.py                 # Service entry point
├── models/                 # Data models and schemas
│   └── __init__.py
├── services/               # Business logic services
│   ├── config.py           # Configuration management
│   ├── mqtt_service.py     # MQTT data ingestion
│   ├── weather_service.py  # Weather API integration
│   ├── vlm_service.py      # VLM analysis service
│   └── data_aggregator.py  # Data processing and coordination
├── api/                    # REST API endpoints
│   └── routes.py
├── config/                 # Configuration files
│   └── traffic_intelligence.json
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container build
├── docker-compose.yml     # Multi-service deployment
└── start.sh               # Service startup script
```

### Adding New Features

1. **New Alert Types**: Extend `AlertType` enum in `models/__init__.py`
2. **Additional Cameras**: Update camera topics in configuration
3. **Custom Analysis**: Modify VLM prompts in `vlm_service.py`
4. **New Endpoints**: Add routes to `api/routes.py`

### Testing

```bash
# Run tests with uv
uv run pytest

# Test with mock data
uv run python -m pytest tests/ -v

# Integration tests
docker-compose -f docker-compose.test.yml up
```

## Troubleshooting

### Common Issues

**MQTT Connection Failed**
- Verify broker hostname and TLS configuration
- Check certificate paths and permissions
- Ensure network connectivity to broker

**VLM Analysis Not Triggering**
- Check traffic density against threshold
- Verify VLM service connectivity
- Review analysis timing configuration

**Weather Data Unavailable**
- Confirm intersection coordinates are valid
- Check National Weather Service API accessibility
- Verify user agent configuration

**Missing Camera Data**
- Verify MQTT topic subscriptions
- Check camera data format
- Review message processing logs

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
uv run python -m traffic_intelligence.main
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Submit a pull request

## Support

For issues and questions:
- Review logs with debug level enabled
- Check service status endpoints
- Verify configuration parameters
- Consult API documentation
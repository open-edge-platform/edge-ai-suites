# RSU Monitoring System

A real-time web dashboard for monitoring Road Side Unit (RSU) traffic and environmental data using Gradio.

## Features

- **Real-time Dashboard**: Live monitoring of traffic density, environmental conditions, and system alerts
- **Auto-refresh**: Configurable automatic data refresh (default: 5 seconds)
- **Modern UI**: Dark theme with responsive design inspired by professional monitoring systems
- **Modular Architecture**: Clean separation of concerns with dedicated modules for data, UI, and configuration
- **Environmental Configuration**: All settings configurable via environment variables

## Quick Start

### Using UV (Recommended)

```bash
# Clone and navigate to the project
cd /path/to/agent_ui

# Run the startup script (creates venv, installs dependencies, and starts the app)
chmod +x start.sh
./start.sh
```

### Manual Setup

```bash
# Create virtual environment with uv
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Run the application
python app.py
```

## Configuration

Configure the system using environment variables or by editing `config.py`:

```bash
# Data refresh interval (seconds)
export REFRESH_INTERVAL=5

# API endpoint configuration
export API_URL="http://localhost:8081/api/v1/traffic/current"

# UI settings
export UI_THEME="dark"  # or "light"
export APP_TITLE="RSU MONITORING SYSTEM"

# Alert thresholds
export HIGH_DENSITY_THRESHOLD=5
export MODERATE_DENSITY_THRESHOLD=3
export HIGH_WIND_THRESHOLD=25.0
export HEAVY_RAIN_THRESHOLD=5.0
```

## Application Structure

```
agent_ui/
├── app.py                 # Main Gradio application
├── config.py             # Configuration management
├── models.py             # Data models and classes
├── data_loader.py        # Data loading and parsing
├── ui_components.py      # UI component generators
├── auto_refresh.py       # Auto-refresh functionality
├── requirements.txt     # Python dependencies
├── start.sh            # Startup script
└── README.md           # This file
```

## Data Source

The system fetches data from the Traffic Intelligence API endpoint. The API returns data in this structure:

```json
{
  "timestamp": "2025-09-15T20:30:45Z",
  "intersection_id": "INT_001",
  "data": {
    "intersection_name": "Highway South & Pedestrian Crossing",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "northbound_density": 3,
    "southbound_density": 2,
    "eastbound_density": 1,
    "westbound_density": 0,
    "total_density": 6
  },
  "camera_images": {
    "CAM_1": {
      "camera_id": "INTERSECTION_NORTH",
      "direction": "North",
      "timestamp": "2025-09-15T20:30:45Z"
    }
  },
  "vlm_analysis": {
    "analysis": "Traffic flow optimized. Pedestrian activity normal.",
    "alerts": ["URGENT: UNIDENTIFIED OBJECT DETECTED NEAR CAM 4"]
  },
  "weather_data": {
    "temperature_fahrenheit": 28,
    "humidity_percent": 55,
    "precipitation_prob": 0.0,
    "wind_speed_mph": 12.0,
    "wind_direction_degrees": 180,
    "conditions": "Clear Sky"
  }
}
```

## Auto-Refresh

The dashboard automatically refreshes every X seconds (configurable). Features include:

- **Visual Indicator**: Green dot showing auto-refresh is active
- **Manual Refresh**: Backup refresh button
- **Error Handling**: Graceful handling of data loading errors
- **Background Processing**: Non-blocking refresh mechanism

## UI Components

### Traffic Summary
- Real-time traffic density by direction (North, South, East, West)
- Total vehicle count
- Active camera information

### Environmental Panel
- Temperature, humidity, wind speed and direction
- Precipitation levels
- Air quality assessment based on conditions

### Alerts & Analysis
- VLM (Vision Language Model) analysis results
- System alerts with severity levels (Urgent, Advisory, Info)
- Analysis confidence and age indicators

### System Information
- Last update timestamp
- Intersection location and ID
- System status indicators

## Dependencies

- **gradio**: Web UI framework
- **pydantic**: Data validation and models
- **python-dateutil**: Date/time handling

## Development

To extend the system:

1. **Add new data fields**: Update `models.py` with new data classes
2. **Modify UI**: Update `ui_components.py` component generators
3. **Change data source**: Modify `data_loader.py` for different data formats
4. **Adjust configuration**: Add new settings to `config.py`

## Troubleshooting

### Common Issues

1. **Port already in use**: Change `APP_PORT` in configuration
2. **API connection failed**: Ensure the Traffic Intelligence API is running at the configured endpoint
3. **Import errors**: Make sure virtual environment is activated and dependencies are installed

### Logs

The application provides detailed logging. Check console output for:
- Data loading errors
- Configuration issues
- Network problems

## License

This project is part of the RSU monitoring system implementation.
# API Reference

The Live Video Alert Agent application exposes several REST and SSE endpoints for management and data consumption.

## Dashboard Endpoints

### `GET /`
Serves the main monitoring dashboard HTML interface.
- **Response**: HTML page
- **Status Codes**: 
  - `200`: Success

### `GET /events` (SSE)
Server-Sent Events stream for real-time analysis results.
- **Response Type**: `text/event-stream`
- **Events**: 
  - `init`: Initial connection with current streams and results
  - `analysis`: Real-time analysis updates per stream
  - `keepalive`: Heartbeat every 15 seconds
- **Example Event**:
  ```json
  {
    "event": "analysis",
    "data": {
      "stream_id": "default",
      "results": {
        "person": {"answer": "YES", "reason": "One person visible in frame"}
      }
    }
  }
  ```

### `GET /video_feed`
MJPEG video stream for real-time frame preview.
- **Query Parameters**: 
  - `stream_id` (string, optional): Stream identifier (default: `default`)
- **Response Type**: `multipart/x-mixed-replace`
- **Status Codes**: 
  - `200`: Stream active

## Configuration Endpoints

### `GET /config/agents`
Returns the current list of alert agents.
- **Response**: Array of agent configurations
- **Example**:
  ```json
  [
    {
      "name": "person",
      "prompt": "Is there a person?",
      "enabled": true
    }
  ]
  ```

### `POST /config/agents`
Updates the list of alert agents (maximum 4 agents).
- **Request Body**: Array of agent objects
  ```json
  [
    {
      "name": "person",
      "prompt": "Is there a person?",
      "enabled": true
    },
    {
      "name": "fire",
      "prompt": "Is there fire or smoke?",
      "enabled": true
    }
  ]
  ```
- **Response**: 
  ```json
  {"status": "saved", "count": 2}
  ```
- **Status Codes**:
  - `200`: Configuration saved successfully
  - `400`: Invalid request (e.g., more than 4 agents)
  - `503`: Service not initialized

## Stream Management

### `GET /streams`
Returns a list of active stream identifiers.
- **Response**: 
  ```json
  {"streams": ["default", "lobby-cam"]}
  ```

### `POST /streams`
Registers a new video stream.
- **Request Body**: 
  ```json
  {
    "id": "lobby-cam",
    "url": "rtsp://<camera-ip>:554/stream"
  }
  ```
- **Response**: 
  ```json
  {"status": "added", "id": "lobby-cam"}
  ```
- **Status Codes**:
  - `200`: Stream added successfully
  - `400`: Missing id or url
  - `503`: Service not initialized

### `DELETE /streams/{stream_id}`
Removes an active stream.
- **Path Parameters**: 
  - `stream_id` (string): Stream identifier
- **Response**: 
  ```json
  {"status": "removed", "id": "lobby-cam"}
  ```
- **Status Codes**:
  - `200`: Stream removed successfully
  - `503`: Service not initialized

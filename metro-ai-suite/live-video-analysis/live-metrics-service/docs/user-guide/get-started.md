# Get Started

This guide will help you quickly get the Metrics Service up and running.

## Using Docker Compose

### Step 1: Navigate to the Directory

Clone and navigate to the live-metrics-service directory:

```bash
cd live-metrics-service
```

### Step 2: Start the Service with Collector

Copy the example environment file and customize as needed:

```bash
cp .env.example .env
```

Edit `.env` to configure:
- `METRICS_PORT` - Service port (default: 9090)
- `LOG_LEVEL` - Logging verbosity (default: INFO)
- `CORS_ORIGINS` - CORS allowed origins (default: *)

**Option A: Pull from registry (recommended)**

```bash
export REGISTRY="intel/"
export TAG="1.0.0-rc.0"
docker compose up
```

**Option B: Build locally**

```bash
docker compose up --build
```

### Step 3: Verify the Service is Running

```bash
curl http://localhost:9090/health
# Response: {"status": "healthy"}
```

### Step 4: Connect a Client

Open a WebSocket connection to `ws://localhost:9090/ws/clients`

## Integration Examples

### Testing WebSocket with curl

You can test WebSocket connections using curl with the upgrade headers:

> Note: Change the key-value to a random 16-byte value encoded in Base64

**Test the clients endpoint:**

```bash
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Host: localhost:9090" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: <key-value>" \
  http://localhost:9090/ws/clients
```

### JavaScript/TypeScript Client

```javascript
class MetricsClient {
  constructor(url = 'ws://localhost:9090/ws/clients') {
    this.url = url;
    this.ws = null;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 10;
    this.reconnectDelay = 3000;
  }

  connect() {
    this.ws = new WebSocket(this.url);

    this.ws.onopen = () => {
      console.log('Connected to metrics service');
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      this.handleMetrics(data.metrics);
    };

    this.ws.onclose = () => {
      console.log('Disconnected from metrics service');
      this.attemptReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  }

  handleMetrics(metrics) {
    metrics.forEach(metric => {
      switch (metric.name) {
        case 'cpu':
          console.log(`CPU: ${metric.fields.usage_user}%`);
          break;
        case 'mem':
          console.log(`Memory: ${metric.fields.used_percent}%`);
          break;
        // Handle other metrics...
      }
    });
  }

  attemptReconnect() {
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      setTimeout(() => this.connect(), this.reconnectDelay);
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
    }
  }
}

// Usage
const client = new MetricsClient();
client.connect();
```

### Python Client

```python
import asyncio
import json
import websockets

async def metrics_client():
    uri = "ws://localhost:9090/ws/clients"
    
    async with websockets.connect(uri) as websocket:
        print("Connected to metrics service")
        
        async for message in websocket:
            data = json.loads(message)
            for metric in data.get("metrics", []):
                name = metric.get("name")
                fields = metric.get("fields", {})
                
                if name == "cpu":
                    print(f"CPU: {fields.get('usage_user', 0):.1f}%")
                elif name == "mem":
                    print(f"Memory: {fields.get('used_percent', 0):.1f}%")

# Run the client
asyncio.run(metrics_client())
```

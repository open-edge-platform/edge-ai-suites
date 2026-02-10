# Known Issues and Troubleshooting

## Common Issues

### Collector Cannot Connect

**Symptom:** Collector shows connection errors or immediately disconnects.

**Solutions:**
1. Check if another collector is already connected (only one allowed)
2. Verify the WebSocket URL is correct: `ws://live-metrics-service:9090/ws/collector`
3. Check network connectivity between containers
4. Review logs: `docker logs live-metrics-service`

### Clients Not Receiving Metrics

**Symptom:** Client connects but receives no data.

**Solutions:**
1. Verify collector is connected: `curl http://localhost:9090/api/metrics/status`
2. Check if Telegraf is actually sending data
3. Ensure client is connected to `/ws/clients` (not `/ws/collector`)

### High Memory Usage

**Symptom:** Service memory grows over time.

**Solutions:**
1. Check for client connection leaks (clients not properly disconnecting)
2. Monitor client count: `curl http://localhost:9090/api/health`
3. Reduce metric batch size in Telegraf configuration

## Debugging

### Viewing Logs

```bash
# Docker logs
docker logs live-metrics-service

# With follow
docker logs -f live-metrics-service

# Enable debug logging
docker run -e LOG_LEVEL=DEBUG live-metrics-service:latest
```

### Health Check Commands

```bash
# Basic health
curl http://localhost:9090/health

# Detailed status
curl http://localhost:9090/api/health

# Metrics status
curl http://localhost:9090/api/metrics/status
```

## Limitations

### Single Collector Restriction

- Only one collector can connect at a time
- This is by design to ensure data consistency
- If multiple collectors are needed, deploy multiple instances of the service

### WebSocket-Only Protocol

- The service only supports WebSocket connections
- HTTP polling is not supported
- For REST-based metrics, consider using the optional polling feature

### No Data Persistence

- Metrics are not stored or persisted
- The service acts as a real-time relay only
- For historical metrics, implement storage on the client side

## Performance Considerations

### High Client Count

- Each connected client receives all metrics
- For 100+ concurrent clients, consider:
  - Increasing service resources
  - Using multiple service instances with load balancing
  - Implementing client-side filtering

### High Metric Frequency

- Default Telegraf interval is 1 second
- For very high-frequency metrics (< 100ms), consider:
  - Batching metrics on the collector side
  - Reducing the number of metric types collected
  - Using sampling techniques

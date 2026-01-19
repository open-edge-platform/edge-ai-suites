## Troubleshooting

### Stack Not Starting

Check status and logs:

```bash
# View container status
docker ps -a

# Check specific service logs
docker compose -f docker/compose.yaml logs traffic-intelligence
docker compose -f docker/compose.yaml logs vlm-openvino-serving
docker compose -f docker/compose.yaml logs broker

# Restart services
source setup.sh --stop
source setup.sh --run
```

Common issues:
- Missing secrets/certificates in `src/secrets/` directory
- Port conflicts (check ports 8081, 7860, 9764, 443, 1883, 8555)
- Insufficient system resources for VLM service
- Proxy configuration issues

### Traffic Intelligence Service Issues

Check service health:

```bash
# Verify API is responding
curl http://localhost:8081/health

# Check UI accessibility
curl http://localhost:7860/

# View detailed logs
docker logs -f scene-intelligence-traffic-intelligence

# Check container is running
docker ps | grep traffic-intelligence
```

### Service Health Issues

Verify individual service health:

```bash
# Traffic Intelligence
curl http://localhost:8081/health

# VLM Service
curl http://localhost:9764/health

```

### MQTT Connection Issues

Verify MQTT broker connectivity:

```bash
# Check broker is running
docker ps | grep broker

# Verify certificate is mounted
docker exec scene-intelligence-traffic-intelligence ls -la /app/secrets/certs/

# Check network connectivity
docker compose -f docker/compose.yaml exec traffic-intelligence ping broker.scenescape.intel.com
```

### VLM Analysis Not Working

Debug VLM integration:

```bash
# Check VLM service health
curl http://localhost:9764/health

# Verify traffic threshold configuration
curl http://localhost:8081/api/v1/config

# Check camera data availability
docker logs scene-intelligence-traffic-intelligence | grep "camera"

# Monitor VLM requests
docker logs scene-intelligence-traffic-intelligence | grep -i vlm
```

### Performance Issues

Monitor resource usage:

```bash
# Check container resource usage
docker stats

# Adjust VLM workers if needed
export VLM_WORKERS=2
docker compose -f docker/compose.yaml up -d vlm-openvino-serving
```

### Configuration Issues

Validate configuration files:

```bash
# Check JSON syntax
cat src/traffic-intelligence/config/traffic_intelligence.json | jq .
cat config/scene_intelligence_config.json | jq .

# Verify mounted configuration
docker compose -f docker/compose.yaml exec traffic-intelligence ls -la /app/config/
```

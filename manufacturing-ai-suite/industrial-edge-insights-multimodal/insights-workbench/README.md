# Insights Workbench - Influx Table Viewer

A lightweight Flask UI that reads data from InfluxDB and shows it in a table with pagination.

## Files

- `app.py`: Flask backend and REST endpoints.
- `templates/index.html`: Simple UI for tabular view and pagination.
- `Dockerfile`: Container image definition.
- `requirements.txt`: Python dependencies.

## Endpoints

- `GET /`: Web UI
- `GET /api/measurements`: List available measurements
- `GET /api/data?measurement=<name>&page=1&page_size=25`: Paginated rows

## Environment Variables

- `INFLUX_HOST` (default: `localhost`)
- `INFLUX_PORT` (default: `8086`)
- `INFLUX_USER` (default: `admin`)
- `INFLUX_PASSWORD` (default: `admin`)
- `INFLUX_DB` (default: `datain`)
- `FUSION_MEASUREMENT` (default: `fusion_result`)

## Run with Docker

```bash
docker build -t insights-workbench .
docker run --rm -p 8080:8080 \
  -e INFLUX_HOST=ia-influxdb \
  -e INFLUX_PORT=8086 \
  -e INFLUX_USER=$INFLUXDB_USERNAME \
  -e INFLUX_PASSWORD=$INFLUXDB_PASSWORD \
  -e INFLUX_DB=datain \
  insights-workbench
```

Open: `http://localhost:8080`

## Optional: Add to parent docker-compose

You can add this service under `services:` in the parent `docker-compose.yml`:

```yaml
  insights-workbench:
    container_name: insights-workbench
    hostname: insights-workbench
    build:
      context: ./insights-workbench
      dockerfile: ./insights-workbench/Dockerfile
    restart: unless-stopped
    environment:
      INFLUX_HOST: ia-influxdb
      INFLUX_PORT: 8086
      INFLUX_USER: ${INFLUXDB_USERNAME}
      INFLUX_PASSWORD: ${INFLUXDB_PASSWORD}
      INFLUX_DB: datain
    ports:
      - "8088:8080"
    networks:
      - timeseries_network
    depends_on:
      - ia-influxdb
```

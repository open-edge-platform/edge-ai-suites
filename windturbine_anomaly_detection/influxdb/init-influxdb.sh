#!/bin/bash

# Wait for InfluxDB to start
INFLUX_URL="http://localhost:8086"
until curl -s  "$INFLUX_URL/ping"; do
    echo "Waiting for InfluxDB to start..."
    sleep 1
done

echo "Adding retention policy"
curl -i -XPOST "$INFLUX_URL/query" \
    -u "$INFLUXDB_ADMIN_USER:$INFLUXDB_ADMIN_PASSWORD" \
    --data-urlencode "q=ALTER RETENTION POLICY autogen ON $INFLUXDB_DB DURATION $RETENTION_DURATION REPLICATION 1 SHARD DURATION 1h DEFAULT"

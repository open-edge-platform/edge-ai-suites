# Analytics Pipeline (Downstream)

Raw metadata is valuable, but actionable insights come from the Analytics Pipeline.

## Node-RED Transformation

- **Input:** The **MQTT IN Node** subscribes to `scenescape/event/region/+/+/objects`.
- **Logic:** The **Function node** aggregates counts per region and calculates **Dwell Time** (congestion).
- **Output:** The **InfluxDB OUT Node** writes normalized data points to InfluxDB.

![Node-RED Flow](../_assets/smart_tolling_nodered.png)

### Storage (InfluxDB)

InfluxDB acts as a single source of truth. All critical and shared data is
stored in one location, ensuring every user and system accesses the same,
accurate and consistent information.

![InfluxDB Dashboard 1](../_assets/smart_tolling_influx_db.png)

### Visualization (Grafana)

The system ships with a pre-configured dashboard (`anthem-intersection.json` schema)
focusing on Traffic Volume, Flow Efficiency and Safety Alerts.

![Grafana Dashboard 1](../_assets/garfana_Dashboard1.png)

## Learn More

- [Perception Layer](./perception-layer.md)
- [Optimizations](./optimization.md)
- [Support and Troubleshooting](../troubleshooting.md)
<!--
Copyright (C) 2026 Intel Corporation

SPDX-License-Identifier: Apache-2.0

These contents may have been developed with support from one or more
Intel-operated generative artificial intelligence solutions.
-->
# ROS2 KPI Grafana Dashboard Setup

## 🎯 Overview

This integration provides real-time visualization of ROS2 metrics using **Grafana** dashboards powered by **Prometheus**. Monitor topic frequencies, processing delays, CPU/memory usage, and more with beautiful, interactive graphs.

## 📊 Features

- **Real-time Metrics Visualization**
  - Topic message frequencies and rates
  - Processing delays and latencies
  - Inter-message timing (jitter analysis)
  - CPU usage per process/thread
  - Memory consumption
  - I/O throughput (read/write)

- **Pre-configured Dashboard**
  - Multiple visualization panels
  - Auto-refreshing (5s intervals)
  - Historical data tracking
  - Interactive filtering and zooming

- **Easy Deployment**
  - Docker Compose setup
  - Automatic Grafana provisioning
  - No manual configuration needed

---

## 🚀 Quick Start

### Prerequisites

```bash
# Install Docker and Docker Compose
sudo apt-get update
sudo apt-get install -y docker.io docker-compose

# Add your user to docker group (logout/login required)
sudo usermod -aG docker $USER

# Install Python dependencies
uv sync
```

### Start the Dashboard Stack

```bash
# From the ros2-kpi directory
./start_grafana.sh
```

This will:
1. Start Prometheus (metrics database) on port 9090
2. Start Grafana (visualization) on port 30000
3. Configure Prometheus to scrape ROS2 metrics on port **9092**

> **Why port 9092?** Prometheus runs in host-network mode and binds port 9090 itself. The ROS2 KPI exporter uses port 9092 to avoid the conflict.

### Start Monitoring with Prometheus Export

Open two terminals:

**Terminal 1 - Run your ROS2 monitoring and export:**
```bash
# Monitor for 2 minutes and save a session
make monitor DURATION=120

# Then export that session to Prometheus (replace timestamp with session name printed above)
make grafana-export SESSION=20260306_154140

# Metrics served at http://localhost:9092/metrics
```

**Or keep the exporter always running in live mode:**
```bash
make grafana-export-live
```

### Access Grafana

1. Open browser: http://localhost:30000
2. Login:
   - Username: `admin`
   - Password: `admin`
3. Dashboard will load automatically: **ROS2 KPI Dashboard**

---

## 📈 Dashboard Panels

### 1. Topic Message Frequencies
Line chart showing message rates (Hz) for all topics over time.
- Color-coded by topic
- Separate lines for input/output
- Shows mean, last, and max values

### 2. Processing Delays
Monitor input→output processing delays in milliseconds.
- Threshold indicators (green/yellow/red)
- Identify bottlenecks and slow processing

### 3. Inter-Message Timing (Jitter)
Track timing consistency between messages.
- Detect irregular message patterns
- Identify network or processing issues

### 4. CPU Usage
Real-time CPU usage by process and thread.
- Gauge visualization with color thresholds
- Per-thread breakdown for detailed analysis

### 5. Memory Usage
Stacked area chart of memory consumption.
- Track memory leaks
- Compare resource usage across processes

### 6. I/O Throughput
Bidirectional I/O visualization (read/write).
- Read rates shown above baseline
- Write rates shown below baseline

### 7. Topic Statistics Table
Sortable table with current topic stats.
- Click column headers to sort
- Quick overview of all active topics

### 8. Node Activity Distribution
Pie chart showing message frequency by node.
- Visual breakdown of system activity

### 9. Node Latency Distribution
Pie chart showing average latency per node.
- Color-coded (green=fast, red=slow)
- Identify performance hotspots

### 10. Node Detail — `$node`
Two table panels showing per-topic detail for a selected node.
- Use the **Node** variable dropdown (top of dashboard) to select any node
- **Publishes** table: topic, frequency (Hz), latency (ms), message count
- **Subscribes** table: same layout for input topics
- Latency cells are color-coded: green < 20 ms, yellow < 100 ms, red ≥ 100 ms
- Powered by `ros2_node_topic_frequency_hz`, `ros2_node_topic_latency_ms`, `ros2_node_topic_msg_count` metrics

---

## 🔧 Configuration

### Custom Prometheus Port

The exporter defaults to **port 9092** (port 9090 is reserved by Prometheus in host-network mode).

To use a different port:
```bash
uv run python src/prometheus_exporter.py --port 9095 --session-dir monitoring_sessions/latest
```

Then update `prometheus/prometheus.yml`:
```yaml
scrape_configs:
  - job_name: 'ros2-kpi'
    static_configs:
      - targets: ['localhost:9095']  # Match your chosen port
```

Restart Prometheus: `docker restart ros2-prometheus`

### Change Update Interval

**For Prometheus:**
Edit `prometheus/prometheus.yml`:
```yaml
global:
  scrape_interval: 10s  # Change from 5s to 10s
```

**For Exporter:**
```bash
./src/prometheus_exporter.py --interval 10
```

**For Grafana Dashboard:**
In Grafana UI, click the refresh dropdown (top-right) and select desired interval.

### Add Custom Metrics

Edit `src/prometheus_exporter.py` and add new Gauge/Counter metrics:

```python
self.my_custom_metric = Gauge(
    'ros2_custom_metric_name',
    'Description of metric',
    ['label1', 'label2']
)

# Update in your collection loop
self.my_custom_metric.labels(label1='value1', label2='value2').set(123.45)
```

---

## 🔍 Monitoring Modes

### Mode 1: File-Based (Current Implementation)

The exporter reads from CSV/log files generated by `monitor_stack.py`.

```bash
# Terminal 1: Start monitoring and save to session
uv run python src/monitor_stack.py --session grafana_demo

# Terminal 2: Start exporter reading from session files
uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/grafana_demo
```

**Pros:**
- Works with existing monitoring scripts
- No code changes needed
- Can replay historical sessions

**Cons:**
- Slight delay (file I/O overhead)
- Requires both processes running

### Mode 2: Live Integration (Future Enhancement)

Direct metric export from `monitor_stack.py` without intermediate files.

```bash
# Start exporter in live mode
uv run python src/prometheus_exporter.py --mode live

# Start monitoring with --prometheus flag (requires implementation)
uv run python src/monitor_stack.py --prometheus
```

This requires updating `monitor_stack.py` to call the exporter directly (see TODO).

---

## 📦 Docker Stack Management

### Start Services
```bash
docker-compose up -d
```

### Stop Services
```bash
docker-compose down
```

### Stop and Remove Data
```bash
docker-compose down -v  # Removes volume data
```

### View Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f prometheus
docker-compose logs -f grafana
```

### Restart Services
```bash
docker-compose restart
```

---

## 🛠️ Troubleshooting

### Grafana shows "No Data"

**Check 1: Is Prometheus scraping metrics?**
```bash
# Visit Prometheus UI
firefox http://localhost:9090/targets

# Should show 'ros2-kpi' target as UP (green)
```

**Check 2: Is exporter running?**
```bash
# Check if metrics are exposed
curl http://localhost:9092/metrics | grep ros2_

# Should show ros2_* metrics
```

**Check 3: Is monitoring collecting data?**
```bash
# Check if session files have data
cat monitoring_sessions/latest/graph_timing.csv
```

### Prometheus target shows DOWN

**Issue:** Exporter not running or wrong port.

**Fix:**
```bash
# Verify exporter is running
ps aux | grep prometheus_exporter

# Check correct port
netstat -tulpn | grep 9092

# Restart exporter
uv run python src/prometheus_exporter.py --port 9092 --session-dir monitoring_sessions/latest
```

### Dashboard panels are empty

**Issue:** Metric names don't match queries.

**Fix:**
1. Check available metrics:
   ```bash
   curl http://localhost:9090/api/v1/label/__name__/values | grep ros2
   ```

2. Edit dashboard queries to match available metrics:
   - Grafana → Dashboard → Panel → Edit Query

### Port conflicts

**Expected layout:**
- Port 9090: Prometheus server (host-network mode)
- Port 9092: ROS2 KPI exporter (default)
- Port 30000: Grafana

**Exporter port already in use:**
```bash
# Free port 9092 and retry
fuser -k 9092/tcp && make grafana-export SESSION=<name>
```

**Change Grafana or Prometheus UI port in `docker-compose.yml`:**
```yaml
services:
  grafana:
    ports:
      - "30001:30000"  # Grafana on 30001
```
Then restart: `docker-compose down && docker-compose up -d`

### Permission denied on Docker

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Logout and login, or run:
newgrp docker
```

---

## 📊 Advanced Usage

### Create Custom Dashboards

1. In Grafana, click **+** → **Dashboard**
2. Add Panel → Select visualization type
3. Configure query:
   ```promql
   # Example: Average processing delay
   avg(ros2_processing_delay_ms)

   # Example: Max CPU usage by process
   max(ros2_process_cpu_percent) by (process)

   # Example: Total messages across all topics
   sum(rate(ros2_topic_message_count[1m]))
   ```
4. Save dashboard

### Export Dashboard

```bash
# Save dashboard JSON from Grafana UI
# Dashboard → Settings → JSON Model → Copy

# Or export via API
curl -H "Content-Type: application/json" \
  http://admin:admin@localhost:30000/api/dashboards/uid/ros2-kpi-dashboard \
  > my_dashboard.json
```

### Alert Rules

Configure alerts in Grafana:

1. Edit panel → Alert tab
2. Set conditions (e.g., `processing_delay > 100ms`)
3. Configure notification channels (Slack, email, etc.)

### Historical Analysis

Prometheus stores data in time-series database:

```promql
# Query historical data (24h ago)
ros2_topic_frequency_hz offset 24h

# Rate of change
rate(ros2_topic_message_count[5m])

# Predict future values
predict_linear(ros2_process_memory_mb[1h], 3600)
```

---

## 🎨 Dashboard Customization

### Change Theme

Grafana → Configuration → Preferences → UI Theme → Dark/Light

### Modify Time Range

Top-right time picker:
- Last 5 minutes
- Last 30 minutes
- Last 1 hour
- Custom range

### Add Variables

Create dashboard variables for filtering:

1. Dashboard Settings → Variables → Add variable
2. Example: Create `$node` variable
3. Query: `label_values(ros2_topic_frequency_hz, node)`
4. Use in panel queries: `ros2_topic_frequency_hz{node="$node"}`

---

## 🔗 Integration with Existing Tools

### Use with ROS Bags

```bash
# Play a bag and monitor
ros2 bag play my_bag.db3 &

# Start monitoring
uv run python src/monitor_stack.py --session bag_analysis

# Start exporter
uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/bag_analysis
```

### Remote Monitoring

```bash
# Monitor remote ROS2 system
uv run python src/monitor_stack.py --remote-ip 192.168.1.100 --session remote_robot

# Export metrics locally
uv run python src/prometheus_exporter.py --session-dir monitoring_sessions/remote_robot
```

---

## 📚 Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/)

---

## 🤝 Contributing

Improvements welcome:
- Additional dashboard panels
- Alert rule templates
- Better metric aggregations
- Alternative exporters (InfluxDB, Datadog, etc.)

---

## 📝 TODO

- [ ] Direct integration mode (bypass file I/O)
- [ ] Automatic session detection for exporter
- [ ] Multi-session comparison dashboard
- [ ] Alert templates for common issues
- [ ] Grafana Loki integration for logs
- [x] ROS2 node topology visualization (Node Detail `$node` panels added)

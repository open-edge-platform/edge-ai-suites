# Get Started

This guide provides step-by-step procedure to:

- Set up the agent using the automated setup script for quick deployment.
- Run predefined tasks to explore its functionality.
- Learn how to modify configurations to suit specific requirements.

## Prerequisites

Before you begin ensure the following:

- **System Requirements**: Verify that the system meets the
  [minimum requirements](./get-started/system-requirements.md).
- **Docker Installation Complete**: Install Docker, For installation instructions, see
  [Get Docker](https://docs.docker.com/get-docker/).
- **MQTT Explorer**: Ensure access to
  [MQTT explorer](https://mqttexplorer.com/download/) for traffic data streaming and verifying payloads.

> **Note:**
>
> - Make sure the following ports are available
>   - localhost:1880 (for **NodeRED**)
>   - localhost:8086 (for **InfluxDB**)
>   - localhost:3000 (for **Grafana**)

## Setup Guide

### 1. Deploy Source Code

Clone the repository to your Edge Server:

```bash
git clone https://github.com/open-edge-platform/edge-ai-suites.git
```

Go to the directory:

```bash
cd edge-ai-suites/metro-ai-suite/metro-vision-ai-app-recipe/
```

### 2. Configure Environment

Ensure the following specialized adapters are present in `src/dlstreamer-pipeline-server/user_scripts/`:

- `sscape_adapter_lpr.py` (Front/Rear LPR)
- `sscape_adapter_side.py` (Axle Counting)

*Note: Verify variables in `.env` match your camera RTSP endpoints.*

### 3. Create .yml file

Generate the 'docker-compose.yml' file:

```bash
./install.sh smart-tolling
```

The `docker-compose.yml` file mentions all the relative paths in the pipeline which is configured in config.json file.

### 4. Launch Services

Start the application stack using Docker Compose:

```bash
docker compose up
```

**OR** to hide the logs:

```bash
docker compose up -d
```

To **stop** the application:

```bash
docker compose down
```

### 5. Verify Deployment

Check the status of all containers:

```bash
docker compose ps
```

*Expected Output:* Services `dlstreamer-pipeline-server`, `broker`, `web`, `influxdb`, `node-red` and `grafana` should be `Up`.

## Accessing the Application

- **Web UI (Scenescape Configuration):** `https://localhost`
- **Grafana (Dashboard):** `http://localhost:3000` (Default Login: `admin`/`admin`)

### User Interface

Open a browser and go to the following endpoints to access the application.

> **Note:**
>
> - For passwords stored in files (e.g., `supass` or `influxdb2-admin-token`), refer to the respective secret files in your deployment under ./src/secrets (Docker) or chart/files/secrets (Helm).
> - Since the application uses HTTPS with self-signed certificates, your browser may display a certificate warning. For the best experience, use **Google Chrome** and accept the certificate.

- **URL**: [https://localhost](https://localhost)
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: Stored in `supass`. (Check `./smart-intersection/src/secrets/supass`)

> **Note:**
>
> - After starting the application, wait approximately 1 minute for the MQTT broker to initialize. You can confirm it is ready when green arrows appear for MQTT in the application interface . Since the application uses HTTPS, your browser may display a self-signed certificate warning. For the best experience, use **Google Chrome**.

### MQTT Explorer

Login with the following credentials:

- **Protocol**: `mqtt://`
- **Host**: `localhost`
- **Port**: `1883`

> **Note:**
>
> - Make sure to disable "Validate Certificate" and enable "Encryption(tls)".

### NodeRED UI

- **URL**: [http://localhost:1880](http://localhost:1880)

### InfluxDB UI

- **URL**: [http://localhost:8086](http://localhost:8086)
- **Log in with credentials**:

  - **Username**: `<your_influx_username>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-username`)
  - **Password**: `<your_influx_password>` (Check `./smart-intersection/src/secrets/influxdb2/influxdb2-admin-password`)

### Grafana UI

- **URL**: [http://localhost:3000](http://localhost:3000)
- **Log in with credentials**:
  - **Username**: `admin`
  - **Password**: (You will be prompted to change it on first login)

<!--hide_directive
:::{toctree}
:hidden:

./get-started/system-requirements
Server File Download Checklist <./get-started/server-files-checklist>

:::
hide_directive-->

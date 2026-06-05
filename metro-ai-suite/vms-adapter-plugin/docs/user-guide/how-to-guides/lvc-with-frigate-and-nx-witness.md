# Tutorial: Live Video Captioning with Nx Witness

This tutorial walks through the complete end-to-end setup of Live Video Captioning (LVC) as a Analytics App in the VMS Adapter Plugin. Camera streams can come from **Nx Witness** (VMS REST API) or a combination of multiple VMS installations.

At the end of this tutorial you will have:

- LVC running and accessible from VAP
- Cameras discovered from Nx Witness or all installed VMS.
- A captioning pipeline running against a live camera RTSP stream
- AI captions displayed over a WebRTC video feed in the VAP provider dashboard

Note: Frigate is used as a proxy for an open-source VMS with limited functionality support.

## Prerequisites

- A host machine running Ubuntu 22.04 or 24.04 with Docker and Docker Compose installed.
- The `edge-ai-suites` repository cloned:

  ```bash
  git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
  cd edge-ai-suites
  git sparse-checkout set metro-ai-suite
  ```

- At least one IP camera with an accessible RTSP stream.
- Choose your VMS source: **Nx Witness**, **Frigate**, or both.

---

## Architecture Overview

```
Camera (RTSP)
  │
  ├── Nx Witness VMS (REST API v4)
  │       VAP queries /rest/v4/devices for camera list
  │
  └── Frigate VMS (local config.yml)
          VAP reads config directly, no API needed

          ↓ camera_id resolved to RTSP URL ↓

VMS Adapter Plugin (VAP)
  ┌─────────────────────────────────────────────────────┐
  │  LiveCaptioningAnalyticsAppShim                     │
  │  POST /api/runs  ──────────────────────────────────►│ LVC Backend (:4173)
  │                                                     │ DLStreamer + VLM
  │  GET .../results/stream  ◄──────────────────────────│ SSE captions
  │  (SSE proxy to dashboard)                           │
  │            MediaMTX (:8889)                         |
  └─────────────────────────────────────────────────────┘
           │
  ┌────────▼─────────────────────┐
  │  Provider Dashboard (:3100)  │
  │  WebRTC player + captions    │
  └──────────────────────────────┘
```

**Key data flows:**

1. VAP discovers cameras from Nx Witness (queries REST API) or Frigate (reads `config.yml`).
2. On run start, VAP resolves the selected `camera_id` to an RTSP URL and sends `POST /api/runs` to the LVC backend.
3. LVC processes the stream with DLStreamer + VLM and emits captions as an SSE stream.
4. VAP proxies the SSE stream to the dashboard at `/v1/analytics-apps/live_captioning/results/stream`.
5. The WebRTC video feed is served by MediaMTX (in the LVC stack), proxied by nginx at `/whep/`.

---

## Part 1 — Set Up Live Video Captioning

LVC must be running before VAP starts. VAP fetches the LVC OpenAPI schema at startup to build the dynamic analytics form.

### 1.1 Install and Start LVC

```bash
cd metro-ai-suite/live-video-analysis/live-video-captioning
```

Follow the [LVC Get Started guide](../../live-video-analysis/live-video-captioning/docs/user-guide/get-started.md) to download models and configure its `.env`, then start the stack:

```bash
docker compose up -d
```

### 1.2 Verify LVC Is Running

```bash
curl http://localhost:4173/health
```

Expected: `{"status": "ok"}` or similar.

Verify MediaMTX (WebRTC relay) is also up:

```bash
curl http://localhost:8889/
```

LVC exposes two services that VAP depends on:

| **Service** | **Default Port** | **Purpose** |
|---|---|---|
| LVC Backend | `4173` | REST API + SSE caption stream |
| MediaMTX | `8889` | WebRTC signalling (WHEP endpoint for the video player) |

---

## Part 2 — Set Up Camera Sources

Choose one or both options below. VAP discovers from all configured VMS instances simultaneously.

---

### Option A: Nx Witness (VMS REST API)

#### A.1 Download and Install Nx Witness

Download the **Windows x64 Client & Server** installer from the official Nx Witness releases page:

👉 **[https://nxvms.com/download/releases/windows](https://nxvms.com/download/releases/windows)**

Select **Windows x64 — Client & Server** and run the installer. This installs:
- **Nx Witness Server** — the VMS backend that manages cameras and exposes the REST API.
- **Nx Witness Desktop Client** — the GUI for camera management and viewing.

Follow the on-screen installation wizard. After installation:

1. The Nx Witness Server starts automatically as a Windows service.
2. Open the **Nx Witness Desktop Client**.
3. Connect to `localhost` with the admin credentials you set during installation.

Verify the REST API is accessible from the Ubuntu VAP host:

```bash
curl -k -s https://<NX_HOST_IP>:7001/rest/v4/info | python3 -m json.tool | grep '"name"\|"version"'
```

> Replace `<NX_HOST_IP>` with the Windows machine's LAN IP address.

#### A.2 Add Cameras to Nx Witness

In the **Nx Witness Desktop Client**:

1. Right-click the server in the resource tree → **Add Device**.
2. Add cameras by entering their RTSP URLs or using auto-discovery on the local network.
3. Confirm each camera appears in the resource tree with a live video feed.

Note the **Device ID (UUID)** for each camera you plan to use:

- Desktop client: right-click a camera → **Camera Settings** → **Information** tab.
- REST API:
  ```bash
  curl -k -u admin:<password> https://<NX_HOST_IP>:7001/rest/v4/devices \
    | python3 -m json.tool | grep '"id"\|"name"'
  ```

#### A.3 Enable Digest Authentication for RTSP

VAP constructs RTSP URLs in this format and passes them to LVC:

```
rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST_IP>:7001/<device-uuid>?onvif_replay=true
```

For DLStreamer (used internally by LVC) to authenticate against Nx Witness, digest authentication must be enabled:

1. In the Desktop Client, go to **Main Menu** (hamburger icon) → **User Management**.
2. Select the user account that VAP will use (`NX_USERNAME`).
3. Under **Info**, check **Allow insecure (digest) authentication**. Re-enter the password and click **OK**.
4. Click **Apply**.

> **Why this is needed:** GStreamer's `rtspsrc` element uses RTSP digest challenge-response. If Nx Witness only accepts bearer tokens, the pipeline fails with `401 Unauthorized`.

#### A.4 Verify RTSP Access

Test the RTSP URL is reachable from the Ubuntu VAP host:

```bash
gst-launch-1.0 rtspsrc \
  location="rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST_IP>:7001/<device-uuid>?onvif_replay=true" \
  ! fakesink
```

A pipeline that runs for a few seconds without errors confirms connectivity.

---

### Option B: Frigate (Standalone)

Frigate is **not** bundled inside the VAP Docker Compose stack. It must be running separately before you start VAP.

#### B.1 Install and Start Frigate

Follow the [official Frigate installation guide](https://docs.frigate.video/frigate/installation). The quickest way is Docker:

```bash
docker run -d \
  --name frigate \
  --restart=unless-stopped \
  --shm-size=256m \
  -p 5000:5000 \
  -p 8554:8554 \
  -v /path/to/your/frigate/config:/config \
  -v /etc/localtime:/etc/localtime:ro \
  ghcr.io/blakeblackshear/frigate:0.15.1
```

#### B.2 Add Cameras to the Frigate Config
Edit `vms_shim/frigate/config/config.yml` and add each camera to **both** the `cameras:` section and the `go2rtc.streams:` section. VAP discovers cameras by calling Frigate's `GET /api/go2rtc/streams` API — the stream names come from `go2rtc.streams`, not from `cameras.inputs.path`.

```yaml
go2rtc:
  streams:
    front-door:
      - rtsp://user:pass@192.168.1.10:554/stream
    warehouse-cam:
      - rtsp://user:pass@192.168.1.11:554/stream

cameras:
  front-door:
    ffmpeg:
      inputs:
        - path: rtsp://user:pass@192.168.1.10:554/stream
          roles:
            - detect
  warehouse-cam:
    ffmpeg:
      inputs:
        - path: rtsp://user:pass@192.168.1.11:554/stream
          roles:
            - detect
```

- The key under `go2rtc.streams:` (for example, `front-door`) becomes the camera name in the VAP dashboard.
- VAP builds the RTSP URL as `rtsp://<frigate_host>:8554/<stream_name>` (go2rtc port `8554`).
- Both `go2rtc.streams` and `cameras` entries must use the **same key name**.
- Refer to the [Frigate configuration docs](https://docs.frigate.video/configuration/) for the full YAML schema.

#### B.3 Verify Frigate is Running

```bash
curl http://localhost:5000/api/go2rtc/streams
```

You should see a JSON object listing your configured streams. Then set `FRIGATE_HOST` in your `.env` to point VAP at the running Frigate instance (use `host.docker.internal` if Frigate is on the same host as VAP). Continue to [Part 3](#part-3--configure-vap).

---

## Part 3 — Configure VAP

### 3.1 Create the `.env` File

```bash
cd metro-ai-suite/vms-adapter-plugin
cp .env.example .env
```

Edit `.env` based on your camera source:

**Nx Witness only (or Frigate + Nx Witness):**

```bash
# PostgreSQL
PG_PASSWORD=changeme

# LVC
LVC_HOST=host.docker.internal
LVC_BASE_URL=http://host.docker.internal:4173
MEDIAMTX_URL=http://host.docker.internal:8889

# Nx Witness
NX_HOST=<NX_HOST_IP>
NX_USERNAME=admin
NX_PASSWORD=<nx_admin_password>

# VAP ports
BACKEND_PORT=8085
UI_PORT=3100
```

**Frigate only:**

```bash
# PostgreSQL
PG_PASSWORD=changeme

# LVC — address as seen from inside the VAP container
# If LVC is on the same host, use host.docker.internal
LVC_HOST=host.docker.internal
LVC_BASE_URL=http://host.docker.internal:4173

# MediaMTX — used by the WebRTC video player
MEDIAMTX_URL=http://host.docker.internal:8889

# Frigate — use host.docker.internal if Frigate runs on the same host as VAP,
# otherwise use the Frigate host IP or hostname
FRIGATE_HOST=host.docker.internal

# VAP ports
BACKEND_PORT=8085
UI_PORT=3100
```

> Replace `host.docker.internal` with the actual IP address if LVC runs on a different host.

### 3.2 Verify `config/config.yaml`

Open `config/config.yaml` and confirm the sections match your setup.

**LVC Analytics App (always required):**

```yaml
analytics_apps:
  - type: live_captioning
    base_url: "http://${LVC_HOST:-host.docker.internal}:${LVC_PORT:-4173}"
    mediamtx_url: "http://${MEDIAMTX_HOST:-host.docker.internal}:${MEDIAMTX_PORT:-8889}"
```

**Nx Witness VMS instance (if using Nx Witness):**

```yaml
vms_instances:
  - name: nx-main
    vendor: nx_witness
    base_url: "https://${NX_HOST}:7001"
    auth:
      username: "${NX_USERNAME}"
      password: "${NX_PASSWORD}"
      auth_type: digest
```

**Frigate VMS instance (if using Frigate):**

```yaml
vms_instances:
  - name: frigate-main
    vendor: frigate
    base_url: "http://${FRIGATE_HOST}:5000"
    auth:
      auth_type: none
```

> To use both Frigate and Nx Witness, include both entries under `vms_instances`.

---

## Part 4 — Build and Start VAP

### 4.1 Start the Stack

Navigate to the VAP directory and start all services:

```bash
cd metro-ai-suite/vms-adapter-plugin
docker compose up -d --build
```

Check all services are healthy:

```bash
docker compose ps
```

Expected output:

```
NAME              STATUS
vms-backend       Up (healthy)
vms-ui            Up
postgres          Up (healthy)
```

> Frigate runs as a separate service outside this stack. Verify it is up with `docker ps | grep frigate` or `curl http://<FRIGATE_HOST>:5000/api/go2rtc/streams`.

### 4.2 Verify the LVC schema

```bash
curl http://localhost:8085/v1/analytics-apps/live_captioning/schema \
  | python3 -m json.tool | head -20
```

If you see a JSON schema with fields like `prompt`, `model_name`, and `pipeline_name`, LVC integration is working correctly.

Check VAP logs for startup issues:

```bash
docker compose logs vms-backend | grep -i "lvc\|schema\|analytics_app\|error"
```

---

## Part 5 — Discover Cameras and Start a Captioning Run

### 5.1 Open the Provider Dashboard

```
http://localhost:3100
```

### 5.2 Discover Cameras

1. In the **Camera Discovery** panel, click **Discover Cameras**.
2. VAP queries all configured VMS sources and stores results in PostgreSQL.
3. The camera list updates:
   - Nx Witness cameras appear as: `nx:e3e9a385-7fe0-3ba5-5482-a86cde7faf48`
   - Frigate cameras appear as: `frigate:front-door`, `frigate:warehouse-cam`

Alternatively, via the API:

```bash
curl -X POST http://localhost:8085/v1/cameras/discover
```

### 5.3 Enable a Camera

In the **Camera Discovery** panel, click the toggle next to the camera you want to use. Only enabled cameras appear in the analytics form.

Via the API:

```bash
# Nx Witness camera
curl -X POST http://localhost:8085/v1/cameras/enable \
  -H "Content-Type: application/json" \
  -d '{"camera_id": "nx:<device-uuid>", "enabled": true}'

# Frigate camera
curl -X POST http://localhost:8085/v1/cameras/enable \
  -H "Content-Type: application/json" \
  -d '{"camera_id": "frigate:front-door", "enabled": true}'
```

### 5.4 Configure and Start a Captioning Run

1. In the **Analytics Engine** panel, click **Discover Apps**. Select **Live Video Captioning**.

2. Fill in the form:

   | **Field** | **Description** | **Default** |
   |---|---|---|
   | **Camera** | Dropdown of enabled cameras (Frigate or Nx Witness) | — |
   | **Enter Prompt** | Instruction sent to the VLM for each frame | `"Describe what you see in one sentence."` |
   | **Select Model** | VLM model to use (fetched live from LVC) | `OpenGVLab/InternVL2-2B` |
   | **Max New Tokens** | Maximum caption length in tokens | `70` |
   | **Select Pipeline** | DLStreamer pipeline (fetched live from LVC) | — |
   | **Run Name** | Display name for this run | — |
   | **Frame Rate** | Frames per second sent to the VLM | `1` |
   | **Chunk Size** | Frames grouped per inference call | `1` |
   | **Frame Resolution** | Resolution: `default`, `1280×720`, `640×480`, `480×360` | `default` |

3. Example prompts:
   - `"Describe what you see in one sentence."`
   - `"Is there a person in the frame? Answer yes or no."`
   - `"What objects are visible on the warehouse floor?"`

4. Click **Start Run**.

### 5.5 What Happens When You Click Start

1. VAP resolves the selected `camera_id` to an RTSP URL:
   - **Nx Witness camera**: calls `GET /rest/v4/devices` on Nx; RTSP URL is `rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST>:7001/<device-uuid>?onvif_replay=true`.
   - **Frigate camera**: calls `GET /api/go2rtc/streams` on Frigate; RTSP URL is `rtsp://<frigate_host>:8554/<stream_name>`.   
2. Frame Resolution is mapped to `frameWidth`/`frameHeight` if not `default` (for example, `1280×720` → `{frameWidth: 1280, frameHeight: 720}`).
3. VAP sends `POST /api/runs` to the LVC backend with all parameters.
4. LVC's DLStreamer pipeline starts consuming the RTSP stream at the configured frame rate.
5. The VLM generates captions and publishes them to an MQTT broker → LVC SSE stream.
6. VAP proxies the SSE stream at `/v1/analytics-apps/live_captioning/results/stream`.

### 5.6 Verify the Run Is Active

In the **Analytics Engine** panel, the active run appears in the runs list.

Via the API:

```bash
curl http://localhost:8085/v1/analytics-apps/live_captioning/runs | python3 -m json.tool
```

---

## Part 6 — View Live Captions in the Dashboard

### 6.1 Open the Live Stream Tab

After starting a run, open the **Live Stream** tab. It shows:

- **WebRTC video player** — live video from the camera relayed through MediaMTX.
- **Caption overlay** — the most recent AI caption displayed in real time.

Captions appear within a few seconds of the pipeline starting.

### 6.2 Stop the Captioning Run

Click **Stop** next to the active run in the **Analytics Engine** panel.

Or via the API:

```bash
curl -X DELETE http://localhost:8085/v1/analytics-apps/live_captioning/runs/<run_id>
```

---

## Troubleshooting

### Analytics Form Does Not Render

**Symptom:** The Analytics Engine panel shows an error or blank form after clicking **Discover Apps**.

**Cause:** VAP could not reach the LVC backend to fetch the OpenAPI schema at startup.

**Fix:**
1. Verify LVC is running: `curl http://localhost:4173/health`
2. Check connectivity from inside VAP: `docker compose exec vms-backend curl http://host.docker.internal:4173/health`
3. Restart VAP: `docker compose restart vms-backend`

### No Cameras After Discovery

**Symptom:** Clicking **Discover Cameras** returns an empty list.

**Frigate checks:**
1. Confirm Frigate is running: `docker ps | grep frigate`
2. Confirm cameras are defined in your Frigate `config.yml` under both `go2rtc.streams:` and `cameras:`.
3. Verify Frigate streams are reachable: `curl http://<FRIGATE_HOST>:5000/api/go2rtc/streams`
4. Check VAP logs: `docker compose logs vms-backend | grep -i "frigate\|discover"`

**Nx Witness checks:**
1. Verify `NX_HOST`, `NX_USERNAME`, `NX_PASSWORD` are correct in `.env`.
2. Check VAP can reach Nx: `docker compose exec vms-backend curl -k https://<NX_HOST_IP>:7001/rest/v4/info`
3. Check logs: `docker compose logs vms-backend | grep -i "nx\|discover"`

### No Captions Appearing

**Symptom:** Run is active but the caption overlay stays blank.

**Checks:**
1. Verify the SSE stream is emitting data:
   ```bash
   curl -N http://localhost:8085/v1/analytics-apps/live_captioning/results/stream
   ```
   You should see `data: {...}` lines every few seconds.

2. Check the run is active in LVC directly:
   ```bash
   curl http://localhost:4173/api/runs | python3 -m json.tool
   ```

3. Check LVC logs for pipeline errors (from the LVC directory):
   ```bash
   docker compose logs | grep -i "error\|pipeline\|rtsp"
   ```

### WebRTC Video Not Loading

**Symptom:** The Live Stream video player is blank.

**Checks:**
1. Verify MediaMTX is running: `curl http://localhost:8889/`
2. Check `MEDIAMTX_URL` in `.env` is correct.
3. Verify nginx `/whep/` proxy:
   ```bash
   docker compose exec vms-ui cat /etc/nginx/conf.d/default.conf | grep whep
   ```

### Run Start Fails with Nx Witness Camera

**Symptom:** Starting a run with an Nx Witness camera returns an error.

**Checks:**
1. Confirm digest auth is enabled for the Nx Witness user (see [Step B.3](#b3-enable-digest-authentication-for-rtsp)).
2. Test the RTSP URL:
   ```bash
   gst-launch-1.0 rtspsrc \
     location="rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST_IP>:7001/<device-uuid>" \
     ! fakesink
   ```
3. Check VAP logs: `docker compose logs vms-backend | grep -i "error\|start_run\|rtsp"`

---

## Summary

| **Step** | **Where** |
|---|---|
| Install and start LVC + MediaMTX | `metro-ai-suite/live-video-analysis/live-video-captioning/` → `docker compose up -d` |
| **Frigate:** add cameras to `config.yml` | `vms_shim/frigate/config/config.yml` |
| **Nx Witness:** download from [nxvms.com/download/releases/windows](https://nxvms.com/download/releases/windows), install Client & Server, add cameras, enable digest auth | Nx Witness Desktop Client on Windows |
| Set `LVC_BASE_URL`, `MEDIAMTX_URL`, and VMS credentials in `.env` | `metro-ai-suite/vms-adapter-plugin/.env` |
| Configure VMS instance(s) in `config.yaml` | `config/config.yaml` |
| Start VAP | `cd metro-ai-suite/vms-adapter-plugin` → `docker compose up -d --build` |
| Discover cameras | Dashboard → Discover Cameras |
| Enable cameras for analytics | Dashboard → Camera toggle |
| Select Live Video Captioning | Dashboard → Analytics Engine → Discover Apps |
| Enter prompt, model, pipeline and click Start | Dashboard → Analytics Engine → Start Run |
| View live captions on video feed | Dashboard → Live Stream tab |
| Stop the run | Dashboard → Analytics Engine → Stop |

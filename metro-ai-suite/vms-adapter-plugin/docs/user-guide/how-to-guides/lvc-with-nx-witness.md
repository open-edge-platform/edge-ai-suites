# Tutorial: Live Video Captioning with Nx Witness

This tutorial walks through the complete end-to-end setup of Live Video Captioning (LVC) as a Analytics App in the VMS Adapter Plugin. Camera streams come from **Nx Witness** (VMS REST API).

At the end of this tutorial, you will have:

- LVC running and accessible from VAP
- Cameras discovered from Nx Witness.
- A captioning pipeline running against a live camera RTSP stream
- AI captions displayed over a WebRTC video feed in the VAP provider dashboard

## Prerequisites

- A host machine running the Ubuntu OS (version 22.04 or 24.04) with Docker and Docker Compose
  installed.
- The `edge-ai-suites` repository cloned:

  ```bash
  git clone --filter=blob:none --sparse --branch main https://github.com/open-edge-platform/edge-ai-suites.git
  cd edge-ai-suites
  git sparse-checkout set metro-ai-suite
  ```

- At least one IP camera with an accessible RTSP stream.

## Architecture Overview

```text
Camera (RTSP)
  │
  └── Nx Witness VMS (REST API v4)
          VAP queries /rest/v4/devices for camera list

          ↓ camera_id resolved to RTSP URL ↓

VMS Adapter Plugin (VAP)
  ┌─────────────────────────────────────────────────────┐
  │  LiveCaptioningAnalyticsAppShim                     │
  │  POST /api/runs  ──────────────────────────────────►│ LVC Backend (:4173)
  │                                                     │ DL Streamer with VLM
  │  GET .../results/stream  ◄──────────────────────────│ SSE captions
  │  (SSE proxy to dashboard)                           │
  │            MediaMTX (:8889)                         |
  └─────────────────────────────────────────────────────┘
           │
  ┌────────▼─────────────────────┐
  │  Provider Dashboard (:3443)  │
  │  WebRTC player with captions │
  └──────────────────────────────┘
```

**Key data flows:**

1. VAP discovers cameras from Nx Witness (queries REST API).
2. On run start, VAP resolves the selected `camera_id` to an RTSP URL and sends `POST /api/runs`
   to the LVC backend.
3. LVC processes the stream with DL Streamer and a Vision-Language Model (VLM), then emits
   captions as an SSE stream.
4. VAP proxies the SSE stream to the dashboard at `/v1/analytics-apps/live_captioning/results/stream`.
5. MediaMTX (in the LVC stack) serves the WebRTC video feed, and nginx proxies it at `/whep/`.

## Part 1 — Set Up Live Video Captioning

LVC must be running before VAP starts. VAP fetches the LVC OpenAPI schema at startup to build
the dynamic analytics form.

### 1.1 Install and Start LVC

```bash
cd metro-ai-suite/live-video-analysis/live-video-captioning
```

Follow the [LVC Get Started guide](https://docs.openedgeplatform.intel.com/dev/edge-ai-suites/live-video-captioning/get-started.html) to download models and configure its `.env`, then start the stack:

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

| **Service** | **Default Port** | **Purpose**                                            |
| ----------- | ---------------- | ------------------------------------------------------ |
| LVC Backend | `4173`           | REST API + SSE caption stream                          |
| MediaMTX    | `8889`           | WebRTC signalling (WHEP endpoint for the video player) |

## Part 2 — Set Up Nx Witness

### 2.1 Download and Install Nx Witness

Download the **Windows x64 — Client & Server** installer from the official Nx Witness releases page:

- [https://nxvms.com/download/releases/windows](https://nxvms.com/download/releases/windows)

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

> **Note:** Replace `<NX_HOST_IP>` with the Windows machine's LAN IP address.

### 2.2 Add Cameras to Nx Witness

In the **Nx Witness Desktop Client**:

1. Right-click the server in the resource tree → **Add Device**.
2. Add cameras by entering their RTSP URLs or using auto-discovery on the local network.
3. Confirm each camera appears in the resource tree with a live video feed.

Note the **Device ID**, a Universally Unique Identifier (UUID), for each camera you plan to use:

- Desktop client: right-click a camera → **Camera Settings** → **Information** tab.
- REST API:

  ```bash
  curl -k -u admin:<password> https://<NX_HOST_IP>:7001/rest/v4/devices \
    | python3 -m json.tool | grep '"id"\|"name"'
  ```

### 2.3 Enable Digest Authentication for RTSP

VAP constructs RTSP URLs in this format and passes them to LVC:

```
rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST_IP>:7001/<device-uuid>?onvif_replay=true
```

For DL Streamer (used internally by LVC) to authenticate against Nx Witness, digest
authentication must be enabled:

1. In the Nx Witness desktop client, go to **Main Menu** (hamburger icon) → **User Management**.
2. Select the user account that VAP will use (`NX_USERNAME`).
3. Under **Info**, check **Allow insecure (digest) authentication**. Re-enter the password and
   click **OK**.
4. Click **Apply**.

> **Why this is needed:** GStreamer's `rtspsrc` element uses RTSP digest challenge-response.
> If Nx Witness only accepts bearer tokens, the pipeline fails with `401 Unauthorized`.

### 2.4 Verify RTSP Access

Test the RTSP URL is reachable from the Ubuntu VAP host:

```bash
gst-launch-1.0 rtspsrc \
  location="rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST_IP>:7001/<device-uuid>?onvif_replay=true" \
  ! fakesink
```

A pipeline that runs for a few seconds without errors confirms the RTSP connection is working.

## Part 3 — Configure VAP

### 3.1 Create the `.env` File

Navigate to the VAP directory:

```bash
cd metro-ai-suite/vms-adapter-plugin
cp .env.example .env
```

Edit `.env` for your Nx Witness setup:

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
UI_HTTPS_PORT=3443
```

> **Note:** Replace `host.docker.internal` with the actual IP address if LVC runs on a different host.

### 3.2 Verify `config/config.yaml`

Open `config/config.yaml`, and confirm the following sections match your setup. The file
uses `${ENV_VAR}` placeholders resolved from `.env` at startup.

**LVC Analytics App (always required):**

```yaml
analytics_apps:
  - type: live_captioning
    display_name: "Live Video Captioning"
    base_url: "http://${LVC_HOST:-host.docker.internal}:${LVC_PORT:-4173}"
    mediamtx_url: "http://${MEDIAMTX_HOST:-host.docker.internal}:${MEDIAMTX_PORT:-8889}"
```

**Nx Witness VMS instance:**

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

### 3.3 Allow API Integrations registration requests

In the Nx Witness desktop client:

1. Go to **Main Menu** → **System Administration**.
2. In the window, click **Integrations**.
3. In the **Manage Integrations** window, go to the **Settings** tab and check *Accept API
   Integrations registration requests* to enable REST-based API integration.
4. Click **OK**

![Accept API Integrations registration requests setting in Nx Witness](../_assets/nx-enable_api_integration.png "accept api integrations registration requests in nx witness")

## Part 4 — Start VAP and verify LVC schema

### 4.1 Build and Start VAP

Go to app directory
```bash
cd metro-ai-suite/vms-adapter-plugin
```

#### 4.1.1 Build from source (Optional):
```bash
docker compose build
```
> **Note:** You can skip this optional step since `docker compose up -d` that is run later in this document automatically pulls the required images.

#### 4.1.2 Start VAP
```bash
docker compose up -d
```

Check that all VAP services are healthy:

```bash
docker compose ps
```

Expected output:

```text
NAME                          STATUS
vms-adapter-backend           Up (healthy)
vms-adapter-ui                Up
vms-adapter-postgres          Up (healthy)
```

### 4.2 Verify the LVC schema

```bash
curl -k https://localhost:3443/v1/analytics-apps/live_captioning/schema \
  | python3 -m json.tool | head -20
```

If you see a JSON schema with fields like `prompt`, `model_name`, and `pipeline_name`, LVC
integration is working correctly.

Check VAP logs for startup issues:

```bash
docker compose logs vms-adapter-backend | grep -i "lvc\|schema\|analytics_app\|error"
```

## Part 5 — Discover Cameras and Start a Captioning Run

### 5.1 Start a Captioning Run from the Nx Witness Client (Recommended, Nx only)

When using Nx Witness, the recommended way to start and stop an LVC pipeline is directly from
the **Nx Witness camera settings panel**. VAP polls Nx every 5 seconds and reacts to per-camera
settings changes automatically.

#### 5.1.1 Open Camera Settings

1. In the Nx Witness desktop client, close any open camera visualizer window.
2. Navigate to the left panel, and under the server, find the camera you wish to run analytics on and right-click to open context menu.
3. Select **Camera Settings**.
4. Go to the **Integrations** tab.
5. Click **VAP Analytics Integration** to expand the per-camera settings.

You will see a **Live Video Captioning** group with the following fields:

| Field                                     | Type       | Description                                                        |
| ----------------------------------------- | ---------- | ------------------------------------------------------------------ |
| **Enable Live Video Captioning Pipeline** | Checkbox   | Starts or stops the LVC pipeline for this camera                   |
| **Device**                                | Dropdown   | Inference device: `CPU`, `GPU`, or `NPU`                           |
| **Prompt**                                | Text field | Custom prompt sent to the VLM. Leave empty to use the LVC default. |

#### 5.1.2 Enable the Pipeline

1. Optionally enter a **Prompt** (e.g., `"Describe what you see in one sentence."`)
2. Select the **Device** from the dropdown (e.g., `GPU`).
3. Check the **Enable Live Video Captioning Pipeline** checkbox.
4. Click **Apply**, and then **OK**.

VAP detects the change within 5 seconds, and starts the captioning pipeline. Check the VAP logs to confirm:

```bash
docker compose logs -f vms-adapter-backend
```

Expected output:

```text
[info     ] lvc_run_registered             camera_id=nx:<device-uuid> run_id=<run-id>
[info     ] nx_pipeline_started            app_id=live_captioning device_id=<device-uuid> run_id=<run-id>
```

#### 5.1.3 Stop the Pipeline

1. Re-open **Camera Settings → Integrations → VAP Analytics Integration**.
2. Uncheck the **Enable Live Video Captioning Pipeline** checkbox.
3. Click **Apply**, and then **OK**.

Expected log output:

```text
[info] nx_dls_pipeline_stopped        device_id=<device-uuid>  run_id=<hex-instance-id>  success=True
```

> **Note:** To run Live Video Captioning and Loitering Detection simultaneously, see the
> [Run Both Applications Simultaneously](./run-simultaneous-apps.md) guide.

### 5.2 Start a Captioning Run from the VAP Dashboard (Optional)

<!--hide_directive
<details>
<summary>hide_directive-->Click to expand — how to start a captioning run from the provider dashboard
<!--hide_directive</summary>
hide_directive-->

#### Open the Dashboard

Open a browser and navigate to `https://localhost:3443`.

#### Discover Cameras

1. In the **Camera Discovery** panel, click **Discover Cameras**.
2. VAP queries all configured VMS sources and stores results in PostgreSQL.
3. The camera list updates Nx Witness cameras which appear as: `nx:e3e9a385-7fe0-3ba5-5482-a86cde7faf48`

```bash
# Or via API:
curl -k -X POST https://localhost:3443/v1/cameras/discover
```

#### Enable a Camera

In the **Camera Discovery** panel, click the toggle next to the camera you want to use. Only
enabled cameras appear in the analytics form.

```bash
# Or via API:
# Nx Witness camera
curl -k -X POST https://localhost:3443/v1/cameras/enable \
  -H "Content-Type: application/json" \
  -d '{"camera_ids": ["nx:<device-uuid>"], "enabled": true}'
```

#### Configure and start a captioning run

1. In the **Analytics Engine** panel, click **Discover Apps**. Select **Live Video Captioning**.

2. Fill in the configuration form:

   | **Field**            | **Description**                                         | **Default**                                |
   | -------------------- | ------------------------------------------------------- | ------------------------------------------ |
   | **Camera**           | Dropdown of enabled cameras (Nx Witness)                | —                                          |
   | **Enter Prompt**     | Instruction sent to the VLM for each frame              | `"Describe what you see in one sentence."` |
   | **Select Model**     | VLM model to use (fetched live from LVC)                | `OpenGVLab/InternVL2-2B`                   |
   | **Max New Tokens**   | Maximum caption length in tokens                        | `70`                                       |
   | **Select Pipeline**  | DL Streamer pipeline (fetched live from LVC)            | —                                          |
   | **Run Name**         | Display name for this run                               | —                                          |
   | **Frame Rate**       | Frames per second sent to the VLM                       | `1`                                        |
   | **Chunk Size**       | Frames grouped per inference call                       | `1`                                        |
   | **Frame Resolution** | Resolution: `default`, `1280×720`, `640×480`, `480×360` | `default`                                  |

3. Example prompts:
   - `"Describe what you see in one sentence."`
   - `"Is there a person in the frame? Answer yes or no."`
   - `"What objects are visible on the warehouse floor?"`

4. Click **Start Run**.

<!--hide_directive
</details>hide_directive-->

### 5.3 What Happens When You Click Start

1. VAP resolves the selected `camera_id` to an RTSP URL:
   - **Nx Witness camera**: calls `GET /rest/v4/devices` on Nx; RTSP URL is `rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST>:7001/<device-uuid>?onvif_replay=true`.
2. Frame Resolution is mapped to `frameWidth`/`frameHeight` if not `default` (for example, `1280×720` → `{frameWidth: 1280, frameHeight: 720}`).
3. VAP sends `POST /api/runs` to the LVC backend with all parameters.
4. LVC's DL Streamer pipeline starts consuming the RTSP stream at the configured frame rate.
5. The VLM generates captions and publishes them to an MQTT broker → LVC SSE stream.
6. VAP proxies the SSE stream at `/v1/analytics-apps/live_captioning/results/stream`.

### 5.4 Verify the Run Is Active

In the **Analytics Engine** panel, the active run appears in the runs list.

Via the API:

```bash
curl -k https://localhost:3443/v1/analytics-apps/live_captioning/runs | python3 -m json.tool
```

## Part 6 — View Live Captions in Nx Witness

### 6.1 Captions as Nx Bookmarks

When a captioning pipeline is running against an Nx Witness camera, VAP pushes each AI-generated
caption as a **bookmark** on the camera's timeline. No dashboard interaction is needed.

To view captions in the Nx Witness client:

1. Open the **Nx Witness Desktop Client** and connect to your server.
2. Double-click the camera that the pipeline is running on.
3. In the camera panel, open the **Bookmarks** tab (or press **Ctrl+B**).

Each caption appears as a bookmark entry timestamped to when it was generated. The caption text
is the bookmark name:

![Nx Witness Bookmarks tab showing LVC captions as timestamped bookmark entries](../_assets/view_lvc_captions.png "nx witness bookmarks tab showing lvc captions as timestamped bookmark entries")

> **How it works:** VAP's LVC MQTT subscriber receives captions from the LVC backend and calls
> `POST /rest/v4/devices/{deviceId}/bookmarks` on the Nx REST API for each one — up to the first
> 500 characters of the caption text.

### 6.2 Stop the Captioning Run

**Nx Witness (recommended):**

1. Re-open **Camera Settings → Integrations → VAP Analytics Integration**.
2. Uncheck **Enable Live Video Captioning Pipeline**.
3. Click **Apply** then **OK**.

Or, via the API:

**LVC API (alternative):**

```bash
curl -k -X DELETE https://localhost:3443/v1/analytics-apps/live_captioning/runs/<run_id>
```

### 6.3 View Live Captions in the VAP Dashboard (Optional)

<!--hide_directive
<details>
<summary>hide_directive-->Click to expand — how to view captions in the provider dashboard
<!--hide_directive</summary>
hide_directive-->

Open a browser and navigate to `https://localhost:3443`, then open the **Live Stream** tab. It
shows:

- **WebRTC video player** — live video from the camera relayed through MediaMTX.
- **Caption overlay** — the most recent AI caption displayed in real time.

Captions appear within a few seconds of the pipeline starting.

<!--hide_directive
</details>hide_directive-->

## Troubleshooting

### Analytics Form Does Not Render

**Symptom:** The Analytics Engine panel shows an error or blank form after clicking **Discover
Apps**.

**Cause:** VAP could not reach the LVC backend to fetch the OpenAPI schema at startup.

**Fix:**

1. Verify LVC is running: `curl http://localhost:4173/health`
2. Check connectivity from inside VAP: `docker compose exec vms-adapter-backend curl http://host.docker.internal:4173/health`
3. Restart VAP: `docker compose restart vms-adapter-backend`

### No Cameras After Discovery

**Symptom:** Clicking **Discover Cameras** returns an empty list.

**Nx Witness checks:**

1. Verify `NX_HOST`, `NX_USERNAME`, `NX_PASSWORD` are correct in `.env`.
2. Check VAP can reach Nx: `docker compose exec vms-adapter-backend curl -k https://<NX_HOST_IP>:7001/rest/v4/info`
3. Check logs: `docker compose logs vms-adapter-backend | grep -i "nx\|discover"`

### No Captions Appearing

**Symptom:** Run is active but the caption overlay stays blank.

**Checks:**

1. Verify the SSE stream is emitting data:

   ```bash
   curl -k -N https://localhost:3443/v1/analytics-apps/live_captioning/results/stream
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
   docker compose exec vms-adapter-ui cat /etc/nginx/conf.d/default.conf | grep whep
   ```

### Run Start Fails with Nx Witness Camera

**Symptom:** Starting a run with an Nx Witness camera returns an error.

**Checks:**

1. Confirm digest auth is enabled for the Nx Witness user (see [Step 2.3](#23-enable-digest-authentication-for-rtsp)).
2. Test the RTSP URL:

   ```bash
   gst-launch-1.0 rtspsrc \
     location="rtsp://<NX_USERNAME>:<NX_PASSWORD>@<NX_HOST_IP>:7001/<device-uuid>" \
     ! fakesink
   ```

3. Check VAP logs: `docker compose logs vms-adapter-backend | grep -i "error\|start_run\|rtsp"`

## Summary

| **Step** | **Where** |
| -------- | --------- |
| Install and start LVC and MediaMTX | `metro-ai-suite/live-video-analysis/live-video-captioning/` → `docker compose up -d` |
| **Nx Witness:** install Client & Server, add cameras, enable digest auth, enable API Integrations | Nx Witness Desktop Client |
| Set `LVC_BASE_URL`, `MEDIAMTX_URL`, and VMS credentials in `.env` | `metro-ai-suite/vms-adapter-plugin/.env` |
| Configure VMS instance(s) in `config.yaml` | `config/config.yaml` |
| Start VAP | `cd metro-ai-suite/vms-adapter-plugin` → `docker compose up -d --build` |
| Discover cameras | Dashboard → Discover Cameras |
| Enable cameras for analytics | Dashboard → Camera toggle |
| **Nx Witness:** Start pipeline | Camera Settings → Integrations → VAP Analytics Integration → Enable checkbox |
| View live captions | Nx Witness client → camera Bookmarks tab (each caption is a bookmark) |
| **Nx Witness:** Stop the run | Camera Settings → Integrations → VAP Analytics Integration → Uncheck the checkbox |

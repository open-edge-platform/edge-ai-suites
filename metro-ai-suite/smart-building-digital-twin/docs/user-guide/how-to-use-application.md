# How to Use the Application

## Project Structure

```
config/          Model files, and pipeline and tracker configuration
datasets/        Looping video files per scene (Git LFS)
scenes/          Scene zip bundles and sensor event data
scripts/
  narrator.py        Converts MQTT tracks to rolling scene narrative and alerts
  dashboard.py       FastAPI server — SSE streams and web UI
  sensor_replay.py   Replays sensor events (badge, FaceID, and ambient light) in synchronization with video loops
  export-config.sh   Exports object class definitions and scene configurations from the live API
  restore-assets.sh  Restores object class definitions to a fresh Scenescape instance
  static/
    index.html       Three-column analytics dashboard (scene state | narrator feed | event detail)
config/
  object-classes.json   Backed-up object class definitions (person, luggage, and door)
  scenes/               Scene configuration snapshots exported from the API
docker-compose.yml
setup.sh
```

## Analytics Dashboard

After setup, get the analytics dashboard URL from the `.env` file and open
it in a browser.

The application opens a dashboard with three columns:

- **Scene State** (left): live counts of people, bags, doors, and region
  occupancy updated each tick

- **System Telemetry** (left, below Region Occupancy): CPU SKU plus current
  CPU, GPU, memory, and storage usage sampled with each dashboard snapshot

- **Scene Narrator** (center): a rolling 10-minute feed of scene events and
  camera snapshots updated every 10 seconds. You can configure the update
  interval via `SNAPSHOT_INTERVAL` in the `.env` file. Security alerts are
  highlighted in red.

- **Event Detail** (right): expanded view of the selected narrator entry

The Scene State and Scene Narrator feed persist across page reloads through
the browser `localStorage` API.

For `luggage stolen` events, the detail view shows `handoff ...` images
before `alert ...` images so the evidence appears in chronological order.

## Scene Events and Alerts

The narrator (`narrator.py`) subscribes to MQTT track data and produces a rolling 10-minute
text window of scene events. It detects the following alert and warning types:

| Alert | Description |
|---|---|
| No credentials at `Checkpoint` | Person enters an inbound zone without a badge or FaceID |
| Badge switch | An inbound `Checkpoint` or `Entry` crossing shows a badge associated with a different face than the face previously associated with the badge during the loop |
| Possible badge switch | An outbound `Checkpoint` or `Entry` crossing shows a badge associated with a different face than the face previously associated with the badge during the loop |
| Possible fall | Person in a horizontal posture outside a furniture region |
| Luggage abandoned | Owner walks ≥ 4 m away from their luggage while still moving — fires immediately, captures snapshots of both person and bag |
| Unattended luggage | Luggage has had no companion for more than 30 seconds — covers cases where the owner has left the scene entirely |
| Luggage stolen | A single bag's companion changes to a different person; the dashboard captures both handoff-time and alert-time images for evidence |
| Luggage switch | Two bags swap companions coordinately (bag A: person 1 → person 2, bag B: person 2 → person 1) |

## Telemetry

- The analytics container samples CPU, memory, storage, and CPU SKU directly.
- For Panther Lake `xe` GPU telemetry, `./setup.sh` expects host `xpu-smi` to already be installed. It then configures host access, starts the bridge, and keeps writing fresh GPU utilization snapshots to `generated/telemetry/xpu-smi.json`.
- `./setup.sh` is intended to be run interactively when host permissions must be adjusted for `xpu-smi`. In non-interactive mode, the script warns instead of prompting for `sudo`.
- `./cleanup.sh` stops the host telemetry bridge as part of teardown.
- The analytics container reads the bridge JSON from `generated/telemetry/xpu-smi.json` and also has direct fallbacks for CPU, memory, storage, and Intel GPU probes.
- After setup, you can inspect the current host GPU telemetry bridge output in `generated/telemetry/xpu-smi.json`.

## Configuration

Key variables in the `.env` file:

| Variable | Default | Description |
|---|---|---|
| `PUBLIC_HOSTNAME` | Detected from the `hostname` | The hostname used to build the default web and API URLs, and TLS certificate Subject Alternative Names (SANs) |
| `API_BASE_URL` | `https://localhost/api/v1` | Host-local Scenescape API base URL used by the setup and helper scripts; override this when running the helper scripts from another machine |
| `SCENESCAPE_UI_URL` | `https://$PUBLIC_HOSTNAME` | Scenescape web UI URL printed by the setup |
| `DASHBOARD_URL` | `http://$PUBLIC_HOSTNAME:$DASHBOARD_PORT` | Browser URL for the analytics dashboard |
| `SNAPSHOT_INTERVAL` | `10` | Seconds between narrator snapshots |
| `DASHBOARD_PORT` | `7000` | Host port for the analytics dashboard |
| `SCENESCAPE_IMAGE_TAG` | `2026.2.0-rc3` | Scenescape image tag pulled from Docker Hub |
| `MODEL_NAME` | `smartbuilding-int8` | Detection model variant; set to `smartbuilding-fp16` for FP16 |

## Add a New Scene

Follow these steps:

1. Add `scenes/{SceneName}.zip` and `datasets/{scene-name}/cam-*.ts`
2. (Optional) Add `scenes/{SceneName}-sensors.json` for sensor replay. If present,
   the project’s sensor replay process can replay those events in synchronization
   with the scene’s looping camera videos. 
3. Run `./setup.sh`

## Export Configuration

After making changes in the Scenescape UI, for example, editing object classes,
adjusting camera transforms, and updating regions, run the export script to capture
the new state:

```bash
PASSWORD=<admin-password> ./scripts/export-config.sh
```

This writes to the following:

- `config/object-classes.json`
   This file contains the current object-class library, i.e. person, luggage, and door.

- `config/scenes/{Name}.json`
   This file contains the complete configuration for each scene, e.g. cameras, camera
   intrinsics, transforms, and regions.

Commit the updated files to keep the repository in synchronization with the live instance.

## Useful Commands

```bash
docker compose up -d                    # start all services
docker compose down                     # stop all services
docker compose ps                       # check service status
docker compose logs -f analytics        # stream analytics logs
docker compose logs -f scene-narrator   # stream dashboard and narrator logs
./cleanup.sh                            # stop services and remove all generated files and volumes
```

## Copilot Workspace Files

This repository includes shared Copilot customization files to help with cross-system tuning and deployment debugging:

- `.github/copilot-instructions.md` — always-on project guidance for preserving the Scenescape networking model, localhost setup behavior, and tuning workflow
- `.github/skills/tune-other-systems/SKILL.md` — on-demand skill for investigating why another machine behaves differently from the reference system
- `.github/skills/tune-other-systems/assets/system-delta-template.md` — checklist for capturing machine, environment, service, and scene differences before making changes

Use the tuning skill before changing analytics logic on another system. In most cases, the important first comparisons are `.env`, GPU and CPU mode, service health, `config/resolved-uuids.json`, and exported scene and object-class configuration.


## Notice for FFmpeg Project:

FFmpeg is an open source project licensed under LGPL and GPL. See https://www.ffmpeg.org/legal.html. You are solely responsible for determining if your use of FFmpeg requires any additional licenses. Intel is not responsible for obtaining any such licenses, nor liable for any licensing fees due, in connection with your use of FFmpeg.
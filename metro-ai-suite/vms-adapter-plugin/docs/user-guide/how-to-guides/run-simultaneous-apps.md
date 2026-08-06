# Run Both Applications Simultaneously

Both Live Video Captioning and Loitering Detection can run in parallel on the same camera from
the same Nx Witness integration.

## Prerequisite — avoid container name and port conflicts

The Loitering Detection (LD) and Live Video Captioning (LVC) stacks share some service names and
host ports by default. Update the Loitering Detection `docker-compose.yml` file with the
following changes to avoid clashes:

| Service                      | Change                                                             |
| ---------------------------- | ------------------------------------------------------------------ |
| `broker`                     | Host port changed from `1883` to `1884` (`"1884:1883"`)            |
| `dlstreamer-pipeline-server` | Container name changed to `dlstreamer-pipeline-server-ld`          |
| `coturn`                     | Container name changed to `coturn-ld`; host port changed to `3479` |
| `metrics-manager`            | Container name changed to `metrics-manager-ld`                     |

## Run applications simultaneously

1. Start the LVC stack (its broker occupies host port `1883`):

   ```bash
   cd metro-ai-suite/live-video-analysis/live-video-captioning
   docker compose up -d
   ```

2. Start the LD stack (its broker now occupies host port `1884`):

   ```bash
   cd metro-ai-suite/metro-vision-ai-app-recipe
   docker compose up -d
   ```

3. Update `.env` in the VAP directory so the LD MQTT subscriber uses the LD broker on port `1884`:

   ```bash
   # metro-ai-suite/vms-adapter-plugin/.env
   MQTT_PORT=1884
   ```

4. Start VAP (already configured with both apps in `config.yaml`):

   ```bash
   cd metro-ai-suite/vms-adapter-plugin
   docker compose up -d
   ```

5. In the Nx Witness client, open **Camera Settings → Integrations → VAP Analytics
   Integration**. There are two checkboxes: **Live Video Captioning** and **Loitering
   Detection**. Enable the checkboxes for both.

VAP starts both pipelines independently within 5 seconds.

## View results in Nx Witness

Both pipelines run in parallel, but Nx Witness displays only one type of analytics output at a
time:

- **Bookmarks tab** (or press **Ctrl+B**) — shows LVC captions, each pushed as a timestamped bookmark.
- **Object Search** (or press **Alt+O**) — shows Loitering Detection bounding boxes (`vap.pedestrian`,
  `vap.vehicle`, etc.) overlaid on the live feed.

This is an Nx Witness limitation: the client cannot overlay detection boxes and bookmarks
simultaneously in the same camera panel, even though both pipelines produce results
concurrently.

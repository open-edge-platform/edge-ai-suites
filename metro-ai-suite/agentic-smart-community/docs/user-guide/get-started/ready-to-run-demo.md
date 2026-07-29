# Ready-to-Run Demo

This optional guide configures reference video streams and monitors for the bundled Fridge, Child Safety, and Elder Wakeup use cases. It registers only the monitors whose user-provided video streams start successfully.

## Prerequisites

Complete [Get Started](../get-started.md) through **Step 1 - Start dependent services**. The demo also requires `ffmpeg`, `ffprobe`, Python 3, and MediaMTX at `~/.local/bin/mediamtx` unless you change `mediamtx.binary` in [streams.yaml](../../../demo/videos/streams.yaml).

The demo supports four independent video-analysis streams. Videos are not included in release artifacts. All four entries in [streams.yaml](../../../demo/videos/streams.yaml) default to `enabled: true`, but a stream is automatically skipped with a warning when its environment variable is unset, empty, or points to an unreadable file. Its corresponding monitor is not registered.

| Stream | Environment variable | Purpose |
|---|---|---|
| `cam_fridge` | `SMARTBUILDING_DEMO_FRIDGE_VIDEO` | Tracks fridge door activity and supports inventory-oriented daily reports. |
| `cam_child` | `SMARTBUILDING_DEMO_CHILD_VIDEO` | Detects potentially dangerous child behavior for safety alerts and reports. |
| `cam_elder_bedroom` | `SMARTBUILDING_DEMO_ELDER_VIDEO` | Tracks daily wakeup activity for the elder-wakeup workflow. |
| `cam_elder_bedroom_2` | `SMARTBUILDING_DEMO_ELDER_2_VIDEO` | Runs a second, independent elder-wakeup camera input. |

Prepare any subset of compatible local MP4 files. The RTSP pusher copies the source stream, so each selected file must be playable by `ffmpeg` and compatible with your MediaMTX deployment.

## Step 1 - Provide video paths

Export an absolute path for every stream you want to run. Omit variables for streams you do not have; no YAML edits are required.

```bash
export SMARTBUILDING_DEMO_FRIDGE_VIDEO=/absolute/path/fridge.mp4
export SMARTBUILDING_DEMO_CHILD_VIDEO=/absolute/path/child-safety.mp4
export SMARTBUILDING_DEMO_ELDER_VIDEO=/absolute/path/elder-wakeup.mp4
export SMARTBUILDING_DEMO_ELDER_2_VIDEO=/absolute/path/elder-wakeup-2.mp4
```

To manually disable a stream even when its variable is available, set that stream's `enabled: false` in [streams.yaml](../../../demo/videos/streams.yaml).

## Step 2 - Start the demo

From the component root, run:

```bash
bash demo/scripts/start-demo.sh
```

The MCP server registers the three bundled tasks with `multilevel-video-understanding`. The demo launcher starts MediaMTX and the selected RTSP pushers, then starts the MCP server with the matching subset of [monitors.demo.yaml](../../../demo/monitors.demo.yaml).

It prints the active stream file at `demo/videos/.run/active-streams.txt`. Verify the running RTSP paths and the selected monitors:

```bash
cat demo/videos/.run/active-streams.txt
ffprobe -rtsp_transport tcp rtsp://localhost:8554/live/child
tail -f /tmp/smartbuilding-$(id -u)/mcp-server.log
```

Replace `child` with the selected path: `fridge`, `child`, `elder`, or `elder2`. The MCP endpoint is `http://localhost:3100/mcp` and the event webhook is `http://localhost:3101/events`.

## Step 3 - Connect an agent

Connect an MCP client as described in [Get Started - Step 3](../get-started.md#step-3---connect-an-agent-host). The demo supports reactive tool use immediately after the MCP server is registered.

## Step 4 - Optional OpenClaw demo integration

The reference OpenClaw installer is demo-specific: it installs the alert adapter, imports the repository skills, provisions the Fridge, Child Safety, and Elder Wakeup personas, and creates the reference alert routes for `cam_child` and `cam_elder_bedroom`.

Before running it, complete the OpenClaw MCP registration in [Get Started](../get-started.md#openclaw). On a development machine that needs the reference local-vLLM and MiniMax provider configuration, run the optional helper first. It only writes a `MINIMAX_API_KEY` placeholder; provide the real value through OpenClaw's supported secret configuration.

```bash
cd ~/edge-ai-suites/metro-ai-suite/agentic-smart-community/packages/framework-adapter-sdk/examples/openclaw

# Optional development-only provider setup.
bash scripts/fire_models.sh

# Install the demo adapter, agents, skills, and alert routes.
bash scripts/install.sh
```

The installer restarts the OpenClaw gateway and wakes the demo agents. Open the dashboard with `openclaw dashboard`; the `cam_child` and `cam_elder_bedroom` sessions receive their routed alert turns as selected video pipelines create alerts.

### Optional scheduled reports

The installer does not create cron jobs. Add only the scheduled demo behavior you want, replacing `Asia/Shanghai` with the applicable timezone:

```bash
# Fridge daily report at 22:00.
openclaw cron add --name fridge-daily-report-22 --cron "0 22 * * *" --tz Asia/Shanghai \
  --agent fridge-agent --session "session:daily_report" --session-key agent:fridge-agent:daily_report \
  --no-deliver --message "Generate today's fridge daily report."

# Child-safety daily report at 22:30.
openclaw cron add --name child-safety-daily-22 --cron "30 22 * * *" --tz Asia/Shanghai \
  --agent child-safety-agent --session "session:daily_report" --session-key agent:child-safety-agent:daily_report \
  --no-deliver --message "Generate today's child-safety daily report."

# Elder-wakeup weekly report every Sunday at 22:00.
openclaw cron add --name elder-wakeup-weekly-22 --cron "0 22 * * 0" --tz Asia/Shanghai \
  --agent elder-wakeup-agent --session "session:weekly_report" --session-key agent:elder-wakeup-agent:weekly_report \
  --no-deliver --message "Generate this week's elder wakeup report for cam_elder_bedroom."

# Daily no-wakeup fallback at 10:00.
openclaw cron add --name elder-wakeup-fallback-10 --cron "0 10 * * *" --tz Asia/Shanghai \
  --agent elder-wakeup-agent --session "session:cam_elder_bedroom" --session-key agent:elder-wakeup-agent:cam_elder_bedroom \
  --no-deliver --message "If no get_up event has been observed by 10:00, use scene_query to recheck whether the bed is occupied and emit a no_wakeup alert when appropriate."
```

Verify or remove scheduled jobs with:

```bash
openclaw cron list
openclaw cron rm <job-id>
```

## Step 5 - Stop the demo

Stop the MCP server and RTSP pushers together:

```bash
bash demo/scripts/stop-demo.sh
```

To stop the dependent containers as well, run `bash setup_docker.sh --down`.
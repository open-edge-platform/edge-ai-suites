# Ready-to-Run Demo

This optional guide configures reference video streams and monitors for the bundled Fridge, Child Safety, and Elder Wakeup use cases. It registers only the monitors whose user-provided video streams start successfully.

## Prerequisites

Before starting the demo, complete both of the following sections in [Get Started](../get-started.md):

1. Complete all [Prerequisites](../get-started.md#prerequisites), including the required system software and command-line tools.
2. Complete [Step 1 - Start dependent services](../get-started.md#step-1---start-dependent-services), and confirm that the model serving, video-summary, and video-stream analytics health checks succeed.

The demo supports four independent video-analysis streams with bundled use cases.

| Stream | Purpose |
|---|---|
| `cam_fridge` | Tracks fridge door activity and supports inventory-oriented daily reports. |
| `cam_child` | Detects potentially dangerous child behavior for safety alerts and reports. |
| `cam_elder_bedroom` | Tracks daily wakeup activity for the elder-wakeup workflow. |
| `cam_elder_bedroom_2` | Runs a second, independent elder-wakeup camera input. |

Prepare any subset of compatible local MP4 files. The RTSP pusher copies the source stream, so each selected file must be playable by `ffmpeg` and compatible with your MediaMTX deployment.

## Step 1 - Provide video paths

Video files are not included in release artifacts. All four entries in [streams.yaml](../../../demo/videos/streams.yaml) default to `enabled: true`, but a stream will be automatically skipped with a warning when its environment variable is unset, empty, or points to an unreadable file.

Export an absolute path for every stream you want to run. Omit variables for streams you do not have; no YAML edits are required.

```bash
export SMARTBUILDING_DEMO_FRIDGE_VIDEO=/absolute/path/fridge.mp4
export SMARTBUILDING_DEMO_CHILD_VIDEO=/absolute/path/child-safety.mp4
export SMARTBUILDING_DEMO_ELDER_VIDEO=/absolute/path/elder-wakeup.mp4
export SMARTBUILDING_DEMO_ELDER_2_VIDEO=/absolute/path/elder-wakeup-2.mp4
```

To manually disable a stream even when its variable is available, set that stream's `enabled: false` in [streams.yaml](../../../demo/videos/streams.yaml).

## Step 2 - Start the demo

From the component root (`metro-ai-suite/agentic-smart-community`), run:

```bash
bash demo/scripts/start-demo.sh
```

> If an MCP server is already running on port `3100`, stop it with `bash scripts/mcp-server/stop.sh` before starting the demo.

The demo launcher starts MediaMTX and the selected RTSP pushers, then starts the MCP server with the matching subset of [monitors.demo.yaml](../../../demo/monitors.demo.yaml).

It prints the active stream file at `demo/videos/.run/active-streams.txt`. Verify the running RTSP paths and the selected monitors:

```bash
cat demo/videos/.run/active-streams.txt
ffprobe -rtsp_transport tcp rtsp://localhost:8554/live/child
curl -fsS http://localhost:3101/health
tail -f /tmp/smartbuilding-$(id -u)/mcp-server.log
```

Replace `child` with the selected path: `fridge`, `child`, `elder`, or `elder2`. Press `Ctrl-C` to stop following the log. The MCP endpoint is `http://localhost:3100/mcp` and the event webhook is `http://localhost:3101/events`.

## Step 3 - Connect an agent

Connect an MCP client as described in [Get Started - Step 3](../get-started.md#step-3---connect-an-agent-host). The demo supports reactive tool use immediately after the MCP server is registered.

## Step 4 - *[Optional]* Enable proactive OpenClaw alerts

If you are connecting Smart Building to OpenClaw and want an agent to proactively send alert notifications to a specific agent session, install the OpenClaw adapter described in this step. The adapter routes MCP alert updates to the configured OpenClaw agent and session; it is not required for interactive MCP tool calls.

The adapter installer enables proactive alerts for this demo. It configures alert routes for `cam_child` and `cam_elder_bedroom`, imports the Smart Building skills, and provisions the Fridge, Child Safety, and Elder Wakeup agent personas.

This OpenClaw adapter is built with the [Framework Adapter SDK](../../../packages/framework-adapter-sdk/README.md). For details about building the plugin and configuring alert routes, see the [OpenClaw adapter guide](../../../packages/framework-adapter-sdk/examples/openclaw/README.md).

Run the installer from the component root:

```bash
bash demo/openclaw-adapter/install.sh
```

The installer is safe to run again. It builds the SDK, installs and links the OpenClaw plugin, preserves existing alert routes, merges missing demo agents by ID, copies personas without overwriting existing files, imports skills, validates `openclaw.json`, and restarts the gateway. New demo agents use the current `agents.defaults.model.primary`; set `AGENT_MODEL` to override it. By default the adapter uses `http://localhost:3100/mcp`; set `MCP_URL` to update the endpoint.

Open the Control UI at `http://localhost:18789` with `openclaw dashboard`. When a selected video pipeline raises an alert, the adapter immediately appends the formatted notification to the configured agent session. This zero-LLM delivery path keeps latency low and requires no user prompt or polling. The demo enables this flow for `cam_child` and `cam_elder_bedroom`.

### Scheduled reports based on OpenClaw Cron

The following optional OpenClaw cron jobs provide scheduled reports and a safety fallback for the demo agents:

| Cron job | Schedule | Agent | Session | Behavior |
|---|---|---|---|---|
| Fridge daily report | Daily at 22:00 | `fridge-agent` | `daily_report` | Generates a daily fridge inventory and dietary report. |
| Child-safety daily report | Daily at 22:30 | `child-safety-agent` | `daily_report` | Summarizes the day's child-safety alerts and notable events. |
| Elder-wakeup weekly report | Sunday at 22:00 | `elder-wakeup-agent` | `weekly_report` | Summarizes the week's wakeup activity for `cam_elder_bedroom`. |
| Elder no-wakeup fallback | Daily at 10:00 | `elder-wakeup-agent` | `cam_elder_bedroom` | Rechecks the scene and raises a `no_wakeup` alert when no get-up event has been observed. |

Add only the scheduled demo behavior you want, replacing `Asia/Shanghai` with the applicable timezone:

```bash
# Fridge daily report at 22:00.
openclaw cron add --name fridge-daily-report-22 --cron "0 22 * * *" --tz Asia/Shanghai --exact \
  --agent fridge-agent --session isolated --session-key agent:fridge-agent:daily_report \
  --no-deliver --message "Generate today's fridge daily report."

# Child-safety daily report at 22:30.
openclaw cron add --name child-safety-daily-22 --cron "30 22 * * *" --tz Asia/Shanghai --exact \
  --agent child-safety-agent --session isolated --session-key agent:child-safety-agent:daily_report \
  --no-deliver --message "Generate today's child-safety daily report."

# Elder-wakeup weekly report every Sunday at 22:00.
openclaw cron add --name elder-wakeup-weekly-22 --cron "0 22 * * 0" --tz Asia/Shanghai --exact \
  --agent elder-wakeup-agent --session isolated --session-key agent:elder-wakeup-agent:weekly_report \
  --no-deliver --message "Generate this week's elder wakeup report for cam_elder_bedroom."

# Daily no-wakeup fallback at 10:00.
openclaw cron add --name elder-wakeup-fallback-10 --cron "0 10 * * *" --tz Asia/Shanghai --exact \
  --agent elder-wakeup-agent --session isolated --session-key agent:elder-wakeup-agent:cam_elder_bedroom \
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
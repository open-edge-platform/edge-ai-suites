# Ready-to-Run Demo

This optional guide configures reference video streams and monitors for the bundled Fridge, Child Safety, and Elder Wakeup use cases. It registers only the monitors whose user-provided video streams start successfully.

## Prerequisites

Before starting the demo, complete both of the following sections in [Get Started](../get-started.md):

1. Complete all [Prerequisites](../get-started.md#prerequisites), including the required system software and command-line tools.
2. Complete [Step 1 - Start all services](../get-started.md#step-1---start-all-services), and confirm that the model serving, video-summary, and video-stream analytics health checks succeed.

The demo supports four independent video-analysis streams with bundled use cases.

| Stream                | Purpose                                                                     |
| --------------------- | --------------------------------------------------------------------------- |
| `cam_fridge`          | Tracks fridge door activity and supports inventory-oriented daily reports.  |
| `cam_child`           | Detects potentially dangerous child behavior for safety alerts and reports. |
| `cam_elder_bedroom`   | Tracks daily wakeup activity for the elder-wakeup workflow.                 |
| `cam_elder_bedroom_2` | Runs a second, independent elder-wakeup camera input.                       |

Prepare any subset of compatible local MP4 files. The RTSP pusher copies the source stream, so each selected file must be playable by `ffmpeg` and compatible with your MediaMTX deployment.

## Step 1 - Provide video paths

Video files are not included in release artifacts. All four entries in [streams.yaml](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/demo/videos/streams.yaml) default to `enabled: true`, but a stream will be automatically skipped with a warning when its environment variable is unset, empty, or points to an unreadable file.

Export an absolute path for every stream you want to run. Omit variables for streams you do not have; no YAML edits are required.

```bash
export SMART_COMMUNITY_DEMO_FRIDGE_VIDEO=/absolute/path/fridge.mp4
export SMART_COMMUNITY_DEMO_CHILD_VIDEO=/absolute/path/child-safety.mp4
export SMART_COMMUNITY_DEMO_ELDER_VIDEO=/absolute/path/elder-wakeup.mp4
export SMART_COMMUNITY_DEMO_ELDER_2_VIDEO=/absolute/path/elder-wakeup-2.mp4
```

To manually disable a stream even when its variable is available, set that stream's `enabled: false` in [streams.yaml](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/demo/videos/streams.yaml).

## Step 2 - Start the demo

From the component root (`metro-ai-suite/agentic-smart-community`), run:

```bash
# Change to mirror endpoint if you are in China and want to use the mirror site for Hugging Face.
export HF_ENDPOINT=https://hf-mirror.com

bash demo/scripts/start-demo.sh
```

This one-shot launcher pushes the demo RTSP streams, writes the demo config/monitors into `$SMART_COMMUNITY_DATA_DIR`, then brings the stack up with `setup_docker.sh --light` (reusing an already-warm `vllm-ipex-serving`) and reloads the `smart-community-mcp-server` container so it picks up the demo config. No separate MCP-server start is needed — it runs as a container in the stack.

The launcher writes [config.demo.yaml](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/demo/config.demo.yaml) to `$SMART_COMMUNITY_DATA_DIR/config.yaml`. It filters [monitors.demo.yaml](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/demo/monitors.demo.yaml) to the active streams and writes the result to `$SMART_COMMUNITY_DATA_DIR/monitors.yaml`. The MCP server then starts with these two files.

If either file changes, the previous version is backed up as `<filename>.YYYYMMDD-HHMMSS.bak`. Runtime configuration changes are written to the files in `$SMART_COMMUNITY_DATA_DIR`; the files under `demo/` remain unchanged.

It prints the active stream file at `demo/videos/.run/active-streams.txt`. Verify the running RTSP paths and the selected monitors:

```bash
cat demo/videos/.run/active-streams.txt
cat "${SMART_COMMUNITY_DATA_DIR:-$HOME/.mcp-smart-community}/monitors.yaml"
ffprobe -rtsp_transport tcp rtsp://localhost:8554/live/child
curl -fsS http://localhost:3101/health
docker logs -f smart-community-mcp-server
```

Replace `child` with the selected path: `fridge`, `child`, `elder`, or `elder2`. Press `Ctrl-C` to stop following the log. Open `http://localhost:3100/` to verify that active monitors appear automatically and that selecting one starts its RTSP live preview. Multiple browser windows viewing the same monitor share one ffmpeg process. The MCP endpoint is `http://localhost:3100/mcp` and the event webhook is `http://localhost:3101/events`.

## Step 3 - Connect an agent

Connect an MCP client as described in [Get Started - Step 3](../get-started.md#step-3---connect-an-agent-host). The demo supports reactive tool use immediately after the MCP server is registered.

## Step 4 - (Optional) Enable proactive OpenClaw alerts

If you are connecting Smart Community to OpenClaw and want an agent to proactively send alert notifications to a specific agent session, install the OpenClaw adapter described in this step. The adapter routes MCP alert updates to the configured OpenClaw agent and session; it is not required for interactive MCP tool calls.

The adapter installer enables proactive alerts for this demo. It configures alert routes for `cam_child` and `cam_elder_bedroom`, imports the Smart Community skills, and provisions the Fridge, Child Safety, and Elder Wakeup agent personas.

This OpenClaw adapter is built with the [Framework Adapter SDK](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/packages/framework-adapter-sdk/README.md). For details about building the plugin and configuring alert routes, see the [OpenClaw adapter guide](https://github.com/open-edge-platform/edge-ai-suites/blob/main/metro-ai-suite/agentic-smart-community/packages/framework-adapter-sdk/examples/openclaw/README.md).

Run the installer from the component root:

```bash
bash demo/openclaw-adapter/install.sh
```

The installer is safe to run again. It builds the SDK, installs and links the OpenClaw plugin, preserves existing alert routes, merges missing demo agents by ID, copies personas without overwriting existing files, imports skills, validates `openclaw.json`, and restarts the gateway. New demo agents use the current `agents.defaults.model.primary`; set `AGENT_MODEL` to override it. By default the adapter uses `http://localhost:3100/mcp`; set `MCP_URL` to update the endpoint.

Open the Control UI at `http://localhost:18789` with `openclaw dashboard`. When a selected video pipeline raises an alert, the adapter immediately appends the formatted notification to the configured agent session. This zero-LLM delivery path keeps latency low and requires no user prompt or polling. The demo enables this flow for `cam_child` and `cam_elder_bedroom`.

### Scheduled reports based on OpenClaw Cron

The following optional OpenClaw cron jobs provide scheduled reports and a safety fallback for the demo agents:

| Cron job | Schedule | Agent | Session | Behavior |
| -------- | -------- | ----- | ------- | -------- |
| Fridge daily report | Daily at 22:00 | `fridge-agent` | `daily_report` | Generates a daily fridge inventory and dietary report. |
| Child-safety daily report | Daily at 22:30 | `child-safety-agent` | `daily_report` | Summarizes the day's child-safety alerts and notable events. |
| Elder-wakeup weekly report | Sunday at 22:00 | `elder-wakeup-agent` | `weekly_report` | Summarizes the week's wakeup activity for `cam_elder_bedroom`. |
| Elder no-wakeup fallback | Daily at 10:00 | `elder-wakeup-agent` | `cam_elder_bedroom` | Rechecks the scene and raises a `no_wakeup` alert when no get-up event has been observed. |

Add only the scheduled demo behavior you want, replacing `Asia/Shanghai` with the applicable timezone:

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

## Step 5 - Talk with agents

Talk naturally with any demo agent about a camera or time period, then ask follow-up questions as needed. The agent will choose the appropriate Smart Community tools.

If you installed the OpenClaw adapter in Step 4, open the Control UI and select one of these agents:

### Fridge agent

Select `fridge-agent` to discuss the current fridge contents, reports, nutrition, and related lifestyle goals. For example:

- "Generate today's fridge daily report."
- "Based on my health goals, is the food in my fridge reasonable? Give me some diet advice."
- "Any other slimming tips? And where can I go to exercise nearby?"

Try following up with questions such as "Why did you recommend that?", "What changed since yesterday?", or "Give me a shorter shopping list."

### Child Safety agent

Select `child-safety-agent` to ask about recent safety events, the current scene, or patterns over a period of time. For example:

- "Is the child safe right now?"
- "Were there any child-safety alerts today?"
- "Generate today's child-safety report and explain the most important event."
- "How many risky events happened this week?"
- "What changes would make this room safer?"

You can continue with requests such as "Show me only unacknowledged alerts", "What happened before that alert?", or "Compare today with yesterday."

### Elder Wakeup agent

Select `elder-wakeup-agent` to discuss wakeup activity, daily status, and longer-term patterns. For example:

- "What happened in the elder's bedroom today?"
- "Has the elder gotten up yet?"
- "Was today's wakeup later than usual?"
- "Generate this week's wakeup report and highlight anything unusual."
- "Compare this week's wakeup times with last week."

Follow up naturally with questions such as "Which day was latest?", "Check the current scene again", or "Explain why this was marked unusual."

These are conversation starters, not a required script. Try your own wording, combine several questions in one conversation, and ask the agent to clarify, compare, summarize, or take a closer look whenever the first answer raises another question. If you skipped the optional OpenClaw adapter, ask the MCP-capable agent connected in Step 3 and include the relevant monitor ID, such as `cam_fridge`, `cam_child`, or `cam_elder_bedroom`.

## Step 6 - Stop the demo

Stop the demo RTSP pushers and the app tier (MCP server + analytics + video-summary) together, leaving `vllm-ipex-serving` running so its multi-minute recompile is not repaid on the next start:

```bash
bash demo/scripts/stop-demo.sh
```

To tear the whole stack down, including `vllm-ipex-serving`, run `bash setup_docker.sh --down`.

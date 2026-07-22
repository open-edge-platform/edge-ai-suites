# Agentic Smart Community 

An AI Agent-native video analysis platform designed for MCP (Model Context Protocol) integration. Provides a universal, framework-agnostic toolkit for video surveillance and analysis — agents can autonomously create, manage, and respond to custom use cases without modifying core components.

## Built-in Use Cases

| ID | Description | Status |
|----|-------------|--------|
| Fridge_monitor | Refrigerator monitoring — regular reports (food shortage alerts, diet adjustment suggestions, lifestyle/fitness recommendations) + interactive chat for personalized Q&A | Adapter shipped (prompt only; no alert rules) |
| Child_safety | Child danger alert notification — real-time detection of risky behaviors (jumping from heights, playing with knives/fire, etc.), immediate alerts to parents, daily summaries, and follow-up conversations | Adapter shipped (`evaluate_rules.py` + prompt) |
| Elder_wakeup | Elder care (wake-up tracking) — monitor daily wake-up times, alert caregivers on significant deviations, weekly summary reports, and follow-up reminders | Adapter shipped (`evaluate_rules.py` + prompt) |


## Architecture

The platform is built around MCP, enabling AI agents (OpenClaw, Hermes, etc.) to orchestrate video analysis pipelines through standardized tool interfaces.

## MCP Server Workflow

The MCP server (`packages/mcp-server`) sits between AI agents and three external services:

```
   agents (OpenClaw / Claude Desktop / Hermes)
                │  MCP tools
                ▼
        ┌──────────────┐  ← config.yaml + monitors.yaml
        │  MCP Server  │  :3100
        └──┬───────┬──┬┘
   /events │       │  │ chat/completions (single frame)
    :3101  │       │  │
           ▼       ▼  ▼
   videostream-  multilevel-      vllm-serving-ipex
   analytics     video-under-     :41091
   :8999         standing :8192   (scene_query)
   (RTSP +       (caption-only
   motion         SRT report)
   detect)
```

### Lifecycle

- **Startup** (`mcp-server --config config.yaml --monitors monitors.yaml`): load config → init DB → reconcile crash residue → auto-register each `enabled: true` monitor → start storage cleaner (24h period; purges expired logs and segments)
- **Runtime** (per monitor): analytics `:8999` pulls RTSP → POSTs events to `:3101` → MCP worker polls pending tasks → calls `:8192` for summary → rule-engine decides alert → agents query via MCP tools
- **Shutdown** (SIGINT/SIGTERM): stop cleaner → graceful-stop all workers → pause analytics sources → close DB

## Supporting Resources

- [Get Started Guide](./get-started.md)
- [API Reference](./api-reference.md)
- [System Requirements](./get-started/system-requirements.md)
- [Release Notes](./release-notes.md)

## License

See [LICENSE](LICENSE).

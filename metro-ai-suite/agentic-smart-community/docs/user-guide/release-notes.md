# Release Notes

## 0.1.0

Initial Agentic Smart Community release:

- MCP tools and resources over Streamable HTTP, with a dedicated video-event webhook.
- Runtime monitor lifecycle management backed by SQLite and persistent YAML configuration.
- Conversational use-case authoring with two confirmation gates, four-section prompt generation,
	schema/rule consistency checks, and the `generate_task` → `register` workflow.
- Videostream analytics for motion, static periods, and continuous recording, with OpenVINO
	prefiltering, ROI preparation, health recovery, and keepalive support.
- Bundled Fridge, Child Safety, and Elder Wakeup use cases, plus an optional OpenClaw adapter for
	proactive alert delivery.

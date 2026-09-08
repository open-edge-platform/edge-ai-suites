# Release Notes: Smart NVR

- [Version 2026.2.0](#version-202620)
- [Version 2026.1.0](#version-202610)
- [Version 1.2.4](#version-124)

## Version 2026.2.0

**Release Date**: September 9, 2026

**New**:

- Distributed, multi-broker deployment: Smart NVR can now connect to multiple independent MQTT brokers at once, running side-by-side with Scenescape (Smart Intersection) in a dual-mode configuration. Adds `brokers` and `vss` REST API endpoints for managing this.
- Single-command startup: `setup.sh` now brings up the full stack (RTSP streamer, Scenescape, NVR event-router) in one command, including automatic network joining.
- Migrated Python dependency management from Poetry to `uv`.
- Added multi-broker Scenescape integration and advanced configuration guides.

**Improved**:

- Event-processing pipeline no longer blocks the UI during high event volume: summarization and search-embedding calls now run on background threads, and rule summaries are fetched concurrently instead of serially.
- Continuous camera ingestion now uploads videos through Pipeline Manager and
  submits their search embeddings through asynchronous DataPrep batch jobs.
- Added configurable watcher batch size, job polling interval, and job timeout
  settings for Docker Compose and Helm deployments.

**Fixed**:

- Fixed MQTT broker TLS/certificate handling in Scenescape dual-mode by migrating the MQTT client to `aiomqtt`, removing an unnecessary client-certificate requirement.

**Known Issues**:

- Scenescape integration is currently not supported when deploying with Helm charts.
- Smart NVR will not work on either Standalone or Developer Node versions of Edge Microvisor Toolkit due to its incompatibility with Frigate.
- The AI-Powered Event Viewer feature relies on Frigate GenAI features, which may exhibit instability or bugs, impacting event data processing reliability.

## Version 2026.1.0

**Release Date**: June 17, 2026

**Improved**:

- Documentation updates to improve clarity and accuracy.

**Fixed**:

- Fixed Dependabot security vulnerabilities in dependencies.
- Minor bug fixes.

**Known Issues**:

- Scenescape integration is currently not supported when deploying with Helm charts.
- Smart NVR will not work on either Standalone or Developer Node versions of
  Edge Microvisor Toolkit due to its incompatibility with Frigate.
- The AI-Powered Event Viewer feature relies on Frigate GenAI features, which may exhibit
  instability or bugs, impacting event data processing reliability.

## Version 1.2.4

**Release Date**: 17 Feb 2026

**New Features**:

- Dependabot fixes for security vulnerabilities in dependencies.
- Documentation updates for clarity and accuracy.
- Minor bug fixes.

<!--hide_directive
:::{toctree}
:hidden:

Release Notes 2025 <./release-notes/release-notes-2025.md>

:::
hide_directive-->

# Agentic Smart Community 

An AI Agent-native video analysis platform designed for MCP (Model Context Protocol) integration. Provides a universal, framework-agnostic toolkit for video surveillance and analysis — agents can autonomously create, manage, and respond to custom use cases without modifying core components.

The MCP server also hosts a Vue dashboard at `http://localhost:3100/`. It discovers monitors from the runtime database, provides RTSP live preview through a bounded server-side ffmpeg proxy, and shows activity, reports, local token usage, and optional Router/OpenClaw integrations.

Below, you'll find links to detailed documentation to help you get started, configure, and deploy the sample application.

## Documentation

- **Overview**
  - [Overview](./docs/user-guide/index.md): A high-level introduction to the sample application.

- **Getting Started**
  - [Get Started](./docs/user-guide/get-started.md): Step-by-step guide for the MCP server and bundled use cases.
  - [Ready-to-Run Demo](./docs/user-guide/get-started/ready-to-run-demo.md): Optional reference demo using user-provided video inputs.
  - [System Requirements](./docs/user-guide/get-started/system-requirements.md): Hardware and software requirements for running the sample application.

- **API Reference**
  - [API Reference](./docs/user-guide/api-reference.md): Comprehensive reference for the available API endpoints.

- **Release Notes**
  - [Release Notes](./docs/user-guide/release-notes.md): Information on the latest release, improvements, and bug fixes.

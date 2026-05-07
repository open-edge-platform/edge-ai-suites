# NICU Warmer — Intelligent Patient Monitoring

The NICU Warmer application helps medical AI developers and systems engineers evaluate Intel® Core™ Ultra processors for AI-enabled neonatal patient monitoring. It demonstrates that you can run **5 AI models concurrently in a single GStreamer pipeline on Intel GPU, NPU, and CPU** — detecting patient presence, caretaker activity, warmer latch status, contactless vital signs, and action recognition.

You can view all monitoring outputs through a single React dashboard that displays:

- Object detection (patient, caretaker, latch clip presence)
- Contactless vital signs via rPPG (heart rate, respiratory rate, waveforms)
- Action recognition (11 NICU-specific activity categories)
- Hardware telemetry (CPU, GPU, NPU, memory, power utilization)

All inference runs in a **single Intel DL Streamer Pipeline Server** pipeline at ~15 FPS, with device assignments configurable at runtime. This validates BOM reduction by consolidating multi-model AI on one edge system.

The solution is intended to:

- Showcase multi-model AI capabilities of Intel Core Ultra (Meteor Lake)
- Run on Ubuntu 24.04 with containerized workloads
- Be startable with two commands from a clean clone (`make setup` then `make run`)

## Get Started

To see the system requirements and setup instructions, see the following guides:

- [Get Started](docs/user-guide/get-started.md): Follow step-by-step instructions to set up
  the application.
- [System Requirements](docs/user-guide/get-started/system-requirements.md): Check the
  hardware and software requirements for deploying the application.

## How It Works

At a high level, the system runs 5 AI models in a single GStreamer pipeline, communicating via MQTT to a Flask backend that streams results to a React dashboard over Server-Sent Events (SSE).

For details, see [How It Works](docs/user-guide/how-it-works.md).

## Learn More

For detailed information about system requirements, architecture, and how the application
works, see the:

- [Full Documentation](docs/user-guide/index.md)
- [Release Notes](docs/user-guide/release-notes.md)

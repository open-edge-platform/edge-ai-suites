# NICU Warmer — Intelligent Patient Monitoring

> This application is for **reference and evaluation purposes**. It is
> **not intended for direct use in clinical or diagnostic environments** and is not
> validated as such.

The NICU Warmer application helps medical AI developers and systems engineers evaluate Intel® Core™ Ultra processors, demonstrating that you can run **5 AI models concurrently in a single GStreamer pipeline on Intel GPU, NPU, and CPU** —  with workloads representative of a real neonatal scenario (detects patient presence, caretaker activity, warmer latch status, contactless vital signs, and action recognition).

You can view all monitoring outputs through a single React dashboard that displays:

- Object detection (patient, caretaker, latch clip presence)
- Mock vital signs data via rPPG (heart rate, respiratory rate, waveforms)
- Action recognition (11 activity categories)
- Hardware telemetry (CPU, GPU, NPU, memory, power utilization)

All inference runs in a **single Intel DL Streamer Pipeline Server** pipeline at ~15 FPS, with device assignments configurable at runtime. This validates BOM reduction by consolidating multi-model AI on one edge system.

The solution is intended to:

- Showcase multi-model AI capabilities of Intel Core Ultra (Meteor Lake)
- Run on Ubuntu 24.04 with containerized workloads
- Be startable with two commands from a clean clone (`make setup` then `make run`)

## Manual Model Staging

Before running `make run`, stage the workload models in these locations:

- Repository root:
  - patient detection model files: `.xml` and `.bin`
  - person detection model files: `.xml` and `.bin`
  - latch detection model files: `.xml` and `.bin`
  - action recognition encoder model files: `.xml` and `.bin`
  - action recognition decoder model files: `.xml` and `.bin`
- `models_rppg/`:
  - rPPG workload source model: `.hdf5`

`make run` expects these files to exist. If `models_rppg/mtts_can.xml` and
`models_rppg/mtts_can.bin` are missing, the rPPG converter container generates
them automatically from `models_rppg/mtts_can.hdf5`.

## Get Started

To see the system requirements and setup instructions, see the following guides:

- [Get Started](./docs/user-guide/get-started.md): Follow step-by-step instructions to set up
  the application.
- [System Requirements](./docs/user-guide/get-started/system-requirements.md): Check the
  hardware and software requirements for deploying the application.

## How It Works

At a high level, the system runs 5 AI models in a single GStreamer pipeline, communicating via MQTT to a Flask backend that streams results to a React dashboard over Server-Sent Events (SSE).

For details, see [How It Works](./docs/user-guide/how-it-works.md).

## Learn More

For detailed information about system requirements, architecture, and how the application
works, see the:

- [Full Documentation](./docs/user-guide/index.md)
- [Release Notes](./docs/user-guide/release-notes.md)

## Disclaimer

Intel is committed to respecting human rights and avoiding complicity in human rights abuses. See [Intel's Global Human Rights Principles](https://www.intel.com/content/www/us/en/policy/policy-human-rights.html). Intel's products and software are intended only to be used in applications that do not cause or contribute to a violation of an internationally recognized human right.  



# Surgical Instrument Sample App

> Note:
> This application is for **reference and evaluation purposes only**. It is
> **not intended for direct use in clinical or diagnostic environments** and is
> not validated for such a purpose.

The app demonstrates real-time polyp detection in endoscopic video using Intel
hardware acceleration (CPU / Intel iGPU / Intel NPU) via OpenVINO. It is
packaged as a Docker Compose workload with a decoupled capture / inference /
display architecture, so the displayed video stays smooth regardless of
inference speed.

Supported inputs:

- Basler industrial camera (via `pypylon`)
- USB / V4L2 webcam
- Video file (for demos and benchmarking)

Display path:

- OpenGL vsync presenter with `cv2` and headless fallback
- Optional fullscreen direct-scanout for low latency
- Optional camera trigger modes (`software`, `vsync`) for low photon-to-pixel
  latency

How to start:

- See [Get Started](./get-started.md) for a step-by-step deployment guide.
- See [Runtime Configuration](./runtime-configuration.md) for every knob and
  CLI option exposed by the app.
- See [Troubleshooting](./troubleshooting.md) for common issues.
- See [Release Notes](./release-notes.md) for version history.

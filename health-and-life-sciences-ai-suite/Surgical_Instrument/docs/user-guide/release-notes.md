# Release Notes - Surgical Instrument

## Version 2026.2.0

**Release Date**: Sep 9, 2026

This is the initial release of the application. It is intended for reference and evaluation
purposes only and not for direct use in clinical or diagnostic environments.

It may be used to test performance of Intel hardware (Arc iGPU, AI Boost NPU, or CPU) applied
to the task of real-time polyp-detection in endoscopic videos. It runs entirely at
the edge and performs the following:

- Trains a model — automatically builds a YOLO11n polyp-detection model on startup, using the
  ColonDB dataset.
- Detects polyps — runs detection on recorded endoscopy video or a live Basler industrial
  camera.
- Presents results in a GUI — a local UI displays the video with detections, while a browser
  UI displays live performance metrics (FPS, latency, and CPU/GPU/NPU usage).

**To get started**:

- Run make doctor to check that your system is ready.
- Run make up to build and launch the app.
- Open your browser to <http://localhost:8080>. On the first launch, you will see a note:
  `The first startup trains the model and takes about 20–35 minutes on an Intel Arc iGPU.
  After that, the app starts in seconds`.

**Key Features**:

- Simple web interface — open the UI in your browser at port 8080; no command-line knowledge
  needed to operate it.
- Runs on your choice of hardware — switch detection between CPU, GPU, and NPU from the
  Settings menu.
- Flexible video input — use bundled demo video, upload your own, or connect a USB or Basler
  camera.
- Live performance metrics — see real-time FPS, latency percentiles, and hardware utilization.

**Known Limitations**:

- Not a medical device — not validated for production use, intended for evaluation and reference only.
- First boot is slow — model training takes 20–35 minutes; the UI is unavailable until it finishes.
- Switching video source requires a Stop/Start.
- NPU option requires an Intel NPU on the host; otherwise use GPU or CPU.

For more information on the application, its system requirements and usage guides, refer to the
[Surgical Instrument User Documentation](https://docs.openedgeplatform.intel.com/2026.2/edge-ai-suites/surgical-instrument/index.html)

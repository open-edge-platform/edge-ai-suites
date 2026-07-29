# Release Notes: Win Vision AI

## Version 2026.1.0

Win Vision AI is a new Windows-only component introduced in this release: a
Python application built on GStreamer and Intel DL Streamer for running multiple
concurrent AI inference pipelines on Intel hardware, configured through YAML
and capable of RTSP and WebRTC output streaming.

The initial release of Win Vision AI application features:

- Support for running multiple AI inference pipelines concurrently.
- Support for multiple concurrent pipelines managed on a shared GLib main loop
  via PipelineManager.
- YAML-driven configuration for models, inputs, and outputs, allowing workload
  changes without code modifications.
- Support for detection and classification inference types via DL Streamer
  `gvadetect` and `gvaclassify`.
- CPU, GPU, and NPU inference target support.
- RTSP and WebRTC streaming output through MediaMTX.
- MQTT and file-based inference metadata output.
- Raw GStreamer pipeline mode for advanced users who want to provide custom
  pipeline strings directly.
- Optional Prometheus metrics export option for per-pipeline monitoring.
- Support for file, RTSP, and GenICam industrial camera inputs.
- The pre-built `gstgencamsrc.dll` plugin and `setup_genicam_runtime.ps1` to
  simplify GenICam camera enablement on Windows.
- Setup to use the official DL Streamer Windows installer instead of manual
  DLL extraction, which simplifies installation.
- Addition of `gstreamer_python==1.28.2` and Python dependency minimum versions
  for more reproducible environments.
- Upgrade of the default MediaMTX version from v1.15.3 to v1.18.1.

**Known Issues**

- Win Vision AI is supported on Windows only in this release.
- NPU inference can fail with errors such as "Failed to construct
  OpenVINOImageInference" when the installed NPU driver is not at the required
  supported version.

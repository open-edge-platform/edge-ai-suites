# Release Notes: NICU Warmer

## Version 1.0.0 - 2026

This is the initial release of the application, therefore, it is considered a preview version.

NICU Warmer showcases how a single Intel-powered edge system can simultaneously run multiple
AI models for neonatal patient monitoring — object detection, contactless vital signs,
and action recognition — all within one integrated GStreamer pipeline and React dashboard.

It proves that heterogeneous workloads — from multi-object detection to heart-rate extraction
via rPPG and activity classification — can coexist efficiently on one Intel Core Ultra platform
without compromising performance or stability.

**New**

The initial feature set of the application is now available:

- Real-time object detection: patient, caretaker, and latch clip presence (GPU)
- Contactless vital signs via rPPG: heart rate and respiratory rate (CPU)
- Action recognition with 11 NICU-specific categories (NPU)
- Motion analysis via frame differencing
- React dashboard with live video, detection overlays, and vitals charts
- Hardware telemetry monitoring (CPU, GPU, NPU, memory, power)
- Runtime device configuration via UI settings or REST API
- Docker Compose deployment with automatic model download (`make setup`)
- Device profile presets (all-CPU, all-GPU, all-NPU, mixed-optimized)

**Known issues**

- Video upload is limited to 500 MB per file.

- rPPG accuracy requires adequate lighting and minimal patient motion during the first
  10-15 seconds of warmup.

- If `make run` is executed before `make setup`, Docker creates empty directories for
  bind-mount paths, causing pipeline failures.

  To work around the issue, run:

  ```bash
  make down
  sudo rm -rf Warmer_Testbed_YTHD.mp4 model_artifacts models_rppg
  make setup
  make run
  ```

- NPU fallback to CPU is not reflected in the device profile API response until the
  pipeline is restarted.

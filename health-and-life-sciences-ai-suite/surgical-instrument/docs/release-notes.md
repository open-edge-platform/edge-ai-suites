# Release Notes - Surgical Instrument

## Version 2026.2.0

**Aug 18, 2026**

This is the initial release of the application. It is intended for reference
and evaluation purposes only and not for direct use in clinical or diagnostic
environments.

**New**

- Docker Compose driven workflow with a single `make up` entrypoint that
  supports both registry pull (default) and local source build via
  `REGISTRY=false`.
- Decoupled capture / inference / display architecture: display shows every
  captured frame while OpenVINO inference runs on its own thread.
- Pure OpenVINO detector (no `ultralytics` runtime coupling) with YOLO
  letterbox preprocessing and numpy NMS.
- Multiple sources through a single interface: Basler camera (via `pypylon`),
  USB / V4L2 webcam, and video file.
- OpenGL vsync presenter with `cv2` and headless fallback.
- Optional Basler capture trigger modes (`off` / `software` / `vsync`) with
  present-completion phase-lock for low photon-to-pixel latency.
- Fullscreen OpenGL direct-scanout to bypass the compositor.
- Per-stage latency CSV (`trigger_to_grab`, `grab_to_display`,
  `trigger_to_display`, `infer_ms`, `disp_fps`, `cap_fps`) for A/B comparison.
- Optional core pinning and `SCHED_FIFO` real-time priority for capture,
  inference, and display threads.
- Restructured layout with `src/`, `docker/`, and `docs/` folders and a
  compose-only Makefile.

"""Configuration for the updated endoscopy demo.

All knobs are exposed via both CLI flags and environment variables (CLI wins).
Core pinning is fully configurable and OFF by default for portability — no
hardcoded per-machine core layout.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _opt_int(v: str | None) -> int | None:
    return int(v) if v not in (None, "", "-1", "none", "None") else None


def _opt_float(v: str | None) -> float | None:
    return float(v) if v not in (None, "", "none", "None") else None


@dataclass
class Config:
    # source
    source: str          # file | v4l2 | basler
    source_arg: str      # path | device index/path | camera serial ("" = first)
    loop: bool           # loop video files
    width: int
    height: int
    target_fps: float
    camera_fps: float    # Basler acquisition-rate cap (0 = free-running)
    camera_trigger: str  # off | software | vsync
    vsync_divisor: int   # trigger every Nth vblank (vsync mode)
    exposure_us: float | None
    gain: float | None

    # model / inference
    model: str
    device: str          # CPU | GPU | NPU
    threshold: float
    iou: float
    frame_skip: int      # run inference every Nth captured frame

    # display / output
    headless: bool
    presenter: str       # auto | gl | cv2  (gl = vsync-locked OpenGL present)
    fullscreen: bool     # GL: fullscreen direct-scanout (bypass compositor, low latency)
    display_scale: float
    record_path: str | None
    detection_ttl_ms: int
    latency_trace: bool  # emit per-stage photon-to-pixel CSV

    # scheduling (all optional; None = no affinity, priority 0 = SCHED_OTHER)
    cpu_capture: int | None
    cpu_inference: int | None
    cpu_display: int | None
    rt_priority: int


def parse_config(argv: list[str] | None = None) -> Config:
    p = argparse.ArgumentParser(description="Updated endoscopy demo (camera or file, OpenVINO).")

    # source
    p.add_argument("--source", default=_env("SOURCE", "basler"), choices=["file", "v4l2", "basler"])
    p.add_argument("--source-arg", default=_env("SOURCE_ARG", ""),
                   help="file: path | v4l2: index or /dev/videoN | basler: serial ('' = first camera)")
    p.add_argument("--no-loop", dest="loop", action="store_false", default=_env("LOOP", "1") != "0")
    p.add_argument("--width", type=int, default=int(_env("WIDTH", "1280")))
    p.add_argument("--height", type=int, default=int(_env("HEIGHT", "720")))
    p.add_argument("--target-fps", type=float, default=float(_env("TARGET_FPS", "60")))
    p.add_argument("--camera-fps", type=float, default=float(_env("CAMERA_FPS", "0")),
                   help="Basler capture-rate cap in FPS (0 = free-running). "
                        "Set to a submultiple of the display refresh to avoid jitter.")
    p.add_argument("--camera-trigger", default=_env("CAMERA_TRIGGER", "off").lower(),
                   choices=["off", "software", "vsync"],
                   help="Basler capture mode: off (free-run, newest-frame-wins) | "
                        "software (expose on demand per captured frame) | vsync "
                        "(software-trigger locked to the monitor vblank via GLX_OML). "
                        "vsync/software minimise photon-to-pixel latency.")
    p.add_argument("--vsync-divisor", type=int, default=int(_env("VSYNC_DIVISOR", "1")),
                   help="vsync trigger: capture every Nth vblank (1 = every refresh; "
                        "raise to 2 only on high-refresh panels if the camera can't keep up). "
                        "Default 1 — on a 60Hz display, 2 would drop capture to 30fps.")
    p.add_argument("--exposure-us", default=_env("EXPOSURE_US", ""))
    p.add_argument("--gain", default=_env("GAIN", ""))

    # model
    p.add_argument("--model", default=_env("MODEL", "/models/yolo11n_polyp/best_openvino_model/best.xml"))
    p.add_argument("--device", default=_env("DEVICE", "GPU").upper(), choices=["CPU", "GPU", "NPU"])
    p.add_argument("--threshold", type=float, default=float(_env("THRESHOLD", "0.5")))
    p.add_argument("--iou", type=float, default=float(_env("IOU", "0.45")))
    p.add_argument("--frame-skip", type=int, default=int(_env("FRAME_SKIP", "1")),
                   help="inference every Nth frame (1 = every frame)")

    # display / output
    p.add_argument("--headless", action="store_true", default=_env("HEADLESS", "0") != "0")
    p.add_argument("--presenter", default=_env("PRESENTER", "auto").lower(),
                   choices=["auto", "gl", "cv2"],
                   help="display backend: auto (GL vsync, else cv2) | gl (vsync-locked "
                        "OpenGL) | cv2 (legacy imshow, no vsync)")
    p.add_argument("--fullscreen", action="store_true", default=_env("FULLSCREEN", "0") != "0",
                   help="GL presenter only: fullscreen + immediate present (vsync off) so the "
                        "compositor is bypassed (direct scanout). Biggest photon-to-pixel win "
                        "on a normal desktop; may tear.")
    p.add_argument("--display-scale", type=float, default=float(_env("DISPLAY_SCALE", "1.0")))
    p.add_argument("--record", default=_env("RECORD", ""), help="path to write annotated .mp4/.avi")
    p.add_argument("--detection-ttl-ms", type=int, default=int(_env("DETECTION_TTL_MS", "200")))
    p.add_argument("--latency-trace", action="store_true", default=_env("LATENCY_TRACE", "0") != "0",
                   help="print per-stage photon-to-pixel latency as CSV (trigger->grab->display).")

    # scheduling
    p.add_argument("--cpu-capture", default=_env("CPU_CAPTURE", ""))
    p.add_argument("--cpu-inference", default=_env("CPU_INFERENCE", ""))
    p.add_argument("--cpu-display", default=_env("CPU_DISPLAY", ""))
    p.add_argument("--rt-priority", type=int, default=int(_env("RT_PRIORITY", "0")),
                   help="SCHED_FIFO priority (0 = normal SCHED_OTHER). Needs privileges.")

    a = p.parse_args(argv)
    return Config(
        source=a.source,
        source_arg=a.source_arg,
        loop=a.loop,
        width=a.width,
        height=a.height,
        target_fps=a.target_fps,
        camera_fps=a.camera_fps,
        camera_trigger=a.camera_trigger,
        vsync_divisor=max(1, a.vsync_divisor),
        exposure_us=_opt_float(a.exposure_us),
        gain=_opt_float(a.gain),
        model=a.model,
        device=a.device,
        threshold=a.threshold,
        iou=a.iou,
        frame_skip=max(1, a.frame_skip),
        headless=a.headless,
        presenter=a.presenter,
        fullscreen=a.fullscreen,
        display_scale=a.display_scale,
        record_path=a.record or None,
        detection_ttl_ms=a.detection_ttl_ms,
        latency_trace=a.latency_trace,
        cpu_capture=_opt_int(a.cpu_capture),
        cpu_inference=_opt_int(a.cpu_inference),
        cpu_display=_opt_int(a.cpu_display),
        rt_priority=a.rt_priority,
    )

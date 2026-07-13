"""Basler USB3 → stdout raw-BGR bridge for the gst-launch fdsrc path.

Why this exists
---------------
The DL Streamer 2026.1 base image does NOT ship `gencamsrc` or the Basler
`pylonsrc` GStreamer plugin. Installing the pylon Debian SDK inflates the
pipeline image by ~150 MB and requires a network fetch behind Basler's
registration wall.

pypylon (already installed for enumeration in the backend, and for this
bridge in the pipeline) bundles the pylon runtime and works fully headless.
We open the camera in Python, convert to BGR8, and write raw bytes to
stdout. The pipeline gst-launch command is then piped as:

    python3 basler_reader.py <serial> WxH@fps
      | gst-launch-1.0 fdsrc fd=0 blocksize=$((W*H*3))
                     ! rawvideoparse format=bgr width=W height=H framerate=fps/1
                     ! videoconvert
                     ! ...  (rest of the polyp pipeline)

Rationale for stdout piping over shmsink / v4l2loopback:
- shmsink needs Python-GStreamer bindings + a control socket; ~40 lines
  more code and one more failure mode (broken control socket races).
- v4l2loopback needs a host kernel module we don't own on customer
  hardware.
- Piping via fdsrc is portable, zero-dependency beyond pypylon, and lets
  us reuse the existing pipeline_string.py from `videoconvert` onward.

Frame pacing
------------
Basler acA1920-150uc runs up to 150 fps at full 1920x1080. We drive it at
the pipeline's target_fps (60 by default) via the `AcquisitionFrameRate`
node so downstream pacing is not needed (unlike the file source which
uses `videorate + identity sync=true`).

Failure semantics
-----------------
Any pypylon exception → non-zero exit → gst-launch sees EOF on stdin →
gst pipeline emits EOS → launcher.py supervisor sees the exit and either
respawns (if /start is still the user intent) or unwinds cleanly.
"""
from __future__ import annotations

import argparse
import re
import signal
import sys
import time

# Import pypylon lazily so the module can be imported at test time on hosts
# without the SDK.
try:
    from pypylon import pylon  # type: ignore
except ImportError as exc:  # pragma: no cover
    sys.stderr.write(f"[basler_reader] pypylon import failed: {exc}\n")
    sys.exit(2)


def _parse_geometry(spec: str) -> tuple[int, int, int]:
    """Parse `WxH@fps` (e.g. `1920x1080@60`)."""
    m = re.fullmatch(r"(\d+)x(\d+)@(\d+)", spec)
    if not m:
        raise argparse.ArgumentTypeError(
            f"invalid geometry {spec!r} (want WxH@fps, e.g. 1920x1080@60)"
        )
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _open_camera(serial: str | None) -> "pylon.InstantCamera":
    tl = pylon.TlFactory.GetInstance()
    if serial:
        devices = tl.EnumerateDevices()
        match = [d for d in devices if d.GetSerialNumber() == serial]
        if not match:
            sys.stderr.write(
                f"[basler_reader] no Basler with serial {serial!r} found; "
                f"visible: {[d.GetSerialNumber() for d in devices]}\n"
            )
            sys.exit(3)
        cam = pylon.InstantCamera(tl.CreateDevice(match[0]))
    else:
        cam = pylon.InstantCamera(tl.CreateFirstDevice())
    cam.Open()
    return cam


def main() -> int:
    p = argparse.ArgumentParser(description="Basler → stdout raw video bridge.")
    p.add_argument("serial", nargs="?", default=None,
                   help="Camera serial (omit to grab first device)")
    p.add_argument("--geometry", type=_parse_geometry, default="1920x1080@60",
                   help="Frame geometry as WxH@fps (default 1920x1080@60)")
    p.add_argument("--pixel-format", choices=("bgr", "uyvy"),
                   default="bgr",
                   help="Output raw pixel format on stdout (default bgr for "
                        "backward compat). 'uyvy' switches the camera itself "
                        "to native YCbCr422_8 output (2 B/px, packed UYVY) "
                        "and skips pylon's ImageFormatConverter entirely. "
                        "That's the fastest path: sensor debayer + colour "
                        "convert both happen in the camera FPGA, and the "
                        "downstream pipeline uses `vapostproc` (iGPU media "
                        "engine, ~1 ms) for UYVY\u2192NV12 instead of software "
                        "`videoconvert` (~19 ms). NV12 and converter-based "
                        "YUY2 modes were removed \u2014 pylon's converter can "
                        "only output RGB/BGR/Mono for Bayer-native models "
                        "like acA1920-150uc.")
    args = p.parse_args()
    w, h, fps = args.geometry if isinstance(args.geometry, tuple) \
        else _parse_geometry(args.geometry)

    cam = _open_camera(args.serial)

    # Configure resolution + fps. Not every model exposes all of these; guard
    # via try/except because pypylon's __getattr__ calls GetNode() under the
    # hood — a missing GenICam node raises LogicalErrorException, so
    # `hasattr(cam, node)` never returns False.
    def _try_set(node: str, value):
        try:
            getattr(cam, node).SetValue(value)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[basler_reader] warn: cannot set {node}={value}: {e.__class__.__name__}\n")

    _try_set("Width",  w)
    _try_set("Height", h)
    _try_set("AcquisitionFrameRateEnable", True)
    _try_set("AcquisitionFrameRate", float(fps))
    # Some ace-U models expose the older AcquisitionFrameRateAbs.
    _try_set("AcquisitionFrameRateAbs", float(fps))
    # Keep exposure short so we don't cap fps under office lighting.
    #
    # `ExposureAuto=Continuous` on its own is NOT enough: Basler's driver
    # default for `AutoExposureTimeUpperLimit` is 500 000 µs (0.5 s), which
    # caps sensor output at 2 fps in dim scenes. Any exposure > 1/fps forces
    # the sensor below the target frame rate. Cap the upper limit at ~1/(2·fps)
    # so auto-exposure can still adapt but never drags us below target.
    # In an actual endoscopy setting the scope has its own light source and
    # exposure will always be short (µs range) — this cap only matters for
    # bench/demo use where the camera is pointed at ambient office lighting.
    max_exposure_us = max(1000, int(1_000_000 / (fps * 2)))  # ≈ 8 333 µs @60 fps
    _try_set("ExposureAuto", "Continuous")
    _try_set("AutoExposureTimeUpperLimit",     max_exposure_us)  # SFNC 2.x
    _try_set("AutoExposureTimeAbsUpperLimit",  max_exposure_us)  # legacy alias
    sys.stderr.write(
        f"[basler_reader] target fps={fps} → AutoExposureTimeUpperLimit "
        f"capped at {max_exposure_us} µs (≈ 1/{1_000_000 // max_exposure_us} s)\n"
    )

    # Output pixel format. Two paths:
    #
    #   --pixel-format bgr   (default, backward-compat)
    #     Camera stays on its BayerBG8 default. `ImageFormatConverter` runs
    #     a debayer + BGR8 pack in the pylon runtime (SIMD, ~2 ms). Downstream
    #     pipeline uses `rawvideoparse format=bgr ! videoconvert` (or
    #     `vapostproc`) to reach NV12 for gvadetect. 3 B/px on the wire.
    #
    #   --pixel-format uyvy  (fastest — recommended when supported)
    #     Camera is switched to native `YCbCr422_8` — the sensor FPGA does
    #     debayer + YUV422 pack internally, and we write the raw grabbed
    #     buffer straight to stdout (no ImageFormatConverter). Byte layout
    #     is UYVY (Cb Y0 Cr Y1), 2 B/px. Downstream pipeline uses
    #     `rawvideoparse format=uyvy ! vapostproc ! ...NV12` (VA hardware
    #     colour convert on iGPU media engine, ~1 ms) instead of the ~19 ms
    #     software `videoconvert`. Requires that the camera advertises
    #     YCbCr422_8 in its PixelFormat symbolics — we validate that up
    #     front and exit non-zero otherwise so the pipeline can never
    #     silently mis-align the blocksize.
    use_converter = args.pixel_format == "bgr"
    if args.pixel_format == "uyvy":
        symbolics = list(cam.PixelFormat.GetSymbolics())
        if "YCbCr422_8" not in symbolics:
            sys.stderr.write(
                f"[basler_reader] camera does not advertise YCbCr422_8 in its "
                f"PixelFormat symbolics ({symbolics}); refusing to fall back "
                f"(would misalign pipeline). Use --pixel-format bgr instead.\n"
            )
            sys.exit(4)
        cam.PixelFormat.SetValue("YCbCr422_8")
        bytes_per_px = 2
        sys.stderr.write(
            f"[basler_reader] output format = camera-native YCbCr422_8 "
            f"(UYVY, {bytes_per_px} B/px, blocksize={int(w*h*bytes_per_px)})\n"
        )
        converter = None
    else:
        # bgr — go through pylon's software converter.
        bytes_per_px = 3
        converter = pylon.ImageFormatConverter()
        converter.OutputPixelFormat = pylon.PixelType_BGR8packed
        converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned
        sys.stderr.write(
            f"[basler_reader] output format = PixelType_BGR8packed "
            f"({bytes_per_px} B/px, blocksize={int(w*h*bytes_per_px)})\n"
        )

    stop = {"flag": False}
    signal.signal(signal.SIGTERM, lambda *_: stop.update(flag=True))
    signal.signal(signal.SIGINT,  lambda *_: stop.update(flag=True))
    # If gst-launch dies (SIGPIPE), we quietly exit instead of crashing.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    cam.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
    sys.stderr.write(
        f"[basler_reader] grabbing {w}x{h}@{fps} from "
        f"{cam.GetDeviceInfo().GetModelName()} sn="
        f"{cam.GetDeviceInfo().GetSerialNumber()}\n"
    )

    frames = 0
    t0 = time.time()
    try:
        while cam.IsGrabbing() and not stop["flag"]:
            res = cam.RetrieveResult(1000, pylon.TimeoutHandling_ThrowException)
            if not res.GrabSucceeded():
                sys.stderr.write(
                    f"[basler_reader] grab failed: {res.ErrorCode} {res.ErrorDescription}\n"
                )
                res.Release()
                continue
            if use_converter:
                img = converter.Convert(res)
                # `GetBuffer()` returns bytes/bytearray of packed BGR pixels.
                sys.stdout.buffer.write(img.GetBuffer())
                img.Release()
            else:
                # Camera is already emitting the target pixel format; write
                # the raw grabbed buffer straight through (UYVY packed).
                sys.stdout.buffer.write(res.GetBuffer())
            sys.stdout.buffer.flush()
            res.Release()
            frames += 1
            # Log every ~2s so `docker logs` gives operator feedback.
            if frames % max(1, fps * 2) == 0:
                dt = time.time() - t0
                sys.stderr.write(
                    f"[basler_reader] {frames} frames in {dt:.1f}s "
                    f"= {frames/dt:.1f} fps\n"
                )
    except BrokenPipeError:
        # gst-launch closed stdin — normal shutdown path.
        pass
    finally:
        try:
            cam.StopGrabbing()
        finally:
            cam.Close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

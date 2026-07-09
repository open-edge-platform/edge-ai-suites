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
    p = argparse.ArgumentParser(description="Basler → stdout raw BGR bridge.")
    p.add_argument("serial", nargs="?", default=None,
                   help="Camera serial (omit to grab first device)")
    p.add_argument("--geometry", type=_parse_geometry, default="1920x1080@60",
                   help="Frame geometry as WxH@fps (default 1920x1080@60)")
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
    _try_set("ExposureAuto", "Continuous")

    # BGR8 output so the downstream `rawvideoparse format=bgr` is a straight copy.
    converter = pylon.ImageFormatConverter()
    converter.OutputPixelFormat = pylon.PixelType_BGR8packed
    converter.OutputBitAlignment = pylon.OutputBitAlignment_MsbAligned

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
            img = converter.Convert(res)
            # `GetBuffer()` returns bytes/bytearray of BGR packed pixels.
            sys.stdout.buffer.write(img.GetBuffer())
            sys.stdout.buffer.flush()
            img.Release()
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

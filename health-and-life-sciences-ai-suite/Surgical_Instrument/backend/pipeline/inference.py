"""OpenVINO IR inference — two entry points:

* :func:`run_batch_annotated` — POC-style: reads a video, writes an annotated
  MP4 + per-frame CSV. Used by ``backend/main_infer.py`` for standalone
  verification.
* :class:`InferenceWorker` — background thread for the Flask backend. Pulls
  frames from a video source, runs YOLO, and exposes the latest annotated
  JPEG + detection payload for the UI (/api/frame + /api/stream SSE).

Ported from poc/st2_app/pipeline/dls_pipeline.py.
"""
from __future__ import annotations

import csv
import threading
import time
from collections import deque
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# NB: importing ultralytics is expensive (~1 s + pulls torch); the backend
# server must not import this module until it actually needs to run inference.
from ultralytics import YOLO


STAGES = ("decode", "upscale", "infer", "annotate", "write", "total")


def _device_str(device: str) -> str:
    m = {"cpu": "intel:cpu", "gpu": "intel:gpu", "npu": "intel:npu"}
    if device not in m:
        raise ValueError(f"unknown device: {device!r} (want cpu|gpu|npu)")
    return m[device]


def _stats(name: str, arr: np.ndarray) -> dict:
    if arr.size == 0:
        return {f"{name}_{k}_ms": 0.0 for k in ("mean", "p50", "p95", "p99", "max")}
    return {
        f"{name}_mean_ms": float(arr.mean()),
        f"{name}_p50_ms": float(np.percentile(arr, 50)),
        f"{name}_p95_ms": float(np.percentile(arr, 95)),
        f"{name}_p99_ms": float(np.percentile(arr, 99)),
        f"{name}_max_ms": float(arr.max()),
    }


# ---------------------------------------------------------------------------
# Batch (CLI) entry point — POC verbatim behavior
# ---------------------------------------------------------------------------


def run_batch_annotated(
    ir_dir: Path,
    video_in: Path,
    device: str,
    out_video: Path,
    out_csv: Path,
    output_size: tuple[int, int] = (1920, 1080),
    infer_size: int = 640,
    target_fps: float = 60.0,
    warmup_frames: int = 5,
    annotate: bool = True,
) -> dict:
    ir_dir = Path(ir_dir)
    video_in = Path(video_in)
    out_video = Path(out_video)
    out_csv = Path(out_csv)
    out_video.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    dev = _device_str(device)
    tick_s = 1.0 / target_fps
    tick_ms = tick_s * 1000.0

    print(f"[pipeline] model={ir_dir.name} device={dev} target={target_fps}fps "
          f"output={output_size} infer={infer_size} annotate={annotate}")

    model = YOLO(str(ir_dir))

    dummy = np.zeros((infer_size, infer_size, 3), dtype=np.uint8)
    for _ in range(warmup_frames):
        model(dummy, device=dev, verbose=False)

    cap = cv2.VideoCapture(str(video_in))
    if not cap.isOpened():
        raise RuntimeError(f"failed to open {video_in}")
    src_n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    writer = None
    if annotate:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(out_video), fourcc, target_fps, output_size)

    t_decode: list[float] = []
    t_upscale: list[float] = []
    t_infer: list[float] = []
    t_annotate: list[float] = []
    t_write: list[float] = []
    t_total: list[float] = []
    slack: list[float] = []
    n_dets: list[int] = []
    over: list[int] = []

    wall_t0 = time.perf_counter()
    next_deadline = wall_t0
    i = 0

    while True:
        frame_start = time.perf_counter()

        t0 = time.perf_counter()
        ok, frame = cap.read()
        t1 = time.perf_counter()
        if not ok:
            break
        td = (t1 - t0) * 1000.0

        frame_1080 = cv2.resize(frame, output_size)
        t2 = time.perf_counter()
        tu = (t2 - t1) * 1000.0

        results = model(frame_1080, device=dev, verbose=False, imgsz=infer_size)
        t3 = time.perf_counter()
        ti = (t3 - t2) * 1000.0

        r0 = results[0]
        nd = 0 if r0.boxes is None else len(r0.boxes)

        ta = 0.0
        tw = 0.0
        if annotate:
            annotated = r0.plot()
            t4 = time.perf_counter()
            ta = (t4 - t3) * 1000.0
            writer.write(annotated)
            t5 = time.perf_counter()
            tw = (t5 - t4) * 1000.0

        tt = (time.perf_counter() - frame_start) * 1000.0

        t_decode.append(td); t_upscale.append(tu); t_infer.append(ti)
        t_annotate.append(ta); t_write.append(tw); t_total.append(tt); n_dets.append(nd)

        next_deadline += tick_s
        slack_s = next_deadline - time.perf_counter()
        slack.append(slack_s * 1000.0)
        if slack_s > 0:
            time.sleep(slack_s)
            over.append(0)
        else:
            over.append(1)
            next_deadline = time.perf_counter()
        i += 1

    wall_total = time.perf_counter() - wall_t0
    cap.release()
    if writer is not None:
        writer.release()

    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "decode_ms", "upscale_ms", "infer_ms", "annotate_ms",
                    "write_ms", "total_ms", "slack_ms", "n_dets", "over_budget"])
        for idx, (d, u, ii, a, ww, tt, s, nd_, ov) in enumerate(
            zip(t_decode, t_upscale, t_infer, t_annotate, t_write, t_total, slack, n_dets, over),
            start=1,
        ):
            w.writerow([idx, f"{d:.3f}", f"{u:.3f}", f"{ii:.3f}", f"{a:.3f}",
                        f"{ww:.3f}", f"{tt:.3f}", f"{s:.3f}", nd_, ov])

    a_dec = np.array(t_decode); a_up = np.array(t_upscale); a_inf = np.array(t_infer)
    a_ann = np.array(t_annotate); a_wr = np.array(t_write); a_tot = np.array(t_total)

    delivered_fps = i / wall_total if wall_total > 0 else 0.0
    missed = int(sum(over))
    missed_pct = 100.0 * missed / i if i else 0.0
    overhead_mean = float(a_tot.mean() - a_inf.mean()) if i else 0.0

    verdict = "PASS" if missed_pct <= 2.0 else ("MARGINAL" if missed_pct <= 10.0 else "MISS")

    stats: dict = {
        "frames": i, "src_frames": src_n, "wall_s": wall_total,
        "delivered_fps": delivered_fps, "target_fps": target_fps, "tick_ms": tick_ms,
        "annotated": annotate, "missed_ticks": missed, "missed_pct": missed_pct,
        "overhead_mean_ms": overhead_mean, "verdict": verdict,
        "video": str(out_video), "csv": str(out_csv),
    }
    stats.update(_stats("decode", a_dec)); stats.update(_stats("upscale", a_up))
    stats.update(_stats("infer", a_inf)); stats.update(_stats("annotate", a_ann))
    stats.update(_stats("write", a_wr)); stats.update(_stats("total", a_tot))

    print(f"[pipeline] {i} frames in {wall_total:.2f}s | delivered {delivered_fps:.2f} fps "
          f"| infer mean {stats['infer_mean_ms']:.2f} ms (max {stats['infer_max_ms']:.2f}) "
          f"| total mean {stats['total_mean_ms']:.2f} ms (max {stats['total_max_ms']:.2f}) "
          f"| overhead {overhead_mean:+.2f} ms | missed {missed}/{i} ({missed_pct:.1f}%) → {verdict}")
    return stats


# ---------------------------------------------------------------------------
# Streaming worker for the Flask backend
# ---------------------------------------------------------------------------


class InferenceWorker:
    """Background thread that runs YOLO on a looping video source.

    Consumers pull the latest annotated JPEG via :meth:`latest_frame_jpeg` and
    the latest detection payload via :meth:`latest_detections`. Both are safe
    to call from any thread.

    The worker loops the video file when EOF is reached so the UI has a
    continuous stream during demos.
    """

    def __init__(
        self,
        ir_dir: str | Path,
        video_src: str | int,
        device: str = "gpu",
        target_fps: float = 30.0,
        output_size: tuple[int, int] = (1920, 1080),
        infer_size: int = 640,
        warmup_frames: int = 5,
        annotate: bool = True,
        jpeg_quality: int = 80,
        tracker: str = "bytetrack.yaml",
        min_track_len: int = 5,
    ):
        self.ir_dir = str(ir_dir)
        self.video_src = video_src
        self.device = device
        self.target_fps = float(target_fps)
        self.output_size = tuple(output_size)
        self.infer_size = int(infer_size)
        self.warmup_frames = int(warmup_frames)
        self.annotate = bool(annotate)
        self.jpeg_quality = int(jpeg_quality)
        self.tracker = str(tracker)
        self.min_track_len = int(min_track_len)

        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._latest_jpeg: Optional[bytes] = None
        self._latest_dets: dict = {"detections": [], "frame_id": 0, "ts": 0.0}
        self._frame_id = 0
        self._start_time = 0.0
        self._recent_latencies: deque[float] = deque(maxlen=120)
        self._recent_infer_ms: deque[float] = deque(maxlen=120)
        self._frames_with_detection = 0
        self._cumulative_detections = 0
        self._peak_confidence = 0.0
        # track_id -> frames seen. distinct_polyps = count of tracks with >= min_track_len frames.
        self._track_frame_counts: dict[int, int] = {}
        self._error: Optional[str] = None

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="inference", daemon=True)
        self._start_time = time.perf_counter()
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    def is_running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    # -- consumer API --------------------------------------------------------

    def latest_frame_jpeg(self) -> Optional[bytes]:
        with self._lock:
            return self._latest_jpeg

    def latest_detections(self) -> dict:
        with self._lock:
            return dict(self._latest_dets)

    def stats(self) -> dict:
        with self._lock:
            wall = time.perf_counter() - self._start_time if self._start_time else 0.0
            fps = (self._frame_id / wall) if wall > 0 else 0.0
            infer_arr = np.fromiter(self._recent_infer_ms, dtype=float) if self._recent_infer_ms else None
            total_arr = np.fromiter(self._recent_latencies, dtype=float) if self._recent_latencies else None
            detection_rate = (self._frames_with_detection / self._frame_id) if self._frame_id > 0 else 0.0
            distinct_polyps = sum(1 for c in self._track_frame_counts.values() if c >= self.min_track_len)
            return {
                "running": self.is_running(),
                "frame_id": self._frame_id,
                "delivered_fps": fps,
                "target_fps": self.target_fps,
                "infer_mean_ms": float(infer_arr.mean()) if infer_arr is not None else 0.0,
                "infer_p95_ms":  float(np.percentile(infer_arr, 95)) if infer_arr is not None else 0.0,
                "infer_p99_ms":  float(np.percentile(infer_arr, 99)) if infer_arr is not None else 0.0,
                "total_mean_ms": float(total_arr.mean()) if total_arr is not None else 0.0,
                "total_p95_ms":  float(np.percentile(total_arr, 95)) if total_arr is not None else 0.0,
                "total_p99_ms":  float(np.percentile(total_arr, 99)) if total_arr is not None else 0.0,
                "uptime_s": wall,
                "frames_with_detection": self._frames_with_detection,
                "cumulative_detections": self._cumulative_detections,
                "detection_rate": detection_rate,
                "peak_confidence": self._peak_confidence,
                "distinct_polyps": distinct_polyps,
                "device": self.device,
                "error": self._error,
            }

    # -- loop ----------------------------------------------------------------

    def _open_capture(self) -> cv2.VideoCapture:
        src = self.video_src
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        cap = cv2.VideoCapture(src)
        if not cap.isOpened():
            raise RuntimeError(f"failed to open video source: {self.video_src!r}")
        return cap

    def _run(self) -> None:
        try:
            dev = _device_str(self.device)
            model = YOLO(self.ir_dir)
            dummy = np.zeros((self.infer_size, self.infer_size, 3), dtype=np.uint8)
            for _ in range(self.warmup_frames):
                model(dummy, device=dev, verbose=False)

            cap = self._open_capture()
            tick_s = 1.0 / self.target_fps
            next_deadline = time.perf_counter()
            jpeg_params = [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]

            while not self._stop.is_set():
                frame_start = time.perf_counter()

                ok, frame = cap.read()
                if not ok:
                    # loop the video file
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError("video source exhausted and cannot rewind")

                frame_out = cv2.resize(frame, self.output_size)

                t_i0 = time.perf_counter()
                results = model.track(
                    frame_out,
                    device=dev,
                    verbose=False,
                    imgsz=self.infer_size,
                    persist=True,
                    tracker=self.tracker,
                )
                t_i1 = time.perf_counter()
                infer_ms = (t_i1 - t_i0) * 1000.0

                r0 = results[0]
                dets = self._serialize_detections(r0)

                display = r0.plot() if self.annotate else frame_out
                ok_enc, buf = cv2.imencode(".jpg", display, jpeg_params)
                jpeg = buf.tobytes() if ok_enc else None

                total_ms = (time.perf_counter() - frame_start) * 1000.0
                self._frame_id += 1

                with self._lock:
                    if jpeg is not None:
                        self._latest_jpeg = jpeg
                    self._latest_dets = {
                        "frame_id": self._frame_id,
                        "ts": time.time(),
                        "detections": dets,
                        "infer_ms": infer_ms,
                        "total_ms": total_ms,
                    }
                    self._recent_latencies.append(total_ms)
                    self._recent_infer_ms.append(infer_ms)
                    polyp_dets = [d for d in dets if str(d.get("class_name", "")).lower() == "polyp"]
                    if polyp_dets:
                        self._frames_with_detection += 1
                        self._cumulative_detections += len(polyp_dets)
                        top = max(float(d.get("confidence", 0.0)) for d in polyp_dets)
                        if top > self._peak_confidence:
                            self._peak_confidence = top
                        for d in polyp_dets:
                            tid = d.get("track_id")
                            if tid is not None:
                                self._track_frame_counts[int(tid)] = self._track_frame_counts.get(int(tid), 0) + 1

                next_deadline += tick_s
                slack = next_deadline - time.perf_counter()
                if slack > 0:
                    self._stop.wait(timeout=slack)
                else:
                    next_deadline = time.perf_counter()

            cap.release()
        except Exception as exc:  # noqa: BLE001
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _serialize_detections(r0) -> list[dict]:
        if r0.boxes is None or len(r0.boxes) == 0:
            return []
        boxes = r0.boxes
        xyxy = boxes.xyxy.cpu().numpy() if hasattr(boxes.xyxy, "cpu") else np.asarray(boxes.xyxy)
        conf = boxes.conf.cpu().numpy() if hasattr(boxes.conf, "cpu") else np.asarray(boxes.conf)
        cls = boxes.cls.cpu().numpy() if hasattr(boxes.cls, "cpu") else np.asarray(boxes.cls)
        ids = None
        if getattr(boxes, "id", None) is not None:
            ids = boxes.id.cpu().numpy() if hasattr(boxes.id, "cpu") else np.asarray(boxes.id)
        names = getattr(r0, "names", {}) or {}
        out = []
        for i in range(len(boxes)):
            cid = int(cls[i])
            item = {
                "class_id": cid,
                "class_name": names.get(cid, str(cid)),
                "confidence": float(conf[i]),
                "bbox": [float(x) for x in xyxy[i].tolist()],  # [x1,y1,x2,y2]
            }
            if ids is not None:
                item["track_id"] = int(ids[i])
            out.append(item)
        return out

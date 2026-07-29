"""Ego/LiDAR coordinate 3D detection evaluation (CPU, runnable).

Inputs:
  - One txt file per frame in GT folder and pred folder, with KITTI label columns:
    type truncated occluded alpha bbox(4) dims(h,w,l) loc(x,y,z) ry [score]

This script:
    - Greedy 1:1 matching (per frame), global score-sorted PR.
    - Computes AP11 + AP40 for 3D IoU only (no 2D bbox in pred).
    - Filters GT (and optionally pred) by distance along a chosen axis (default: x <= 102.4m).
    - Handles class name mapping between GT and pred taxonomies.
    - Writes CSV + JSON summaries and saves PR curve PNGs (if matplotlib available).
"""

import argparse
import csv
import json
import math
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple, Callable

import numpy as np


def _lazy_import_matplotlib_pyplot():
    try:
        import matplotlib.pyplot as plt  # type: ignore

        return plt
    except Exception:
        return None


# --------------------------
# Class mapping (override-able)
# --------------------------

DEFAULT_GT_CLASS_MAP: Dict[str, str] = {
    # Vehicles
    "car": "Car",
    "truck": "Truck",
    "van": "Van",
    "bus": "Bus",
    # Humans / riders
    "pedestrian": "Pedestrian",
    "cyclist": "Cyclist",
    "tricyclist": "Tricyclist",
    "motorcyclist": "Motorcyclist",
    # Others
    "barrowlist": "Barrowlist",
    "trafficcone": "Trafficcone",
    "dontcare": "DontCare",
}


DEFAULT_PRED_CLASS_MAP: Dict[str, str] = {
    "car": "Car",
    "truck": "Truck",
    "construction_vehicle": "Truck",
    "trailer": "Truck",
    "bus": "Bus",
    "pedestrian": "Pedestrian",
    "bicycle": "Cyclist",
    "motorcycle": "Motorcyclist",
    "traffic_cone": "Trafficcone",
    "barrier": "Other",
}


DEFAULT_EVAL_CLASSES: List[str] = [
    "Car",
    "Truck",
    "Van",
    "Bus",
    "Pedestrian",
    "Cyclist",
    "Tricyclist",
    "Motorcyclist",
    "Barrowlist",
    "Trafficcone",
    "Other",
]


DEFAULT_IOU_THRESHOLDS: Dict[str, Dict[str, float]] = {
    # metric -> class -> threshold (3D only)
    "3d": {
        "Car": 0.5,
        "Truck": 0.5,
        "Van": 0.5,
        "Bus": 0.5,
        "Pedestrian": 0.3,
        "Cyclist": 0.3,
        "Tricyclist": 0.3,
        "Motorcyclist": 0.3,
        "Barrowlist": 0.25,
        "Trafficcone": 0.25,
        "Other": 0.25,
    },
}


# KITTI-like difficulty presets (used only if you enable difficulty filtering)
KITTI_MIN_BBOX_HEIGHT = {"easy": 40.0, "moderate": 25.0, "hard": 25.0}
KITTI_MAX_OCCLUSION = {"easy": 0, "moderate": 1, "hard": 2}
KITTI_MAX_TRUNCATION = {"easy": 0.15, "moderate": 0.3, "hard": 0.5}


def _wrap_pi(x: float) -> float:
    while x > math.pi:
        x -= 2 * math.pi
    while x < -math.pi:
        x += 2 * math.pi
    return x


@dataclass
class KittiLabel:
    cls: str  # mapped
    cls_raw: str
    truncated: float
    occluded: int
    alpha: float
    bbox: np.ndarray  # (4,) l,t,r,b
    hwl: np.ndarray  # (3,) h,w,l
    xyz: np.ndarray  # (3,) x,y,z (camera)
    ry: float
    score: float

    @property
    def z(self) -> float:
        return float(self.xyz[2])

    @property
    def x(self) -> float:
        return float(self.xyz[0])

    @property
    def y(self) -> float:
        return float(self.xyz[1])

    @property
    def h(self) -> float:
        return float(self.hwl[0])

    @property
    def w(self) -> float:
        return float(self.hwl[1])

    @property
    def l(self) -> float:
        return float(self.hwl[2])


def _compute_alpha_from_ry_and_xyz(ry: float, x: float, z: float) -> float:
    # Kept for compatibility; not used by default in ego/velo evaluation.
    return _wrap_pi(ry - math.atan2(x, z))


def _parse_label_line(
    line: str,
    is_pred: bool,
    class_map: Dict[str, str],
    keep_unmapped_as_other: bool,
) -> Optional[KittiLabel]:
    it = line.strip().split()
    if not it:
        return None
    if len(it) < 15:
        return None

    cls_raw = it[0]
    mapped = class_map.get(cls_raw.lower())
    if mapped is None:
        if keep_unmapped_as_other:
            mapped = "Other"
        else:
            return None

    truncated = float(it[1])
    occluded = int(float(it[2]))
    alpha = float(it[3])
    bbox = np.array(list(map(float, it[4:8])), dtype=np.float32)
    hwl = np.array(list(map(float, it[8:11])), dtype=np.float32)
    xyz = np.array(list(map(float, it[11:14])), dtype=np.float32)
    ry = float(it[14])
    score = float(it[15]) if (is_pred and len(it) >= 16) else 1.0

    return KittiLabel(
        cls=mapped,
        cls_raw=cls_raw,
        truncated=truncated,
        occluded=occluded,
        alpha=alpha,
        bbox=bbox,
        hwl=hwl,
        xyz=xyz,
        ry=ry,
        score=score,
    )


def load_kitti_txt(
    path: str,
    is_pred: bool,
    class_map: Dict[str, str],
    keep_unmapped_as_other: bool,
    recompute_alpha: bool,
    transform: Optional[Callable[["KittiLabel"], None]] = None,
) -> List[KittiLabel]:
    if not os.path.exists(path):
        return []
    labels: List[KittiLabel] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            lb = _parse_label_line(
                line,
                is_pred=is_pred,
                class_map=class_map,
                keep_unmapped_as_other=keep_unmapped_as_other,
            )
            if lb is None:
                continue
            if recompute_alpha:
                lb.alpha = _compute_alpha_from_ry_and_xyz(lb.ry, lb.x, lb.z)
            if transform is not None:
                transform(lb)
            labels.append(lb)
    return labels


def _apply_flip_y(label: KittiLabel) -> None:
    label.xyz[1] = -label.xyz[1]
    label.ry = _wrap_pi(-label.ry)


def _apply_z_center_to_bottom(label: KittiLabel) -> None:
    # If z is center-height, convert to bottom-height for IoU.
    label.xyz[2] = label.xyz[2] - 0.5 * label.h


def _make_transform(flip_y: bool, z_center: bool) -> Callable[[KittiLabel], None]:
    def _t(label: KittiLabel) -> None:
        if flip_y:
            _apply_flip_y(label)
        if z_center:
            _apply_z_center_to_bottom(label)

    return _t


# --------------------------
# IoU implementations
# --------------------------


def _bev_corners_xy(label: KittiLabel) -> np.ndarray:
    # Ego/LiDAR frame: x forward, y left, z up. Yaw rotates around +z.
    c, s = math.cos(label.ry), math.sin(label.ry)
    dx, dy = label.l / 2.0, label.w / 2.0
    corners = np.array([[dx, dy], [dx, -dy], [-dx, -dy], [-dx, dy]], dtype=np.float32)
    rot = np.array([[c, -s], [s, c]], dtype=np.float32)
    corners = corners @ rot.T
    corners[:, 0] += label.x
    corners[:, 1] += label.y
    return corners


def _cross2d(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _is_inside(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> bool:
    """Inside test for clockwise clip polygon: point is inside if to the right of edge a->b."""
    return _cross2d(b - a, p - a) <= 1e-9


def _line_intersection(p1: np.ndarray, p2: np.ndarray, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
    """Intersection of infinite lines (p1,p2) and (q1,q2). Assumes they are not parallel."""
    r = p2 - p1
    s = q2 - q1
    denom = _cross2d(r, s)
    if abs(denom) < 1e-12:
        return p2
    t = _cross2d(q1 - p1, s) / denom
    return p1 + t * r


def _polygon_clip(subject: np.ndarray, clip: np.ndarray) -> np.ndarray:
    """Sutherland–Hodgman polygon clipping for convex polygons.

    subject: (N,2) polygon (clockwise)
    clip: (M,2) polygon (clockwise)
    returns: (K,2) intersection polygon vertices (clockwise)
    """
    output = subject
    if output.size == 0:
        return output
    for i in range(clip.shape[0]):
        cp1 = clip[i]
        cp2 = clip[(i + 1) % clip.shape[0]]
        input_list = output
        if input_list.size == 0:
            break
        out_list: List[np.ndarray] = []
        s = input_list[-1]
        for e in input_list:
            if _is_inside(e, cp1, cp2):
                if not _is_inside(s, cp1, cp2):
                    out_list.append(_line_intersection(s, e, cp1, cp2))
                out_list.append(e)
            elif _is_inside(s, cp1, cp2):
                out_list.append(_line_intersection(s, e, cp1, cp2))
            s = e
        if out_list:
            output = np.stack(out_list, axis=0).astype(np.float32)
        else:
            output = np.zeros((0, 2), dtype=np.float32)
    return output


def _polygon_area(poly: np.ndarray) -> float:
    if poly.shape[0] < 3:
        return 0.0
    x = poly[:, 0]
    y = poly[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def iou_3d(a: KittiLabel, b: KittiLabel) -> float:
    ca = _bev_corners_xy(a)
    cb = _bev_corners_xy(b)
    inter_poly = _polygon_clip(ca, cb)
    inter_area = _polygon_area(inter_poly)
    if inter_area <= 0.0:
        return 0.0

    # ego coordinates: z up; location z is bottom center in this project
    a_zmin, a_zmax = a.z, a.z + a.h
    b_zmin, b_zmax = b.z, b.z + b.h
    inter_h = max(0.0, min(a_zmax, b_zmax) - max(a_zmin, b_zmin))
    if inter_h <= 0:
        return 0.0

    inter_vol = inter_area * inter_h
    vol_a = float(a.l * a.w * a.h)
    vol_b = float(b.l * b.w * b.h)
    union = vol_a + vol_b - inter_vol
    return float(inter_vol / union) if union > 0 else 0.0


def _select_iou_fn(metric: str):
    if metric == "3d":
        return iou_3d
    raise ValueError(f"Unknown metric: {metric}")


# --------------------------
# Filtering (distance / difficulty)
# --------------------------


def _passes_difficulty(gt: KittiLabel, difficulty: str) -> bool:
    if difficulty == "all":
        return True
    bbox_h = float(gt.bbox[3] - gt.bbox[1])
    if bbox_h <= KITTI_MIN_BBOX_HEIGHT[difficulty]:
        return False
    if gt.occluded > KITTI_MAX_OCCLUSION[difficulty]:
        return False
    if gt.truncated > KITTI_MAX_TRUNCATION[difficulty]:
        return False
    return True


def _filter_labels(
    labels: Iterable[KittiLabel],
    *,
    allowed_classes: Optional[set],
    max_distance: Optional[float],
    distance_min: Optional[float] = None,
    distance_max: Optional[float] = None,
    difficulty: str = "all",
    is_gt: bool,
    distance_axis: str = "x",
) -> List[KittiLabel]:
    out: List[KittiLabel] = []
    for lb in labels:
        dist_val = lb.x if distance_axis == "x" else (lb.y if distance_axis == "y" else lb.z)
        if allowed_classes is not None and lb.cls not in allowed_classes:
            continue
        if max_distance is not None and dist_val > max_distance:
            continue
        if distance_min is not None and dist_val < distance_min:
            continue
        if distance_max is not None and dist_val >= distance_max:
            continue
        if is_gt and not _passes_difficulty(lb, difficulty):
            continue
        out.append(lb)
    return out


# --------------------------
# Matching + stats
# --------------------------


@dataclass
class MatchStats:
    scores: List[float]
    is_tp: List[int]
    sim: List[float]  # orientation similarity for TP, else 0
    num_gt: int
    num_pred: int
    # extra TP error stats (computed for default IoU only)
    tp_center_dist: List[float]
    tp_yaw_err: List[float]
    tp_size_err: List[Tuple[float, float, float]]


def _orientation_similarity(alpha_gt: float, alpha_dt: float) -> float:
    da = _wrap_pi(alpha_dt - alpha_gt)
    return float((1.0 + math.cos(da)) / 2.0)


def match_frame_greedy(
    gt_labels: List[KittiLabel],
    dt_labels: List[KittiLabel],
    *,
    cls: str,
    metric: str,
    iou_thr: float,
    max_distance: Optional[float],
    filter_dt_by_distance: bool,
    difficulty: str,
    distance_bin: Optional[Tuple[float, float]] = None,
    distance_axis: str = "x",
) -> Tuple[List[Tuple[float, int, float, Optional[Tuple[float, float, float]]]], int, int]:
    """Return per-detection records + num_gt + num_pred.

    record = (score, is_tp, similarity, extra_errors)
      - similarity used for AOS; for FP it's 0
      - extra_errors is (center_dist, yaw_err, size_err_l2?) only when TP
    """
    allowed = {cls}
    dmin, dmax = (distance_bin if distance_bin is not None else (None, None))

    gt = _filter_labels(
        gt_labels,
        allowed_classes=allowed,
        max_distance=max_distance,
        distance_min=dmin,
        distance_max=dmax,
        difficulty=difficulty,
        is_gt=True,
        distance_axis=distance_axis,
    )
    dt = _filter_labels(
        dt_labels,
        allowed_classes=allowed,
        max_distance=max_distance if filter_dt_by_distance else None,
        # For per-distance-bin metrics, always restrict detections to that bin.
        # For "all" bin, only restrict detections if filter_dt_by_distance is enabled.
        distance_min=dmin if (distance_bin is not None or filter_dt_by_distance) else None,
        distance_max=dmax if (distance_bin is not None or filter_dt_by_distance) else None,
        difficulty="all",
        is_gt=False,
        distance_axis=distance_axis,
    )
    num_gt = len(gt)
    num_pred = len(dt)
    if num_pred == 0:
        return [], num_gt, 0

    iou_fn = _select_iou_fn(metric)
    dt_sorted = sorted(dt, key=lambda x: (-x.score, -x.z))
    matched_gt: set = set()
    records: List[Tuple[float, int, float, Optional[Tuple[float, float, float]]]] = []

    for d in dt_sorted:
        best_iou = -1.0
        best_idx = -1
        for gi, g in enumerate(gt):
            if gi in matched_gt:
                continue
            ov = iou_fn(g, d)
            if ov > best_iou:
                best_iou = ov
                best_idx = gi
        if best_iou >= iou_thr and best_idx >= 0:
            matched_gt.add(best_idx)
            g = gt[best_idx]
            sim = _orientation_similarity(g.ry, d.ry)
            center_dist = float(np.linalg.norm(g.xyz - d.xyz))
            yaw_err = abs(_wrap_pi(d.ry - g.ry))
            size_err = float(np.linalg.norm(g.hwl - d.hwl))
            records.append((d.score, 1, sim, (center_dist, yaw_err, size_err)))
        else:
            records.append((d.score, 0, 0.0, None))
    return records, num_gt, num_pred


def _pr_from_records(
    records: List[Tuple[float, int, float, Optional[Tuple[float, float, float]]]],
    num_gt: int,
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Returns recall, precision, aos_recall, aos_precision arrays.

    aos_precision is 'orientation precision' (similarity cumulative / (tp+fp)).
    """
    if not records:
        return [], [], [], []
    scores = np.array([r[0] for r in records], dtype=np.float32)
    tps = np.array([r[1] for r in records], dtype=np.int32)
    sims = np.array([r[2] for r in records], dtype=np.float32)

    order = scores.argsort()[::-1]
    tps = tps[order]
    sims = sims[order]

    tp_cum = np.cumsum(tps)
    fp_cum = np.cumsum(1 - tps)
    denom = np.maximum(tp_cum + fp_cum, 1)

    recall = tp_cum / max(num_gt, 1)
    precision = tp_cum / denom
    sim_cum = np.cumsum(sims)
    aos_precision = sim_cum / denom
    aos_recall = recall
    return recall.tolist(), precision.tolist(), aos_recall.tolist(), aos_precision.tolist()


def _ap_from_pr(recall: List[float], precision: List[float], num_pts: int) -> float:
    if not recall:
        return 0.0
    r = np.array(recall, dtype=np.float32)
    p = np.array(precision, dtype=np.float32)
    # monotonic precision envelope
    for i in range(len(p) - 2, -1, -1):
        p[i] = max(p[i], p[i + 1])
    ts = np.linspace(0.0, 1.0, num_pts)
    ap = 0.0
    for t in ts:
        mask = r >= t
        ap += float(np.max(p[mask])) if np.any(mask) else 0.0
    return ap / float(num_pts)


def _max_f1(recall: List[float], precision: List[float]) -> Tuple[float, float, float]:
    if not recall:
        return 0.0, 0.0, 0.0
    r = np.array(recall, dtype=np.float32)
    p = np.array(precision, dtype=np.float32)
    denom = np.maximum(p + r, 1e-12)
    f1 = 2 * p * r / denom
    idx = int(np.argmax(f1))
    return float(f1[idx]), float(p[idx]), float(r[idx])


# --------------------------
# Evaluation driver
# --------------------------


def _list_frame_ids(gt_dir: str, pred_dir: str) -> List[str]:
    gt_files = {f for f in os.listdir(gt_dir) if f.endswith(".txt")}
    dt_files = {f for f in os.listdir(pred_dir) if f.endswith(".txt")}
    return sorted(gt_files | dt_files)


def _validate_prediction_format(pred_dir: str, verbose: bool = True) -> bool:
    """Validate that prediction files have the correct format including score column."""
    pred_files = [f for f in os.listdir(pred_dir) if f.endswith(".txt")]
    if not pred_files:
        return True
    
    # Check first few non-empty files
    checked = 0
    missing_scores = []
    for fname in pred_files[:5]:
        fpath = os.path.join(pred_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if not parts:
                    continue
                checked += 1
                if len(parts) < 16:
                    missing_scores.append(fname)
                break  # Only check first line of each file
    
    if missing_scores and verbose:
        print(f"WARNING: {len(missing_scores)} prediction file(s) may be missing score column (column 16).")
        print(f"  Example: {missing_scores[0]}")
        print(f"  This will cause all predictions to have score=1.0, affecting PR curve computation.")
        print(f"  Please ensure predictions include detection confidence scores.\n")
        return False
    
    return True


def _maybe_load_json(path: Optional[str]) -> Optional[dict]:
    if not path:
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate(
    gt_dir: str,
    pred_dir: str,
    out_dir: str = "eval_output",
    *,
    eval_classes: Optional[List[str]] = None,
    max_distance: float = 102.4,
    filter_dt_by_distance: bool = False,
    recompute_alpha: bool = True,
    difficulty: str = "all",
    distance_bins: Optional[List[Tuple[float, float]]] = None,
    class_map_gt: Optional[Dict[str, str]] = None,
    class_map_pred: Optional[Dict[str, str]] = None,
    iou_thresholds: Optional[Dict[str, Dict[str, float]]] = None,
    distance_axis: str = "x",
    flip_y_gt: bool = False,
    flip_y_pred: bool = False,
    z_center_gt: bool = False,
    z_center_pred: bool = False,
    verbose: bool = True,
) -> None:
    os.makedirs(out_dir, exist_ok=True)

    eval_classes = eval_classes or DEFAULT_EVAL_CLASSES
    allowed_classes = set(eval_classes)
    class_map_gt = class_map_gt or DEFAULT_GT_CLASS_MAP
    class_map_pred = class_map_pred or DEFAULT_PRED_CLASS_MAP
    iou_thresholds = iou_thresholds or DEFAULT_IOU_THRESHOLDS
    distance_bins = distance_bins or [(0.0, 30.0), (30.0, 60.0), (60.0, max_distance)]

    frames = _list_frame_ids(gt_dir, pred_dir)
    if not frames:
        raise RuntimeError(f"No .txt frames found under {gt_dir} and {pred_dir}")

    # Validate prediction format
    if verbose:
        _validate_prediction_format(pred_dir, verbose=True)

    # Aggregate per (class, metric, bin)
    agg: Dict[Tuple[str, str, str], Dict[str, object]] = {}
    for cls in eval_classes:
        for metric in ("3d",):
            agg[(cls, metric, "all")] = {
                "records": [],
                "num_gt": 0,
                "num_pred": 0,
                "tp_center_dist": [],
                "tp_yaw_err": [],
                "tp_size_err": [],
            }
            for (b0, b1) in distance_bins:
                agg[(cls, metric, f"{b0:.1f}-{b1:.1f}")] = {
                    "records": [],
                    "num_gt": 0,
                    "num_pred": 0,
                    "tp_center_dist": [],
                    "tp_yaw_err": [],
                    "tp_size_err": [],
                }

    gt_transform = _make_transform(flip_y_gt, z_center_gt)
    pred_transform = _make_transform(flip_y_pred, z_center_pred)

    if verbose:
        print(f"Evaluating {len(frames)} frames...")
        print(f"  GT dir: {gt_dir}")
        print(f"  Pred dir: {pred_dir}")
        print(f"  Classes: {', '.join(eval_classes)}")
        print(f"  Max distance ({distance_axis}): {max_distance}")
        print(f"  Distance bins: {distance_bins}")
        print()

    for i, frame in enumerate(frames):
        if verbose and (i % 10 == 0 or i == len(frames) - 1):
            print(f"  Processing: {i+1}/{len(frames)} frames...", end="\r")
        
        gt_path = os.path.join(gt_dir, frame)
        dt_path = os.path.join(pred_dir, frame)
        gt_labels = load_kitti_txt(
            gt_path,
            is_pred=False,
            class_map=class_map_gt,
            keep_unmapped_as_other=True,
            recompute_alpha=recompute_alpha,
            transform=gt_transform,
        )
        dt_labels = load_kitti_txt(
            dt_path,
            is_pred=True,
            class_map=class_map_pred,
            keep_unmapped_as_other=True,
            recompute_alpha=recompute_alpha,
            transform=pred_transform,
        )

        # remove DontCare from evaluation classes, but keep for potential future extensions
        gt_labels = [g for g in gt_labels if g.cls != "DontCare"]

        # global distance filter applied inside match
        for cls in eval_classes:
            if cls not in allowed_classes:
                continue
            for metric in ("3d",):
                thr = float(iou_thresholds[metric].get(cls, 0.5))

                records_all, n_gt_all, n_dt_all = match_frame_greedy(
                    gt_labels,
                    dt_labels,
                    cls=cls,
                    metric=metric,
                    iou_thr=thr,
                    max_distance=max_distance,
                    filter_dt_by_distance=filter_dt_by_distance,
                    difficulty=difficulty,
                    distance_bin=None,
                    distance_axis=distance_axis,
                )
                bucket = agg[(cls, metric, "all")]
                bucket["records"].extend(records_all)  # type: ignore
                bucket["num_gt"] += n_gt_all  # type: ignore
                bucket["num_pred"] += n_dt_all  # type: ignore
                for r in records_all:
                    if r[1] == 1 and r[3] is not None:
                        cd, ye, se = r[3]
                        bucket["tp_center_dist"].append(cd)  # type: ignore
                        bucket["tp_yaw_err"].append(ye)  # type: ignore
                        bucket["tp_size_err"].append(se)  # type: ignore

                for (b0, b1) in distance_bins:
                    records_bin, n_gt_bin, n_dt_bin = match_frame_greedy(
                        gt_labels,
                        dt_labels,
                        cls=cls,
                        metric=metric,
                        iou_thr=thr,
                        max_distance=max_distance,
                        filter_dt_by_distance=filter_dt_by_distance,
                        difficulty=difficulty,
                        distance_bin=(b0, b1),
                        distance_axis=distance_axis,
                    )
                    bname = f"{b0:.1f}-{b1:.1f}"
                    bucket = agg[(cls, metric, bname)]
                    bucket["records"].extend(records_bin)  # type: ignore
                    bucket["num_gt"] += n_gt_bin  # type: ignore
                    bucket["num_pred"] += n_dt_bin  # type: ignore
                    for r in records_bin:
                        if r[1] == 1 and r[3] is not None:
                            cd, ye, se = r[3]
                            bucket["tp_center_dist"].append(cd)  # type: ignore
                            bucket["tp_yaw_err"].append(ye)  # type: ignore
                            bucket["tp_size_err"].append(se)  # type: ignore

    if verbose:
        print()  # New line after progress
        print("Computing metrics...")

    # Summarize
    plt = _lazy_import_matplotlib_pyplot()
    summary: Dict[str, object] = {
        "config": {
            "gt_dir": gt_dir,
            "pred_dir": pred_dir,
            "max_distance": max_distance,
            "filter_dt_by_distance": filter_dt_by_distance,
            "difficulty": difficulty,
            "eval_classes": eval_classes,
            "distance_bins": [{"min": b0, "max": b1} for (b0, b1) in distance_bins],
            "iou_thresholds": iou_thresholds,
            "recompute_alpha": recompute_alpha,
            "distance_axis": distance_axis,
            "flip_y_gt": flip_y_gt,
            "flip_y_pred": flip_y_pred,
            "z_center_gt": z_center_gt,
            "z_center_pred": z_center_pred,
        },
        "results": {},
    }

    csv_rows: List[List[object]] = []
    csv_header = [
        "class",
        "metric",
        "distance_bin",
        "iou_thr",
        "num_gt",
        "num_pred",
        "ap11",
        "ap40",
        "max_f1",
        "precision_at_max_f1",
        "recall_at_max_f1",
        "mean_center_dist_tp",
        "mean_yaw_err_tp_rad",
        "mean_size_err_l2_tp",
    ]

    for cls in eval_classes:
        summary["results"][cls] = {}
        for metric in ("3d",):
            iou_thr = float(iou_thresholds[metric].get(cls, 0.5))
            summary["results"][cls][metric] = {}
            for bin_name in ["all"] + [f"{b0:.1f}-{b1:.1f}" for (b0, b1) in distance_bins]:
                bucket = agg[(cls, metric, bin_name)]
                records = bucket["records"]  # type: ignore
                num_gt = int(bucket["num_gt"])  # type: ignore
                num_pred = int(bucket["num_pred"])  # type: ignore
                recall, precision, aos_recall, aos_precision = _pr_from_records(records, num_gt)
                ap11 = _ap_from_pr(recall, precision, num_pts=11)
                ap40 = _ap_from_pr(recall, precision, num_pts=41)
                f1, p_at, r_at = _max_f1(recall, precision)

                tp_cd = np.array(bucket["tp_center_dist"], dtype=np.float32)  # type: ignore
                tp_ye = np.array(bucket["tp_yaw_err"], dtype=np.float32)  # type: ignore
                tp_se = np.array(bucket["tp_size_err"], dtype=np.float32)  # type: ignore
                mean_cd = float(tp_cd.mean()) if tp_cd.size else 0.0
                mean_ye = float(tp_ye.mean()) if tp_ye.size else 0.0
                mean_se = float(tp_se.mean()) if tp_se.size else 0.0

                summary["results"][cls][metric][bin_name] = {
                    "iou_thr": iou_thr,
                    "num_gt": num_gt,
                    "num_pred": num_pred,
                    "ap11": ap11,
                    "ap40": ap40,
                    "max_f1": f1,
                    "precision_at_max_f1": p_at,
                    "recall_at_max_f1": r_at,
                    "mean_center_dist_tp": mean_cd,
                    "mean_yaw_err_tp_rad": mean_ye,
                    "mean_size_err_l2_tp": mean_se,
                    "pr_curve": {
                        "recall": recall,
                        "precision": precision,
                    },
                }

                csv_rows.append(
                    [
                        cls,
                        metric,
                        bin_name,
                        iou_thr,
                        num_gt,
                        num_pred,
                        ap11,
                        ap40,
                        f1,
                        p_at,
                        r_at,
                        mean_cd,
                        mean_ye,
                        mean_se,
                    ]
                )

                # Save PR curves for "all" bin
                if plt is not None and bin_name == "all":
                    fig = plt.figure()
                    plt.plot(recall, precision, label="PR")
                    plt.xlabel("Recall")
                    plt.ylabel("Precision")
                    plt.title(f"PR Curve - {cls} ({metric})")
                    plt.grid(True)
                    plt.legend()
                    safe_cls = cls.replace("/", "_")
                    fig.savefig(os.path.join(out_dir, f"pr_{safe_cls}_{metric}.png"), dpi=150, bbox_inches="tight")
                    plt.close(fig)

    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    with open(os.path.join(out_dir, "summary.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(csv_header)
        writer.writerows(csv_rows)

    if verbose:
        print(f"\n{'='*80}")
        print(f"Evaluation Results Summary")
        print(f"{'='*80}")
        print(f"\nOverall Performance (distance: all, metric: 3d):")
        print(f"{'Class':<20} {'AP@0.5(11pt)':<15} {'AP@0.5(40pt)':<15} {'Max F1':<10}")
        print(f"{'-'*60}")
        for cls in eval_classes:
            if cls in summary["results"] and "3d" in summary["results"][cls]:
                data = summary["results"][cls]["3d"].get("all", {})
                ap11 = data.get("ap11", 0.0)
                ap40 = data.get("ap40", 0.0)
                f1 = data.get("max_f1", 0.0)
                print(f"{cls:<20} {ap11*100:>6.2f}%        {ap40*100:>6.2f}%        {f1:>6.4f}")
        
        # Compute mean AP
        ap11_values = []
        ap40_values = []
        for cls in eval_classes:
            if cls in summary["results"] and "3d" in summary["results"][cls]:
                data = summary["results"][cls]["3d"].get("all", {})
                ap11_values.append(data.get("ap11", 0.0))
                ap40_values.append(data.get("ap40", 0.0))
        
        if ap11_values:
            mean_ap11 = sum(ap11_values) / len(ap11_values)
            mean_ap40 = sum(ap40_values) / len(ap40_values)
            print(f"{'-'*60}")
            print(f"{'Mean':<20} {mean_ap11*100:>6.2f}%        {mean_ap40*100:>6.2f}%")
        
        print(f"\n{'='*80}")
        print(f"Outputs saved to: {out_dir}")
        print(f"  - summary.json: Detailed results with PR curves")
        print(f"  - summary.csv: Tabular results")
        print(f"  - pr_*.png: PR curve plots for each class")
        print(f"{'='*80}\n")
    else:
        print(f"Evaluation finished. Outputs written to: {out_dir}")


def _parse_classes_arg(s: str) -> List[str]:
    return [c.strip() for c in s.split(",") if c.strip()]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--gt", required=True, help="GT folder containing per-frame .txt")
    parser.add_argument("--pred", required=True, help="Pred folder containing per-frame .txt")
    parser.add_argument("--out", default="eval_output", help="Output folder")
    parser.add_argument("--max-distance", type=float, default=102.4, help="Filter GT by distance axis <= this value")
    parser.add_argument(
        "--distance-axis",
        choices=["x", "y", "z"],
        default="x",
        help="Axis used for distance filtering (ego frame default: x)",
    )
    parser.add_argument(
        "--filter-dt-by-distance",
        action="store_true",
        help="Also filter predictions by z distance (usually not needed)",
    )
    parser.add_argument(
        "--difficulty",
        choices=["all", "easy", "moderate", "hard"],
        default="all",
        help="KITTI-style difficulty filter using bbox height / truncation / occlusion",
    )
    parser.add_argument(
        "--classes",
        default=",".join(DEFAULT_EVAL_CLASSES),
        help="Comma-separated eval classes after mapping",
    )
    parser.add_argument(
        "--no-recompute-alpha",
        action="store_true",
        help="Do not recompute alpha from (ry,x,z); use alpha column as-is",
    )
    parser.add_argument(
        "--flip-y-gt",
        action="store_true",
        help="Flip GT y-axis sign and yaw (use if GT y-axis is right-handed)",
    )
    parser.add_argument(
        "--flip-y-pred",
        action="store_true",
        help="Flip pred y-axis sign and yaw (use if pred y-axis is right-handed)",
    )
    parser.add_argument(
        "--z-center-gt",
        action="store_true",
        help="Interpret GT z as center height and convert to bottom height",
    )
    parser.add_argument(
        "--z-center-pred",
        action="store_true",
        help="Interpret pred z as center height and convert to bottom height",
    )
    parser.add_argument(
        "--class-map-gt",
        default=None,
        help="Optional JSON file: {raw_class_lower: mapped_class}",
    )
    parser.add_argument(
        "--class-map-pred",
        default=None,
        help="Optional JSON file: {raw_class_lower: mapped_class}",
    )
    parser.add_argument(
        "--iou-thresholds",
        default=None,
        help='Optional JSON file: {"bbox": {"Car": 0.7, ...}, "bev": {...}, "3d": {...}}',
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=True,
        help="Print detailed progress and results (default: True)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose output",
    )

    args = parser.parse_args()

    eval_classes = _parse_classes_arg(args.classes)
    class_map_gt = _maybe_load_json(args.class_map_gt) or DEFAULT_GT_CLASS_MAP
    class_map_pred = _maybe_load_json(args.class_map_pred) or DEFAULT_PRED_CLASS_MAP
    iou_thresholds = _maybe_load_json(args.iou_thresholds) or DEFAULT_IOU_THRESHOLDS

    verbose = args.verbose and not args.quiet

    evaluate(
        args.gt,
        args.pred,
        args.out,
        eval_classes=eval_classes,
        max_distance=args.max_distance,
        filter_dt_by_distance=args.filter_dt_by_distance,
        recompute_alpha=not args.no_recompute_alpha,
        difficulty=args.difficulty,
        class_map_gt={k.lower(): v for k, v in class_map_gt.items()},
        class_map_pred={k.lower(): v for k, v in class_map_pred.items()},
        iou_thresholds=iou_thresholds,
        distance_axis=args.distance_axis,
        flip_y_gt=args.flip_y_gt,
        flip_y_pred=args.flip_y_pred,
        z_center_gt=args.z_center_gt,
        z_center_pred=args.z_center_pred,
        verbose=verbose,
    )


if __name__ == "__main__":
    main()

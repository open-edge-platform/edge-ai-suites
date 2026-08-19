#!/usr/bin/env python3
"""Convert an NCLT groundtruth_<date>.csv into TUM format for evo_ape.

NCLT's ground truth (http://robots.engin.umich.edu/nclt/) is a SLAM
pose-graph-derived 6DOF trajectory already in a local metric frame (x, y,
z, roll, pitch, yaw) - unlike UrbanLoco's raw geodetic INSPVAX messages,
this needs no anchor point or ENU/geodetic conversion, just a straight
Euler-to-quaternion conversion.

Columns (verified against NCLT's own read_ground_truth.py devkit script and
a real downloaded groundtruth_2012-01-15.csv sample):
  utime, x, y, z, roll, pitch, heading (yaw) - in a NED (North-East-Down)
  frame. No manual NED->ENU conversion is applied here: evo_ape's Umeyama
  alignment (`-a`) finds the best rigid rotation+translation between the
  estimate and ground truth, which absorbs a fixed frame difference like
  this automatically.

Usage:
  extract_nclt_gt.py --csv groundtruth_<date>.csv --out gt_tum.txt
"""
import argparse
import math


def euler_to_quaternion(roll, pitch, yaw):
    """ZYX (yaw-pitch-roll) Euler convention, matching NCLT's documented order."""
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    return qx, qy, qz, qw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    rows_written = 0
    with open(args.csv, "r") as fin, open(args.out, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            if len(parts) < 7:
                continue
            try:
                utime = int(parts[0])
                x, y, z = (float(v) for v in parts[1:4])
                roll, pitch, yaw = (float(v) for v in parts[4:7])
            except ValueError:
                continue
            # Skip NaN rows - NCLT's ground truth CSV documents these as gaps
            # where the pose-graph optimizer had no fix (e.g. GPS-denied
            # indoor stretches without adequate SLAM constraints).
            if any(math.isnan(v) for v in (x, y, z, roll, pitch, yaw)):
                continue
            qx, qy, qz, qw = euler_to_quaternion(roll, pitch, yaw)
            t = utime / 1_000_000.0
            fout.write(f"{t:.9f} {x:.6f} {y:.6f} {z:.6f} "
                       f"{qx:.9f} {qy:.9f} {qz:.9f} {qw:.9f}\n")
            rows_written += 1

    if rows_written == 0:
        raise SystemExit(f"No valid ground-truth rows parsed from {args.csv} - "
                          "check its column layout matches this script's assumptions.")
    print(f"==> Wrote {rows_written} ground-truth poses to {args.out}")


if __name__ == "__main__":
    main()

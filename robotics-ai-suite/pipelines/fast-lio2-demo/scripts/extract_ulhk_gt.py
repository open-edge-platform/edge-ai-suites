#!/usr/bin/env python3
"""Extract ground-truth trajectory from NovAtel SPAN-CPT INSPVAX messages in
the converted UrbanLoco ROS2 bag, and write it out in TUM format for
evo_ape.

UrbanLoco's official site documents its ground truth as coming from an
IMU/SPAN-CPT unit; the recorded bag carries this as
novatel_oem7_msgs/msg/INSPVAX on the topic configured as ULHK_GT_TOPIC in
env.sh (/novatel_data/inspvax by default) - geodetic latitude/longitude/
height, converted here to a local ENU frame (origin at the first fix).

Reads the topic directly out of the bag's own sqlite3 .db3 file by fixed
CDR byte offset rather than deserializing through the novatel_oem7_msgs
message definitions, so no extra ROS package needs to be installed just to
read ground truth. Orientation is left as an identity quaternion since
INSPVAX's own roll/pitch/azimuth are not aligned with the LiDAR body frame;
evo_ape's Umeyama alignment (`-a`) finds the best rigid rotation+translation
between the estimate and ground truth, which absorbs this automatically.

Usage:
  extract_ulhk_gt.py --bag-dir ulhk_bag --out gt_tum.txt
"""
import argparse
import math
import sqlite3
import struct
from pathlib import Path

# CDR byte offsets for INSPVAX fields (little-endian doubles).
_OFF_LAT = 60
_OFF_LON = 68
_OFF_HGT = 76

# WGS84 ellipsoid.
_A = 6378137.0
_E2 = 0.00669437999014


def _geodetic_to_enu(lat, lon, hgt, lat0, lon0, hgt0, r_n0, cos_lat0):
    """Convert geodetic (deg) to local ENU (m) relative to origin."""
    dlat = math.radians(lat - lat0)
    dlon = math.radians(lon - lon0)
    r_m = r_n0 * (1 - _E2) / (1 - _E2 * math.sin(math.radians(lat0)) ** 2)
    east = dlon * r_n0 * cos_lat0
    north = dlat * r_m
    up = hgt - hgt0
    return east, north, up


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bag-dir", required=True)
    parser.add_argument("--topic", default="/novatel_data/inspvax")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    bag_dir = Path(args.bag_dir)
    db3_files = sorted(bag_dir.glob("*.db3"))
    if not db3_files:
        raise SystemExit(f"No .db3 files found in {bag_dir}")

    poses = []
    lat0 = lon0 = hgt0 = None
    r_n0 = cos_lat0 = None

    for db3 in db3_files:
        conn = sqlite3.connect(str(db3))
        cur = conn.cursor()
        cur.execute("SELECT id FROM topics WHERE name=?", (args.topic,))
        row = cur.fetchone()
        if row is None:
            conn.close()
            continue
        topic_id = row[0]

        cur.execute(
            "SELECT timestamp, data FROM messages WHERE topic_id=? ORDER BY timestamp",
            (topic_id,),
        )
        for timestamp, data in cur:
            if len(data) < _OFF_HGT + 8:
                continue
            lat = struct.unpack_from("<d", data, _OFF_LAT)[0]
            lon = struct.unpack_from("<d", data, _OFF_LON)[0]
            hgt = struct.unpack_from("<d", data, _OFF_HGT)[0]

            if lat0 is None:
                lat0, lon0, hgt0 = lat, lon, hgt
                lat0_rad = math.radians(lat0)
                sin_lat0 = math.sin(lat0_rad)
                r_n0 = _A / math.sqrt(1 - _E2 * sin_lat0 ** 2)
                cos_lat0 = math.cos(lat0_rad)

            e, n, u = _geodetic_to_enu(lat, lon, hgt, lat0, lon0, hgt0, r_n0, cos_lat0)
            poses.append((timestamp / 1e9, e, n, u))
        conn.close()

    if not poses:
        raise SystemExit(
            f"No {args.topic} messages found in {bag_dir} - check env.sh's "
            "ULHK_GT_TOPIC matches the bag's actual topic name "
            "('ros2 bag info' output)."
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        for t, e, n, u in poses:
            f.write(f"{t:.9f} {e:.6f} {n:.6f} {u:.6f} 0 0 0 1\n")

    print(f"==> Wrote {len(poses)} ground-truth poses to {out_path}")


if __name__ == "__main__":
    main()

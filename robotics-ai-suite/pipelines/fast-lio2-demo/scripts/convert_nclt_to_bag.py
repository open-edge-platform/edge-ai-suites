#!/usr/bin/env python3
# SPDX-FileCopyrightText: (C) 2026 Intel Corporation
# SPDX-License-Identifier: Apache-2.0
"""Convert an NCLT session's Velodyne + IMU data into a standard ROS 2 bag.

NCLT (http://robots.engin.umich.edu/nclt/) does not ship a plug-and-play
ROS bag: Velodyne data is a custom little-endian binary format and IMU data
is a plain CSV. The dataset's own authors provide ROS1 conversion scripts,
but only via a Google Drive link (not scriptable/reproducible), and
community forks are ROS1-oriented. This script reads the raw files
directly, once, and writes sensor_msgs/PointCloud2 + sensor_msgs/Imu
messages (in timestamp order) into a rosbag2 bag on disk - replacing the
previous approach of re-parsing and live-publishing the raw files on every
run. Downstream, `run_nclt.sh` replays the resulting bag with the standard
`ros2 bag play`, matching every other RAI-suite SLAM demo. Conversion only
needs to happen once per dataset: rerunning this script is a no-op if
`--output-bag` already exists (pass `--force` to redo it).

Formats below are verified directly against NCLT's own devkit scripts
(read_vel_hits.py, read_ground_truth.py, downloaded from
s3.us-east-2.amazonaws.com/nclt.perl.engin.umich.edu/python/) and against a
real (partial) download of the 2012-01-15 session's velodyne_hits.bin and
ms25.csv - not guessed:

  - sensor_data/velodyne_hits.bin (NOT velodyne_sync/ - the *_vel.tar.gz
    archive only ships the raw, per-packet stream): a sequence of packets,
    each: 8-byte magic (4x little-endian uint16, each == 44444), uint32
    num_hits (LE), uint64 utime (LE, microseconds), 4 bytes padding, then
    num_hits * 8 bytes: uint16 x, uint16 y, uint16 z (LE, 5mm resolution,
    offset -100.0m: meters = raw * 0.005 - 100.0), uint8 intensity, uint8
    laser/ring id. There is no per-scan (per-revolution) grouping in this
    file - packets are grouped into scans here using a fixed ~100ms window
    (matching the Velodyne HDL-32E's 10Hz rate, i.e. config's scan_rate: 10),
    since the archive doesn't ship the image timestamps velodyne_sync/ was
    originally resynced against.
  - sensor_data/ms25.csv: utime, mag_x, mag_y, mag_z, accel_x, accel_y,
    accel_z, rot_r, rot_p, rot_h (accelerometer in m/s^2, gyro in rad/s) -
    column layout and units confirmed against a real downloaded file.

Usage:
  convert_nclt_to_bag.py --dataset-dir DIR --output-bag BAG_DIR
                          [--velodyne-topic /velodyne_points]
                          [--imu-topic /imu/data] [--storage-id sqlite3]
                          [--force]
"""
import argparse
import glob
import os
import shutil
import struct
import sys
import time

import rclpy.serialization
import rclpy.time
import rosbag2_py
from sensor_msgs.msg import PointCloud2, PointField, Imu
from std_msgs.msg import Header

MAGIC = 44444
HEADER_STRUCT = struct.Struct("<HHHHIQ4x")  # 4x magic uint16, num_hits u32, utime u64, 4 pad
POINT_STRUCT = struct.Struct("<HHHBB")      # x, y, z (uint16), intensity, ring
VEL_SCALE = 0.005
VEL_OFFSET = -100.0
SCAN_PERIOD_US = 100_000  # ~100ms, matches the Velodyne HDL-32E's 10Hz scan rate
PROGRESS_INTERVAL_S = 15  # how often convert() prints a progress line below


def find_file(dataset_dir, name):
    matches = glob.glob(os.path.join(dataset_dir, "**", name), recursive=True)
    return matches[0] if matches else None


def iter_velodyne_packets(vel_hits_path, progress=None):
    """Yield (utime_us, [(x, y, z, intensity, ring), ...]) per raw packet.

    If `progress` is given (a dict), it is updated in place with the
    current byte offset into vel_hits_path after every packet, so a caller
    iterating a downstream generator (iter_velodyne_scans) can still report
    a bytes-read-based completion percentage without re-implementing the
    file parsing.
    """
    with open(vel_hits_path, "rb") as f:
        while True:
            header = f.read(HEADER_STRUCT.size)
            if len(header) == 0:
                break
            if len(header) < HEADER_STRUCT.size:
                raise ValueError(f"Truncated packet header at EOF in {vel_hits_path}")
            m0, m1, m2, m3, num_hits, utime = HEADER_STRUCT.unpack(header)
            if not (m0 == m1 == m2 == m3 == MAGIC):
                raise ValueError(
                    f"Bad magic in {vel_hits_path} (got {m0:#x},{m1:#x},{m2:#x},{m3:#x}, "
                    f"expected {MAGIC:#x} x4) - packet framing is out of sync."
                )
            body = f.read(num_hits * POINT_STRUCT.size)
            if len(body) < num_hits * POINT_STRUCT.size:
                raise ValueError(f"Truncated packet body at EOF in {vel_hits_path}")
            if progress is not None:
                progress["bytes_read"] = f.tell()
            points = []
            for i in range(num_hits):
                xu, yu, zu, intensity, ring = POINT_STRUCT.unpack_from(body, i * POINT_STRUCT.size)
                x = xu * VEL_SCALE + VEL_OFFSET
                y = yu * VEL_SCALE + VEL_OFFSET
                z = zu * VEL_SCALE + VEL_OFFSET
                points.append((x, y, z, float(intensity), ring))
            yield utime, points


def iter_velodyne_scans(vel_hits_path, progress=None):
    """Group raw packets into ~SCAN_PERIOD_US scans: yield (scan_utime, points),
    each point as (x, y, z, intensity, ring, time_offset_us) where
    time_offset_us is that point's packet utime minus the scan's utime (all
    points in one packet share their packet's utime - NCLT's raw stream has
    no finer per-point timestamp than that). This offset - not just per-scan
    grouping - is what FAST_LIO's velodyne_handler needs (as the point cloud's
    "time" field, see make_pointcloud2) for per-point motion compensation;
    without it, velodyne_handler falls back to a same-ring monotonic-angle
    heuristic that has already caused a mid-scan reset
    ("Failed to find match for field 'time'" / "No point, skip this scan!")
    on this dataset.
    """
    scan_utime = None
    scan_points = []
    for utime, points in iter_velodyne_packets(vel_hits_path, progress=progress):
        if scan_utime is None:
            scan_utime = utime
        elif utime - scan_utime >= SCAN_PERIOD_US:
            yield scan_utime, scan_points
            scan_utime = utime
            scan_points = []
        offset_us = utime - scan_utime
        scan_points.extend((x, y, z, intensity, ring, offset_us) for (x, y, z, intensity, ring) in points)
    if scan_points:
        yield scan_utime, scan_points


def make_pointcloud2(points, frame_id, stamp):
    # "time" is a per-point offset (microseconds, matching
    # config/velodyne_generic.yaml's preprocess.timestamp_unit: 2) from this
    # scan's own header.stamp, required by FAST_LIO's velodyne_handler
    # (src/preprocess.h's velodyne_ros::Point) for per-point motion
    # de-skewing; without it in msg.fields, velodyne_handler logs "Failed to
    # find match for field 'time'" and falls back to an angle-based estimate.
    fields = [
        PointField(name="x", offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name="y", offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name="z", offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name="intensity", offset=12, datatype=PointField.FLOAT32, count=1),
        PointField(name="time", offset=16, datatype=PointField.FLOAT32, count=1),
        PointField(name="ring", offset=20, datatype=PointField.UINT16, count=1),
    ]
    point_step = 22
    buf = bytearray(point_step * len(points))
    off = 0
    for (x, y, z, intensity, ring, time_offset_us) in points:
        struct.pack_into("<fffffH", buf, off, x, y, z, intensity, float(time_offset_us), ring)
        off += point_step
    msg = PointCloud2()
    msg.header = Header(stamp=stamp, frame_id=frame_id)
    msg.height = 1
    msg.width = len(points)
    msg.fields = fields
    msg.is_bigendian = False
    msg.point_step = point_step
    msg.row_step = point_step * len(points)
    msg.data = bytes(buf)
    msg.is_dense = True
    return msg


def load_imu_samples(ms25_path):
    """Return a sorted list of (utime_us, accel_xyz, gyro_rpy) from ms25.csv."""
    samples = []
    with open(ms25_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(",")
            if len(parts) < 10:
                continue
            try:
                utime = int(parts[0])
                accel = tuple(float(v) for v in parts[4:7])
                gyro = tuple(float(v) for v in parts[7:10])
            except ValueError:
                continue
            samples.append((utime, accel, gyro))
    samples.sort(key=lambda item: item[0])
    return samples


def make_imu_msg(accel, gyro, frame_id, stamp):
    msg = Imu()
    msg.header = Header(stamp=stamp, frame_id=frame_id)
    msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z = accel
    msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z = gyro
    # Raw IMU has no absolute orientation estimate; mark it unknown per the
    # sensor_msgs/Imu convention (-1 in orientation_covariance[0]).
    msg.orientation_covariance[0] = -1.0
    return msg


def utime_to_ros_stamp(utime_us):
    sec = utime_us // 1_000_000
    nanosec = (utime_us % 1_000_000) * 1000
    return sec, nanosec


def utime_to_bag_ns(utime_us):
    """rosbag2 write() timestamps are recording-time nanoseconds - `ros2 bag
    play` paces messages using the deltas between these, so they must be
    derived from the same utime_us used for each message's header.stamp
    (utime_to_ros_stamp) for playback pacing to match sensor timing."""
    return utime_us * 1000


def convert(args):
    vel_hits_path = find_file(args.dataset_dir, "velodyne_hits.bin")
    if not vel_hits_path:
        print(
            f"No velodyne_hits.bin found under {args.dataset_dir}. "
            "Run fetch_nclt.sh first, or check the *_vel.tar.gz contents.",
            file=sys.stderr,
        )
        sys.exit(1)
    ms25_path = find_file(args.dataset_dir, "ms25.csv")
    if not ms25_path:
        print(f"No ms25.csv found under {args.dataset_dir}.", file=sys.stderr)
        sys.exit(1)

    if os.path.exists(args.output_bag):
        if not args.force:
            print(f"{args.output_bag} already exists - conversion already done, skipping "
                  "(pass --force to redo it).")
            return
        print(f"--force given: removing existing {args.output_bag}")
        shutil.rmtree(args.output_bag)

    imu_samples = load_imu_samples(ms25_path)
    if not imu_samples:
        print(f"No IMU samples parsed from {ms25_path}.", file=sys.stderr)
        sys.exit(1)

    vel_hits_size_gb = os.path.getsize(vel_hits_path) / 1e9
    print(f"Converting Velodyne scans from {vel_hits_path} ({vel_hits_size_gb:.1f} GB) and "
          f"{len(imu_samples)} IMU samples from {ms25_path} into {args.output_bag} "
          f"(storage: {args.storage_id})")
    print("This is a single sequential pass over the Velodyne file and typically "
          "takes several minutes; progress is reported below every "
          f"{PROGRESS_INTERVAL_S}s - it is not stuck if nothing else prints in between.")

    storage_options = rosbag2_py.StorageOptions(uri=args.output_bag, storage_id=args.storage_id)
    converter_options = rosbag2_py.ConverterOptions(
        input_serialization_format="cdr", output_serialization_format="cdr")
    writer = rosbag2_py.SequentialWriter()
    writer.open(storage_options, converter_options)
    # ROS 2 Jazzy's rosbag2_py.TopicMetadata requires an explicit `id`
    # (older distros defaulted it); the writer assigns the real topic id
    # itself, so any placeholder value here is fine.
    writer.create_topic(rosbag2_py.TopicMetadata(
        id=0, name=args.velodyne_topic, type="sensor_msgs/msg/PointCloud2",
        serialization_format="cdr"))
    writer.create_topic(rosbag2_py.TopicMetadata(
        id=0, name=args.imu_topic, type="sensor_msgs/msg/Imu", serialization_format="cdr"))

    # velodyne_hits.bin is 16-20 GB - stream scans lazily rather than loading
    # the whole file, and merge against the (much smaller, fully in-memory)
    # IMU sample list with a manual two-pointer merge instead of building one
    # combined sorted list. Messages are written in strict timestamp order,
    # which rosbag2 (and `ros2 bag play`) expects.
    progress = {"bytes_read": 0}
    total_bytes = os.path.getsize(vel_hits_path)
    scan_iter = iter_velodyne_scans(vel_hits_path, progress=progress)
    imu_idx = 0
    next_scan = next(scan_iter, None)
    scan_count = 0

    start_time = time.monotonic()
    last_report = start_time

    while next_scan is not None or imu_idx < len(imu_samples):
        next_imu = imu_samples[imu_idx] if imu_idx < len(imu_samples) else None
        if next_scan is not None and (next_imu is None or next_scan[0] <= next_imu[0]):
            utime, points = next_scan
            sec, nanosec = utime_to_ros_stamp(utime)
            stamp = rclpy.time.Time(seconds=sec, nanoseconds=nanosec).to_msg()
            msg = make_pointcloud2(points, args.frame_id, stamp)
            writer.write(args.velodyne_topic, rclpy.serialization.serialize_message(msg),
                         utime_to_bag_ns(utime))
            scan_count += 1
            next_scan = next(scan_iter, None)
        else:
            utime, accel, gyro = next_imu
            sec, nanosec = utime_to_ros_stamp(utime)
            stamp = rclpy.time.Time(seconds=sec, nanoseconds=nanosec).to_msg()
            msg = make_imu_msg(accel, gyro, args.imu_frame_id, stamp)
            writer.write(args.imu_topic, rclpy.serialization.serialize_message(msg),
                         utime_to_bag_ns(utime))
            imu_idx += 1

        now = time.monotonic()
        if now - last_report >= PROGRESS_INTERVAL_S:
            pct = 100.0 * progress["bytes_read"] / total_bytes if total_bytes else 0.0
            print(f"  ... {pct:.1f}% of velodyne_hits.bin read, {scan_count} scans and "
                  f"{imu_idx}/{len(imu_samples)} IMU samples written, "
                  f"{now - start_time:.0f}s elapsed")
            last_report = now

    del writer  # flush + close the bag (rosbag2_py has no explicit close())
    print(f"Wrote {scan_count} Velodyne scans and {len(imu_samples)} IMU samples "
          f"to {args.output_bag} in {time.monotonic() - start_time:.0f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset-dir", required=True)
    parser.add_argument("--output-bag", required=True)
    parser.add_argument("--velodyne-topic", default="/velodyne_points")
    parser.add_argument("--imu-topic", default="/imu/data")
    parser.add_argument("--frame-id", default="velodyne")
    parser.add_argument("--imu-frame-id", default="imu")
    parser.add_argument("--storage-id", default="sqlite3")
    parser.add_argument("--force", action="store_true",
                         help="Reconvert even if --output-bag already exists.")
    args = parser.parse_args()
    convert(args)


if __name__ == "__main__":
    main()

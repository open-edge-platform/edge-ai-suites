"""
Convert KITTI dataset (MMDetection3D v1.x pkl format) to V2XDataset-compatible format.

This script reads data from --src-root (KITTI dataset) and creates a
V2XDataset-compatible dataset at --dst-root with:
  - image/          symlinks to source images
  - velodyne/       symlinks to source point clouds
  - calib/virtuallidar_to_camera/  JSON calib files
  - training/label_2/   symlink to source labels (for evaluator)
  - kitti_v2x_infos_{train,val}.pkl   converted annotation files

Usage:
    python tools/convert_kitti_to_v2x_format.py \
        --src-root data/kitti \
        --dst-root data/kitti-v2x
"""

import argparse
import json
import os
import pickle
from importlib import import_module

import numpy as np
from pyquaternion import Quaternion


KITTI_CAT_TO_NUSCENES = {
    "Pedestrian": "human.pedestrian.adult",
    "Cyclist": "vehicle.bicycle",
    "Car": "vehicle.car",
    "Van": "vehicle.car",
    "Truck": "vehicle.truck",
    "Person_sitting": "human.pedestrian.adult",
    "Tram": "vehicle.bus.rigid",
    "Misc": "ignore",
    "DontCare": "ignore",
}


_ALLOWED_PICKLE_GLOBALS = {
    "builtins": {
        "dict", "list", "tuple", "set", "frozenset", "slice",
        "str", "int", "float", "bool", "bytes",
    },
    "collections": {"OrderedDict", "defaultdict"},
    "numpy": {"dtype", "ndarray"},
    "numpy.core.multiarray": {"_reconstruct", "scalar"},
    "numpy._core.multiarray": {"_reconstruct", "scalar"},
}


class RestrictedUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        allowed_names = _ALLOWED_PICKLE_GLOBALS.get(module)
        if allowed_names and name in allowed_names:
            return getattr(import_module(module), name)
        raise pickle.UnpicklingError(f"Unsupported pickle global: {module}.{name}")


def load_restricted_pickle(file_obj):
    return RestrictedUnpickler(file_obj).load()


def kitti_bbox3d_to_lidar(bbox_3d, lidar2cam):
    """Convert KITTI 3D bbox from camera rect frame to lidar frame.

    Args:
        bbox_3d: [x_cam, y_cam, z_cam, l, h, w, rot_y]
            x_cam, y_cam, z_cam: bottom center in camera rectified frame
            l: length (along cam_z), h: height (along cam_y), w: width (along cam_x)
            rot_y: rotation around cam_y axis
        lidar2cam: 4x4 matrix (R0_rect @ Tr_velo_to_cam)

    Returns:
        center_lidar: [3] geometric center in lidar frame
        size: [w, l, h] (nuscenes Box convention: width, length, height)
        yaw_lidar: yaw angle in lidar frame
    """
    x_cam, y_cam, z_cam = bbox_3d[0], bbox_3d[1], bbox_3d[2]
    l, h, w = bbox_3d[3], bbox_3d[4], bbox_3d[5]
    rot_y_cam = bbox_3d[6]

    cam2lidar = np.linalg.inv(lidar2cam)

    # KITTI y_cam is bottom center; convert to geometric center
    center_cam = np.array([x_cam, y_cam - h / 2, z_cam, 1.0])
    center_lidar = cam2lidar @ center_cam

    # Convert heading direction from camera to lidar frame
    heading_cam = np.array([np.sin(rot_y_cam), 0.0, np.cos(rot_y_cam)])
    heading_lidar = cam2lidar[:3, :3] @ heading_cam
    yaw_lidar = np.arctan2(heading_lidar[1], heading_lidar[0])

    return center_lidar[:3], np.array([w, l, h]), yaw_lidar


def convert_pkl(input_pkl, output_pkl, src_root):
    with open(input_pkl, "rb") as f:
        raw_data = load_restricted_pickle(f)

    if isinstance(raw_data, list):
        print(f"  {input_pkl} is already a list — skipping conversion.")
        return

    metainfo = raw_data["metainfo"]
    data_list = raw_data["data_list"]
    label_to_cat = {v: k for k, v in metainfo["categories"].items()}

    infos = []
    for item in data_list:
        sample_idx = item["sample_idx"]

        cam2 = item["images"]["CAM2"]
        img_filename = f"image/{cam2['img_path']}"
        lidar_filename = f"velodyne/{item['lidar_points']['lidar_path']}"

        # lidar2cam = R0_rect @ Tr_velo_to_cam (already computed in pkl)
        lidar2cam = np.array(cam2["lidar2cam"]).reshape(4, 4)
        cam2lidar = np.linalg.inv(lidar2cam)
        rotation_matrix = cam2lidar[:3, :3]
        translation = cam2lidar[:3, 3]

        # Camera intrinsic (4x4 padded)
        cam_intrinsic_4x4 = np.array(cam2["cam2img"]).reshape(4, 4)
        cam_intrinsic_3x3 = cam_intrinsic_4x4[:3, :3]

        ego_rotation = Quaternion(matrix=np.eye(3))
        ego_translation = [0.0, 0.0, 0.0]

        sample_token = img_filename
        scene_token = sample_token

        cam_info = {
            "CAM_FRONT": {
                "sample_token": sample_token,
                "timestamp": 1000000 + sample_idx,
                "is_key_frame": True,
                "height": int(cam2.get("height", 370)),
                "width": int(cam2.get("width", 1224)),
                "filename": img_filename,
                "ego_pose": {
                    "translation": ego_translation,
                    "rotation": list(ego_rotation),
                    "token": sample_token,
                    "timestamp": 1000000 + sample_idx,
                },
                "calibrated_sensor": {
                    "token": sample_token,
                    "sensor_token": sample_token,
                    "translation": translation,
                    "rotation_matrix": rotation_matrix,
                    "camera_intrinsic": cam_intrinsic_3x3,
                },
            }
        }

        lidar_info = {
            "LIDAR_TOP": {
                "sample_token": sample_token,
                "ego_pose": {
                    "translation": ego_translation,
                    "rotation": list(ego_rotation),
                    "token": sample_token,
                    "timestamp": 1000000 + sample_idx,
                },
                "timestamp": 1000000 + sample_idx,
                "filename": lidar_filename,
                "calibrated_sensor": {
                    "token": sample_token,
                    "sensor_token": sample_token,
                    "translation": translation,
                    "rotation_matrix": rotation_matrix,
                    "camera_intrinsic": cam_intrinsic_3x3,
                },
            }
        }

        ann_infos = []
        for inst in item["instances"]:
            cat_name = label_to_cat.get(inst["bbox_label_3d"], "Misc")
            nuscenes_cat = KITTI_CAT_TO_NUSCENES.get(cat_name, "ignore")
            if nuscenes_cat == "ignore":
                continue

            bbox_3d = inst["bbox_3d"]
            # Skip invalid annotations (DontCare placeholders)
            if bbox_3d[0] < -900:
                continue

            center_lidar, size, yaw_lidar = kitti_bbox3d_to_lidar(
                bbox_3d, lidar2cam
            )

            q = Quaternion(axis=[0, 0, 1], angle=yaw_lidar)

            ann = {
                "category_name": nuscenes_cat,
                "translation": center_lidar,
                "rotation": q,
                "yaw_lidar": float(yaw_lidar),
                "size": size,
                "prev": "",
                "next": "",
                "sample_token": sample_token,
                "instance_token": sample_token,
                "token": sample_token,
                "visibility_token": str(inst.get("occluded", 0)),
                "num_lidar_pts": max(int(inst.get("num_lidar_pts", 0)), 1),
                "num_radar_pts": 0,
                "velocity": np.array([0.0, 0.0, 0.0]),
            }
            ann_infos.append(ann)

        info = {
            "sample_token": sample_token,
            "timestamp": 1000000 + sample_idx,
            "scene_token": scene_token,
            "cam_infos": cam_info,
            "lidar_infos": lidar_info,
            "sweeps": [],
            "ann_infos": ann_infos,
        }
        infos.append(info)

    with open(output_pkl, "wb") as f:
        pickle.dump(infos, f)
    print(f"  Converted {len(infos)} samples -> {output_pkl}")


def create_calib_jsons(src_root, dst_root):
    """Generate calib JSON files from KITTI calib txt + R0_rect."""
    calib_dir = os.path.join(src_root, "training", "calib")
    output_dir = os.path.join(dst_root, "calib", "virtuallidar_to_camera")
    os.makedirs(output_dir, exist_ok=True)

    calib_files = sorted(f for f in os.listdir(calib_dir) if f.endswith(".txt"))
    count = 0
    for calib_file in calib_files:
        calib = {}
        with open(os.path.join(calib_dir, calib_file), "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(": ", 1)
                if len(parts) != 2:
                    continue
                key, vals_str = parts
                calib[key] = [float(x) for x in vals_str.split()]

        if "Tr_velo_to_cam" not in calib:
            continue

        # Build R0_rect (3x3 -> 4x4)
        if "R0_rect" in calib:
            R0 = np.array(calib["R0_rect"]).reshape(3, 3)
            R0_4x4 = np.eye(4)
            R0_4x4[:3, :3] = R0
        else:
            R0_4x4 = np.eye(4)

        # Build Tr_velo_to_cam (3x4 -> 4x4)
        Tr = np.array(calib["Tr_velo_to_cam"]).reshape(3, 4)
        Tr_4x4 = np.eye(4)
        Tr_4x4[:3, :] = Tr

        # lidar2cam = R0 @ Tr
        lidar2cam = R0_4x4 @ Tr_4x4
        rotation = lidar2cam[:3, :3].tolist()
        translation = lidar2cam[:3, 3:].tolist()

        json_name = calib_file.replace(".txt", ".json")
        json_path = os.path.join(output_dir, json_name)
        with open(json_path, "w") as f:
            json.dump({"rotation": rotation, "translation": translation}, f)
        count += 1

    print(f"  Created {count} calib JSON files in {output_dir}")


def _make_symlink(src, dst):
    """Create a symlink dst -> src, replacing existing symlink if needed."""
    if os.path.realpath(dst) == os.path.realpath(src):
        print(f"  Skip (same path): {dst}")
        return
    if os.path.exists(dst):
        if os.path.islink(dst):
            os.unlink(dst)
        else:
            print(f"  WARNING: {dst} exists and is not a symlink, skipping")
            return
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    os.symlink(src, dst)
    print(f"  Symlink: {dst} -> {src}")


def create_symlinks(src_root, dst_root):
    src_root_abs = os.path.abspath(src_root)
    dst_root_abs = os.path.abspath(dst_root)

    # Top-level convenience symlinks
    _make_symlink(
        os.path.join(src_root_abs, "training", "image_2"),
        os.path.join(dst_root_abs, "image"),
    )
    _make_symlink(
        os.path.join(src_root_abs, "training", "velodyne"),
        os.path.join(dst_root_abs, "velodyne"),
    )

    # training/ subdirectories
    training_links = ["image_2", "velodyne", "label_2", "calib", "velodyne_reduced"]
    for name in training_links:
        src = os.path.join(src_root_abs, "training", name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(dst_root_abs, "training", name)
        _make_symlink(src, dst)

    # testing/ subdirectories
    testing_links = ["image_2", "velodyne", "calib", "velodyne_reduced"]
    for name in testing_links:
        src = os.path.join(src_root_abs, "testing", name)
        if not os.path.exists(src):
            continue
        dst = os.path.join(dst_root_abs, "testing", name)
        _make_symlink(src, dst)


def main():
    parser = argparse.ArgumentParser(
        description="Convert KITTI (MMDetection3D v1.x) to V2XDataset format"
    )
    parser.add_argument(
        "--src-root",
        type=str,
        default="data/kitti",
        help="Source KITTI data directory",
    )
    parser.add_argument(
        "--dst-root",
        type=str,
        default="data/kitti-v2x",
        help="Output directory for V2X-compatible format",
    )
    args = parser.parse_args()
    src_root = args.src_root
    dst_root = args.dst_root

    os.makedirs(dst_root, exist_ok=True)

    print("Step 1: Creating symlinks for images, velodyne, labels...")
    create_symlinks(src_root, dst_root)

    print("Step 2: Creating calib/virtuallidar_to_camera JSON files...")
    create_calib_jsons(src_root, dst_root)

    print("Step 3: Converting pkl files...")
    for split in ["train", "val", "trainval", "test"]:
        input_pkl = os.path.join(src_root, f"kitti_infos_{split}.pkl")
        if os.path.exists(input_pkl):
            output_pkl = os.path.join(dst_root, f"kitti_infos_{split}.pkl")
            convert_pkl(input_pkl, output_pkl, src_root)

    print("\nDone! Use these config settings:")
    print(f"  dataset_root: {dst_root}")
    print(f"  dataset_kitti_root: {dst_root}/training/label_2")
    print(f'  ann_file: ${{dataset_root + "/kitti_infos_train.pkl"}}')


if __name__ == "__main__":
    main()

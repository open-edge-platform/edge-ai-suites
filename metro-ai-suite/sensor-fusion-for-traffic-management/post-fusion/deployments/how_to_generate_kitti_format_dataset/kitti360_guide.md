# Guide: Converting KITTI-360 to KITTI Format and Testing LiDAR Pipeline

## Table of Contents


- [Guide: Converting KITTI-360 to KITTI Format and Testing LiDAR Pipeline](#guide-converting-kitti-360-to-kitti-format-and-testing-lidar-pipeline)
  - [Introduction](#introduction)
  - [Prerequisites](#prerequisites)
  - [Converting KITTI-360 to KITTI Format](#converting-kitti-360-to-kitti-format)

---

## Introduction
This guide explains how to convert the KITTI-360 dataset into the KITTI format and test a LiDAR-based pipeline (e.g., PointPillars). The KITTI format is widely used in 3D object detection tasks, and this conversion allows you to use KITTI-360 data with existing pipelines.

---

## Prerequisites
Before starting, ensure you have the following:
- **KITTI-360 Dataset**: Download from [KITTI-360 website](http://www.cvlibs.net/datasets/kitti-360/).

The download dataset directory will be as follows.
```
├── KITTI-360
│   ├── calibration
│   ├── data_2d_raw
│   ├── data_2d_semantics
│   ├── data_3d_bboxes
│   ├── data_3d_raw
│   └── data_poses
...
```

- **Python Environment**: Python 3.8+ with necessary libraries installed.
- **Required Libraries**:
  - `numpy`
  - `shutil`
  - `mmcv`
  - `mmengine`
  - `mmdet3d`(follow the official installation guide https://mmdetection3d.readthedocs.io/en/latest/get_started.html)

---

## Converting KITTI-360 to KITTI Format

Convert kitti 360 dataset to kitti format

```bash
python kitti360_convert_to_kitti.py /path-to-kitti360 /path-to-output-folder
```

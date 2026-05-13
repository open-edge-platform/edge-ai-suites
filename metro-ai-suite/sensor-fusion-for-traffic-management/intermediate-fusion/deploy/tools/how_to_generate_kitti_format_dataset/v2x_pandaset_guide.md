# Dataset Conversion Guide: PandaSet & DAIR-V2X-I to KITTI Format

The conversion scripts covered by this guide live under `tools/how_to_generate_kitti_format_dataset/`.
The example commands below assume this project root is already the current working directory.

This document provides a comprehensive guide on converting PandaSet and DAIR-V2X-I datasets to KITTI format, including original dataset structures, coordinate system definitions, conversion processes, and verification methods.

## Table of Contents

1. [Overview](#overview)
2. [PandaSet Dataset](#pandaset-dataset)
3. [DAIR-V2X-I Dataset](#dair-v2x-i-dataset)
4. [KITTI Format](#kitti-format)
5. [Conversion Implementation](#conversion-implementation)
6. [Calibration Verification](#calibration-verification)
7. [Usage Guide](#usage-guide)

## Quick Start

### Basic Conversion Examples

```bash
# 1. PandaSet quick conversion (standard mode)
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py

# 2. PandaSet convert specific sequences (encoding mode)
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --sequences 001 002 --encode_img

# 3. DAIR-V2X-I quick conversion (standard mode)
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py

# 4. DAIR-V2X-I convert first 1000 frames (encoding mode)
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --max_frames 1000 --encode_img
```

### Help Information

```bash
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --help
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --help
```

## Overview

This project provides complete solutions for converting two mainstream autonomous driving datasets (PandaSet and DAIR-V2X-I) to the widely-used KITTI format, enabling the use of existing KITTI toolchains for research and development.

### Conversion Script List

| Script File | Function | Input Format | Output Format | Image Support |
|------------|----------|--------------|---------------|---------------|
| `pandaset_to_kitti.py` | PandaSet Conversion | PandaSet Original | KITTI Format | PNG/Binary Encoded |
| `dair_v2x_i_to_kitti.py` | DAIR-V2X-I Conversion | DAIR-V2X-I Original | KITTI Format | JPEG/Binary Encoded |
| `kitti_pandaset_verification.py` | PandaSet Verification | KITTI Format | Visualization Results | - |
| `kitti_dair_v2x_verification.py` | DAIR-V2X-I Verification | KITTI Format | Visualization Results | - |

## PandaSet Dataset

### Dataset Introduction

PandaSet is an autonomous driving dataset jointly released by Hesai and Scale AI, containing high-quality LiDAR point cloud and camera image data.

### Original Data Structure

```
pandaset/
├── 001/                          # Sequence ID
│   ├── camera/
│   │   ├── front_camera/
│   │   │   ├── 00.jpg            # Camera images
│   │   │   ├── 01.jpg
│   │   │   └── ...
│   │   │   ├── intrinsics.json   # Camera intrinsics
│   │   │   ├── poses.json        # Camera extrinsics (poses in world coordinates)
│   │   │   └── timestamps.json   # Timestamps
│   ├── lidar/
│   │   ├── 00.pkl.gz             # LiDAR point cloud data
│   │   ├── 01.pkl.gz
│   │   └── ...
│   │   ├── poses.json            # LiDAR extrinsics (poses in world coordinates)
│   │   └── timestamps.json       # Timestamps
│   ├── cuboids/
│   │   ├── 00.pkl.gz             # 3D annotation data
│   │   ├── 01.pkl.gz
│   │   └── ...
│   └── meta/
│       └── gps.json              # GPS data
├── 002/
└── ...
```

### Coordinate System Definitions

#### 1. PandaSet World Coordinate System
- **Origin**: Data collection starting position
- **X-axis**: East direction
- **Y-axis**: North direction
- **Z-axis**: Up direction
- **Note**: Global unified coordinate system, reference for all sensor data

#### 2. PandaSet Ego Coordinate System
- **Origin**: Vehicle geometric center
- **X-axis**: Pointing to the right
- **Y-axis**: Pointing forward
- **Z-axis**: Pointing upward
- **Note**: Vehicle-centered local coordinate system

#### 3. Sensor Coordinate Systems
- **LiDAR Coordinate System**: LiDAR-centered local coordinate system
- **Camera Coordinate System**: Camera optical center-centered, Z-axis pointing forward

### Sensor Configuration

#### LiDAR Sensors
- **Models**: Hesai PandarGT (64-line) and Pandar64 (forward-facing)
- **Data Format**: PKL format, containing coordinates (x, y, z) and intensity (i)
- **Coordinate System**: Stored in world coordinate system
- **Frequency**: 10Hz

#### Camera Sensors
- **Model**: Front-facing camera
- **Resolution**: 1920×1080
- **Data Format**: JPEG images
- **Calibration**: Includes intrinsics and distortion parameters

### Annotation Format

#### 3D Bounding Box Annotations
```python
{
    'uuid': 'unique_id',           # Unique object identifier
    'label': 'Car',               # Object category
    'position': {                 # Center position (world coordinates)
        'x': 10.5,
        'y': 20.3, 
        'z': 1.2
    },
    'dimensions': {               # Dimensions
        'x': 1.8,               # Width (left to right)
        'y': 4.5,               # Length (front to back)
        'z': 1.5                # Height (top to bottom)
    },
    'yaw': 0.5,                  # Rotation angle around Z-axis
    'stationary': False,         # Whether stationary
    'attributes': {...}          # Other attributes
}
```

#### Supported Categories
- Vehicles: Car, Pickup Truck, Semi-truck, Bus, etc.
- Pedestrians: Pedestrian, Pedestrian with Object
- Cyclists: Bicycle, Motorcycle, Personal Mobility Device
- Others: Train, Tram, Animals, Signs, etc.

## DAIR-V2X-I Dataset

### Dataset Introduction

DAIR-V2X-I is a vehicle-infrastructure cooperative dataset focused on roadside perception, using roadside-installed LiDAR and cameras for data collection.

### Original Data Structure

```
dair-v2x-i/
├── data_info.json               # Data index file
├── velodyne/                    # LiDAR point cloud data
│   ├── 000000.pcd
│   ├── 000001.pcd
│   └── ...
├── image/                       # Camera image data
│   ├── 000000.jpg
│   ├── 000001.jpg
│   └── ...
├── calib/                       # Calibration files
│   ├── camera_intrinsic/        # Camera intrinsics
│   │   ├── 000000.json
│   │   └── ...
│   └── virtuallidar_to_camera/  # Extrinsics
│       ├── 000000.json
│       └── ...
└── label/                       # Annotation files
    ├── camera/                  # Camera annotations
    │   ├── 000000.json
    │   └── ...
    └── virtuallidar/            # LiDAR annotations
        ├── 000000.json
        └── ...
```

### Coordinate System Definitions

#### 1. Virtual LiDAR Coordinate System
- **Origin**: LiDAR sensor geometric center
- **X-axis**: Parallel to ground, pointing forward
- **Y-axis**: Parallel to ground, pointing left
- **Z-axis**: Perpendicular to ground, pointing upward
- **Note**: Extrinsically transformed so X-Y plane is parallel to ground

#### 2. Camera Coordinate System  
- **Origin**: Camera optical center
- **X-axis**: Parallel to image X-axis, pointing right
- **Y-axis**: Parallel to image Y-axis, pointing down
- **Z-axis**: Camera optical axis, pointing forward

#### 3. Image Coordinate System
- **Origin**: Top-left corner of image
- **X-axis**: Horizontal, pointing right
- **Y-axis**: Vertical, pointing down

### Sensor Configuration

#### LiDAR Sensors
- **Model**: 300-line LiDAR
- **Sampling Frequency**: 10Hz
- **Field of View**: Horizontal 100°, Vertical 40°
- **Detection Range**: 200-280m
- **Data Format**: PCD format

#### Camera Sensors
- **Sensor**: 1-inch global shutter CMOS
- **Sampling Frequency**: 25Hz
- **Resolution**: Maximum 4096×2160, compressed to 1920×1080
- **Image Format**: JPEG

### Calibration File Format

#### Camera Intrinsics (`camera_intrinsic/*.json`)
```json
{
    "cam_K": [2183.375, 0.0, 940.590, 0.0, 2329.297, 567.568, 0.0, 0.0, 1.0],
    "cam_D": [-0.482834, 0.501014, -0.000996, 0.000294, 0.0],
    "width": 1920,
    "height": 1080,
    "distortion_model": "plumb_bob"
}
```

#### Extrinsics (`virtuallidar_to_camera/*.json`)
```json
{
    "rotation": [
        [0.999, -0.001, 0.02],
        [0.001, 1.0, 0.003], 
        [-0.02, -0.003, 0.999]
    ],
    "translation": [0.5, 0.1, -1.8]
}
```

### Annotation Format

#### 3D Bounding Box Annotations (`label/virtuallidar/*.json`)
```json
[
    {
        "type": "Car",
        "3d_location": {"x": 15.2, "y": -3.1, "z": 0.8},
        "3d_dimensions": {"h": 1.5, "w": 1.8, "l": 4.2},
        "rotation": 1.57,
        "occluded": 0,
        "truncated": 0.0,
        "alpha": 1.2
    }
]
```

#### 2D Bounding Box Annotations (`label/camera/*.json`)
```json
[
    {
        "type": "Car", 
        "2d_box": {
            "xmin": "100.5",
            "ymin": "200.3",
            "xmax": "350.8", 
            "ymax": "480.1"
        },
        "occluded": 0,
        "truncated": 0.0
    }
]
```

#### Supported Categories
- Car, Truck, Van, Bus
- Pedestrian, Cyclist, Tricyclist, Motorcyclist  
- Barrowlist, Trafficcone
- Other categories

### Important Note on Image Undistortion

**DAIR-V2X-I Dataset**: According to the official documentation, images in DAIR-V2X-I are **already undistorted during data collection**. Therefore, our converter defaults to `undistort_img=False` to avoid re-processing already corrected images.

## KITTI Format

### Data Structure

```
kitti-format/
├── training/
│   ├── image_2/                 # Left camera images  
│   │   ├── 000000.png
│   │   └── ...
│   ├── velodyne/                # LiDAR point cloud data
│   │   ├── 000000.bin
│   │   └── ...
│   ├── label_2/                 # 3D annotations
│   │   ├── 000000.txt
│   │   └── ...
│   └── calib/                   # Calibration files
│       ├── 000000.txt
│       └── ...
└── testing/
    ├── image_2/
    ├── velodyne/
    └── calib/
```

### Coordinate System Definition

#### KITTI Ego Coordinate System
- **Origin**: LiDAR sensor center
- **X-axis**: Pointing forward
- **Y-axis**: Pointing left  
- **Z-axis**: Pointing upward
- **Note**: Standard ego coordinate system used for 3D object detection

### File Formats

#### Point Cloud Data (`velodyne/*.bin`)
- **Format**: Binary file, float32
- **Structure**: [x, y, z, intensity] × N points
- **Coordinate System**: KITTI ego coordinates

#### Calibration File (`calib/*.txt`)
```
P0: 718.856 0.000000 607.192800 0.000000 0.000000 718.856 185.215600 0.000000 0.000000 0.000000 1.000000 0.000000
P1: 718.856 0.000000 607.192800 -386.1448 0.000000 718.856 185.215600 0.000000 0.000000 0.000000 1.000000 0.000000
P2: 718.856 0.000000 607.192800 0.000000 0.000000 718.856 185.215600 0.000000 0.000000 0.000000 1.000000 0.000000
P3: 718.856 0.000000 607.192800 -386.1448 0.000000 718.856 185.215600 0.000000 0.000000 0.000000 1.000000 0.000000
R0_rect: 1.000000 0.000000 0.000000 0.000000 1.000000 0.000000 0.000000 0.000000 1.000000
Tr_velo_to_cam: 7.533745e-03 -9.999714e-01 -6.166020e-04 -4.069766e-03 1.480249e-02 7.280733e-04 -9.998902e-01 -7.631618e-02
Tr_imu_to_velo: 9.999976e-01 7.553071e-04 -2.035826e-03 -8.086759e-01 -7.854027e-04 9.998898e-01 -1.482298e-02 3.195559e-01
```

#### 3D Annotation Format (`label_2/*.txt`)
```
Car 0.00 0 -1.57 599.41 156.40 629.75 189.25 2.85 1.63 8.33 11.40 -0.20 1.57 1.57
type truncated occluded alpha bbox_2d(4) dimensions_3d(3) location_3d(3) rotation_y
```

- **type**: Object class (Car, Truck, Van, Tram, Pedestrian, Cyclist, etc.)
- **truncated**: Truncation level [0,1]
- **occluded**: Occlusion level {0,1,2,3}
- **alpha**: Observation angle [-pi, pi]
- **bbox_2d**: 2D bounding box [left, top, right, bottom]
- **dimensions_3d**: 3D dimensions [height, width, length]
- **location_3d**: 3D location [x, y, z] in camera coordinates
- **rotation_y**: Rotation around Y-axis [-pi, pi]

## Conversion Implementation

### PandaSet Converter (`pandaset_to_kitti.py`)

#### Key Features
- **Coordinate Transformation**: World → PandaSet Ego → Standard Ego
- **Image Processing**: Optional undistortion support (default: disabled)
- **Multi-format Support**: PNG/Binary encoding options
- **Sensor Selection**: Uses forward-facing LiDAR (sensor_id=1)

#### Command Line Arguments
```bash
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --help

Arguments:
  --pandaset_root       PandaSet dataset root directory (default: ./pandaset)
  --output_root        Output KITTI format directory (default: ./pandaset-kitti)
  --sequences          Specific sequences to convert (default: auto-detect all)
  --train_ratio        Training set ratio (default: 1.0)
  --encode_img         Encode images as binary files instead of PNG
  --undistort_img      Enable image undistortion (default: disabled)
  --calib_file         Path to static_extrinsic_calibration.yaml
```

#### Usage Examples
```bash
# Basic conversion (all sequences, PNG images)
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py

# Convert specific sequences with binary encoding
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --sequences 001 002 003 --encode_img

# Enable undistortion with custom calibration file
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --undistort_img --calib_file /path/to/calib.yaml

# Custom training split ratio
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --train_ratio 0.8
```

### DAIR-V2X-I Converter (`dair_v2x_i_to_kitti.py`)

#### Key Features
- **Coordinate Consistency**: Virtual LiDAR = KITTI Ego (same coordinate system)
- **Image Processing**: Smart undistortion detection (default: disabled for pre-processed images)
- **Projection Matrix**: Always uses original cam_K for consistent 3D-2D projections
- **Multi-format Support**: JPEG/Binary encoding options

#### Command Line Arguments
```bash
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --help

Arguments:
  --dair_v2x_root      DAIR-V2X-I dataset root directory (default: ./dair-v2x-i)
  --output_root        Output KITTI format directory (default: ./dair-v2x-i-kitti)
  --data_split         Data split to convert (default: training)
  --max_frames         Maximum number of frames to convert (default: all)
  --encode_img         Encode images as binary files instead of JPEG
  --undistort_img      Enable image undistortion (default: disabled)
```

#### Usage Examples
```bash
# Basic conversion (all frames, JPEG images)
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py

# Convert first 1000 frames with binary encoding
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --max_frames 1000 --encode_img

# Convert testing split only
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --data_split testing

# Force undistortion (not recommended for DAIR-V2X-I)
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --undistort_img
```

### Conversion Process Details

#### PandaSet Conversion Pipeline

1. **Data Loading**
   ```python
   # Load sequence data
   seq = dataset[seq_id]
   seq.load()
   seq.lidar.set_sensor(1)  # Select forward-facing LiDAR
   ```

2. **Coordinate Transformation**
   ```python
   # PandaSet Ego → Standard Ego transformation
   transform_matrix = np.array([
       [0,  1,  0],    # y_pandaset → x_standard  
       [-1, 0,  0],    # -x_pandaset → y_standard
       [0,  0,  1]     # z_pandaset → z_standard
   ])
   ```

3. **Camera Calibration**
   ```python
   # World → Camera transformation
   T_world_to_camera = np.linalg.inv(pose_to_transform_matrix(camera_pose))
   T_world_to_ego = np.linalg.inv(pose_to_transform_matrix(lidar_pose))
   T_ego_to_camera = T_world_to_camera @ np.linalg.inv(T_world_to_ego)
   ```

#### DAIR-V2X-I Conversion Pipeline

1. **Data Loading**
   ```python
   # Load data_info.json
   data_info = load_json(data_info_path)
   for frame_info in data_info:
       # Process each frame
   ```

2. **Coordinate Handling**
   ```python
   # Virtual LiDAR = KITTI Ego (same coordinate system)
   # Direct coordinate copy, no transformation needed
   points_kitti_ego = virtual_lidar_points
   ```

3. **Calibration Processing**
   ```python
   # Always use original cam_K for projection consistency
   if 'cam_K' in camera_intrinsic:
       K = np.array(camera_intrinsic['cam_K']).reshape(3, 3)
       P2 = np.hstack([K, np.zeros((3, 1))])
   ```

## Calibration Verification

### PandaSet Verification (`kitti_pandaset_verification.py`)

#### Features
- **Point Cloud Projection**: Verify LiDAR-camera calibration accuracy
- **3D Box Visualization**: Check annotation consistency
- **Depth Color Mapping**: Visualize point cloud depth distribution
- **Multi-format Support**: Handle both PNG and binary image formats

#### Usage Examples
```bash
# Verify single frame
python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py --single_frame 001_000000

# Batch verification with custom settings
python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py --batch_frames 50 --max_points 100000

# Verify binary encoded dataset
python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py --decode_img
```

### DAIR-V2X-I Verification (`kitti_dair_v2x_verification.py`)

#### Features
- **Projection Accuracy**: Verify cam_K-based projection consistency
- **3D-2D Alignment**: Check 3D box projection to 2D images
- **Coordinate Verification**: Validate Virtual LiDAR = KITTI Ego assumption
- **Multi-format Support**: Handle both JPEG and binary image formats

#### Usage Examples
```bash
# Verify single frame
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py --single_frame 000000

# Batch verification for testing split
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py --split testing --batch_frames 25

# Verify binary encoded dataset
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py --decode_img
```

### Verification Output

#### Generated Files
- `verification_XXXXXX.jpg`: Individual frame visualization
- `verification_summary.jpg`: Batch verification overview
- `verification_report.txt`: Detailed statistics and analysis

#### Visualization Elements
- **Point Cloud**: Depth-colored LiDAR points projected to image
- **3D Boxes**: Object bounding boxes projected from 3D to 2D
- **2D Boxes**: Original 2D annotations (training split only)
- **Color Coding**: Different object types shown in different colors

## Usage Guide

### Environment Setup

```bash
# Install required packages
pip3 install -r tools/how_to_generate_kitti_format_dataset/requirements.txt

# For pandaset devkit
# refer https://github.com/scaleapi/pandaset-devkit to install pandaset
```

### Directory Preparation

```bash
# PandaSet
mkdir -p pandaset
# Download and extract PandaSet data to pandaset/

# DAIR-V2X-I  
mkdir -p dair-v2x-i
# Download and extract DAIR-V2X-I data to dair-v2x-i/
```

### Conversion Workflow

#### PandaSet Conversion
```bash
# Step 1: Basic conversion
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --pandaset_root /path/to/pandaset --output_root /path/to/output

# Step 2: Verify results
python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py --kitti_root /path/to/output

# Step 3: Check verification results
# View verification_*.jpg files and verification_report.txt
```

#### DAIR-V2X-I Conversion
```bash
# Step 1: Basic conversion
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --dair_v2x_root /path/to/dair-v2x-i --output_root /path/to/output

# Step 2: Verify results
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py --kitti_root /path/to/output

# Step 3: Check verification results
# View dair_v2x_verification_*.jpg files and dair_v2x_verification_report.txt
```

### Performance Optimization

#### Memory Management
```bash
# Limit maximum points for visualization to reduce memory usage
python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py --max_points 20000
# Or use kitti_dair_v2x_verification.py with the same flag

# Process limited number of frames for large datasets (DAIR-V2X-I example)
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --max_frames 1000
```

#### Storage Optimization
```bash
# Use binary encoding to reduce file size during conversion
python3 tools/how_to_generate_kitti_format_dataset/pandaset_to_kitti.py --sequences 001 002 --encode_img
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --max_frames 1000 --encode_img

# Remember to use --decode_img during verification
python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py --decode_img
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py --decode_img
```

### Troubleshooting

#### Common Issues

1. **Memory Error during Conversion**
   ```bash
    # Solution: Process in smaller batches when the converter supports it
    python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --max_frames 500
   ```

2. **Missing Dependencies**
   ```bash
   # For PandaSet
   # refer https://github.com/scaleapi/pandaset-devkit to install pandaset
   
   # For YAML support
   pip install PyYAML
   
   # For 3D operations
   pip install open3d transforms3d
   ```

3. **Calibration Verification Issues**
   ```bash
   # Check if using correct image format
    python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py --decode_img  # For binary images
    python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py --decode_img  # For binary images
    python3 tools/how_to_generate_kitti_format_dataset/kitti_pandaset_verification.py               # For regular images
    python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py               # For regular images
   ```

4. **DAIR-V2X-I Undistortion Warning**
   ```bash
   # This is normal - images are pre-undistorted
   # Only use --undistort_img if you have raw distorted images
    python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py              # Recommended
    python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --undistort_img  # Only for raw images
   ```

#### Dataset-Specific Notes

**PandaSet**:
- Uses sensor_id=1 (forward-facing LiDAR) for better compatibility
- Coordinate transformation from PandaSet ego to standard ego
- Optional fisheye undistortion support with YAML calibration

**DAIR-V2X-I**:
- Images are pre-undistorted, avoid re-processing
- Virtual LiDAR coordinate system matches KITTI ego coordinates
- Always uses original cam_K for projection consistency

### Best Practices

1. **Always verify converted datasets** using verification scripts
2. **Check coordinate system consistency** in verification outputs
3. **Use appropriate image encoding** based on storage/processing needs
4. **Monitor memory usage** for large datasets
5. **Keep original cam_K for DAIR-V2X-I** to ensure projection accuracy

## Conclusion

This conversion pipeline provides robust, verified solutions for converting PandaSet and DAIR-V2X-I datasets to KITTI format, with comprehensive calibration verification and flexible configuration options. The implementations handle coordinate system transformations, sensor calibration, and annotation format conversions while maintaining data integrity and projection accuracy.

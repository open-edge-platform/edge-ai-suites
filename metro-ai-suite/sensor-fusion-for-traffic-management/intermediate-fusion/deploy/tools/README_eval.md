# KITTI 3D Object Detection Evaluation

The commands below assume this project root is already the current working directory.

## 📑 Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Complete Workflow](#complete-workflow)
- [Command Reference](#command-reference)
- [Understanding Results](#understanding-results)
- [Output Files](#output-files)
- [Prediction File Format](#prediction-file-format)
- [Class Name Mapping](#class-name-mapping)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

---

## Overview

This evaluation script assesses 3D object detection results using KITTI-format annotation files. It computes standard metrics including:
- Average Precision (AP) at IoU 0.5
- Precision-Recall curves
- Position, orientation, and size errors
- Distance-range breakdowns

**Supported**: KITTI-format dataset

---

## Quick Start

```bash
# 1. Generate predictions with bevfusion
./build/bevfusion data/v2xfusion/dataset --dump-pred --pred-dir build/pred

# 2. Run evaluation
python3 tools/kitti_3d_eval.py \
  --gt data/v2xfusion/dataset/label_2 \
  --pred build/pred \
  --out build/eval_output

# 3. View results
cat build/eval_output/summary.csv
```

**Expected output**: CSV with AP@0.5, F1, and error metrics per class.

---

## Complete Workflow

### Step 1: Generate Predictions

First, run BEVFusion inference to generate prediction files:

```bash
./build/bevfusion /path/to/dataset --dump-pred --pred-dir build/pred
```

**What happens**:
- Processes all frames in the dataset
- Generates one `.txt` file per frame in `build/pred/` directory
- Files are in KITTI `label_2` format

**Output structure**:
```
build/pred/
├── 000000.txt
├── 000001.txt
├── 000002.txt
...
```

### Step 2: Run Evaluation Script

Basic usage:

```bash
python3 tools/kitti_3d_eval.py \
    --gt /path/to/dataset/label_2 \
    --pred build/pred \
  --out build/eval_out
```

**Processing**:
1. Loads ground truth annotations
2. Loads prediction files (matches by frame ID)
3. Filters by distance range
4. Computes IoU for each detection
5. Matches predictions to ground truth
6. Calculates AP, precision, recall
7. Generates output files and plots

### Step 3: Analyze Results

**Quick summary**:
```bash
# View overall metrics
cat build/eval_output/summary.csv

# View detailed JSON
python3 -m json.tool build/eval_output/summary.json | less

# View PR curves (if matplotlib installed)
ls build/eval_output/pr_*.png
```

---

## Command Reference

### Common Parameters

- `--gt PATH`: Ground truth annotation folder path (required)
- `--pred PATH`: Prediction folder path (required)
- `--out PATH`: Output results folder (default: `eval_output`)
- `--max-distance METERS`: Maximum evaluation distance (default: `102.4`)
- `--distance-axis AXIS`: Axis for distance calculation (default: `x`, options: `x`, `y`, `z`)
- `--classes CLASSES`: Comma-separated class list (default: `Car,Truck,Van,Bus,Pedestrian,Cyclist`)
- `--quiet`: Quiet mode, reduce output verbosity

### Coordinate System Transformation

If GT and predictions have different coordinate systems, use these parameters:

- `--flip-y-gt`: Flip GT y-axis (right-hand ↔ left-hand conversion)
- `--flip-y-pred`: Flip prediction y-axis
- `--z-center-gt`: Convert GT z from center height to bottom height
- `--z-center-pred`: Convert prediction z from center height to bottom height

**When to use**:
- **`--flip-y-*`**: When one coordinate system is right-handed and the other is left-handed
- **`--z-center-*`**: When one uses box center for z-coordinate and the other uses bottom face

### Advanced Options

- `--class-map-gt JSON_FILE`: Custom GT class name mapping (JSON format)
- `--class-map-pred JSON_FILE`: Custom prediction class name mapping (JSON format)
- `--iou-threshold FLOAT`: IoU threshold for matching (default: `0.5`)

---

## Understanding Results

### Key Metrics Explained

#### AP@0.5 (Average Precision at IoU 0.5)
- **11-point**: Interpolated at 11 recall levels (0.0, 0.1, ..., 1.0) - legacy metric
- **40-point**: Interpolated at 40 recall levels - more precise, **recommended**
- **Range**: 0-100 (higher is better)
- **Interpretation**: 
  - \>80%: Excellent
  - 60-80%: Good
  - 40-60%: Moderate
  - <40%: Poor

#### Max F1 Score
- Best harmonic mean of precision and recall
- **Range**: 0-1 (higher is better)
- **Interpretation**: Optimal operating point on PR curve

#### Mean Center Distance (meters)
- Average Euclidean distance between predicted and GT box centers (for TP detections)
- **Typical values**: 0.1-0.5m for good detections
- Lower is better

#### Mean Yaw Error (radians)
- Average orientation error (for TP detections)
- **Range**: 0-π (lower is better)
- **Typical values**: 0.05-0.2 rad (3-11 degrees) for good detections

#### Mean Size Error
- Average L2 norm of (height, width, length) error (for TP detections)
- **Typical values**: 0.1-0.5m for good detections
- Lower is better

### Distance Range Breakdown

The script automatically evaluates different distance ranges:

| Range | Use Case |
|-------|----------|
| **0-30m** | Near field - typically highest accuracy |
| **30-60m** | Mid field - challenging for small objects |
| **60-102.4m** | Far field - most difficult |
| **all** | Overall performance |

**Why it matters**: 
- Object detection accuracy typically degrades with distance
- Different applications care about different ranges (parking: 0-30m, highway: 30-100m)

---

## Output Files

### 1. `summary.csv` (Human-readable table)

**Format**:
```csv
class,metric,distance_bin,iou_thr,num_gt,num_pred,ap11,ap40,max_f1,precision_at_max_f1,recall_at_max_f1,mean_center_dist_tp,mean_yaw_err_tp_rad,mean_size_err_l2_tp
Car,3d,all,0.5,5241,5389,0.8532,0.8715,0.8200,0.8456,0.7968,0.2510,0.0830,0.1470
Car,3d,0-30,0.5,3821,3956,0.9211,0.9354,0.8900,0.9087,0.8725,0.1820,0.0610,0.1210
Car,3d,30-60,0.5,1285,1298,0.7845,0.8123,0.7600,0.7812,0.7401,0.3270,0.0980,0.1680
Car,3d,60-102.4,0.5,135,135,0.6521,0.6789,0.6400,0.6598,0.6209,0.4530,0.1250,0.2150
Truck,3d,all,0.5,1523,1487,0.7123,0.7345,0.7100,0.7289,0.6923,0.3120,0.1120,0.2350
...
```

**Columns**:
- `class`: Object class (Car, Truck, etc.)
- `metric`: Evaluation type ("3d" for 3D detection, "bev" for bird's-eye view)
- `distance_bin`: Distance range ("all", "0-30", "30-60", "60-102.4" in meters)
- `iou_thr`: IoU threshold used (0.5 for Car, 0.3 for Pedestrian/Cyclist)
- `num_gt`: Number of ground truth objects
- `num_pred`: Number of predictions
- `ap11`: 11-point interpolated Average Precision
- `ap40`: 40-point interpolated Average Precision (more accurate)
- `max_f1`: Maximum F1 score achieved
- `precision_at_max_f1`: Precision at the maximum F1 score point
- `recall_at_max_f1`: Recall at the maximum F1 score point
- `mean_center_dist_tp`: Average center distance error in meters (true positives only)
- `mean_yaw_err_tp_rad`: Average yaw error in radians (true positives only)
- `mean_size_err_l2_tp`: Average L2 size error in meters (true positives only)

**Example Analysis**:
```csv
Car,3d,0-30,0.5,3821,3956,0.9211,0.9354,0.8900,0.9087,0.8725,0.1820,0.0610,0.1210
```
- Excellent near-field 3D detection (93.5% AP@0.5)
- Slightly more predictions than GT (3956 vs 3821) - some false positives
- Very accurate positions (18.2cm error) and orientations (3.5 degrees)
- Max F1 of 0.89 achieved at 90.87% precision and 87.25% recall

### 2. `summary.json` (Detailed machine-readable)

**Structure**:
```json
{
  "config": {
    "gt_dir": "path/to/gt/labels",
    "pred_dir": "path/to/predictions",
    "output_dir": "path/to/output",
    "classes": ["Car", "Truck", ...],
    "distance_ranges": [[0, 30], [30, 60], [60, 102.4]],
    "iou_thresholds": {"Car": 0.5, "Pedestrian": 0.3, ...}
  },
  "results": {
    "Car": {
      "3d": {
        "all": {
          "iou_thr": 0.5,
          "num_gt": 5241,
          "num_pred": 5389,
          "ap11": 0.8532,
          "ap40": 0.8715,
          "max_f1": 0.8200,
          "precision_at_max_f1": 0.8456,
          "recall_at_max_f1": 0.7968,
          "mean_center_dist_tp": 0.2510,
          "mean_yaw_err_tp_rad": 0.0830,
          "mean_size_err_l2_tp": 0.1470,
          "pr_curve": {
            "precisions": [1.0, 0.9876, 0.9543, ...],
            "recalls": [0.0, 0.0234, 0.0512, ...],
            "scores": [15.234, 14.876, 14.123, ...]
          }
        },
        "0-30": { ... },
        "30-60": { ... },
        "60-102.4": { ... }
      },
      "bev": { ... }
    },
    "Truck": { ... },
    ...
  }
}
```

**Use cases**:
- Plotting custom PR curves
- Further analysis with pandas/numpy
- Integration with MLOps pipelines

### 3. `pr_*.png` (Precision-Recall Curves)

Generated for each class (requires matplotlib).

**Example**: `pr_Car_3d.png`

**How to interpret**:
- **X-axis**: Recall (0-1) - fraction of GT objects detected
- **Y-axis**: Precision (0-1) - fraction of predictions that are correct
- **Curve**: Higher and to the right is better
- **Area under curve**: Approximates AP

**Typical curve shapes**:
- **Good**: Curve stays high (near 1.0) across all recall levels
- **Moderate**: Curve drops as recall increases (precision-recall tradeoff)
- **Poor**: Curve stays low or drops quickly

---

## Prediction File Format

Each prediction file (`.txt`) must contain 15 or 16 columns per line:

```
type truncated occluded alpha bbox_l bbox_t bbox_r bbox_b h w l x y z ry [score]
```

### Column Descriptions

| Column | Name | Type | Description | Typical Range |
|--------|------|------|-------------|---------------|
| 1 | `type` | string | Object class (e.g., "Car", "Truck") | - |
| 2 | `truncated` | float | Truncation level (0-1) | 0.0 for detections |
| 3 | `occluded` | int | Occlusion level (0-3) | 0 for detections |
| 4 | `alpha` | float | Observation angle (-π to π) | Can be 0.0 |
| 5-8 | `bbox_l/t/r/b` | float | 2D bounding box (left, top, right, bottom) | Pixel coords; can be 0 if unavailable |
| 9 | `h` | float | 3D box height (meters) | 0.5-5.0 |
| 10 | `w` | float | 3D box width (meters) | 0.5-3.0 |
| 11 | `l` | float | 3D box length (meters) | 1.0-15.0 |
| 12 | `x` | float | 3D center x in ego/LiDAR frame (meters) | -100 to 100 |
| 13 | `y` | float | 3D center y in ego/LiDAR frame (meters) | -50 to 50 |
| 14 | `z` | float | 3D center z in ego/LiDAR frame (meters) | -5 to 5 |
| 15 | `ry` | float | Yaw/rotation around y-axis (radians) | -π to π |
| 16 | `score` | float | **Confidence score** | Any range (unnormalized OK) |

### Important Notes

#### Score Column (Column 16)
- **Required** for proper AP calculation
- Can be unnormalized (e.g., `0.1` to `16.0`, raw logits from network)
- Only **relative ranking** matters for AP computation
- If missing, all detections get `score=1.0` (no ranking - AP becomes meaningless)

#### Coordinate System
- Must match ground truth (typically **ego/LiDAR frame**)
- **Ego frame**: Origin at vehicle, x=forward, y=left, z=up
- **Yaw convention**: 0 = facing +x, π/2 = facing +y, counter-clockwise

#### Example Line
```
Car 0.0 0 0.0 0.0 0.0 0.0 0.0 1.52 1.75 4.21 12.34 -2.15 0.85 1.57 8.234
```
- Class: Car
- 3D box: height=1.52m, width=1.75m, length=4.21m
- Position: (12.34, -2.15, 0.85) in ego frame
- Yaw: 1.57 rad (90°, facing left)
- Score: 8.234 (high confidence)

---

## Class Name Mapping

### Default Prediction Class Mapping

The script automatically maps common detection class names to KITTI-standard names:

```python
DEFAULT_PRED_CLASS_MAP = {
    "car": "Car",
    "truck": "Truck",
    "construction_vehicle": "Truck",
    "trailer": "Truck",
    "bus": "Bus",
    "pedestrian": "Pedestrian",
    "bicycle": "Cyclist",
    "motorcycle": "Motorcyclist",
    "traffic_cone": "Trafficcone",
    "barrier": "Other"
}
```

### Custom Mapping

Provide a JSON file with `--class-map-pred`:

**Example**: `my_class_map.json`
```json
{
  "my_car_class": "Car",
  "my_truck_class": "Truck",
  "person": "Pedestrian"
}
```

**Usage**:
```bash
python3 tools/kitti_3d_eval.py \
    --gt dataset/label_2 \
    --pred pred \
    --class-map-pred my_class_map.json
```

---

## Troubleshooting

### Issue 1: All APs are 0

**Symptoms**:
```
Car,all,0.00,0.00,0.00,0.0,0.0,0.0,5241,5389
```

**Possible Causes & Solutions**:

1. **Coordinate system mismatch**
   ```bash
   # Try coordinate transformations
   python3 tools/kitti_3d_eval.py \
       --gt dataset/label_2 \
       --pred pred \
       --z-center-gt \       # if GT z is box center
       --flip-y-gt           # if GT uses different handedness
   ```

2. **Distance filtering too strict**
   ```bash
   # Check max GT distance in your dataset
   # Then adjust --max-distance accordingly
   python3 tools/kitti_3d_eval.py \
       --gt dataset/label_2 \
    --pred build/pred \
       --max-distance 200.0   # increase
   ```

3. **Class name mismatch**
   ```bash
   # Check class names in predictions
  head build/pred/000000.txt
   # Should match GT class names (or use mapping)
   ```

4. **Completely wrong predictions (IoU = 0)**
   - Visualize predictions with `bevfusion --display`
   - Check if boxes are in completely wrong locations
   - Verify calibration is correct

**Debug commands**:
```bash
# Check GT statistics
python3 tools/kitti_3d_eval.py \
    --gt dataset/label_2 \
  --pred build/pred \
  --out build/eval_out 2>&1 | grep "num_gt"

# Check prediction statistics
wc -l build/pred/*.txt  # should have lines (objects)
head build/pred/000000.txt  # inspect format
```

---

### Issue 2: Incorrect PR Curves (flat/strange shape)

**Symptoms**:
- PR curve is flat at precision=1.0
- All predictions have same score

**Cause**: Score column (column 16) is missing or constant

**Solution**: Ensure predictions include score column
```bash
# Check if score column exists
awk '{print NF}' build/pred/000000.txt | head -1
# Should output "16" (not "15")

# Check if scores vary
awk '{print $16}' build/pred/000000.txt | sort -u | head -10
# Should show different values
```

**Fix**: Make sure `bevfusion` was run with `--dump-pred`

---

### Issue 3: Prediction Files Not Found

**Symptoms**:
```
Error: No prediction files found in build/pred/
```

**Causes & Solutions**:

1. **bevfusion not run with --dump-pred**
   ```bash
   # Correct command
  ./build/bevfusion dataset_path --dump-pred --pred-dir build/pred
   ```

2. **Wrong prediction directory path**
   ```bash
   # Check actual location
  ls -lh build/pred/  # if run from the project root
   
   # Fix path in evaluation
   python3 tools/kitti_3d_eval.py \
       --gt dataset/label_2 \
       --pred build/pred    # correct path
   ```

3. **Predictions generated but empty**
   ```bash
   # Check if files have content
  ls -lh build/pred/*.txt
   # File size should be >0 bytes
   
   # If empty, check bevfusion output for errors
   ```

---

### Issue 4: Low AP Compared to Baseline

**Symptoms**: AP is 20-30% lower than expected

**Debug Steps**:

1. **Verify distance filtering**
   ```bash
   # Try without distance limit
   python3 tools/kitti_3d_eval.py \
       --gt dataset/label_2 \
       --pred build/pred \
       --max-distance 999999
   ```

2. **Check per-distance breakdown**
   ```bash
   # Look at summary.csv
  cat build/eval_output/summary.csv | grep "Car"
   # If far-field (60-102m) is terrible but near-field (0-30m) is good,
   # this is expected (distant objects are harder)
   ```

3. **Visualize to check detection quality**
   ```bash
  ./build/bevfusion dataset --display
   # Visually inspect if detections look good
   ```

4. **Compare INT8 vs FP32**
   ```bash
   # Generate FP32 predictions
  ./build/bevfusion dataset --fp32 --dump-pred --pred-dir build/pred_fp32
   
   # Evaluate both
  python3 tools/kitti_3d_eval.py --gt dataset/label_2 --pred build/pred --out build/eval_int8
  python3 tools/kitti_3d_eval.py --gt dataset/label_2 --pred build/pred_fp32 --out build/eval_fp32
   
   # Compare summary.csv files
  diff build/eval_int8/summary.csv build/eval_fp32/summary.csv
   ```

---

## Examples

### Example 1: Basic Evaluation (V2XFusion Dataset)

```bash
# Generate predictions
./build/bevfusion data/v2xfusion/dataset --dump-pred --pred-dir build/pred

# Evaluate
python3 tools/kitti_3d_eval.py \
  --gt data/v2xfusion/dataset/label_2 \
  --pred build/pred \
  --out build/eval_v2x \
    --max-distance 102.4 \
    --z-center-gt

# View results
cat build/eval_v2x/summary.csv
```

**Expected Output**:
```csv
class,metric,distance_bin,iou_thr,num_gt,num_pred,ap11,ap40,max_f1,precision_at_max_f1,recall_at_max_f1,mean_center_dist_tp,mean_yaw_err_tp_rad,mean_size_err_l2_tp
Car,3d,all,0.5,5241,5389,0.8530,0.8710,0.8200,0.8456,0.7968,0.2500,0.0800,0.1500
Car,3d,0-30,0.5,3821,3956,0.9210,0.9350,0.8900,0.9087,0.8725,0.1800,0.0600,0.1200
Car,3d,30-60,0.5,1285,1298,0.7840,0.8120,0.7600,0.7812,0.7401,0.3300,0.1000,0.1700
Car,3d,60-102.4,0.5,135,135,0.6520,0.6790,0.6400,0.6598,0.6209,0.4500,0.1300,0.2200
Truck,3d,all,0.5,1523,1487,0.7120,0.7350,0.7100,0.7289,0.6923,0.3100,0.1100,0.2400
...
```

### Example 2: Evaluate Specific Classes Only

```bash
# Only evaluate Car, Truck, and Pedestrian
python3 tools/kitti_3d_eval.py \
    --gt dataset/label_2 \
  --pred build/pred \
    --classes Car,Truck,Pedestrian \
  --out build/eval_selected
```

### Example 3: Custom Distance Range

```bash
# Evaluate only objects within 50 meters
python3 tools/kitti_3d_eval.py \
    --gt dataset/label_2 \
  --pred build/pred \
    --max-distance 50.0 \
  --out build/eval_50m
```

### Example 4: Coordinate System Conversion

```bash
# GT uses center-height z and right-hand coordinates
# Predictions use bottom-height z and left-hand coordinates
python3 tools/kitti_3d_eval.py \
    --gt dataset/label_2 \
  --pred build/pred \
    --z-center-gt \
    --flip-y-gt \
  --out build/eval_converted
```

### Example 5: Quiet Mode for Large Datasets

```bash
# Reduce console output for faster processing
python3 tools/kitti_3d_eval.py \
    --gt large_dataset/label_2 \
    --pred pred_large \
    --quiet \
  --out build/eval_large

# Check progress
tail -f build/eval_large/summary.csv
```

---

## Performance Notes

- **Processing speed**: ~100-500 frames/sec (CPU, single-threaded)
- **Large datasets** (>10K frames): Use `--quiet` to reduce I/O overhead
- **Memory usage**: ~100-500MB for typical datasets (depends on number of objects)

**Optimization tips**:
- Use `--classes` to evaluate only needed classes
- Run on machine with fast SSD (I/O bound)
- For repeated evaluations, cache GT annotations (modify script)

---

## Quick Reference

```bash
# Basic
python3 tools/kitti_3d_eval.py --gt GT_DIR --pred PRED_DIR

# With coordinate transforms
python3 tools/kitti_3d_eval.py --gt GT_DIR --pred PRED_DIR --z-center-gt --flip-y-gt

# Specific classes and distance
python3 tools/kitti_3d_eval.py --gt GT_DIR --pred PRED_DIR --classes Car,Truck --max-distance 50.0

# Quiet mode
python3 tools/kitti_3d_eval.py --gt GT_DIR --pred PRED_DIR --quiet --out results/
```

**Output files**: `summary.csv`, `summary.json`, `pr_*.png`

**Key metric**: **AP@0.5 (40-pt)** in `summary.csv`

---

## Additional Resources

For the main deployment guide, see [../docs/GSG.md](../docs/GSG.md).

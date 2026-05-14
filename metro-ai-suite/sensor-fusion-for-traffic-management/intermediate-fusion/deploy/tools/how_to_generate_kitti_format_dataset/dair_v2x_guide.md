# Dataset Conversion Guide: DAIR-V2X-I to KITTI Format

The files in this directory now cover only the DAIR-V2X-I conversion flow, and the commands below document the files that currently remain in `tools/how_to_generate_kitti_format_dataset/`.

## Available Files

| File | Purpose |
| --- | --- |
| `dair_v2x_i_to_kitti.py` | Convert the DAIR-V2X-I dataset to a KITTI-style layout |
| `kitti_dair_v2x_verification.py` | Verify calibration, point cloud projection, and 3D box alignment on the converted dataset |
| `requirements.txt` | Python dependencies used by the converter and verifier |

## Install Dependencies

```bash
pip3 install -r tools/how_to_generate_kitti_format_dataset/requirements.txt
```

## Source Dataset Layout

The converter expects a DAIR-V2X-I root like:

```text
<dair_v2x_root>/
  data_info.json
  velodyne/
  image/
  calib/
    camera_intrinsic/
    virtuallidar_to_camera/
  label/
    camera/
    virtuallidar/
```

## Output Layout

The converter creates a KITTI-style tree under `<output_root>`:

```text
<output_root>/
  training/
    image_2/
    velodyne/
    label_2/
    calib/
  testing/
    image_2/
    velodyne/
    calib/
```

Use `--data_split training` when you want labels written to `training/label_2/`. Use `--data_split testing` when you only need images, point clouds, and calibration.

## Quick Start

### Convert the training split

```bash
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py \
  --dair_v2x_root /path/to/dair-v2x-i \
  --output_root /path/to/dair-v2x-i-kitti
```

### Convert the testing split

```bash
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py \
  --dair_v2x_root /path/to/dair-v2x-i \
  --output_root /path/to/dair-v2x-i-kitti \
  --data_split testing
```

### Verify the converted dataset

```bash
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py \
  --kitti_root /path/to/dair-v2x-i-kitti \
  --split training
```

If you converted images with `--encode_img`, add `--decode_img` when running the verifier.

## Conversion Behavior

- LiDAR point clouds are saved as KITTI `velodyne/*.bin` files with float32 `[x, y, z, intensity]` layout.
- The current converter treats DAIR-V2X-I virtual LiDAR coordinates as already aligned with the KITTI ego convention used by this project: `x = front`, `y = left`, `z = up`.
- Camera calibration is written to KITTI `calib/*.txt` files from the DAIR-V2X-I intrinsics and `virtuallidar_to_camera` extrinsics.
- By default, images are copied in their regular image format. With the standard DAIR-V2X-I release, that means JPEG files under `image_2/`.
- With `--encode_img`, images are written as `.bin` payloads instead, and the verifier must be run with `--decode_img`.
- `--undistort_img` is disabled by default because the standard DAIR-V2X-I images are already undistorted. Only enable it if you are working from raw distorted images.

## Converter CLI

```bash
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py --help
```

| Option | Meaning |
| --- | --- |
| `--dair_v2x_root` | DAIR-V2X-I dataset root. Default: `./dair-v2x-i` |
| `--output_root` | Output KITTI-style dataset root. Default: `./dair-v2x-i-kitti` |
| `--data_split` | Split to convert. Choices: `training`, `testing` |
| `--max_frames` | Stop after converting the first `N` frames |
| `--encode_img` | Save images as `.bin` instead of regular image files |
| `--undistort_img` | Apply undistortion, which is usually unnecessary for DAIR-V2X-I |

### Common Examples

```bash
# Convert only the first 1000 frames
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py \
  --dair_v2x_root /path/to/dair-v2x-i \
  --output_root /path/to/dair-v2x-i-kitti \
  --max_frames 1000

# Convert with binary-encoded images
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py \
  --dair_v2x_root /path/to/dair-v2x-i \
  --output_root /path/to/dair-v2x-i-kitti \
  --encode_img
```

## Verification

The verifier overlays point clouds and 3D boxes on the camera image so you can catch calibration or label conversion problems early.

```bash
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py --help
```

| Option | Meaning |
| --- | --- |
| `--kitti_root` | Converted KITTI-style dataset root. Default: `./dair-v2x-i-kitti` |
| `--split` | Dataset split to verify. Choices: `training`, `testing` |
| `--max_frames` | Maximum number of frames to inspect before sampling |
| `--batch_frames` | Number of frames included in batch verification |
| `--max_points` | Max projected LiDAR points shown per frame |
| `--output_dir` | Directory for per-frame verification images. Default: `dair_v2x_verification_results` |
| `--single_frame` | Verify one specific frame ID, for example `000000` |
| `--no_batch` | Skip batch verification and only process the selected or sampled frame |
| `--decode_img` | Decode `.bin` images produced by `--encode_img` |

### Common Examples

```bash
# Verify one specific frame
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py \
  --kitti_root /path/to/dair-v2x-i-kitti \
  --single_frame 000000

# Run batch verification on the testing split
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py \
  --kitti_root /path/to/dair-v2x-i-kitti \
  --split testing \
  --batch_frames 25

# Verify a dataset converted with --encode_img
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py \
  --kitti_root /path/to/dair-v2x-i-kitti \
  --decode_img
```

## Verification Outputs

After verification, expect these artifacts:

- Per-frame visualizations in `dair_v2x_verification_results/` by default, or the directory set with `--output_dir`
- A batch summary image named `dair_v2x_verification_summary.jpg`
- A text report named `dair_v2x_verification_report.txt`

The `training` split can also overlay the converted 2D bounding boxes. The `testing` split verifies projection and calibration without `label_2/`.

## Troubleshooting

### Missing dataset root

If the converter prints that the dataset root or `data_info.json` is missing, re-check the `--dair_v2x_root` path and ensure the extracted DAIR-V2X-I tree still contains `velodyne/`, `image/`, `calib/`, and `label/`.

### Encoded images do not open in the verifier

Use the same image mode on both sides:

```bash
# Conversion
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py \
  --dair_v2x_root /path/to/dair-v2x-i \
  --output_root /path/to/dair-v2x-i-kitti \
  --encode_img

# Verification
python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py \
  --kitti_root /path/to/dair-v2x-i-kitti \
  --decode_img
```

### Large dataset, slow verification

Reduce the working set first:

```bash
python3 tools/how_to_generate_kitti_format_dataset/dair_v2x_i_to_kitti.py \
  --dair_v2x_root /path/to/dair-v2x-i \
  --output_root /path/to/dair-v2x-i-kitti \
  --max_frames 500

python3 tools/how_to_generate_kitti_format_dataset/kitti_dair_v2x_verification.py \
  --kitti_root /path/to/dair-v2x-i-kitti \
  --batch_frames 10 \
  --max_points 20000
```

## Summary

The active dataset conversion flow in this repository is now DAIR-V2X-I only. Use `dair_v2x_i_to_kitti.py` to create the KITTI-style dataset and `kitti_dair_v2x_verification.py` to validate projection quality before running BEVFusion inference or evaluation.
# Intel® OEP Sensor Fusion For Traffic Management - Release Notes

## Version 2026.1.0

**June 17, 2026**

This release delivers **BEVFusion 3D object detection** enablement and
optimization on Intel GPUs. It provides a complete end-to-end pipeline — from
training and model export to optimized deployment inference — targeting
autonomous driving and roadside perception (V2X) scenarios with multi-sensor
(Camera + LiDAR) fusion.

Supported Platforms:

| Platform | GPU |
|---|---|
| Intel Panther Lake (PTL) | Integrated GPU |
| Intel Arc B580 (Battlemage) | Discrete GPU |

**New**

- **Sparse Convolution OpenVINO GPU Plugin Implementation**

  Native 3D Sparse Convolution support in the OpenVINO GPU plugin, enabling the
  Second-based BEVFusion unified pipeline to run entirely within a single
  OpenVINO inference call on Intel GPU. The `SparseConvolution` operator
  (registered under domain `org.openvinotoolkit`) covers both SparseConv3d and
  SubMConv3d variants with fused BatchNorm + optional ReLU, totaling ~21 layers
  in the lidar sparse encoder. A custom OpenVINO build patch
  (`custom_openvino_2026.1.0_sparse_ops.patch`, ~12K lines) integrates all GPU
  kernel implementations into the OpenVINO 2026.1.0 GPU plugin.

- **BEVFusion-specific custom operators in GPU plugin**

  `SparseToDense` (sparse feature map to dense BEV tensor conversion) and
  `BevPoolV2` (camera-to-BEV view transform using precomputed geometry) are
  also implemented to support the full unified pipeline.

- **Two deployment pipelines**

  - Split (PointPillars): `./bevfusion` — 4 independent ONNX sub-graphs (camera
    backbone, lidar PFE, fuser, detection head) + external SYCL kernels,
    using standard ONNX / OpenVINO IR.
  - Unified (Second): `./bevfusion_unified` — single unified ONNX with custom
    sparse ops executed inside the OpenVINO GPU plugin.

- **Multi-dataset support**

  DAIR-V2X-I (V2X roadside) and KITTI-360, with
  geometry auto-detection from ONNX attributes via `--preset v2x|kitti` switch.

- **Training and model export toolchain**

  Complete training-to-deploy workflow including dense mode training, BEVPool
  V1/V2 support, automated ONNX export, static-V PFE export, INT8 PTQ
  quantization (NNCF-based), and NVIDIA checkpoint compatibility (direct
  conversion from CUDA-V2XFusion `.pth` to Intel GPU deploy without retraining).

**Improved**

- **INT8 and FP16 inference optimization**

  INT8 quantization via NNCF PTQ for both pipelines; FP16 inference mode for
  accuracy-first scenarios; mixed-precision support with per-stage INT8 toggles
  in the split pipeline.

- **SYCL-based high-performance kernels**

  Hand-written SYCL kernels for voxelization (PointPillars and Second styles),
  BEV pooling, pillar scatter, and CenterHead post-processing (heatmap top-k,
  box decode, rotate-NMS).

- **Docker-based deployment**

  Published Docker image `intel/tfcc:2026.1.0-ubuntu24` with one-command smoke
  test and interactive container mode.

- **Visualization**

  Built-in visualization interface with BEV and camera-view overlays
  (`--save-image`, `--save-video`, `--display`).

**Known Issues**

- On Battlemage GPUs (Arc B580), the split pipeline falls back to FP16 for the
  fuser stage (`fuser.onnx`) due to a known INT8 fuser issue;
  other stages remain INT8.
- Bundled release model assets use dummy weights for runtime interface
  validation; real trained weights are required for meaningful detection results.



<!--hide_directive
:::{toctree}
:hidden:

Release Notes 2025 <release-notes/release-notes-2025.md>
:::
hide_directive-->

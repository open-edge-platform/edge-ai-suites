#!/usr/bin/env python3
"""ONNX export support for SparseConv3d and SubMConv3d as OpenVINO GPU custom ops.

Defines two custom ONNX operators under the ``bevfusion`` domain:

* ``bevfusion::SparseConv3d``  – strided 3-D sparse convolution
* ``bevfusion::SubMConv3d``    – sub-manifold 3-D sparse convolution

Runtime inputs (identical for both ops):
    features      [N, C_in]   fp32/fp16   active-voxel features
    indices       [N, 4]      int32       voxel coords [batch, z, y, x]
    spatial_shape [3]         int32       spatial volume [D, H, W]
    batch_size    [1]         int32       (currently fixed to 1)

Weights (ONNX initializers, attached automatically during export):
    weight        [kD, kH, kW, C_in, C_out]   fp32/fp16
    bias          [C_out]                       fp32/fp16  (optional)

Outputs (4 tensors, forming a SparseConvTensor for the next layer):
    out_features      [N_out, C_out]   fp32/fp16
    out_indices       [N_out, 4]       int32
    out_spatial_shape [3]              int32
    out_batch_size    [1]              int32

Usage pattern (inside an ONNX-export wrapper)::

    out_feat, out_idx, out_ss, out_bs = SparseConv3dExportOp.apply(
        features, indices, spatial_shape, batch_size,
        weight, bias,
        in_channels, out_channels,
        kernel_size, stride, padding, dilation,
    )
"""

from __future__ import annotations

import numpy as np
import torch
from torch import nn

CUSTOM_DOMAIN = "bevfusion"
CUSTOM_OPSET_VERSION = 1


# ---------------------------------------------------------------------------
# Utility: suppress JIT tracing so we can run the real PyTorch forward pass
# and cache its output while the ONNX tracer only sees the symbolic graph.
# ---------------------------------------------------------------------------

class no_jit_trace:
    """Context manager that temporarily disables JIT tracing."""

    def __enter__(self):
        self.state = torch._C._get_tracing_state()
        torch._C._set_tracing_state(None)

    def __exit__(self, *args):
        torch._C._set_tracing_state(self.state)
        self.state = None


# ---------------------------------------------------------------------------
# Global cache: keyed by Python ``id(tensor)`` so each export-time forward
# can stash the real output for the placeholder ``forward()`` to return.
# ---------------------------------------------------------------------------

_cached_outputs: dict = {}


# ===================================================================
# Op 1: bevfusion::SparseConv3d
# ===================================================================

class SparseConv3dExportOp(torch.autograd.Function):
    """ONNX-exportable placeholder for 3-D sparse convolution.

    ``forward()`` returns a dummy tensor with the correct shape (populated
    from the cache filled by the export wrapper).  ``symbolic()`` emits the
    custom ONNX node that the OpenVINO GPU plugin will execute at inference.
    """

    @staticmethod
    def forward(
        ctx,
        features: torch.Tensor,      # [N, C_in]
        indices: torch.Tensor,        # [N, 4]
        spatial_shape: torch.Tensor,  # [3]
        batch_size: torch.Tensor,     # [1]
        weight: torch.Tensor,         # [kD, kH, kW, C_in, C_out]
        bias: torch.Tensor,           # [C_out] or empty
        # --- Python int parameters (become ONNX attributes) ---
        in_channels: int,
        out_channels: int,
        kernel_size_d: int,
        kernel_size_h: int,
        kernel_size_w: int,
        stride_d: int,
        stride_h: int,
        stride_w: int,
        padding_d: int,
        padding_h: int,
        padding_w: int,
        dilation_d: int,
        dilation_h: int,
        dilation_w: int,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        # Return cached real output (populated by the export wrapper).
        cache_key = id(features)
        if cache_key in _cached_outputs:
            return _cached_outputs[cache_key]

        # Fallback: create zero-filled placeholder tensors.
        N = features.size(0)
        device = features.device
        dtype = features.dtype
        out_features = features.new_zeros((N, out_channels))
        out_indices = indices.clone()
        out_spatial_shape = spatial_shape.clone()
        out_batch_size = batch_size.clone()

        # Maintain data dependencies so the ONNX exporter does not prune inputs.
        zero = (features.sum() * 0.0
                + weight.to(dtype=dtype).sum() * 0.0
                + indices.to(dtype=dtype).sum() * 0.0
                + spatial_shape.to(dtype=dtype).sum() * 0.0
                + batch_size.to(dtype=dtype).sum() * 0.0)
        if bias is not None and bias.numel() > 0:
            zero = zero + bias.to(dtype=dtype).sum() * 0.0
        out_features = out_features + zero

        return out_features, out_indices, out_spatial_shape, out_batch_size

    @staticmethod
    def symbolic(
        g,
        features,
        indices,
        spatial_shape,
        batch_size,
        weight,
        bias,
        in_channels: int,
        out_channels: int,
        kernel_size_d: int,
        kernel_size_h: int,
        kernel_size_w: int,
        stride_d: int,
        stride_h: int,
        stride_w: int,
        padding_d: int,
        padding_h: int,
        padding_w: int,
        dilation_d: int,
        dilation_h: int,
        dilation_w: int,
    ):
        # Build input list: 4 runtime tensors + weight + optional bias
        inputs = [features, indices, spatial_shape, batch_size, weight]
        if bias is not None:
            inputs.append(bias)

        return g.op(
            f"{CUSTOM_DOMAIN}::SparseConv3d",
            *inputs,
            in_channels_i=int(in_channels),
            out_channels_i=int(out_channels),
            kernel_size_d_i=int(kernel_size_d),
            kernel_size_h_i=int(kernel_size_h),
            kernel_size_w_i=int(kernel_size_w),
            stride_d_i=int(stride_d),
            stride_h_i=int(stride_h),
            stride_w_i=int(stride_w),
            padding_d_i=int(padding_d),
            padding_h_i=int(padding_h),
            padding_w_i=int(padding_w),
            dilation_d_i=int(dilation_d),
            dilation_h_i=int(dilation_h),
            dilation_w_i=int(dilation_w),
            version_i=int(CUSTOM_OPSET_VERSION),
            outputs=4,
        )


# ===================================================================
# Op 2: bevfusion::SubMConv3d
# ===================================================================

class SubMConv3dExportOp(torch.autograd.Function):
    """ONNX-exportable placeholder for sub-manifold 3-D sparse convolution.

    Same structure as ``SparseConv3dExportOp`` but without stride attributes
    (SubMConv always uses stride=1) and guarantees N_out == N_in.
    """

    @staticmethod
    def forward(
        ctx,
        features: torch.Tensor,      # [N, C_in]
        indices: torch.Tensor,        # [N, 4]
        spatial_shape: torch.Tensor,  # [3]
        batch_size: torch.Tensor,     # [1]
        weight: torch.Tensor,         # [kD, kH, kW, C_in, C_out]
        bias: torch.Tensor,           # [C_out] or empty
        # --- Python int parameters (become ONNX attributes) ---
        in_channels: int,
        out_channels: int,
        kernel_size_d: int,
        kernel_size_h: int,
        kernel_size_w: int,
        padding_d: int,
        padding_h: int,
        padding_w: int,
        dilation_d: int,
        dilation_h: int,
        dilation_w: int,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
        cache_key = id(features)
        if cache_key in _cached_outputs:
            return _cached_outputs[cache_key]

        N = features.size(0)
        device = features.device
        dtype = features.dtype
        # SubM: output N, indices, spatial_shape are identical to input.
        out_features = features.new_zeros((N, out_channels))
        out_indices = indices.clone()
        out_spatial_shape = spatial_shape.clone()
        out_batch_size = batch_size.clone()

        zero = (features.sum() * 0.0
                + weight.to(dtype=dtype).sum() * 0.0
                + indices.to(dtype=dtype).sum() * 0.0
                + spatial_shape.to(dtype=dtype).sum() * 0.0
                + batch_size.to(dtype=dtype).sum() * 0.0)
        if bias is not None and bias.numel() > 0:
            zero = zero + bias.to(dtype=dtype).sum() * 0.0
        out_features = out_features + zero

        return out_features, out_indices, out_spatial_shape, out_batch_size

    @staticmethod
    def symbolic(
        g,
        features,
        indices,
        spatial_shape,
        batch_size,
        weight,
        bias,
        in_channels: int,
        out_channels: int,
        kernel_size_d: int,
        kernel_size_h: int,
        kernel_size_w: int,
        padding_d: int,
        padding_h: int,
        padding_w: int,
        dilation_d: int,
        dilation_h: int,
        dilation_w: int,
    ):
        inputs = [features, indices, spatial_shape, batch_size, weight]
        if bias is not None:
            inputs.append(bias)

        return g.op(
            f"{CUSTOM_DOMAIN}::SubMConv3d",
            *inputs,
            in_channels_i=int(in_channels),
            out_channels_i=int(out_channels),
            kernel_size_d_i=int(kernel_size_d),
            kernel_size_h_i=int(kernel_size_h),
            kernel_size_w_i=int(kernel_size_w),
            padding_d_i=int(padding_d),
            padding_h_i=int(padding_h),
            padding_w_i=int(padding_w),
            dilation_d_i=int(dilation_d),
            dilation_h_i=int(dilation_h),
            dilation_w_i=int(dilation_w),
            version_i=int(CUSTOM_OPSET_VERSION),
            outputs=4,
        )


# ===================================================================
# Export wrapper modules
# ===================================================================

class SparseConv3dExportWrapper(nn.Module):
    """Wraps a ``SparseConvolution`` (subm=False) for ONNX export.

    During tracing:
    1. Runs the real PyTorch forward inside ``no_jit_trace`` and caches output.
    2. Calls ``SparseConv3dExportOp.apply()`` so the tracer emits the custom
       ONNX node with the correct attributes and data dependencies.
    """

    def __init__(self, sparse_conv):
        super().__init__()
        self.conv = sparse_conv
        self.weight = sparse_conv.weight
        self.bias = sparse_conv.bias
        self.in_channels = sparse_conv.in_channels
        self.out_channels = sparse_conv.out_channels
        self.kernel_size = list(sparse_conv.kernel_size)
        self.stride = list(sparse_conv.stride)
        self.padding = list(sparse_conv.padding)
        self.dilation = list(sparse_conv.dilation)

    def forward(self, features, indices, spatial_shape, batch_size_tensor):
        """
        Args:
            features:      [N, C_in]  fp32/fp16
            indices:       [N, 4]     int32
            spatial_shape:  [3]       int32
            batch_size_tensor: [1]    int32
        Returns:
            out_features, out_indices, out_spatial_shape, out_batch_size
        """
        from .structure import SparseConvTensor

        # Step 1: run real forward (invisible to ONNX tracer)
        with no_jit_trace():
            batch_size = int(batch_size_tensor.item())
            sp_shape = tuple(spatial_shape.tolist())
            sp_input = SparseConvTensor(features, indices, sp_shape, batch_size)
            sp_output = self.conv(sp_input)

            out_features = sp_output.features
            out_indices = sp_output.indices
            out_spatial_shape = torch.tensor(
                list(sp_output.spatial_shape), dtype=torch.int32,
                device=features.device,
            )
            out_batch_size = torch.tensor(
                [sp_output.batch_size], dtype=torch.int32,
                device=features.device,
            )

            _cached_outputs[id(features)] = (
                out_features, out_indices, out_spatial_shape, out_batch_size,
            )

        # Step 2: emit ONNX custom op node
        bias = self.bias if self.bias is not None else torch.empty(
            0, dtype=self.weight.dtype, device=self.weight.device,
        )

        return SparseConv3dExportOp.apply(
            features, indices, spatial_shape, batch_size_tensor,
            self.weight, bias,
            self.in_channels, self.out_channels,
            self.kernel_size[0], self.kernel_size[1], self.kernel_size[2],
            self.stride[0], self.stride[1], self.stride[2],
            self.padding[0], self.padding[1], self.padding[2],
            self.dilation[0], self.dilation[1], self.dilation[2],
        )


class SubMConv3dExportWrapper(nn.Module):
    """Wraps a ``SparseConvolution`` (subm=True) for ONNX export."""

    def __init__(self, sparse_conv):
        super().__init__()
        self.conv = sparse_conv
        self.weight = sparse_conv.weight
        self.bias = sparse_conv.bias
        self.in_channels = sparse_conv.in_channels
        self.out_channels = sparse_conv.out_channels
        self.kernel_size = list(sparse_conv.kernel_size)
        self.padding = list(sparse_conv.padding)
        self.dilation = list(sparse_conv.dilation)

    def forward(self, features, indices, spatial_shape, batch_size_tensor):
        from .structure import SparseConvTensor

        with no_jit_trace():
            batch_size = int(batch_size_tensor.item())
            sp_shape = tuple(spatial_shape.tolist())
            sp_input = SparseConvTensor(features, indices, sp_shape, batch_size)
            sp_output = self.conv(sp_input)

            out_features = sp_output.features
            out_indices = sp_output.indices
            out_spatial_shape = torch.tensor(
                list(sp_output.spatial_shape), dtype=torch.int32,
                device=features.device,
            )
            out_batch_size = torch.tensor(
                [sp_output.batch_size], dtype=torch.int32,
                device=features.device,
            )

            _cached_outputs[id(features)] = (
                out_features, out_indices, out_spatial_shape, out_batch_size,
            )

        bias = self.bias if self.bias is not None else torch.empty(
            0, dtype=self.weight.dtype, device=self.weight.device,
        )

        return SubMConv3dExportOp.apply(
            features, indices, spatial_shape, batch_size_tensor,
            self.weight, bias,
            self.in_channels, self.out_channels,
            self.kernel_size[0], self.kernel_size[1], self.kernel_size[2],
            self.padding[0], self.padding[1], self.padding[2],
            self.dilation[0], self.dilation[1], self.dilation[2],
        )


# ===================================================================
# ONNX schema registration (makes onnx.checker.check_model() pass)
# ===================================================================

def register_sparse_conv_onnx_schemas():
    """Register minimal ONNX schemas for SparseConv3d and SubMConv3d."""
    try:
        from onnx import defs
    except ImportError:
        return

    domain = CUSTOM_DOMAIN
    OpSchema = defs.OpSchema
    FP = OpSchema.FormalParameter
    Attr = OpSchema.Attribute

    type_constraints = [
        ("T", ["tensor(float)", "tensor(float16)"], "Floating-point tensors"),
        ("TInt", ["tensor(int32)"], "Integer tensors"),
    ]

    # ---- bevfusion::SparseConv3d ----
    _register_one_schema(
        defs, domain, "SparseConv3d",
        inputs=[
            FP("features", "T", "input sparse features [N, C_in]"),
            FP("indices", "TInt", "voxel coords [N, 4]"),
            FP("spatial_shape", "TInt", "spatial dims [3]"),
            FP("batch_size", "TInt", "batch size [1]"),
            FP("weight", "T", "conv weight [kD,kH,kW,Cin,Cout]"),
            FP("bias", "T", "bias [Cout] or empty"),
        ],
        outputs=[
            FP("out_features", "T", "output features [N_out, C_out]"),
            FP("out_indices", "TInt", "output coords [N_out, 4]"),
            FP("out_spatial_shape", "TInt", "output spatial dims [3]"),
            FP("out_batch_size", "TInt", "output batch size [1]"),
        ],
        type_constraints=type_constraints,
        attributes=[
            Attr("in_channels", OpSchema.AttrType.INT, "input channels", required=False),
            Attr("out_channels", OpSchema.AttrType.INT, "output channels", required=False),
            Attr("kernel_size_d", OpSchema.AttrType.INT, "kernel depth", required=False),
            Attr("kernel_size_h", OpSchema.AttrType.INT, "kernel height", required=False),
            Attr("kernel_size_w", OpSchema.AttrType.INT, "kernel width", required=False),
            Attr("stride_d", OpSchema.AttrType.INT, "stride depth", required=False),
            Attr("stride_h", OpSchema.AttrType.INT, "stride height", required=False),
            Attr("stride_w", OpSchema.AttrType.INT, "stride width", required=False),
            Attr("padding_d", OpSchema.AttrType.INT, "padding depth", required=False),
            Attr("padding_h", OpSchema.AttrType.INT, "padding height", required=False),
            Attr("padding_w", OpSchema.AttrType.INT, "padding width", required=False),
            Attr("dilation_d", OpSchema.AttrType.INT, "dilation depth", required=False),
            Attr("dilation_h", OpSchema.AttrType.INT, "dilation height", required=False),
            Attr("dilation_w", OpSchema.AttrType.INT, "dilation width", required=False),
            Attr("version", OpSchema.AttrType.INT, "op version", required=False),
        ],
    )

    # ---- bevfusion::SubMConv3d ----
    _register_one_schema(
        defs, domain, "SubMConv3d",
        inputs=[
            FP("features", "T", "input sparse features [N, C_in]"),
            FP("indices", "TInt", "voxel coords [N, 4]"),
            FP("spatial_shape", "TInt", "spatial dims [3]"),
            FP("batch_size", "TInt", "batch size [1]"),
            FP("weight", "T", "conv weight [kD,kH,kW,Cin,Cout]"),
            FP("bias", "T", "bias [Cout] or empty"),
        ],
        outputs=[
            FP("out_features", "T", "output features [N, C_out]"),
            FP("out_indices", "TInt", "output coords [N, 4] (same as input)"),
            FP("out_spatial_shape", "TInt", "output spatial dims [3] (same as input)"),
            FP("out_batch_size", "TInt", "output batch size [1] (same as input)"),
        ],
        type_constraints=type_constraints,
        attributes=[
            Attr("in_channels", OpSchema.AttrType.INT, "input channels", required=False),
            Attr("out_channels", OpSchema.AttrType.INT, "output channels", required=False),
            Attr("kernel_size_d", OpSchema.AttrType.INT, "kernel depth", required=False),
            Attr("kernel_size_h", OpSchema.AttrType.INT, "kernel height", required=False),
            Attr("kernel_size_w", OpSchema.AttrType.INT, "kernel width", required=False),
            Attr("padding_d", OpSchema.AttrType.INT, "padding depth", required=False),
            Attr("padding_h", OpSchema.AttrType.INT, "padding height", required=False),
            Attr("padding_w", OpSchema.AttrType.INT, "padding width", required=False),
            Attr("dilation_d", OpSchema.AttrType.INT, "dilation depth", required=False),
            Attr("dilation_h", OpSchema.AttrType.INT, "dilation height", required=False),
            Attr("dilation_w", OpSchema.AttrType.INT, "dilation width", required=False),
            Attr("version", OpSchema.AttrType.INT, "op version", required=False),
        ],
    )


def _register_one_schema(defs, domain, op_name, **kwargs):
    """Register a single ONNX schema, skipping if already registered."""
    try:
        defs.get_schema(op_name, domain=domain, max_inclusive_version=1)
        return  # already registered
    except Exception:
        pass

    schema = defs.OpSchema(
        op_name, domain, 1,
        doc=f"{domain}::{op_name} custom op for BEVFusion sparse conv.",
        **kwargs,
    )
    defs.register_schema(schema)

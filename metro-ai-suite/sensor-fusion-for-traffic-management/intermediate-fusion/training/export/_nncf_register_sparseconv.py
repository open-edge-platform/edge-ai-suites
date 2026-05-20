"""Register the custom `SparseConvolution` op with NNCF so PTQ can place
FakeQuantize nodes around it.

Why this file exists
--------------------
NNCF 3.1's OpenVINO backend has a hard-coded list of quantizable operator
metatypes (nncf/openvino/graph/metatypes/openvino_metatypes.py +
nncf/openvino/graph/metatypes/groups.py). `SparseConvolution` (opset15, from
the patched OpenVINO build at /home/jie/workspace/openvino) is not in that
list, so even after removing it from `IgnoredScope`, NNCF silently assigns it
the `UnknownMetatype` trait (`NON_QUANTIZABLE`) and no FakeQuantize is
inserted.

This module monkey-patches NNCF at import time to register
`OVSparseConvolutionMetatype`, which makes NNCF:

1. Recognize the op as quantizable (INPUTS_QUANTIZABLE_OPERATIONS)
2. Recognize that its weight is on input port 2 (OPERATIONS_WITH_WEIGHTS +
   OPERATIONS_WITH_CONST_PORT_ID; the port is auto-discovered because port 2
   is a Constant while ports 0/1 are dynamic)
3. Use axis 2 of the weight tensor for per-channel quantization
   (const_channel_axis=[2] — weights are [K_vol, C_in, C_out], C_out is axis 2)
4. Reuse the hardware-config entry for "Convolution" (q8_a_sym + q8_w_sym) via
   hw_config_names=[HWConfigOpName.CONVOLUTION]

Why we DON'T add it to CONV_OPERATIONS / LINEAR_OPERATIONS
----------------------------------------------------------
`nncf.openvino.graph.node_utils.get_weight_channel_axes` takes a CONV-specific
fast path for those lists, which calls `get_conv_weights_layout_from_node` and
assumes the standard Conv weight layout [C_out, C_in, K_d, K_h, K_w]. Our
SparseConv weight is [K_vol, C_in, C_out] — if we added it to CONV_OPERATIONS
NNCF would derive the wrong axis. Instead we stay in the default `else` branch
of get_weight_channel_axes, which honours `const_channel_axis` directly.

Why we DON'T list `ignored_input_ports`
---------------------------------------
NNCF's graph builder walks every input of the op via
`_filter_weight_input_ports` and calls `get_operation_const_op` on each. Ports
0 (features) and 1 (coords) have dynamic (non-Constant) producers, so they are
skipped automatically. Only ports 2 (weights) and 3 (bias, when present) are
Constants and get registered as weight ports. No extra filter is needed.

Usage
-----
Import this module BEFORE calling `nncf.quantize(...)`:
  from . import _nncf_register_sparseconv  # noqa: F401

The side-effect-on-import pattern is intentional; the monkey-patch is
idempotent (guarded against double-registration).
"""

from __future__ import annotations

from nncf.common.hardware.opset import HWConfigOpName
from nncf.openvino.graph.metatypes import groups as _ov_groups
from nncf.openvino.graph.metatypes import openvino_metatypes as _ov_metatypes


@_ov_metatypes.OV_OPERATOR_METATYPES.register()
class OVSparseConvolutionMetatype(_ov_metatypes.OVOpMetatype):
    """Custom SparseConvolution op from the patched OpenVINO build.

    Input ports:
      0: features  [M_in, C_in]  float (dynamic)
      1: coords    [M_in, 4]     int32 (dynamic) — NOT quantized (integer)
      2: weights   [K_vol, C_in, C_out]  float (Constant)
      3: bias      [C_out]       float (Constant, optional)

    Output ports:
      0: out_features [M_out, C_out]  float
      1: out_coords   [M_out, 4]      int32
    """

    name = "SparseConvolutionOp"
    op_names = ["SparseConvolution"]
    hw_config_names = [HWConfigOpName.CONVOLUTION]

    # Output feature tensor is [M_out, C_out] — C_out is axis 1
    output_channel_axis = 1

    # Weight tensor is [K_vol, C_in, C_out] — C_out is axis 2.
    # This is the axis along which per-output-channel weight scales are
    # computed (matches the NVIDIA 3DSparseConvolution INT8 scheme).
    const_channel_axis = [2]


# Idempotent registration into NNCF's group tables.
def _add_once(group: list, entry) -> None:
    if entry not in group:
        group.append(entry)


_add_once(_ov_groups.INPUTS_QUANTIZABLE_OPERATIONS, OVSparseConvolutionMetatype)
_add_once(_ov_groups.OPERATIONS_WITH_WEIGHTS, OVSparseConvolutionMetatype)
_add_once(_ov_groups.OPERATIONS_WITH_CONST_PORT_ID, OVSparseConvolutionMetatype)
# NOTE: we deliberately DO NOT add to LINEAR_OPERATIONS or CONV_OPERATIONS
# — see the module docstring.


# ---------------------------------------------------------------------------
# Weight-port-id filter: exclude bias from "weights to quantize"
# ---------------------------------------------------------------------------
# SparseConvolution carries its bias as port 3 (a Constant of shape [C_out]).
# NNCF's OpenVINO backend treats every const port as a weight port by default
# (OVMinMaxAlgoBackend.get_weight_tensor_port_ids just returns all const
# ports). When combined with our `const_channel_axis=[2]`, NNCF then tries to
# reduce the bias tensor (1-D, shape [C_out]) along axis 2, which raises
# `IndexError: list assignment index out of range` in `get_reduction_axes`.
#
# Regular Convolution doesn't hit this because its bias is typically a
# separate Add node on the graph, not a const port on the Conv op itself.
# SparseConvolution inlines the bias into the op, so we need to tell NNCF
# which const ports are actual weights (here: only port 2).
#
# We monkey-patch the OV min-max backend to filter out ports whose shape's
# rank is less than or equal to the largest channel axis configured on the
# metatype. This is a safe, general rule: per-channel quantization along axis
# K requires at least K+1 dimensions; bias (1-D) cannot satisfy that for any
# K >= 1, so it naturally falls out.
from nncf.quantization.algorithms.min_max import openvino_backend as _ovbe  # noqa: E402

_original_get_weight_tensor_port_ids = _ovbe.OVMinMaxAlgoBackend.get_weight_tensor_port_ids


@staticmethod
def _filtered_get_weight_tensor_port_ids(node, graph):
    port_ids = _original_get_weight_tensor_port_ids(node, graph)
    if node.metatype is not OVSparseConvolutionMetatype:
        return port_ids
    # For SparseConvolution: only return ports whose tensor rank accommodates
    # the configured const_channel_axis. This filters out the 1-D bias (port 3).
    max_axis = max(node.metatype.const_channel_axis)
    required_rank = max_axis + 1
    const_attrs = node.layer_attributes.constant_attributes  # {port_id: {"shape": ..., ...}}
    filtered = [pid for pid in port_ids
                if len(const_attrs[pid]["shape"]) >= required_rank]
    return filtered


_ovbe.OVMinMaxAlgoBackend.get_weight_tensor_port_ids = _filtered_get_weight_tensor_port_ids


# ---------------------------------------------------------------------------
# Histogram aggregator speedup: subsample huge activation tensors
# ---------------------------------------------------------------------------
# Without this patch, PTQ on the unified model with SparseConv enabled takes
# ~30 minutes instead of the original ~100 seconds. The reason is that the
# SparseConv activation tensor is [M, C_in] where M can reach 65000 (6x the
# camera-side tensors). NNCF's HistogramAggregator then spends almost all of
# its CPU time inside `np.histogram` and `_combine_histograms` (which itself
# allocates a 2048*16 = 32768-element linspace + searchsorted every frame).
#
# Fix: before NNCF runs histogram on a tensor, if the tensor has more than
# `_HIST_SUBSAMPLE_THRESHOLD` elements, subsample it with a deterministic
# stride. Histogram estimation is inherently statistical — for 2048 bins,
# a subsample of ~500k elements is more than enough to recover accurate
# bin density; going from 5M -> 500k preserves the distribution shape.
#
# The subsample is deterministic (step = ceil(N / target)), so the resulting
# quantization scales are reproducible across runs with identical calib data.
#
# Environment variable `NNCF_HIST_SUBSAMPLE` (default 500000) lets us
# override per run; set to 0 to disable the subsample (for debugging).
import os  # noqa: E402

_HIST_SUBSAMPLE_THRESHOLD = int(os.environ.get("NNCF_HIST_SUBSAMPLE", "500000"))

if _HIST_SUBSAMPLE_THRESHOLD > 0:
    from nncf.common.tensor_statistics import collectors as _nncf_collectors  # noqa: E402

    _orig_register_reduced_input_impl = (
        _nncf_collectors.HistogramAggregator._register_reduced_input_impl
    )

    def _subsampled_register_reduced_input_impl(self, x):
        # `x` is an nncf.tensor.Tensor wrapping a numpy array. Subsample the
        # underlying flat data if it's above threshold. `_combine_histograms`
        # only needs min/max and bin density — both survive subsampling.
        try:
            raw = x.data  # numpy.ndarray
            if hasattr(raw, "size") and raw.size > _HIST_SUBSAMPLE_THRESHOLD:
                stride = (raw.size + _HIST_SUBSAMPLE_THRESHOLD - 1) // _HIST_SUBSAMPLE_THRESHOLD
                flat = raw.ravel()[::stride]
                from nncf.tensor import Tensor as _NNCFTensor
                x = _NNCFTensor(flat)
        except Exception:
            # Never break PTQ if the subsample path hits an unexpected tensor
            # layout; fall back to the original (slow) implementation.
            pass
        return _orig_register_reduced_input_impl(self, x)

    _nncf_collectors.HistogramAggregator._register_reduced_input_impl = (
        _subsampled_register_reduced_input_impl
    )


__all__ = ["OVSparseConvolutionMetatype"]

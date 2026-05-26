#!/usr/bin/env python3
"""
Export the full BEVFusion pipeline to a single ONNX file.

Strategy: export 3 sub-models (camera, lidar sparse encoder, post-fusion),
then merge the ONNX graphs into one unified model.

Custom operators (org.openvinotoolkit domain):
  - BevPoolV2:         camera view transform
  - SparseConvolution: lidar sparse 3D convolution
  - SparseToDense:     sparse-to-dense BEV conversion

Unified model I/O:
  Inputs:
    img              [N, C, H, W]       camera images (NCHW)
    indices          [num_points]       BEVPool V2 sorted indices
    intervals        [num_intervals, 3] BEVPool V2 intervals (start, length, bev_rank)
    voxel_features   [N_vox, C_in]      voxelized lidar features
    voxel_indices    [N_vox, 4]         voxel coordinates (batch, z, y, x)
  Outputs:
    Per-task head predictions (heatmap, reg, height, dim, rot, vel)

Usage:
  $PYTHON export/export_unified_onnx.py \
    configs/V2X-I/det/centerhead/secfpn/camera+lidar/resnet34/bevpoolv2.yaml \
    work_dirs/bevpoolv2/epoch_100.pth \
    --geometry-dir export/geometry \
    -o export/onnx/bevfusion_unified.onnx
"""

import argparse
import os
import struct
import sys
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import onnx
import onnx.helper as helper
from onnx import TensorProto

import torch
import torch.nn as nn

# Add project root for mmdet3d imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

CUSTOM_DOMAIN = "org.openvinotoolkit"
CUSTOM_OPSET = 1


# ---------------------------------------------------------------------------
# Sub-model A: Camera branch (BevPoolV2 view transform)
# ---------------------------------------------------------------------------

class CameraBranchONNX(nn.Module):
    """Camera backbone + neck + depth-aware view transform with BevPoolV2."""

    def __init__(self, model):
        super().__init__()
        self.backbone = model.encoders["camera"]["backbone"]
        self.neck = model.encoders["camera"]["neck"]
        self.vtransform = model.encoders["camera"]["vtransform"]

        self.D = self.vtransform.D
        self.C = self.vtransform.C
        fH, fW = self.vtransform.feature_size
        self.fH = int(fH)
        self.fW = int(fW)
        self.hw_stride = self.fH * self.fW

        self.xbound = list(self.vtransform.xbound)
        self.ybound = list(self.vtransform.ybound)
        self.zbound = list(self.vtransform.zbound)
        self.d_bins = int(self.D)

    def forward(self, img, indices, intervals):
        """img: [B, N, C, H, W] -> bev_features [B, C, H_bev, W_bev]."""
        B, N, C, H, W = img.size()
        img = img.view(B * N, C, H, W)

        feat = self.backbone(img)
        feat = self.neck(feat)
        if not isinstance(feat, torch.Tensor):
            feat = feat[1]

        BN, C, H, W = map(int, feat.size())
        feat = feat.view(B, int(BN / B), C, H, W)
        return self._view_transform(feat, indices, intervals)

    def _view_transform(self, x, indices, intervals):
        B, N, C, fH, fW = map(int, x.shape)
        x = x.view(B * N, C, fH, fW)
        x = self.vtransform.depthnet(x)
        depth = x[:, :self.D].softmax(dim=1)
        feat = x[:, self.D:(self.D + self.C)]

        depth = depth.view(B, N, self.D, fH, fW).contiguous()
        feat = feat.permute(0, 2, 3, 1).contiguous().view(B, N, fH, fW, self.C)

        # Route through OVBEVPoolv2 symbolic op for ONNX export.
        from mmdet3d.ops.bev_pool_v2.bev_pool import OVBEVPoolv2
        depth_trt = depth.view(-1, depth.shape[2], depth.shape[3], depth.shape[4]).contiguous()
        feat_trt = feat.view(-1, feat.shape[2], feat.shape[3], feat.shape[4]).contiguous()
        out_height = int(self.vtransform.nx[1])
        out_width = int(self.vtransform.nx[0])
        return OVBEVPoolv2.apply(
            feat_trt, depth_trt,
            indices.contiguous().int(),
            intervals.contiguous().int(),
            out_height, out_width,
            int(self.C), int(self.C), self.fH, self.fW,
            float(self.xbound[0]), float(self.xbound[1]), float(self.xbound[2]),
            float(self.ybound[0]), float(self.ybound[1]), float(self.ybound[2]),
            float(self.zbound[0]), float(self.zbound[1]), float(self.zbound[2]),
            0.0, float(self.d_bins), 1.0,
        )


class CameraBranchNCHW(nn.Module):
    """Wraps CameraBranchONNX so the exported `img` input is 4-D NCHW."""

    def __init__(self, camera_model):
        super().__init__()
        self.camera_model = camera_model

    def forward(self, img, indices, intervals):
        return self.camera_model(img.unsqueeze(0), indices, intervals)


def _load_precomputed_geometry(geometry_dir, device):
    indices_path = os.path.join(geometry_dir, "indices.bin")
    intervals_path = os.path.join(geometry_dir, "intervals.bin")
    with open(indices_path, "rb") as f:
        count = struct.unpack("I", f.read(4))[0]
        indices_np = np.frombuffer(f.read(count * 4), dtype=np.uint32).copy()
    indices = torch.from_numpy(indices_np.astype(np.int32)).to(device).contiguous()
    with open(intervals_path, "rb") as f:
        count = struct.unpack("I", f.read(4))[0]
        intervals_np = np.frombuffer(
            f.read(count * 3 * 4), dtype=np.int32).reshape(count, 3).copy()
    intervals = torch.from_numpy(intervals_np).to(device).contiguous()
    print(f"  Loaded precomputed geometry: {len(indices)} indices, {len(intervals)} intervals")
    return indices, intervals


def export_camera_branch(model, cfg, output_path, device='cuda', geometry_dir=None):
    if geometry_dir is None:
        raise ValueError("--geometry-dir is required (run precompute_geometry.py first)")

    camera_model = CameraBranchONNX(model).to(device).eval()
    wrapped = CameraBranchNCHW(camera_model).to(device).eval()

    iH, iW = map(int, cfg.model.encoders.camera.vtransform.image_size)
    img = torch.randn(1, 3, iH, iW).to(device)
    indices, intervals = _load_precomputed_geometry(geometry_dir, device)

    with torch.no_grad():
        torch.onnx.export(
            wrapped,
            (img, indices, intervals),
            output_path,
            input_names=["img", "indices", "intervals"],
            output_names=["cam_bev"],
            dynamic_axes={
                "indices":   {0: "num_points"},
                "intervals": {0: "num_intervals"},
            },
            opset_version=13,
            do_constant_folding=True,
        )
    print(f"  Camera branch exported to {output_path}")


# ---------------------------------------------------------------------------
# Sub-model B: Lidar sparse encoder (manual ONNX construction)
# ---------------------------------------------------------------------------

def _np(param):
    return param.detach().cpu().float().numpy()


def _fuse_bn(conv_w, conv_b, bn_rm, bn_rv, bn_eps, bn_w, bn_b):
    """Fuse BN parameters into conv weight & bias."""
    if conv_b is None:
        conv_b = np.zeros_like(bn_rm)
    if bn_w is None:
        bn_w = np.ones_like(bn_rm)
    if bn_b is None:
        bn_b = np.zeros_like(bn_rm)
    bn_var_rsqrt = 1.0 / np.sqrt(bn_rv + bn_eps)
    fused_w = conv_w * (bn_w * bn_var_rsqrt)
    fused_b = (conv_b - bn_rm) * bn_var_rsqrt * bn_w + bn_b
    return fused_w.astype(np.float32), fused_b.astype(np.float32)


def _conv_output_size(spatial, kernel, stride, padding, dilation):
    return [
        (s + 2 * p - d * (k - 1) - 1) // st + 1
        for s, k, st, p, d in zip(spatial, kernel, stride, padding, dilation)
    ]


class _SparseEncoderBuilder:

    def __init__(self, output_bound=80000):
        self.nodes = []
        self.initializers = []
        self._conv_idx = 0
        self._add_idx = 0
        self._relu_idx = 0
        self.output_bound = output_bound

    def _add_init(self, name, arr):
        self.initializers.append(helper.make_tensor(
            name=name, data_type=TensorProto.FLOAT,
            dims=list(arr.shape),
            vals=arr.astype(np.float32).tobytes(), raw=True,
        ))

    def add_sparse_conv(self, conv, bn, feat, idx, spatial, activation, rulebook):
        w_np = _np(conv.weight)
        ks = list(conv.kernel_size)
        stride = list(conv.stride)
        padding = list(conv.padding)
        dilation = list(conv.dilation)
        is_subm = bool(conv.subm)
        out_ch = conv.out_channels
        in_ch = conv.in_channels

        conv_b = _np(conv.bias) if conv.bias is not None else None
        if bn is not None:
            w_fused, b_fused = _fuse_bn(
                w_np, conv_b,
                _np(bn.running_mean), _np(bn.running_var), bn.eps,
                _np(bn.weight), _np(bn.bias),
            )
        else:
            w_fused = w_np.astype(np.float32)
            b_fused = conv_b if conv_b is not None else np.zeros(out_ch, dtype=np.float32)

        kv = ks[0] * ks[1] * ks[2]
        w_flat = w_fused.reshape(kv, in_ch, out_ch)

        ci = self._conv_idx
        self._conv_idx += 1
        w_name, b_name = f"spconv{ci}.weight", f"spconv{ci}.bias"
        self._add_init(w_name, w_flat)
        self._add_init(b_name, b_fused)

        out_feat, out_idx = f"conv{ci}_feat", f"conv{ci}_idx"
        out_spatial = (list(spatial) if is_subm
                       else _conv_output_size(spatial, ks, stride, padding, dilation))

        self.nodes.append(helper.make_node(
            op_type="SparseConvolution",
            inputs=[feat, idx, w_name, b_name],
            outputs=[out_feat, out_idx],
            name=f"conv{ci}",
            domain=CUSTOM_DOMAIN,
            kernel_size=ks, stride=stride, padding=padding, dilation=dilation,
            submanifold_i=1 if is_subm else 0,
            in_channels_i=in_ch, out_channels_i=out_ch,
            input_spatial_shape=list(spatial),
            output_spatial_shape=out_spatial,
            activation_s=activation.encode("utf-8"),
            output_bound_i=self.output_bound,
            rulebook_s=rulebook.encode("utf-8"),
        ))
        return out_feat, out_idx, out_spatial

    def add_relu(self, feat):
        ri = self._relu_idx
        self._relu_idx += 1
        out = f"relu{ri}_out"
        self.nodes.append(helper.make_node("Relu", [feat], [out], name=f"relu{ri}"))
        return out

    def add_add(self, a, b):
        ai = self._add_idx
        self._add_idx += 1
        out = f"add{ai}_out"
        self.nodes.append(helper.make_node("Add", [a, b], [out], name=f"add{ai}"))
        return out

    def process_basic_block(self, block, feat, idx, spatial, rulebook):
        identity = feat
        feat, idx, spatial = self.add_sparse_conv(
            block.conv1, block.norm1, feat, idx, spatial, "ReLU", rulebook)
        feat, idx, spatial = self.add_sparse_conv(
            block.conv2, block.norm2, feat, idx, spatial, "None", rulebook)
        feat = self.add_add(feat, identity)
        feat = self.add_relu(feat)
        return feat, idx, spatial

    def process_module(self, module, feat, idx, spatial, stage_idx):
        from mmdet3d.ops.spconv.conv import SparseConvolution
        from mmdet3d.ops import spconv
        from mmdet3d.ops.sparse_block import SparseBasicBlock

        if isinstance(module, SparseBasicBlock):
            return self.process_basic_block(
                module, feat, idx, spatial, f"subm{stage_idx + 1}")

        if isinstance(module, spconv.SparseSequential):
            children = list(module.children())
            conv_child = bn_child = None
            has_relu = False
            for c in children:
                if isinstance(c, SparseConvolution):
                    conv_child = c
                elif isinstance(c, (nn.BatchNorm1d, nn.BatchNorm2d)):
                    bn_child = c
                elif isinstance(c, nn.ReLU):
                    has_relu = True

            if conv_child is not None:
                if conv_child.indice_key is not None:
                    rulebook = conv_child.indice_key
                elif conv_child.subm:
                    rulebook = f"subm{stage_idx + 1}"
                else:
                    rulebook = f"spconv{stage_idx + 1}"
                return self.add_sparse_conv(
                    conv_child, bn_child, feat, idx, spatial,
                    "ReLU" if has_relu else "None", rulebook)

            for _, child in module.named_children():
                feat, idx, spatial = self.process_module(
                    child, feat, idx, spatial, stage_idx)
            return feat, idx, spatial

        print(f"  [WARN] skipping {type(module).__name__}")
        return feat, idx, spatial


def _build_sparse_encoder_onnx(encoder, batch_size=1, output_bound=80000):
    sparse_shape = list(encoder.sparse_shape)
    in_ch = encoder.in_channels
    out_ch = encoder.output_channels

    builder = _SparseEncoderBuilder(output_bound=output_bound)
    feat, idx, spatial = "features", "indices", list(sparse_shape)
    print(f"  initial spatial_shape = {spatial}")

    feat, idx, spatial = builder.process_module(
        encoder.conv_input, feat, idx, spatial, stage_idx=0)
    print(f"  after conv_input      = {spatial}")

    for i, (stage_name, stage) in enumerate(encoder.encoder_layers.named_children()):
        feat, idx, spatial = builder.process_module(
            stage, feat, idx, spatial, stage_idx=i)
        print(f"  after {stage_name:18s} = {spatial}")

    feat, idx, spatial = builder.process_module(
        encoder.conv_out, feat, idx, spatial, stage_idx=99)
    print(f"  after conv_out        = {spatial}")

    H, W, D = spatial
    final_ch = out_ch * D

    builder.nodes.append(helper.make_node(
        op_type="SparseToDense",
        inputs=[feat, idx],
        outputs=["spatial_features"],
        name="sparse_to_dense",
        domain=CUSTOM_DOMAIN,
        spatial_shape=list(spatial),
        batch_size_i=batch_size,
    ))
    print(f"  output dense shape    = [{batch_size}, {final_ch}, {H}, {W}]")

    graph_inputs = [
        helper.make_tensor_value_info("features", TensorProto.FLOAT, ["N", in_ch]),
        helper.make_tensor_value_info("indices", TensorProto.INT32, ["N", 4]),
    ]
    graph_outputs = [
        helper.make_tensor_value_info(
            "spatial_features", TensorProto.FLOAT,
            [batch_size, final_ch, H, W]),
    ]
    graph = helper.make_graph(
        nodes=builder.nodes,
        name="sparse_encoder",
        inputs=graph_inputs,
        outputs=graph_outputs,
        initializer=builder.initializers,
    )
    opset = [
        helper.make_operatorsetid("", 11),
        helper.make_operatorsetid(CUSTOM_DOMAIN, CUSTOM_OPSET),
    ]
    model = helper.make_model(graph, opset_imports=opset)
    model.ir_version = 7
    entry = onnx.StringStringEntryProto()
    entry.key = "batch_size"
    entry.value = str(batch_size)
    model.metadata_props.append(entry)
    return model


def _register_custom_op_schemas():
    """Register SparseConvolution / SparseToDense schemas under org.openvinotoolkit."""
    try:
        from onnx import defs
    except ImportError:
        return

    FP = defs.OpSchema.FormalParameter
    Attr = defs.OpSchema.Attribute
    tc = [
        ("T", ["tensor(float)", "tensor(float16)"], "float"),
        ("TInt", ["tensor(int32)"], "int"),
    ]
    schema_specs = [
        (
            "SparseConvolution",
            [
                FP("features", "T", "input [N, Cin]"),
                FP("indices", "TInt", "coords [N, 4]"),
                FP("weight", "T", "weight [K, Cin, Cout]"),
                FP("bias", "T", "bias [Cout]"),
            ],
            [
                FP("out_features", "T", "output [M, Cout]"),
                FP("out_indices", "TInt", "output coords [M, 4]"),
            ],
            [
                Attr("kernel_size", defs.OpSchema.AttrType.INTS, "kernel", required=False),
                Attr("stride", defs.OpSchema.AttrType.INTS, "stride", required=False),
                Attr("padding", defs.OpSchema.AttrType.INTS, "padding", required=False),
                Attr("dilation", defs.OpSchema.AttrType.INTS, "dilation", required=False),
                Attr("submanifold", defs.OpSchema.AttrType.INT, "subm flag", required=False),
                Attr("in_channels", defs.OpSchema.AttrType.INT, "in ch", required=False),
                Attr("out_channels", defs.OpSchema.AttrType.INT, "out ch", required=False),
                Attr("input_spatial_shape", defs.OpSchema.AttrType.INTS, "input spatial", required=False),
                Attr("output_spatial_shape", defs.OpSchema.AttrType.INTS, "output spatial", required=False),
                Attr("activation", defs.OpSchema.AttrType.STRING, "ReLU or None", required=False),
                Attr("output_bound", defs.OpSchema.AttrType.INT, "max output voxels", required=False),
                Attr("rulebook", defs.OpSchema.AttrType.STRING, "indice key", required=False),
            ],
        ),
        (
            "SparseToDense",
            [
                FP("features", "T", "input [M, C]"),
                FP("indices", "TInt", "coords [M, 4]"),
            ],
            [FP("dense", "T", "dense BEV [N, C*D, H, W]")],
            [
                Attr("spatial_shape", defs.OpSchema.AttrType.INTS, "spatial [H,W,D]", required=False),
                Attr("batch_size", defs.OpSchema.AttrType.INT, "batch", required=False),
            ],
        ),
    ]
    for op_name, inputs, outputs, attrs in schema_specs:
        try:
            defs.get_schema(op_name, domain=CUSTOM_DOMAIN, max_inclusive_version=1)
            continue
        except Exception:
            pass
        defs.register_schema(defs.OpSchema(
            op_name, CUSTOM_DOMAIN, 1,
            doc=f"{CUSTOM_DOMAIN}::{op_name}",
            inputs=inputs, outputs=outputs,
            type_constraints=tc, attributes=attrs,
        ))


def export_lidar_sparse_encoder(encoder, output_path, batch_size=1, output_bound=80000):
    _register_custom_op_schemas()
    onnx_model = _build_sparse_encoder_onnx(encoder, batch_size, output_bound)
    onnx.save(onnx_model, output_path)
    print(f"  Lidar sparse encoder exported to {output_path}")


# ---------------------------------------------------------------------------
# Sub-model C: Post-fusion (fuser + decoder + head)
# ---------------------------------------------------------------------------

class PostFusionONNX(nn.Module):
    """Wraps fuser + decoder + head for ONNX export."""

    def __init__(self, model):
        super().__init__()
        self.fuser = model.fuser
        self.decoder_backbone = model.decoder["backbone"]
        self.decoder_neck = model.decoder["neck"]
        self.head = list(model.heads.values())[0]  # CenterHead

    def forward(self, cam_bev, lidar_bev):
        x = self.fuser([cam_bev, lidar_bev])
        x = self.decoder_backbone(x)
        x = self.decoder_neck(x)
        if isinstance(x, (list, tuple)):
            x = x[0]
        x = self.head.shared_conv(x)

        outputs = []
        for task_head in self.head.task_heads:
            task_out = task_head(x)
            outputs.append(task_out['heatmap'])
            outputs.append(task_out['reg'])
            outputs.append(task_out['height'])
            outputs.append(task_out['dim'])
            outputs.append(task_out['rot'])
            if 'vel' in task_out:
                outputs.append(task_out['vel'])
        return tuple(outputs)


def export_post_fusion(model, cfg, output_path, device='cuda'):
    post_model = PostFusionONNX(model).to(device).eval()

    cam_out_ch = cfg.model.encoders.camera.vtransform.out_channels
    lidar_bev_ch = cfg.model.fuser.in_channels[1]
    bev_h = int(model.encoders["camera"]["vtransform"].nx[1].item())
    bev_w = int(model.encoders["camera"]["vtransform"].nx[0].item())

    cam_bev = torch.randn(1, cam_out_ch, bev_h, bev_w).to(device)
    lidar_bev = torch.randn(1, lidar_bev_ch, bev_h, bev_w).to(device)

    output_names = []
    for t, task_head in enumerate(model.heads["object"].task_heads):
        output_names.extend([f"task{t}_heatmap", f"task{t}_reg", f"task{t}_height",
                             f"task{t}_dim", f"task{t}_rot"])
        if 'vel' in task_head.heads:
            output_names.append(f"task{t}_vel")

    with torch.no_grad():
        torch.onnx.export(
            post_model,
            (cam_bev, lidar_bev),
            output_path,
            input_names=["cam_bev", "lidar_bev"],
            output_names=output_names,
            opset_version=13,
            do_constant_folding=True,
        )
    print(f"  Post-fusion exported to {output_path}")
    return output_names


# ---------------------------------------------------------------------------
# ONNX Graph Merging
# ---------------------------------------------------------------------------

def _prefix_onnx_model(model, prefix, input_rename_map=None):
    """Prefix internal tensor names; remap external inputs per `input_rename_map`."""
    if input_rename_map is None:
        input_rename_map = {}

    init_names = {i.name for i in model.graph.initializer}
    input_names = {i.name for i in model.graph.input}
    output_names = {o.name for o in model.graph.output}

    rename = {}
    for node in model.graph.node:
        for name in list(node.input) + list(node.output):
            if name and name not in rename:
                rename[name] = prefix + name

    for name in list(input_names):
        if name in init_names:
            pass  # initializer: rename via prefix
        elif name in input_rename_map:
            rename[name] = input_rename_map[name]
        else:
            rename[name] = name
    for name in list(output_names):
        rename[name] = name

    for node in model.graph.node:
        for i in range(len(node.input)):
            if node.input[i] in rename:
                node.input[i] = rename[node.input[i]]
        for i in range(len(node.output)):
            if node.output[i] in rename:
                node.output[i] = rename[node.output[i]]
        if node.name:
            node.name = prefix + node.name

    for init in model.graph.initializer:
        if init.name in rename:
            init.name = rename[init.name]
    for inp in model.graph.input:
        if inp.name in rename:
            inp.name = rename[inp.name]
    for out in model.graph.output:
        if out.name in rename:
            out.name = rename[out.name]


def merge_onnx_models(cam_path, lidar_path, post_path, output_path):
    cam_model = onnx.load(cam_path)
    lidar_model = onnx.load(lidar_path)
    post_model = onnx.load(post_path)

    # Lidar sub-model has "features" / "indices" inputs that collide with
    # the camera branch's "indices"; rename to unique names.
    _prefix_onnx_model(cam_model, "cam/")
    _prefix_onnx_model(lidar_model, "lidar/", input_rename_map={
        "features": "voxel_features",
        "indices":  "voxel_indices",
    })
    _prefix_onnx_model(post_model, "post/")

    cam_out_name = cam_model.graph.output[0].name
    lidar_out_name = lidar_model.graph.output[0].name
    post_cam_in = post_model.graph.input[0].name
    post_lidar_in = post_model.graph.input[1].name

    for node in post_model.graph.node:
        for i in range(len(node.input)):
            if node.input[i] == post_cam_in:
                node.input[i] = cam_out_name
            elif node.input[i] == post_lidar_in:
                node.input[i] = lidar_out_name

    all_nodes = list(cam_model.graph.node) + list(lidar_model.graph.node) + list(post_model.graph.node)
    all_inits = list(cam_model.graph.initializer) + list(lidar_model.graph.initializer) + list(post_model.graph.initializer)

    cam_init_names = {i.name for i in cam_model.graph.initializer}
    lidar_init_names = {i.name for i in lidar_model.graph.initializer}
    post_init_names = {i.name for i in post_model.graph.initializer}

    external_inputs, init_inputs = [], []
    for inp in cam_model.graph.input:
        (init_inputs if inp.name in cam_init_names else external_inputs).append(inp)
    for inp in lidar_model.graph.input:
        (init_inputs if inp.name in lidar_init_names else external_inputs).append(inp)
    for inp in post_model.graph.input:
        if inp.name in post_init_names:
            init_inputs.append(inp)

    graph = helper.make_graph(
        nodes=all_nodes,
        name="bevfusion_unified",
        inputs=external_inputs + init_inputs,
        outputs=list(post_model.graph.output),
        initializer=all_inits,
    )
    opset = [
        helper.make_operatorsetid("", 13),
        helper.make_operatorsetid(CUSTOM_DOMAIN, CUSTOM_OPSET),
    ]
    unified_model = helper.make_model(graph, opset_imports=opset)
    unified_model.ir_version = 7
    for key, val in [("batch_size", "1"), ("framework", "bevfusion")]:
        entry = onnx.StringStringEntryProto()
        entry.key = key
        entry.value = val
        unified_model.metadata_props.append(entry)

    onnx.save(unified_model, output_path)
    print(f"\nUnified ONNX saved to {output_path}")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_unified_onnx(path):
    model = onnx.load(path)
    graph = model.graph
    init_names = {i.name for i in graph.initializer}

    print(f"\n{'=' * 60}")
    print(f"  Unified ONNX Verification: {os.path.basename(path)}")
    print(f"{'=' * 60}")
    print(f"  File size: {os.path.getsize(path):,} bytes")
    print(f"  Nodes: {len(graph.node)}, Initializers: {len(graph.initializer)}")

    print(f"\n  External Inputs:")
    for inp in graph.input:
        if inp.name not in init_names:
            dims = [d.dim_param or d.dim_value for d in inp.type.tensor_type.shape.dim]
            dtype = TensorProto.DataType.Name(inp.type.tensor_type.elem_type)
            print(f"    {inp.name:30s}  {dims}  {dtype}")

    print(f"\n  Outputs:")
    for out in graph.output:
        dims = [d.dim_param or d.dim_value for d in out.type.tensor_type.shape.dim]
        dtype = TensorProto.DataType.Name(out.type.tensor_type.elem_type)
        print(f"    {out.name:30s}  {dims}  {dtype}")

    custom_ops = {}
    for node in graph.node:
        if node.domain == CUSTOM_DOMAIN:
            key = f"{node.domain}::{node.op_type}"
            custom_ops[key] = custom_ops.get(key, 0) + 1
    print(f"\n  Custom Ops:")
    for op, count in custom_ops.items():
        print(f"    {op}: {count}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export full BEVFusion pipeline to unified ONNX")
    parser.add_argument("config", help="torchpack config YAML")
    parser.add_argument("checkpoint", help="checkpoint .pth")
    parser.add_argument("--output", "-o", default=None)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--output-bound", type=int, default=80000,
                        help="Max output voxels for sparse encoder")
    parser.add_argument("--geometry-dir", type=str, required=True,
                        help="Path to precomputed geometry dir (indices.bin + intervals.bin)")
    args = parser.parse_args()

    if args.output is None:
        args.output = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "bevfusion_unified.onnx")

    print("=" * 60)
    print("  BEVFusion Unified ONNX Export")
    print("=" * 60)
    print(f"  config     : {args.config}")
    print(f"  checkpoint : {args.checkpoint}")
    print(f"  output     : {args.output}")
    print()

    print("[1/5] Loading model ...")
    from torchpack.utils.config import configs
    from mmcv import Config
    from mmcv.runner import load_checkpoint
    from mmdet3d.models import build_model
    from mmdet3d.utils import recursive_eval

    configs.load(args.config, recursive=True)
    cfg = Config(recursive_eval(configs), filename=args.config)
    cfg.model.train_cfg = None

    model = build_model(cfg.model, test_cfg=cfg.get("test_cfg"))
    load_checkpoint(model, args.checkpoint, map_location="cpu", strict=False)
    model.cuda().eval()
    print("  Model loaded successfully")
    print()

    tmp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_tmp_unified")
    os.makedirs(tmp_dir, exist_ok=True)
    cam_onnx = os.path.join(tmp_dir, "camera.onnx")
    lidar_onnx = os.path.join(tmp_dir, "lidar.onnx")
    post_onnx = os.path.join(tmp_dir, "postfusion.onnx")

    print("[2/5] Exporting camera branch ...")
    export_camera_branch(model, cfg, cam_onnx, geometry_dir=args.geometry_dir)
    print()

    print("[3/5] Exporting lidar sparse encoder ...")
    export_lidar_sparse_encoder(
        model.encoders["lidar"]["backbone"], lidar_onnx,
        batch_size=args.batch_size, output_bound=args.output_bound)
    print()

    print("[4/5] Exporting post-fusion (fuser + decoder + head) ...")
    export_post_fusion(model, cfg, post_onnx)
    print()

    print("[5/5] Merging sub-models into unified ONNX ...")
    merge_onnx_models(cam_onnx, lidar_onnx, post_onnx, args.output)
    verify_unified_onnx(args.output)

    for f in [cam_onnx, lidar_onnx, post_onnx]:
        if os.path.exists(f):
            os.remove(f)
    if os.path.exists(tmp_dir):
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass

    print("Done!")


if __name__ == "__main__":
    main()

# Copyright (c) Phigent Robotics. All rights reserved.

import torch

from . import bev_pool_v2_ext

__all__ = ['bev_pool_v2', 'OVBEVPoolv2']

class QuickCumsumCuda(torch.autograd.Function):
    r"""BEVPoolv2 implementation for Lift-Splat-Shoot view transformation.

    Please refer to the `paper <https://arxiv.org/abs/2211.17111>`_
    """
    @staticmethod
    def forward(ctx, depth, feat, ranks_depth, ranks_feat, ranks_bev,
                bev_feat_shape, interval_starts, interval_lengths):
        ranks_bev = ranks_bev.int()
        depth = depth.contiguous().float()
        feat = feat.contiguous().float()
        ranks_depth = ranks_depth.contiguous().int()
        ranks_feat = ranks_feat.contiguous().int()
        interval_lengths = interval_lengths.contiguous().int()
        interval_starts = interval_starts.contiguous().int()

        out = feat.new_zeros(bev_feat_shape)

        bev_pool_v2_ext.bev_pool_v2_forward(
            depth,
            feat,
            out,
            ranks_depth,
            ranks_feat,
            ranks_bev,
            interval_lengths,
            interval_starts,
        )

        ctx.save_for_backward(depth, feat, ranks_depth, ranks_feat, ranks_bev,
                             interval_starts, interval_lengths)
        return out

    @staticmethod
    def backward(ctx, out_grad):
        depth, feat, ranks_depth, ranks_feat, ranks_bev, interval_starts, interval_lengths = ctx.saved_tensors

        depth = depth.contiguous()
        feat = feat.contiguous()
        ranks_depth = ranks_depth.contiguous()
        ranks_feat = ranks_feat.contiguous()
        ranks_bev = ranks_bev.contiguous()
        interval_lengths = interval_lengths.contiguous()
        interval_starts = interval_starts.contiguous()

        depth_grad = depth.new_zeros(depth.shape)
        feat_grad = feat.new_zeros(feat.shape)
        out_grad = out_grad.contiguous()

        bev_pool_v2_ext.bev_pool_v2_backward(
            out_grad,
            depth_grad,
            feat_grad,
            depth,
            feat,
            ranks_depth,
            ranks_feat,
            ranks_bev,
            interval_lengths,
            interval_starts,
        )
        return depth_grad, feat_grad, None, None, None, None, None, None, None


def bev_pool_v2(depth, feat, ranks_depth, ranks_feat, ranks_bev,
                bev_feat_shape, interval_starts, interval_lengths):
    x = QuickCumsumCuda.apply(depth, feat, ranks_depth, ranks_feat, ranks_bev,
                              bev_feat_shape, interval_starts,
                              interval_lengths)
    x = x.permute(0, 4, 1, 2, 3).contiguous()  # [B,Z,Y,X,C]->[B,C,Z,Y,X]

    return x


class OVBEVPoolv2(torch.autograd.Function):
    """OpenVINO-compatible BEVPoolV2 autograd function.

    The OV native BevPoolV2 operator outputs NCHW [B, C, H_out, W_out].
    The symbolic() emits attributes that the OV ONNX frontend uses for
    shape inference and kernel dispatch. The forward() is called during
    ONNX tracing to produce dummy output with the correct NCHW shape.
    """

    @staticmethod
    def symbolic(g,
                 feat,
                 depth,
                 indices,
                 intervals,
                 out_height=128,
                 out_width=128,
                 out_channels=80,
                 in_channels=80,
                 image_height=54,
                 image_width=96,
                 x_bound_min=0.0, x_bound_max=102.4, x_bound_step=0.8,
                 y_bound_min=-51.2, y_bound_max=51.2, y_bound_step=0.8,
                 z_bound_min=-5.0, z_bound_max=3.0, z_bound_step=8.0,
                 d_bound_min=0.0, d_bound_max=90.0, d_bound_step=1.0):
        return g.op(
            'org.openvinotoolkit::BevPoolV2',
            feat,
            depth,
            indices,
            intervals,
            input_channels_i=in_channels,
            output_channels_i=out_channels,
            image_width_i=image_width,
            image_height_i=image_height,
            feature_width_i=out_width,
            feature_height_i=out_height,
            feat_layout_s="NHWC",
            x_bound_min_f=x_bound_min,
            x_bound_max_f=x_bound_max,
            x_bound_step_f=x_bound_step,
            y_bound_min_f=y_bound_min,
            y_bound_max_f=y_bound_max,
            y_bound_step_f=y_bound_step,
            z_bound_min_f=z_bound_min,
            z_bound_max_f=z_bound_max,
            z_bound_step_f=z_bound_step,
            d_bound_min_f=d_bound_min,
            d_bound_max_f=d_bound_max,
            d_bound_step_f=d_bound_step,
        )

    @staticmethod
    def forward(g,
                feat,   # N,H,W,C
                depth,  # N,D,H,W
                indices,
                intervals,
                out_height=128,
                out_width=128,
                out_channels=80,
                in_channels=80,
                image_height=54,
                image_width=96,
                x_bound_min=0.0, x_bound_max=102.4, x_bound_step=0.8,
                y_bound_min=-51.2, y_bound_max=51.2, y_bound_step=0.8,
                z_bound_min=-5.0, z_bound_max=3.0, z_bound_step=8.0,
                d_bound_min=0.0, d_bound_max=90.0, d_bound_step=1.0):
        """Run forward. Returns NCHW [B, C, H_out, W_out] matching OV output."""
        ranks_depth = indices.contiguous().int()
        hw_stride = feat.shape[1] * feat.shape[2]
        D = depth.shape[1]
        depth_span = D * hw_stride
        ranks_feat = ((ranks_depth // depth_span) * hw_stride +
                      ranks_depth % hw_stride).contiguous().int()
        interval_starts = intervals[:, 0].contiguous().int()
        interval_ends = intervals[:, 1].contiguous().int()
        interval_lengths = (interval_ends - interval_starts).contiguous().int()
        ranks_bev = intervals[:, 2].contiguous().int()

        # CUDA bev_pool_v2 kernel writes to out[rank * C + c] directly; a
        # sentinel rank=-1 would produce a negative-index out-of-bound write
        # (undefined behavior — crashes on some feat_size/allocator combos,
        # e.g. KITTI fH=24,fW=80, but happens to not crash on V2X-I).
        # The OV runtime kernel handles sentinel natively; filter it only for
        # the CUDA path used to produce the tracer's dummy output.
        valid_mask = ranks_bev >= 0
        if not valid_mask.all():
            ranks_bev = ranks_bev[valid_mask].contiguous()
            interval_starts = interval_starts[valid_mask].contiguous()
            interval_lengths = interval_lengths[valid_mask].contiguous()

        feat = feat.unsqueeze(0)
        depth = depth.unsqueeze(0)
        bev_feat_shape = (depth.shape[0], 1, out_height, out_width,
                          feat.shape[-1])  # (B, Z, Y, X, C)
        bev_feat = bev_pool_v2(depth, feat, ranks_depth, ranks_feat, ranks_bev,
                               bev_feat_shape, interval_starts,
                               interval_lengths)
        # bev_pool_v2 returns [B, C, Z, Y, X], squeeze Z -> [B, C, H, W] (NCHW)
        bev_feat = bev_feat.squeeze(2)
        return bev_feat

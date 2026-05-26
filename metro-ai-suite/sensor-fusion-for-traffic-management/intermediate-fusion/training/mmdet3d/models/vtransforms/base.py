# SPDX-FileCopyrightText: Copyright (c) 2023 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: MIT
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from typing import Tuple

import torch
from mmcv.runner import force_fp32
from torch import nn

from mmdet3d.ops import bev_pool

import os

__all__ = ["BaseTransform", "BaseDepthTransform", "V2XTransform"]

class no_jit_trace:
    def __enter__(self):
        # pylint: disable=protected-access
        self.state = torch._C._get_tracing_state()
        torch._C._set_tracing_state(None)

    def __exit__(self, *args):
        torch._C._set_tracing_state(self.state)
        self.state = None

newx = None
class BEVPooling(torch.autograd.Function):
    @staticmethod
    def forward(ctx, feat, depth, intervals, geom_feats, num_intervals, C, H, W):
        return newx

    @staticmethod
    def symbolic(g, feat, depth, intervals, geom_feats, num_intervals, C, H, W):
        return g.op("BEVPooling", feat, depth, intervals, geom_feats, num_intervals, C_i=C, H_i=H, W_i=W)

def gen_dx_bx(xbound, ybound, zbound):
    dx = torch.Tensor([row[2] for row in [xbound, ybound, zbound]])
    cx = torch.Tensor([row[0] for row in [xbound, ybound, zbound]])
    bx = torch.Tensor([row[0] + row[2] / 2.0 for row in [xbound, ybound, zbound]])
    nx = torch.LongTensor(
        [(row[1] - row[0]) / row[2] for row in [xbound, ybound, zbound]]
    )
    return dx, cx, bx, nx

class BaseTransform(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        image_size: Tuple[int, int],
        feature_size: Tuple[int, int],
        xbound: Tuple[float, float, float],
        ybound: Tuple[float, float, float],
        zbound: Tuple[float, float, float],
        dbound: Tuple[float, float, float],
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.image_size = image_size
        self.feature_size = feature_size
        self.xbound = xbound
        self.ybound = ybound
        self.zbound = zbound
        self.dbound = dbound

        dx, cx, bx, nx = gen_dx_bx(self.xbound, self.ybound, self.zbound)
        self.dx = nn.Parameter(dx, requires_grad=False)
        self.cx = nn.Parameter(cx, requires_grad=False)
        self.bx = nn.Parameter(bx, requires_grad=False)
        self.nx = nn.Parameter(nx, requires_grad=False)

        self.C = out_channels
        self.frustum = self.create_frustum()
        self.D = self.frustum.shape[0]
        self.fp16_enabled = False

    @force_fp32()
    def create_frustum(self):
        iH, iW = self.image_size
        fH, fW = self.feature_size

        ds = (
            torch.arange(*self.dbound, dtype=torch.float)
            .view(-1, 1, 1)
            .expand(-1, fH, fW)
        )
        D, _, _ = ds.shape

        xs = (
            torch.linspace(0, iW - 1, fW, dtype=torch.float)
            .view(1, 1, fW)
            .expand(D, fH, fW)
        )
        ys = (
            torch.linspace(0, iH - 1, fH, dtype=torch.float)
            .view(1, fH, 1)
            .expand(D, fH, fW)
        )

        frustum = torch.stack((xs, ys, ds), -1)
        return nn.Parameter(frustum, requires_grad=False)

    @force_fp32()
    def get_geometry(
        self,
        camera2lidar_rots,
        camera2lidar_trans,
        intrins,
        post_rots,
        post_trans,
        **kwargs,
    ):
        B, N, _ = camera2lidar_trans.shape

        # undo post-transformation
        # B x N x D x H x W x 3
        points = self.frustum - post_trans.view(B, N, 1, 1, 1, 3)
        points = (
            torch.inverse(post_rots)
            .view(B, N, 1, 1, 1, 3, 3)
            .matmul(points.unsqueeze(-1))
        )
        # cam_to_lidar
        points = torch.cat(
            (
                points[:, :, :, :, :, :2] * points[:, :, :, :, :, 2:3],
                points[:, :, :, :, :, 2:3],
            ),
            5,
        )
        combine = camera2lidar_rots.matmul(torch.inverse(intrins))
        points = combine.view(B, N, 1, 1, 1, 3, 3).matmul(points).squeeze(-1)
        points += camera2lidar_trans.view(B, N, 1, 1, 1, 3)

        if "extra_rots" in kwargs:
            extra_rots = kwargs["extra_rots"]
            points = (
                extra_rots.view(B, 1, 1, 1, 1, 3, 3)
                .repeat(1, N, 1, 1, 1, 1, 1)
                .matmul(points.unsqueeze(-1))
                .squeeze(-1)
            )
        if "extra_trans" in kwargs:
            extra_trans = kwargs["extra_trans"]
            points += extra_trans.view(B, 1, 1, 1, 1, 3).repeat(1, N, 1, 1, 1, 1)

        return points

    def get_cam_feats(self, x):
        raise NotImplementedError

    @force_fp32()
    def bev_pool(self, geom_feats, x):
        B, N, D, H, W, C = x.shape
        Nprime = B * N * D * H * W

        # flatten x
        x = x.reshape(Nprime, C)

        # flatten indices
        geom_feats = ((geom_feats - (self.bx - self.dx / 2.0)) / self.dx).long()
        geom_feats = geom_feats.view(Nprime, 3)
        batch_ix = torch.cat(
            [
                torch.full([Nprime // B, 1], ix, device=x.device, dtype=torch.long)
                for ix in range(B)
            ]
        )
        geom_feats = torch.cat((geom_feats, batch_ix), 1)

        # filter out points that are outside box
        kept = (
            (geom_feats[:, 0] >= 0)
            & (geom_feats[:, 0] < self.nx[0])
            & (geom_feats[:, 1] >= 0)
            & (geom_feats[:, 1] < self.nx[1])
            & (geom_feats[:, 2] >= 0)
            & (geom_feats[:, 2] < self.nx[2])
        )
        x = x[kept]
        geom_feats = geom_feats[kept]

        x = bev_pool(x, geom_feats, B, self.nx[2], self.nx[0], self.nx[1])

        # collapse Z
        final = torch.cat(x.unbind(dim=2), 1)

        return final

    @force_fp32()
    def forward(
        self,
        img,
        points,
        camera2ego,
        lidar2ego,
        lidar2camera,
        lidar2image,
        camera_intrinsics,
        camera2lidar,
        img_aug_matrix,
        lidar_aug_matrix,
        **kwargs,
    ):
        rots = camera2ego[..., :3, :3]
        trans = camera2ego[..., :3, 3]
        intrins = camera_intrinsics[..., :3, :3]
        post_rots = img_aug_matrix[..., :3, :3]
        post_trans = img_aug_matrix[..., :3, 3]
        lidar2ego_rots = lidar2ego[..., :3, :3]
        lidar2ego_trans = lidar2ego[..., :3, 3]
        camera2lidar_rots = camera2lidar[..., :3, :3]
        camera2lidar_trans = camera2lidar[..., :3, 3]

        extra_rots = lidar_aug_matrix[..., :3, :3]
        extra_trans = lidar_aug_matrix[..., :3, 3]

        geom = self.get_geometry(
            camera2lidar_rots,
            camera2lidar_trans,
            intrins,
            post_rots,
            post_trans,
            extra_rots=extra_rots,
            extra_trans=extra_trans,
        )

        x = self.get_cam_feats(img)
        x = self.bev_pool(geom, x)
        return x


class BaseDepthTransform(BaseTransform):
    @force_fp32()
    def forward(
        self,
        img,
        points,
        sensor2ego,
        lidar2ego,
        lidar2camera,
        lidar2image,
        cam_intrinsic,
        camera2lidar,
        img_aug_matrix,
        lidar_aug_matrix,
        metas,
        **kwargs,
    ):
        rots = sensor2ego[..., :3, :3]
        trans = sensor2ego[..., :3, 3]
        intrins = cam_intrinsic[..., :3, :3]
        post_rots = img_aug_matrix[..., :3, :3]
        post_trans = img_aug_matrix[..., :3, 3]
        lidar2ego_rots = lidar2ego[..., :3, :3]
        lidar2ego_trans = lidar2ego[..., :3, 3]
        camera2lidar_rots = camera2lidar[..., :3, :3]
        camera2lidar_trans = camera2lidar[..., :3, 3]

        batch_size = len(points)
        depth = torch.zeros(batch_size, img.shape[1], 1, *self.image_size).to(
            points[0].device
        )

        for b in range(batch_size):
            cur_coords = points[b][:, :3]
            cur_img_aug_matrix = img_aug_matrix[b]
            cur_lidar_aug_matrix = lidar_aug_matrix[b]
            cur_lidar2image = lidar2image[b]

            # inverse aug
            cur_coords -= cur_lidar_aug_matrix[:3, 3]
            cur_coords = torch.inverse(cur_lidar_aug_matrix[:3, :3]).matmul(
                cur_coords.transpose(1, 0)
            )
            # lidar2image
            cur_coords = cur_lidar2image[:, :3, :3].matmul(cur_coords)
            cur_coords += cur_lidar2image[:, :3, 3].reshape(-1, 3, 1)
            # get 2d coords
            dist = cur_coords[:, 2, :]
            cur_coords[:, 2, :] = torch.clamp(cur_coords[:, 2, :], 1e-5, 1e5)
            cur_coords[:, :2, :] /= cur_coords[:, 2:3, :]

            # imgaug
            cur_coords = cur_img_aug_matrix[:, :3, :3].matmul(cur_coords)
            cur_coords += cur_img_aug_matrix[:, :3, 3].reshape(-1, 3, 1)
            cur_coords = cur_coords[:, :2, :].transpose(1, 2)

            # normalize coords for grid sample
            cur_coords = cur_coords[..., [1, 0]]

            on_img = (
                (cur_coords[..., 0] < self.image_size[0])
                & (cur_coords[..., 0] >= 0)
                & (cur_coords[..., 1] < self.image_size[1])
                & (cur_coords[..., 1] >= 0)
            )
            for c in range(on_img.shape[0]):
                masked_coords = cur_coords[c, on_img[c]].long()
                masked_dist = dist[c, on_img[c]]
                depth[b, c, 0, masked_coords[:, 0], masked_coords[:, 1]] = masked_dist

        extra_rots = lidar_aug_matrix[..., :3, :3]
        extra_trans = lidar_aug_matrix[..., :3, 3]
        geom = self.get_geometry(
            camera2lidar_rots,
            camera2lidar_trans,
            intrins,
            post_rots,
            post_trans,
            extra_rots=extra_rots,
            extra_trans=extra_trans,
        )

        x = self.get_cam_feats(img, depth)
        x = self.bev_pool(geom, x)
        return x

class V2XTransform(nn.Module):
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        image_size: Tuple[int, int],
        feature_size: Tuple[int, int],
        xbound: Tuple[float, float, float],
        ybound: Tuple[float, float, float],
        zbound: Tuple[float, float, float],
        dbound: Tuple[float, float, float],
        use_bevpool: str = 'bevpoolv1',
        use_depth: bool = True,
        depth_threshold: float = 0,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.image_size = image_size
        self.feature_size = feature_size
        self.downsample_factor = int(image_size[0] / feature_size[0])
        self.xbound = xbound
        self.ybound = ybound
        self.zbound = zbound
        self.dbound = dbound

        self.use_bevpool = use_bevpool
        assert use_bevpool in ['bevpoolv1', 'bevpoolv2']
        self.use_depth = use_depth

        dx, cx, bx, nx = gen_dx_bx(self.xbound, self.ybound, self.zbound)
        self.dx = nn.Parameter(dx, requires_grad=False)
        self.cx = nn.Parameter(cx, requires_grad=False)
        self.bx = nn.Parameter(bx, requires_grad=False)
        self.nx = nn.Parameter(nx, requires_grad=False)

        self.C = out_channels
        self.fp16_enabled = False

        frustum, rays = self.create_frustum_rays()
        self.frustum_rays = frustum
        self.rays = rays
        self.D = self.frustum_rays.shape[0]
        self.depth_threshold = 1 / self.D if depth_threshold == 0 else depth_threshold

    def create_frustum_rays(self):
        """Generate frustum."""
        ogfH, ogfW = self.image_size
        fH, fW = ogfH // self.downsample_factor, ogfW // self.downsample_factor

        Xs = torch.linspace(0, ogfW-1, fW)
        Ys = torch.linspace(0, ogfH-1, fH)
        Ys, Xs = torch.meshgrid(Ys, Xs)
        Zs = torch.ones_like(Xs)
        Ws = torch.ones_like(Xs)

        # H x W x 4
        rays = torch.stack([Xs, Ys, Zs, Ws], dim=-1).to(torch.float32)
        rays_d_bound = [0, 1, self.dbound[2]]

        # DID
        alpha = 1.5
        d_coords = torch.arange(rays_d_bound[2]) / rays_d_bound[2]
        d_coords = torch.pow(d_coords, alpha)
        d_coords = rays_d_bound[0] + d_coords * (rays_d_bound[1] - rays_d_bound[0])
        d_coords = torch.tensor(d_coords, dtype=torch.float).view(-1, 1, 1).expand(-1, fH, fW)

        D, _, _ = d_coords.shape
        x_coords = torch.linspace(0, ogfW - 1, fW, dtype=torch.float).view(
            1, 1, fW).expand(D, fH, fW)
        y_coords = torch.linspace(0, ogfH - 1, fH,
                                dtype=torch.float).view(1, fH,
                                                        1).expand(D, fH, fW)
        paddings = torch.ones_like(d_coords)

        # D x H x W x 3
        frustum = torch.stack((x_coords, y_coords, d_coords, paddings), -1)
        return frustum, rays

    def get_geometry_rays(self, sensor2ego_mat, intrin_mat, ida_mat, bda_mat, denorms):
        """Transfer points from camera coord to ego coord.

        Args:
            sensor2ego_mat(Tensor): camera-to-ego transformation matrix.
            intrin_mat(Tensor): intrinsic matrix.
            ida_mat(Tensor): image-data-augmentation matrix.
            bda_mat(Tensor): BEV-data-augmentation matrix (may be None).
            denorms(Tensor): per-camera ground-plane normals.

        Returns:
            Tensor: points in ego coordinates.
        """
        ego2sensor_mat = sensor2ego_mat.inverse()
        device = ego2sensor_mat.device

        H, W = self.rays.shape[:2]
        B, N = intrin_mat.shape[:2]
        O = (ego2sensor_mat @ torch.tensor([0, 0, 0, 1], dtype=torch.float32, device=device).view(1, 1, 4, 1))[..., :3, 0].view(B, N, 1, 1, 3, 1)
        n = (denorms[:, :, :3] / torch.norm(denorms[:, :, :3], dim=-1, keepdim=True)).view(B, N, 1, 1, 1, 3)
        P0 = O + self.dbound[0] * n.view(B, N, 1, 1, 3, 1)
        P1 = O + self.dbound[1] * n.view(B, N, 1, 1, 3, 1)
        self.rays = self.rays.to(intrin_mat.device)
        self.frustum_rays = self.frustum_rays.to(intrin_mat.device)

        rays = (self.rays.to(intrin_mat.device).view(1, 1, H, W, 4) @ (intrin_mat.inverse() @ ida_mat.inverse()).permute(0, 1, 3, 2).reshape(B, N, 1, 4, 4))[..., :3]
        dirs = (rays / torch.norm(rays, dim=-1, keepdim=True)).unsqueeze(-1)

        t0 = (n @ P0) / (n @ dirs)
        t1 = (n @ P1) / (n @ dirs)

        D, H, W, _ = self.frustum_rays.shape
        gap  = t0 - t1
        points = self.frustum_rays.view(1, 1, D, H, W, 4).repeat(B, N, 1, 1, 1, 1)
        points[..., 2] = (t0.view(B, N, 1, H, W) - points[..., 2] * gap.view(B, N, 1, H, W)) * dirs[..., 2, 0].view(B, N, 1, H, W)
        points = points @ ida_mat.inverse().permute(0, 1, 3, 2).reshape(B, N, 1, 1, 4, 4)
        points[..., :2] *= points[..., [2]]

        matrix = sensor2ego_mat @ intrin_mat.inverse()
        if bda_mat is not None:
            matrix = bda_mat.unsqueeze(1) @ matrix

        return (points @ matrix.permute(0, 1, 3, 2).reshape(B, N, 1, 1, 4, 4))[..., :3]

    def get_cam_feats(self, x):
        raise NotImplementedError

    @force_fp32()
    def bev_pool(self, geom_feats, x, depth_kept=None, export=False):
        B, N, D, H, W, C = x.shape
        Nprime = B * N * D * H * W

        # flatten x
        x = x.reshape(Nprime, C)

        # flatten indices
        geom_feats = ((geom_feats - (self.bx - self.dx / 2.0)) / self.dx).long()
        geom_feats = geom_feats.view(Nprime, 3)
        batch_ix = torch.cat(
            [
                torch.full([Nprime // B, 1], ix, device=x.device, dtype=torch.long)
                for ix in range(B)
            ]
        )
        if export:
            geom_feats = torch.cat((geom_feats, batch_ix, torch.arange(len(batch_ix), device=batch_ix.device, dtype=torch.int32).unsqueeze(1)), 1)
        else:
            geom_feats = torch.cat((geom_feats, batch_ix), 1)

        # filter out points that are outside box
        kept = (
            (geom_feats[:, 0] >= 0)
            & (geom_feats[:, 0] < self.nx[0])
            & (geom_feats[:, 1] >= 0)
            & (geom_feats[:, 1] < self.nx[1])
            & (geom_feats[:, 2] >= 0)
            & (geom_feats[:, 2] < self.nx[2])
        )
        x = x[kept]
        geom_feats = geom_feats[kept]
        if export:
            x, intervals, geom_feats = bev_pool(x, geom_feats, B, self.nx[2], self.nx[0], self.nx[1], export = True)
        else:
            x = bev_pool(x, geom_feats, B, self.nx[2], self.nx[0], self.nx[1])
        # collapse Z
        final = torch.cat(x.unbind(dim=2), 1)

        if export:
            return final, intervals, geom_feats
        else:
            return final

    def voxel_pooling_prepare_v2(self, coor, depth_kept):
        B, N, D, H, W, _ = coor.shape
        num_points = B * N * D * H * W

        ranks_depth = torch.arange(num_points, dtype=torch.int32, device=coor.device)
        ranks_feat = torch.arange(num_points // D, dtype=torch.int32, device=coor.device)
        ranks_feat = ranks_feat.view(B, N, 1, H, W).expand(B, N, D, H, W).flatten()

        coor = ((coor - self.cx.to(coor)) / self.dx.to(coor)).long().view(num_points, 3)
        batch_idx = torch.arange(B, device=coor.device).view(B, 1).expand(B, num_points // B).reshape(num_points, 1)
        coor = torch.cat([coor, batch_idx], dim=1)

        kept = (
            (coor[:, 0] >= 0) & (coor[:, 0] < self.nx[0]) &
            (coor[:, 1] >= 0) & (coor[:, 1] < self.nx[1]) &
            (coor[:, 2] >= 0) & (coor[:, 2] < self.nx[2])
        )

        ranks_bev_full = (
            coor[:, 3] * (self.nx[2] * self.nx[1] * self.nx[0]) +
            coor[:, 2] * (self.nx[1] * self.nx[0]) +
            coor[:, 1] * self.nx[0] +
            coor[:, 0]
        )
        ranks_bev_full = ranks_bev_full.where(kept, torch.tensor(-1, dtype=ranks_bev_full.dtype, device=ranks_bev_full.device))

        _, indices = torch.sort(ranks_bev_full, stable=True)
        indices = indices.long().contiguous()

        sorted_ranks = ranks_bev_full[indices]

        is_start = torch.ones(num_points, dtype=torch.bool, device=coor.device)
        is_start[0] = True
        is_start[1:] = (sorted_ranks[1:] != sorted_ranks[:-1])

        interval_starts = torch.where(is_start)[0].int()

        end_positions = torch.cat([interval_starts[1:], torch.tensor([num_points], device=coor.device)])
        interval_lengths = (end_positions - interval_starts).int()

        ranks_bev_unique = sorted_ranks[is_start]

        ranks_depth_sorted = ranks_depth[indices]
        ranks_feat_sorted = ranks_feat[indices]

        return (
            ranks_bev_unique.int().contiguous(),
            ranks_depth_sorted.int().contiguous(),
            ranks_feat_sorted.int().contiguous(),
            interval_starts.int().contiguous(),
            interval_lengths.int().contiguous(),
            indices.int().contiguous()
        )

    def voxel_pooling_v2(self, coor, depth, feat, depth_kept):
        from mmdet3d.ops.bev_pool_v2.bev_pool import bev_pool_v2

        ranks_bev, ranks_depth, ranks_feat, \
        interval_starts, interval_lengths, indices = \
            self.voxel_pooling_prepare_v2(coor, depth_kept)

        if ranks_feat is None:
            print('warning ---> no points within the predefined '
                  'bev receptive field')
            dummy = torch.zeros(size=[
                feat.shape[0], feat.shape[2],
                int(self.nx[2]),
                int(self.nx[0]),
                int(self.nx[1])
            ]).to(feat)
            dummy = torch.cat(dummy.unbind(dim=2), 1)
            return dummy

        feat = feat.permute(0, 1, 3, 4, 2)
        bev_feat_shape = (depth.shape[0], int(self.nx[2]),
                          int(self.nx[1]), int(self.nx[0]),
                          feat.shape[-1])  # (B, Z, Y, X, C)
        # remove first interval (invalid sentinel rank=-1)
        ranks_bev = ranks_bev[1:]
        interval_starts = interval_starts[1:]
        interval_lengths = interval_lengths[1:]
        bev_feat = bev_pool_v2(depth, feat, indices, ranks_feat, ranks_bev,
                               bev_feat_shape, interval_starts,
                               interval_lengths)
        bev_feat = torch.cat(bev_feat.unbind(dim=2), 1)
        return bev_feat

    @force_fp32()
    def forward(
        self,
        img,
        points,
        camera2ego,
        lidar2ego,
        lidar2camera,
        lidar2image,
        camera_intrinsics,
        camera2lidar,
        img_aug_matrix,
        lidar_aug_matrix,
        metas,
        **kwargs,
    ):
        if 'denorms' in kwargs.keys():
            denorms = kwargs['denorms']

        geom = self.get_geometry_rays(
            camera2lidar,
            camera_intrinsics,
            img_aug_matrix,
            lidar_aug_matrix,
            denorms
        )

        x = self.get_cam_feats(img)

        use_depth = False
        depth_kept = None
        if isinstance(x, tuple):
            x, depth = x
            use_depth = True
            depth_kept = (depth >= self.depth_threshold)

        if self.use_bevpool == 'bevpoolv1':
            x = self.bev_pool(geom, x, depth_kept)
        elif self.use_bevpool == 'bevpoolv2':
            if use_depth:
                x = self.voxel_pooling_v2(geom, depth, x, depth_kept)
            else:
                B, N, D, H, W, C = x.shape
                depth_kept = torch.ones(B * N * D * H * W, device=x.device, dtype=torch.bool)
                depth = torch.ones(B, N, D, H, W, device=x.device)
                x = self.voxel_pooling_v2(geom, depth, x, depth_kept)

        return x

    # @force_fp32()
    def export(
        self,
        img,
        points,
        camera2ego,
        lidar2ego,
        lidar2camera,
        lidar2image,
        camera_intrinsics,
        camera2lidar,
        img_aug_matrix,
        lidar_aug_matrix,
        metas,
        intervals,
        geometry,
        num_intervals,
        **kwargs,
    ):
        if 'denorms' in kwargs.keys():
            denorms = kwargs['denorms']

        feat, depth, x = self.get_cam_feats(img, export=True)

        with no_jit_trace():
            geom = self.get_geometry_rays(
                camera2lidar.detach(),
                camera_intrinsics.detach(),
                img_aug_matrix.detach(),
                lidar_aug_matrix.detach(),
                denorms.detach() if torch.is_tensor(denorms) else denorms,
            )
            x, local_intervals, local_geom_feats = self.bev_pool(geom, x ,export= True)
            global newx
            newx = x

        return BEVPooling.apply(feat.permute(0, 2, 3, 1), depth, intervals, geometry, num_intervals, int(x.size(1)), int(x.size(2)), int(x.size(3)))
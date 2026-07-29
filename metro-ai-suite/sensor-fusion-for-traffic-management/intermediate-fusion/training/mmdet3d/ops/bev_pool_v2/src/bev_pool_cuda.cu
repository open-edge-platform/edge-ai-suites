// Copyright (c) Phigent Robotics. All rights reserved.
// Reference https://arxiv.org/abs/2211.17111

#include <stdio.h>
#include <stdlib.h>
#include <torch/torch.h>

/*
  Function: pillar pooling forward
  Args:
    c:                number of channels
    n_intervals:      number of unique BEV cells
    depth:            input depth weights, float [B*N, D, H, W] (flattened)
    feat:             input features, float [B*N, H, W, C] (flattened)
    ranks_depth:      sorted depth indices, int [n_points]
    ranks_feat:       sorted feature indices, int [n_points]
    ranks_bev:        BEV output index per interval, int [n_intervals]
    interval_starts:  start position per interval, int [n_intervals]
    interval_lengths: length per interval, int [n_intervals]
    out:              output BEV features, float [B, Z, Y, X, C] (flattened)
*/
__global__ void bev_pool_v2_kernel(int c, int n_intervals,
                                  const float *__restrict__ depth,
                                  const float *__restrict__ feat,
                                  const int *__restrict__ ranks_depth,
                                  const int *__restrict__ ranks_feat,
                                  const int *__restrict__ ranks_bev,
                                  const int *__restrict__ interval_starts,
                                  const int *__restrict__ interval_lengths,
                                  float* __restrict__ out) {
  int idx = blockIdx.x * blockDim.x + threadIdx.x;
  int index = idx / c;
  int cur_c = idx % c;

  if (index >= n_intervals) return;

  int interval_start = interval_starts[index];
  int interval_length = interval_lengths[index];

  float psum = 0;
  const float* cur_depth;
  const float* cur_feat;

  for(int i = 0; i < interval_length; i++){
    cur_depth = depth + ranks_depth[interval_start + i];
    cur_feat = feat + ranks_feat[interval_start + i] * c + cur_c;
    psum += *cur_feat * *cur_depth;
  }

  int cur_rank = ranks_bev[index];
  float* cur_out = out + cur_rank * c + cur_c;
  *cur_out = psum;
}


/*
  Function: pillar pooling backward
*/
__global__ void bev_pool_grad_kernel(int c, int n_intervals,
                                  const float *__restrict__ out_grad,
                                  const float *__restrict__ depth,
                                  const float *__restrict__ feat,
                                  const int *__restrict__ ranks_depth,
                                  const int *__restrict__ ranks_feat,
                                  const int *__restrict__ ranks_bev,
                                  const int *__restrict__ interval_starts,
                                  const int *__restrict__ interval_lengths,
                                  float* __restrict__ depth_grad,
                                  float* __restrict__ feat_grad) {
  int idx = blockIdx.x * blockDim.x + threadIdx.x;
  if (idx >= n_intervals) return;

  int interval_start = interval_starts[idx];
  int interval_length = interval_lengths[idx];
  int cur_rank = ranks_bev[idx];

  // depth_grad
  for(int i = 0; i < interval_length; i++){
    const float* cur_out_grad_start = out_grad + cur_rank * c;
    const float* cur_feat_start = feat + ranks_feat[interval_start+i] * c;

    float grad_sum = 0;
    for(int cur_c = 0; cur_c < c; cur_c++){
      const float* cur_out_grad = cur_out_grad_start + cur_c;
      const float* cur_feat = cur_feat_start + cur_c;
      grad_sum += *cur_out_grad * *cur_feat;
    }

    int depth_idx = ranks_depth[interval_start + i];
    float* cur_depth_grad = depth_grad + depth_idx;
    *cur_depth_grad = grad_sum;
  }

  // feat_grad
  for(int i = 0; i < interval_length; i++){
    int depth_idx = ranks_depth[interval_start + i];
    const float* cur_depth = depth + depth_idx;

    for(int cur_c = 0; cur_c < c; cur_c++){
      const float* cur_out_grad = out_grad + cur_rank * c + cur_c;
      float* cur_feat_grad = feat_grad + ranks_feat[interval_start+i] * c + cur_c;

      atomicAdd(cur_feat_grad, *cur_out_grad * *cur_depth);
    }
  }
}


void bev_pool_v2(int c, int n_intervals, const float* depth, const float* feat,
                 const int* ranks_depth, const int* ranks_feat, const int* ranks_bev,
                 const int* interval_starts, const int* interval_lengths,
                 float* out) {
  bev_pool_v2_kernel<<<(int)ceil(((double)n_intervals * c / 256)), 256>>>(
    c, n_intervals, depth, feat, ranks_depth, ranks_feat,
    ranks_bev, interval_starts, interval_lengths, out
  );
}

void bev_pool_v2_grad(int c, int n_intervals, const float* out_grad,
                      const float* depth, const float* feat,
                      const int* ranks_depth, const int* ranks_feat, const int* ranks_bev,
                      const int* interval_starts, const int* interval_lengths,
                      float* depth_grad, float* feat_grad) {
  bev_pool_grad_kernel<<<(int)ceil(((double)n_intervals / 256)), 256>>>(
     c, n_intervals, out_grad, depth, feat, ranks_depth, ranks_feat,
     ranks_bev, interval_starts, interval_lengths, depth_grad, feat_grad
  );
}

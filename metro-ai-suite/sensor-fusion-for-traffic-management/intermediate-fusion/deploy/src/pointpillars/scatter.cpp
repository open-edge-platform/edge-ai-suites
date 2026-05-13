// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "pointpillars/scatter.hpp"

namespace pointpillars {

Scatter::Scatter(int num_features, int grid_x, int grid_y, sycl::queue& queue)
    : num_features_(num_features), grid_x_(grid_x), grid_y_(grid_y), queue_(queue) {}

void Scatter::run(int pillar_count,
                    const int* coors,
                    const float* pfe_output,
                    float* scattered_feature) {
    if (pillar_count <= 0) return;

    const int C = num_features_;
    const int gx = grid_x_;
    const int gy = grid_y_;

    queue_.submit([&](sycl::handler& h) {
        h.parallel_for(
            sycl::nd_range<3>(
                sycl::range<3>(1, 1, pillar_count) * sycl::range<3>(1, 1, C),
                sycl::range<3>(1, 1, C)),
            [=](sycl::nd_item<3> it) {
                const int i_pillar  = it.get_group(2);
                const int i_feature = it.get_local_id(2);
                const int x_idx = coors[i_pillar * 4 + 1];
                const int y_idx = coors[i_pillar * 4 + 2];
                const float feat = pfe_output[i_pillar * C + i_feature];
                const int dst = i_feature * (gx * gy) + x_idx * gy + y_idx;
                scattered_feature[dst] = feat;
            });
    });
}

}  // namespace pointpillars

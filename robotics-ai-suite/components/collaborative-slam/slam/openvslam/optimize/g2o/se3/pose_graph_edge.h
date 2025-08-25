// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZER_G2O_SE3_POSE_GRAPH_EDGE_H
#define OPENVSLAM_OPTIMIZER_G2O_SE3_POSE_GRAPH_EDGE_H

#include <g2o/core/base_vertex.h>
#include <g2o/core/base_binary_edge.h>
#include <g2o/types/sba/types_sba.h>
#include <g2o/types/sba/types_six_dof_expmap.h>
#include <Eigen/Geometry>

namespace openvslam {
namespace optimize {
namespace g2o {
namespace se3 {

// Note that the edge definition is mostly the same as the edgese3expmap in the original g2o
// except the error formulation and jacobian

// Previously the edgese3expmap edge from the original g2o library is used to construct the odom (pose graph) edge.
// However, it seems that the error formulation is not correct and the optimization result depends on the origin of the
// coordinate. Therefore, we experience the drift of z axis in previous tests for the geekplus data (kongkuang). After
// correcting the error formulation bug by defining a new edge (mostly the same as edgese3expmap except for error
// formualtion and jacobian matrix), we are now able to get the correct output.
class pose_graph_edge final
    : public ::g2o::BaseBinaryEdge<6, ::g2o::SE3Quat, ::g2o::VertexSE3Expmap, ::g2o::VertexSE3Expmap> {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    pose_graph_edge();

    bool read(std::istream& is) override;

    bool write(std::ostream& os) const override;

    void computeError() override
    {
        const ::g2o::VertexSE3Expmap* v1 = static_cast<const ::g2o::VertexSE3Expmap*>(_vertices[0]);
        const ::g2o::VertexSE3Expmap* v2 = static_cast<const ::g2o::VertexSE3Expmap*>(_vertices[1]);

        ::g2o::SE3Quat C(_measurement);
        // SE3Quat error_= v2->estimate().inverse()*C*v1->estimate();
        ::g2o::SE3Quat error_ = C * v1->estimate() * v2->estimate().inverse();
        _error = error_.log();
    }

    void linearizeOplus() override;
};

}  // namespace se3
}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZER_G2O_SE3_POSE_GRAPH_EDGE_H

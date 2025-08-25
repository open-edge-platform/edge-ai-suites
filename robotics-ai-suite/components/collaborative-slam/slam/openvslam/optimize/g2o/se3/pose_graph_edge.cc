// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "pose_graph_edge.h"

namespace openvslam {
namespace optimize {
namespace g2o {
namespace se3 {

pose_graph_edge::pose_graph_edge() : BaseBinaryEdge<6, ::g2o::SE3Quat, ::g2o::VertexSE3Expmap, ::g2o::VertexSE3Expmap>() {}

bool pose_graph_edge::read(std::istream& is)
{
    ::g2o::Vector7 meas;
    for (int i = 0; i < 7; i++) is >> meas[i];
    ::g2o::SE3Quat cam2world;
    cam2world.fromVector(meas);
    setMeasurement(cam2world.inverse());
    for (int i = 0; i < 6; i++)
        for (int j = i; j < 6; j++) {
            is >> information()(i, j);
            if (i != j) information()(j, i) = information()(i, j);
        }
    return true;
}

bool pose_graph_edge::write(std::ostream& os) const
{
    ::g2o::SE3Quat cam2world(measurement().inverse());
    for (int i = 0; i < 7; i++) os << cam2world[i] << " ";
    for (int i = 0; i < 6; i++)
        for (int j = i; j < 6; j++) {
            os << " " << information()(i, j);
        }
    return os.good();
}

void pose_graph_edge::linearizeOplus()
{
    /*
    VertexSE3Expmap * vi = static_cast<VertexSE3Expmap *>(_vertices[0]);
    SE3Quat Ti(vi->estimate());

    VertexSE3Expmap * vj = static_cast<VertexSE3Expmap *>(_vertices[1]);
    SE3Quat Tj(vj->estimate());

    const SE3Quat & Tij = _measurement;
    SE3Quat invTij = Tij.inverse();

    SE3Quat invTj_Tij = Tj.inverse()*Tij;
    SE3Quat infTi_invTij = Ti.inverse()*invTij;

    _jacobianOplusXi = invTj_Tij.adj();
    _jacobianOplusXj = -infTi_invTij.adj();
    */
    ::g2o::VertexSE3Expmap* vi = static_cast<::g2o::VertexSE3Expmap*>(_vertices[0]);
    ::g2o::SE3Quat Ti(vi->estimate());

    ::g2o::VertexSE3Expmap* vj = static_cast<::g2o::VertexSE3Expmap*>(_vertices[1]);
    ::g2o::SE3Quat Tj(vj->estimate());

    // const ::g2o::SE3Quat& Tji = _measurement;

    ::g2o::SE3Quat Tj_invTi = Tj * Ti.inverse();
    Eigen::Matrix<double, 6, 6, Eigen::ColMajor> res;
    res.setIdentity();

    _jacobianOplusXi = Tj_invTi.adj();
    _jacobianOplusXj = -res;
}

}  // namespace se3
}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

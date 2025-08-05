// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "optimize/g2o/so3_vertex.h"

Eigen::Matrix3d NormalizeRotation(const Eigen::Matrix3d R)
{
    Eigen::Quaterniond q(R);
    q.normalize();
    // Eigen::JacobiSVD<Eigen::Matrix3d> svd(R, Eigen::ComputeFullU | Eigen::ComputeFullV);
    // return svd.matrixU() * svd.matrixV().transpose();
    return q.toRotationMatrix();
}

namespace openvslam {
namespace optimize {
namespace g2o {
namespace so3 {

so3_vertex::so3_vertex() : BaseVertex<3, Mat33_t>() { updated_times_ = 0; }

bool so3_vertex::read(std::istream&) { return true; }

bool so3_vertex::write(std::ostream& os) const { return os.good(); }

Eigen::Matrix3d ExpSO3(const Eigen::Vector3d& v)
{
    Eigen::Matrix3d I = Eigen::Matrix3d::Identity();
    double x = v[0], y = v[1], z = v[2];
    const double d2 = x * x + y * y + z * z;
    const double d = sqrt(d2);
    Eigen::Matrix3d W;
    W << 0, -z, y, z, 0, -x, -y, x, 0;
    if (d < 0.000001)
        return (I + W + 0.5f * W * W);
    else
        return (I + W * std::sin(d) / d + W * W * (1.0f - std::cos(d)) / d2);
}

void so3_vertex::oplusImpl(const double* update_)
{
    // std::cout << "Vertex " << id() << " Estimate: \n" << estimate() << std::endl;
    // std::cout << "log: \n" << estimate().log() << std::endl;

    Eigen::Map<const Vec3_t> update(update_);
    // std::cout << "update: " << update.transpose() << std::endl;
    Eigen::Matrix3d R;
    R << 0, -update[2], update[1], update[2], 0, -update[0], -update[1], update[0], 0;

    // std::cout << "R: \n" << R.exp() << std::endl;
    // std::cout << "ExpSO3: \n" << ExpSO3(update) << std::endl;

    setEstimate(estimate() * R.exp());
    updated_times_++;
    if (updated_times_ >= 3) {
        _estimate = NormalizeRotation(_estimate);
        updated_times_ = 0;
    }

    // std::cout << "Estimate after update: \n" << estimate() << std::endl;
    // std::cout << "log: \n" << estimate().log() << std::endl;
}

}  // namespace so3
}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam

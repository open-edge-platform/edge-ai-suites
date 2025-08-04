// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef G2O_EDGE_MULTI_CAMERA_H
#define G2O_EDGE_MULTI_CAMERA_H

#include <g2o/core/base_multi_edge.h>
#include <g2o/types/slam3d_addons/g2o_types_slam3d_addons_api.h>
#include "g2o/sim3/shot_vertex.h"

namespace openvslam {
namespace optimize {
namespace g2o {
/**
 * \brief Landmark measurement that also calibrates an offset for the landmark measurement
 */
class EdgeMultiCamera : public ::g2o::BaseMultiEdge<7, ::g2o::Sim3>  // Avoid redefinition of BaseEdge in MSVC
{
public:
    G2O_TYPES_SLAM3D_ADDONS_API EIGEN_MAKE_ALIGNED_OPERATOR_NEW

        G2O_TYPES_SLAM3D_ADDONS_API
        EdgeMultiCamera();

    G2O_TYPES_SLAM3D_ADDONS_API void computeError();

    G2O_TYPES_SLAM3D_ADDONS_API virtual bool read(std::istream& is);

    G2O_TYPES_SLAM3D_ADDONS_API virtual bool write(std::ostream& os) const;
};

}  // namespace g2o
}  // namespace optimize
}  // namespace openvslam
#endif

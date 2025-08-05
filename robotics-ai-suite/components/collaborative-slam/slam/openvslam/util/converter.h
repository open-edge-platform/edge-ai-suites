// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_UTIL_CONVERTER_H
#define OPENVSLAM_UTIL_CONVERTER_H

#include "type.h"

#include <Eigen/Dense>
#include <opencv2/core/core.hpp>
#include <g2o/types/sba/types_six_dof_expmap.h>
#include <g2o/types/sim3/types_seven_dof_expmap.h>

enum IMU_VertexType { PoseVtx, VelocityVtx, GyroBiasVtx, AccBiasVtx, LandmarkVtx, CommonVtx };

inline int uint64ID_to_IMUvtxID(uint64_t id, IMU_VertexType type)
{
    unsigned int client_id = (id >> 56) & 0xFF;
    unsigned int type_code;
    unsigned int low = id & 0xFFFFF;
    int IMU_vertex_id = 0;
    switch (type) {
        case PoseVtx: type_code = 0x000; break;
        case VelocityVtx: type_code = 0x001; break;
        case GyroBiasVtx: type_code = 0x010; break;
        case AccBiasVtx: type_code = 0x011; break;
        case LandmarkVtx: type_code = 0x100; break;
        case CommonVtx: type_code = 0x111; break;
    }
    IMU_vertex_id = static_cast<int>((client_id << 23) | (type_code << 20) | low);
    return IMU_vertex_id;
}

inline int keyframeID_to_vertexID(KeyframeID id)
{
    unsigned int client_id = (id >> 56) & 0xFF;
    unsigned int low = id & 0x7FFFFF;
    return static_cast<int>((client_id << 23) | low);
}

inline int landmarkID_to_vertexID(LandmarkID id)
{
    unsigned int client_id = (id >> 56) & 0xFF;
    unsigned int low = id & 0x7FFFFF;
    return static_cast<int>((client_id << 23) | low);
}

namespace openvslam {
namespace util {

class converter {
public:
    //! descriptor vector
    static std::vector<cv::Mat> to_desc_vec(const cv::Mat& desc);

    //! to SE3 of g2o
    static g2o::SE3Quat to_g2o_SE3(const Mat44_t& cam_pose);

    //! to Eigen::Mat/Vec
    static Mat44_t to_eigen_mat(const g2o::SE3Quat& g2o_SE3);
    static Mat44_t to_eigen_mat(const g2o::Sim3& g2o_Sim3);
    static Mat44_t to_eigen_cam_pose(const Mat33_t& rot, const Vec3_t& trans);

    //! from/to angle axis
    static Vec3_t to_angle_axis(const Mat33_t& rot_mat);
    static Mat33_t to_rot_mat(const Vec3_t& angle_axis);

    //! to homogeneous coordinates
    template<typename T>
    static Vec3_t to_homogeneous(const cv::Point_<T>& pt) {
        return Vec3_t{pt.x, pt.y, 1.0};
    }

    //! to skew symmetric matrix
    static Mat33_t to_skew_symmetric_mat(const Vec3_t& vec);
};

} // namespace util
} // namespace openvslam

#endif // OPENVSLAM_UTIL_CONVERTER_H

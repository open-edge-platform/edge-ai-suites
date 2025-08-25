// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "odom.h"

namespace openvslam {
namespace data {

odom::odom(Eigen::Matrix4d T_image_to_camera) : T_image_to_camera_(T_image_to_camera)
{}

void odom::input_odom(double t, const Eigen::Matrix4d& cam_to_odom_pose)
{
    std::unique_lock<std::mutex> lock(mtx_odom_buf_);
    // typically, T_image_to_camera_ equals to identity
    // it will only be non-identity when the image_frame is not contained in tf tree
    odom_buf_[t] = T_image_to_camera_ * cam_to_odom_pose;
}

int odom::get_odom(double t, Eigen::Matrix4d& cam_to_odom_pose)
{
    // return 2 represent the buffer size is empty, and can get odom in the future
    // return 1 represent it can get odom in the future
    // return 0 represent get odom right
    // return -1 represent it can never get odom data, so it should be stop
    std::unique_lock<std::mutex> lock(mtx_odom_buf_);
    if (odom_buf_.empty()) {
        spdlog::debug("buffer is empty!");
        return 2;
    }
    spdlog::debug("buffer size is {}", odom_buf_.size());

    // use the provided timestamp to find the two nearest timestamp and pose in map
    spdlog::debug("query t is {}", t);
    std::map<double, Eigen::Matrix4d>::iterator it, prev;
    it = odom_buf_.lower_bound(t);

    if (it == odom_buf_.end()) {
        spdlog::debug("queried timestamp is larger than all the keys in map");
        return 1;
    } else if (it->first == t) {
        spdlog::debug("queried timestamp is exactly the same as the key in map");
        cam_to_odom_pose = odom_buf_[it->first];
        return 0;
    } else if (it == odom_buf_.begin()) {
        spdlog::debug("queried timestamp is smaller than all the keys in map");
        return -1;
    }
    // otherwise, use interpolation
    Eigen::Matrix4d post_pose = odom_buf_[it->first];
    spdlog::debug("found post pose, t is {}", it->first);
    prev = std::prev(it);
    Eigen::Matrix4d prev_pose = odom_buf_[prev->first];
    spdlog::debug("found prev pose, t is {}", prev->first);

    interpolation(prev_pose, post_pose, prev->first, it->first, t, cam_to_odom_pose);
    return 0;
}

void odom::interpolation(const Eigen::Matrix4d& prev_pose, const Eigen::Matrix4d& post_pose, double prev_t,
                         double pose_t, double t, Eigen::Matrix4d& pose)
{
    double weight_end = (t - prev_t) / (pose_t - prev_t);
    double weight_start = 1 - weight_end;

    Quat_t quat_end(post_pose.block<3, 3>(0, 0));
    const Vec3_t trans_end = post_pose.block<3, 1>(0, 3);

    Quat_t quat_start(prev_pose.block<3, 3>(0, 0));
    const Vec3_t trans_start = prev_pose.block<3, 1>(0, 3);

    Vec3_t trans_res = weight_start * trans_start + weight_end * trans_end;
    Quat_t quat_res = quat_start.slerp(weight_end, quat_end);

    pose = Mat44_t::Identity();
    const Mat33_t rot_cw(quat_res.normalized().toRotationMatrix());
    const Vec3_t trans_cw(trans_res);
    pose.block<3, 3>(0, 0) = rot_cw;
    pose.block<3, 1>(0, 3) = trans_cw;
}

}  // namespace data
}  // namespace openvslam

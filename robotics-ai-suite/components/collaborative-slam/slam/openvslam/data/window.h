// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <mutex>
#include "type.h"
#include <nlohmann/json.hpp>
#include <g2o/types/sim3/types_seven_dof_expmap.h>


namespace openvslam {
namespace data {
class keyframe;
class window
{
private:
    std::mutex mtx_kf_;
    std::map<KeyframeID, keyframe*> keyframes_;

    Quat_t quat_slerp(Quat_t start, Quat_t end, const float t);
    Quat_t calc_average_quart(const Mat44_t& quater_sum);
    Mat44_t get_pose_from_sim3(const ::g2o::Sim3& sim3_pose);
    ::g2o::Sim3 get_sim3_from_pose(const Mat44_t& mat_pose);

public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    window(unsigned int window_id);
    ~window();
    unsigned int window_id_;
    unsigned int get_window_size();
    bool empty();

    void insert_keyframe(keyframe* keyfrm);
    void erase_keyframe(KeyframeID keyfrm_id);
    void erase_final_kefrm();

    keyframe* get_final_kefrm();
    void get_opt_keframes(std::vector<keyframe*>& origin_keyframes, std::unordered_map<KeyframeID, keyframe*>& keyfrm_ids,
                          const size_t edge_size);
    void update_cam_pose_slerp(const std::vector<::g2o::Sim3, Eigen::aligned_allocator<::g2o::Sim3>>& cam_pose_cw_new,
                               std::unordered_map<unsigned int, ::g2o::Sim3>& corrected_Sim3s_wc,
                               size_t edge_size, unsigned int new_map_id, unsigned int loop_identifier);
};
}
}

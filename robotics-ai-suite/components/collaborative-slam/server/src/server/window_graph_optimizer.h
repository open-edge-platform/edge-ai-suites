// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_WINDOW_OPTIMIZE_GRAPH_OPTIMIZER_H
#define OPENVSLAM_WINDOW_OPTIMIZE_GRAPH_OPTIMIZER_H

#include "server/univloc_graph_optimizer.h"

namespace univloc_server {
class Server;
}

namespace openvslam {

namespace data {
class window;
class keyframe;
class map_database;
}  // namespace data

namespace optimize {

class window_graph_optimizer : public univloc_graph_optimizer
{
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW
    enum OptimizationType { Front_Rear_Optimization, Loop_Optimization };
    OptimizationType optimization_type_ = OptimizationType::Loop_Optimization;

    /**
     * Constructor
     * @param map_db
     * @param fix_scale
     */
    explicit window_graph_optimizer(data::map_database* map_db, const bool fix_scale, univloc_server::Server* server);

    virtual bool slerp_pose_between_keyframes(data::keyframe* kf, double time, Mat44_t& T_interp) const;

    virtual void abort_graph_optimizaion();

    virtual bool is_running();

    /**
     * Destructor
     */
    virtual ~window_graph_optimizer() = default;

    /**
     * Perform pose graph optimization
     * @param loop_keyfrm
     * @param curr_keyfrm
     * @param non_corrected_Sim3s
     * @param pre_corrected_Sim3s
     * @param loop_connections
     */
    virtual void optimize(data::keyframe* loop_keyfrm, data::keyframe* curr_keyfrm,
                  std::map<data::keyframe*, std::set<data::keyframe*>>& loop_connections,int iteration_times);

    virtual MapID get_map_id() { return map_id_; };

private:
    /* window parameters start*/
    const size_t edge_size_ = 2;
    // threshold for tracking landmarks interval
    unsigned int interval_threshold_ = 2;
    // window size for calculate error average
    size_t error_window_size_ = 3;
    // reproject threshold
    float reproj_threshold_ = 1.8;
    // veloctity threshold
    float veloctity_error_threshold_ = 0.05;
    /* window parameters end*/
    std::vector<float> reproject_error_vector_;
    std::vector<Mat44_t, Eigen::aligned_allocator<Mat44_t>> velocity_vector_;

    bool find_edge_ = false;
    data::window* curr_window_ptr_ = nullptr;
    data::keyframe* current_kf_ = nullptr;
    data::keyframe* last_kf_ = nullptr;

    unsigned int current_window_id_ = 0;
    unsigned int edge_number_ = 0;

    void classify_keyframes(const std::map<KeyframeID, data::keyframe*>& all_keyframes, std::vector<data::keyframe*>& single_keyframes,
                            std::vector<data::keyframe*>& window_keyframes, std::vector<data::window*>& all_windows,
                            std::unordered_map<KeyframeID, data::keyframe*>& opt_keyfrm_ids);
    bool judge_window(int kf_count);
    void finished_current_window(std::vector<data::keyframe*>& single_keyframes, std::vector<data::window*>& all_windows, std::vector<data::keyframe*>& window_keyframes,
                                 std::unordered_map<KeyframeID, data::keyframe*>& opt_keyfrm_ids);
    Mat44_t calcualte_median_velocity();
};

}  // namespace optimize
}  // namespace openvslam

#endif

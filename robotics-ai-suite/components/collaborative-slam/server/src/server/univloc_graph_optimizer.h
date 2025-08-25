// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_UNIVLOC_OPTIMIZE_GRAPH_OPTIMIZER_H
#define OPENVSLAM_UNIVLOC_OPTIMIZE_GRAPH_OPTIMIZER_H

#include "optimize/graph_optimizer.h"

#include <atomic>
#include <mutex>

namespace univloc_server {
class Server;
}

namespace openvslam {

namespace data {
class keyframe;
class map_database;
}  // namespace data

typedef std::vector<std::pair<std::pair<data::keyframe*, Mat44_t>, std::pair<data::keyframe*, Mat44_t>>>
    pair_keyframe_pose_vec;

namespace optimize {

// enum graph_optimizer::OptimizationType;

class univloc_graph_optimizer: public graph_optimizer {
public:
    enum OptimizationType { Front_Rear_Optimization, Loop_Optimization } optimization_type_;

    /**
     * Constructor
     * @param map_db
     * @param fix_scale
     */
    explicit univloc_graph_optimizer(data::map_database* map_db, const bool fix_scale, univloc_server::Server* server);

    virtual bool slerp_pose_between_keyframes(data::keyframe* kf, double time, Mat44_t& T_interp) const;

    virtual void abort_graph_optimizaion();

    virtual bool is_running();

    virtual ClientID get_keyframe_id();
    /**
     * Destructor
     */
    virtual ~univloc_graph_optimizer() = default;

    /**
     * Perform pose graph optimization
     * @param loop_keyfrm
     * @param curr_keyfrm
     * @param non_corrected_Sim3s
     * @param pre_corrected_Sim3s
     * @param loop_connections
     */
    virtual void optimize(data::keyframe* loop_keyfrm, data::keyframe* curr_keyfrm,
                  std::map<data::keyframe*, std::set<data::keyframe*>>& loop_connections,
                  std::vector<data::keyframe*>& unused_nerbors, pair_keyframe_pose_vec loop_connections_with_pose,
                  int iteration_times);

    virtual void optimize_involved(data::keyframe* cur_keyframe, data::keyframe* constraint_keyframe, int iteration_times,
                           bool post_process);

    virtual MapID get_map_id() { return map_id_; };

protected:
    //! number of graph optimization times is performed
    unsigned int num_exec_graph_optimization_ = 0;

    //! flag to abort loop BA
    bool abort_graph_optimization_ = false;

    //! flag which indicates loop BA is running or not
    std::atomic<bool> graph_optimization_is_running_ = false;

    mutable std::mutex mtx_thread_;

    univloc_server::Server* server_;

    std::atomic<ClientID> client_id_;

    std::atomic<MapID> map_id_;
};

}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_UNIVLOC_OPTIMIZE_GRAPH_OPTIMIZER_H

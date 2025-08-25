// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_UNIVLOC_GLOBAL_OPTIMIZATION_MODULE_H
#define OPENVSLAM_UNIVLOC_GLOBAL_OPTIMIZATION_MODULE_H

#include "global_optimization_module.h"
#include "server/univloc_graph_optimizer.h"

namespace univloc_server {
class Server;
}

namespace openvslam {

namespace data {
class keyframe;
class bow_database;
class map_database;
}  // namespace data

class univloc_global_optimization_module: public global_optimization_module {
public:
    //! Constructor
    univloc_global_optimization_module(data::map_database* map_db, data::bow_database* bow_db,
                                       data::bow_vocabulary* bow_vocab, const bool fix_scale,
                                       double front_rear_camera_constraint_thr, int iteration_times,
                                       bool segment_optimize, bool correct_loop);

    //! Destructor
    ~univloc_global_optimization_module() override;

    void set_server(univloc_server::Server* server);

    //-----------------------------------------
    // main process

    //! Run main loop of the global optimization module
    void run() override;

private:
    void Local_BA_for_merging_map(std::vector<data::keyframe*> adjust_keyframes,
                                  std::vector<data::keyframe*> fixed_keyframes);

    //! Perform loop closing
    void correct_loop() override;
    
    bool detect_front_rear_camera_constraint();

    void correct_front_rear_camera_constraint();

    void merge_map_via_loop();

    void merge_map_via_front_rear_camera_constraint();

    void add_loop_connections(MapID map_id,
                              const std::map<data::keyframe*, std::set<data::keyframe*>>& new_connections);

    //TODO_linking verify if this method is needed
    /*
    void map_align(data::keyframe* loop_keyfrm, data::keyframe* curr_keyfrm,
                   const module::keyframe_Sim3_pairs_t& non_corrected_Sim3s,
                   const module::keyframe_Sim3_pairs_t& pre_corrected_Sim3s,
                   const std::map<data::keyframe*, std::set<data::keyframe*>>& loop_connections) const;
    */

    // For multi-slam system;
    univloc_server::Server* server_ = nullptr;

    bool detect_front_rear_camera_constraint_ = false;

   // Pose graph thread for front and rear camera constraint
    std::map<ClientID, std::unique_ptr<std::thread>> thread_for_optimization_client_;

    std::map<ClientID, std::unique_ptr<optimize::univloc_graph_optimizer>> graph_optimizers_client_;

    // Pose graph thread for loop constraint
    std::map<MapID, std::unique_ptr<std::thread>> thread_for_optimization_map_;

    std::map<MapID, std::unique_ptr<optimize::univloc_graph_optimizer>> graph_optimizers_map_;
   
    std::map<MapID, std::map<data::keyframe*, std::set<data::keyframe*>>> loop_connections_;

    std::map<MapID, pair_keyframe_pose_vec> loop_connections_with_pose_;

    std::map<MapID, std::vector<data::keyframe*>> unused_neighbors_;

    std::map<ClientID, data::keyframe*> last_front_rear_camera_constraints_;

    std::map<ClientID, data::keyframe*> last_corrected_front_rear_camera_constraints_;

    // Whether do correct loop since it will bring randomness when enabling IMU
    bool correct_loop_;
};

}  // namespace openvslam

#endif  // OPENVSLAM_UNIVLOC_GLOBAL_OPTIMIZATION_MODULE_H

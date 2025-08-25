// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_DATA_LANDMARK_H
#define OPENVSLAM_DATA_LANDMARK_H

#include "type.h"

#include <atomic>
#include <map>
#include <mutex>

#include <nlohmann/json_fwd.hpp>
#include <opencv2/core/core.hpp>

namespace openvslam {
namespace data {

class frame;

class keyframe;

class map_database;

class landmark {
public:
    EIGEN_MAKE_ALIGNED_OPERATOR_NEW

    // For multi-slam system
    // TODO_Unify: Client id on server side is constant. On tracker tracking module assigns the value
    ClientID client_id_;

    int last_grid_x_ = 0, last_grid_y_ = 0;

    void set_descriptor(cv::Mat& descriptor);

    void change_to_new_map(data::map_database* new_map_db);

    void set_map_id(const MapID map_id);

    MapID get_map_id();

    void assign_to_grid();

    bool new_created_ = true;

    bool is_new_created();

    void set_not_new_created();

    mutable std::mutex mtx_newcreated_;

    static void initial_start_id(const LandmarkID start_id);

    bool update_from_server_ = false;

    bool come_from_server();

    void set_update_from_server(bool update_from_server);

    bool is_update_from_server();

    void set_ref_keyframe(data::keyframe* keyframe);

    unsigned int get_num_observable() { return num_observable_; }

    unsigned int get_num_observed() { return num_observed_; }

    //! default constructor
    landmark(const Vec3_t& pos_w, keyframe* ref_keyfrm, map_database* map_db);

    //! constructor for creating server landmark during insert_new_keyframe
    landmark(const Vec3_t& pos_w, keyframe* ref_keyfrm, map_database* map_db, LandmarkID id, bool come_from_server);

    //! constructor for map loading
    landmark(const LandmarkID id, const KeyframeID first_keyfrm_id, const Vec3_t& pos_w, keyframe* ref_keyfrm,
             const unsigned int num_visible, const unsigned int num_found, map_database* map_db);

    //! constructor for processing server landmark in Client module
    landmark(const LandmarkID id, const ClientID client_id, const Vec3_t& pos_w, const cv::Mat& descriptor,
             const float max_valid_dist, const float min_valid_dist, const Vec3_t mean_normal,
             map_database* map_db = nullptr, bool come_from_server = false);

    //! constructor on the server side
    landmark(const LandmarkID id, const KeyframeID first_keyfrm_id, const Vec3_t& pos_w, keyframe* ref_keyfrm,
             const unsigned int num_visible, const unsigned int num_found, map_database* map_db, ClientID client_id,
             MapID map_id);

    //! set world coordinates of this landmark
    void set_pos_in_world(const Vec3_t& pos_w);
    //! get world coordinates of this landmark
    Vec3_t get_pos_in_world() const;

    //! get mean normalized vector of keyframe->lm vectors, for keyframes such that observe the 3D point.
    Vec3_t get_obs_mean_normal() const;
    //! get reference keyframe, a keyframe at the creation of a given 3D point
    keyframe* get_ref_keyframe() const;

    //! add observation
    void add_observation(keyframe* keyfrm, unsigned int idx, bool is_relocalization = false);
    //! erase observation
    void erase_observation(keyframe* keyfrm, bool is_server = false);

    //! get observations (keyframe and keypoint idx)
    std::map<keyframe*, unsigned int> get_observations() const;
    //! get number of observations
    unsigned int num_observations() const;
    //! whether this landmark is observed from more than zero keyframes
    bool has_observation() const;

    //! get index of associated keypoint in the specified keyframe
    int get_index_in_keyframe(keyframe* keyfrm) const;
    //! whether this landmark is observed in the specified keyframe
    bool is_observed_in_keyframe(keyframe* keyfrm) const;

    //! check the distance between landmark and camera is in ORB scale variance
    inline bool is_inside_in_orb_scale(const float cam_to_lm_dist) const
    {
        const float max_dist = this->get_max_valid_distance();
        const float min_dist = this->get_min_valid_distance();
        return (min_dist <= cam_to_lm_dist && cam_to_lm_dist <= max_dist);
    }

    //! get representative descriptor
    cv::Mat get_descriptor() const;

    //! compute representative descriptor
    void compute_descriptor();

    //! update observation mean normal and ORB scale variance
    void update_normal_and_depth();

    //! get max valid distance between landmark and camera
    float get_min_valid_distance() const;
    //! get min valid distance between landmark and camera
    float get_max_valid_distance() const;
    //! get distance between landmark and camera center
    float get_distance_to_cam_center() const;

    //! predict scale level assuming this landmark is observed in the specified frame
    unsigned int predict_scale_level(const float cam_to_lm_dist, const frame* frm) const;
    //! predict scale level assuming this landmark is observed in the specified keyframe
    unsigned int predict_scale_level(const float cam_to_lm_dist, const keyframe* keyfrm) const;

    //! erase this landmark from database
    void prepare_for_erasing(bool is_redundant = true, bool is_server = false);

    //! whether this landmark will be erased shortly or not
    bool will_be_erased();

    //! replace this with specified landmark
    void replace(landmark* lm);
    //! get replace landmark
    landmark* get_replaced() const;

    void set_replaced() { replaced_ = nullptr; }

    void increase_num_observable(unsigned int num_observable = 1);
    void increase_num_observed(unsigned int num_observed = 1);
    float get_observed_ratio() const;

    void set_existed_in_server_map(bool existed_in_server_map);

    bool is_existed_in_server_map();

    void set_existed_in_tracking(bool existed_in_tracking);

    bool is_existed_in_tracking();

    //! encode landmark information as JSON
    nlohmann::json to_json() const;

    unsigned int out_of_local_map_times_ = 0;

public:
    LandmarkID replace_other_id_;  // This landmark may replace another landmark in client after local mapping and
                                     // this message need to be sent to server
    KeyframeID observed_in_other_keyframe_id_ = 0;
    unsigned int observed_in_other_keyframe_index_ = 0;

    LandmarkID id_;
    static std::atomic<LandmarkID> next_id_;
    KeyframeID first_keyfrm_id_ = 0;
    unsigned int num_observations_ = 0;

    // Variables for frame tracking.
    Vec2_t reproj_in_tracking_;
    float x_right_in_tracking_ = 0.0;
    bool is_observable_in_tracking_ = false;
    int scale_level_in_tracking_ = 0;
    KeyframeID identifier_in_local_map_update_ = 0;
    KeyframeID identifier_in_local_lm_search_ = 0;

    // Variables for loop-closing.
    KeyframeID loop_fusion_identifier_ = 0;
    KeyframeID ref_keyfrm_id_in_loop_fusion_ = 0;
    Vec3_t pos_w_after_global_BA_;
    KeyframeID loop_BA_identifier_ = 0;
    bool being_sliding_out_ = false;
    void set_to_be_erased();

    // flags used in one optimization,
    // will reset at the end of optimization
    bool is_considered_; // if considered (add to container)
    bool is_fixed_;      // if fixed in optimizer

    Vec3_t pos_w_before_correct_;

    void set_identifier_last_observation_id(KeyframeID identifier_last_observation_id);

    KeyframeID get_identifier_last_observation_id();

    void set_previously_sent_flag(const bool value);

    bool get_previously_sent_flag();

private:
    KeyframeID identifier_last_observation_id_ = 0;

    //! world coordinates of this landmark
    Vec3_t pos_w_;

    //! observations (keyframe and keypoint index)
    std::map<keyframe*, unsigned int> observations_;

    //! Normalized average vector (unit vector) of keyframe->lm, for keyframes such that observe the 3D point.
    Vec3_t mean_normal_;

    //! representative descriptor
    cv::Mat descriptor_;

    //! reference keyframe
    keyframe* ref_keyfrm_;

    // track counter
    unsigned int num_observable_ = 1;
    unsigned int num_observed_ = 1;

    //! this landmark will be erased shortly or not
    bool will_be_erased_ = false;

    //! replace this landmark with below
    landmark* replaced_ = nullptr;

    // flag used in localization mode, indicate whether
    // landmark has already been sent to tracker from server
    bool is_previously_sent_ = false;

    // ORB scale variances
    //! max valid distance between landmark and camera
    float min_valid_dist_ = 0;
    //! min valid distance between landmark and camera
    float max_valid_dist_ = 0;

    //! map database
    map_database* map_db_;

    mutable std::mutex mtx_position_;
    mutable std::mutex mtx_observations_;

    bool existed_in_server_map_ = false;

    bool existed_in_tracking_ = false;

    const bool come_from_server_;

    MapID map_id_;
};

typedef std::shared_ptr<landmark> landmark_ptr;

}  // namespace data
}  // namespace openvslam

#endif  // OPENVSLAM_DATA_LANDMARK_H

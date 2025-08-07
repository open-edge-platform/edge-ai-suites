// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_DATA_MAP_DATABASE_H
#define OPENVSLAM_DATA_MAP_DATABASE_H

#include "data/bow_vocabulary.h"
#include "data/frame_statistics.h"

#include <map>
#include <mutex>
#include <unordered_map>
#include <utility>
#include <vector>
#include <list>

#include <nlohmann/json_fwd.hpp>

namespace openvslam {

namespace camera {
class base;
}  // namespace camera

typedef std::pair<int, int> gridxy_index_pair;

namespace data {

class frame;
class keyframe;
class landmark;
class camera_database;
class bow_database;

class map_database {
public:
    MapID register_new_map_id();

    void unregister_map_id(MapID id);

    std::set<MapID> get_all_registered_map_ids();

    void lock_map_mutex() { mtx_map_access_.lock(); }

    std::vector<landmark*> get_local_lms() const { return local_landmarks_; }

    void unlock_map_mutex() { mtx_map_access_.unlock(); }

    void delete_from_grid(const landmark* lm);

    void delete_from_grid(const LandmarkID id, const int grid_x, const int grid_y);

    void insert_into_grid(landmark* lm, int grid_x, int grid_y);

    void add_constraint(int constraint_id, const Eigen::Affine3d& initial_transform)
    {
        constraints_[constraint_id] = initial_transform;
    }

    Eigen::Affine3d get_constraint(int constraint_id) const { return constraints_.at(constraint_id); }

    std::map<int, Eigen::Affine3d> get_all_multicamera_constraints() const
    {  // Need a lock?
        return constraints_;
    }

    void set_constraint(int constraint_id, const Eigen::Matrix4d T);

    void save_map_to_jsonfile(std::string keyframe_jsonfile_name, std::string landmark_jsonfile_name);

    void load_map_from_jsonfile(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                                std::string keyframe_jsonfile_name, std::string landmark_jsonfile_name);

    // Retrieve all landmarks on the given map that fall into the camera frustum with the given pose
    // Will skip recently observed landmarks if kf_id_is_valid is true
    std::vector<landmark*> get_landmarks_in_frustum(Eigen::Matrix4d curr_pose, camera::base* curr_camera,
                                                    MapID curr_map_id, KeyframeID curr_kf_id, bool kf_id_is_valid,
                                                    std::vector<cv::Point3f>& point_3d,
                                                    std::vector<cv::Point2f>& point_2d,
                                                    std::vector<cv::Point2f>& convex_hull, double near = 0.2,
                                                    double far = 10.0, double back = 0);

    std::vector<landmark*> get_landmarks_in_frustum(keyframe* camera_frame, std::vector<cv::Point3f>& point_3d,
                                                    std::vector<cv::Point2f>& point_2d,
                                                    std::vector<cv::Point2f>& convex_hull, double near = 0.2,
                                                    double far = 10.0, double back = 0);

    std::vector<landmark*> get_all_landmarks(MapID map_id1, MapID map_id2) const;

    void get_all_landmarks_map(std::map<LandmarkID, landmark*>& all_landmarks_map, MapID map_id) const;

    std::unordered_map<KeyframeID, keyframe*> get_map_keyframes() const;

    /**
     * Get all of the keyframes in the database
     * @return
     */
    std::vector<keyframe*> get_all_keyframes(MapID map_id1, MapID map_id2) const;

    void get_all_keyframes_map(std::map<KeyframeID, keyframe*>& all_keyframes_map, MapID map_id) const;

    std::vector<std::shared_ptr<landmark>> get_server_landmarks() const;

    std::shared_ptr<landmark> get_server_landmark(LandmarkID id);

    void remove_old_map();

    unsigned int get_server_landmarks_num();

    /**
     * Constructor
     */
    map_database();

    /**
     * Constructor
     */
    map_database(double grid_size);

    /**
     * Destructor
     */
    ~map_database();

    keyframe* get_keyframe(KeyframeID _id) const;

    landmark* get_landmark(LandmarkID _id);

    /**
     * Add keyframe to the database
     * @param keyfrm
     */
    void add_keyframe(keyframe* keyfrm);

    /**
     * Erase keyframe from the database
     * @param keyfrm
     */
    void erase_keyframe(keyframe* keyfrm, bool is_redundant = true);

    void erase_keyframe_from_id(const KeyframeID id);

    /**
     * Add landmark to the database
     * @param lm
     */
    void add_landmark(landmark* lm);

    /**
     * Erase landmark from the database
     * @param lm
     */
    void erase_landmark(landmark* lm, bool is_redundant = true);

    void erase_landmark_from_id(const LandmarkID id, bool is_redundant = true);

    /**
     * Set local landmarks
     * @param local_lms
     */
    void set_local_landmarks(const std::vector<landmark*>& local_lms);

    /**
     * Get local landmarks
     * @return
     */
    std::vector<landmark*> get_local_landmarks() const;

    /**
     * Get all of the keyframes in the database
     * @return
     */
    std::vector<keyframe*> get_all_keyframes() const;

    std::unordered_map<KeyframeID, keyframe*> get_all_keyframes_map() const;

    /**
     * Get the number of keyframes
     * @return
     */
    unsigned get_num_keyframes() const;

    /**
     * Get all of the landmarks in the database
     * @return
     */
    std::vector<landmark*> get_all_landmarks() const;

    /**
     * Get the number of landmarks
     * @return
     */
    unsigned int get_num_landmarks() const;

    /**
     * Get the maximum keyframe ID
     * @return
     */
    KeyframeID get_max_keyframe_id() const;

    /**
     * Update frame statistics
     * @param frm
     * @param is_lost
     */
    void update_frame_statistics(const data::frame& frm, const bool is_lost)
    {
        std::lock_guard<std::mutex> lock(mtx_map_access_);
        frm_stats_.update_frame_statistics(frm, is_lost);
    }

    /**
     * Replace a keyframe which will be erased in frame statistics
     * @param old_keyfrm
     * @param new_keyfrm
     */
    void replace_reference_keyframe(data::keyframe* old_keyfrm, data::keyframe* new_keyfrm)
    {
        std::lock_guard<std::mutex> lock(mtx_map_access_);
        frm_stats_.replace_reference_keyframe(old_keyfrm, new_keyfrm);
    }

    /**
     * Get frame statistics
     * @return
     */
    frame_statistics get_frame_statistics() const
    {
        std::lock_guard<std::mutex> lock(mtx_map_access_);
        return frm_stats_;
    }

    /**
     * Clear the database
     */
    void clear();

    /**
     * Load keyframes and landmarks from JSON
     * @param cam_db
     * @param bow_vocab
     * @param bow_db
     * @param json_keyfrms
     * @param json_landmarks
     */
    void from_json(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                   const nlohmann::json& json_keyfrms, const nlohmann::json& json_landmarks);

    /**
     * Dump keyframes and landmarks as JSON
     * @param json_keyfrms
     * @param json_landmarks
     */
    void to_json(nlohmann::json& json_keyfrms, nlohmann::json& json_landmarks);

    void apply_scaled_rotation(const Mat44_t& Twi, const double scale);

    //! origin keyframe, only used in the tracker side to indicate the origin of current map
    keyframe* origin_keyfrm_ = nullptr;

    //! odom origin keyframe
    keyframe* odom_origin_keyfrm_ = nullptr;

    double grid_size_ = 0.1;

    data::keyframe* get_origin_keyframe(MapID map_id) const;

    std::unordered_map<MapID, data::keyframe*> get_all_origin_keyframes() const;

    void add_origin_keyframe(MapID map_id, data::keyframe* keyframe);

    void set_origin_keyframe(MapID map_id, data::keyframe* keyframe);

    void erase_origin_keyframe(MapID map_id);

    //! mutex for locking ALL access to the database
    //! (NOTE: cannot used in map_database class)
    static std::mutex mtx_database_;

    std::vector<KeyframeID> get_erazed_redundant_keyframes_id();

    std::vector<LandmarkID> get_erazed_redundant_landmarks_id();

    void clear_erazed_redundant_keyframes_id();

    void clear_erazed_redundant_landmarks_id();

    void add_server_landmark(std::shared_ptr<landmark> lm);

    void add_erased_server_landmark(LandmarkID id);

    data::keyframe* get_server_virtual_keyframe();

    void update_server_landmarks_vec();

    void update_server_virtual_keyframe(data::keyframe* server_virtual_keyframe);

    void remove_to_be_erased_server_landmarks();

    static std::map<MapID, std::mutex> mtx_map_database_;

    static std::map<std::pair<ClientID, MapID>, std::mutex> mtx_client_map_database_;

    bool is_keyframe_loaded(keyframe* keyfrm) const;

    bool is_landmark_loaded(landmark* landmark) const;

    std::map<ClientID, std::vector<Eigen::Matrix4d>> get_loaded_keyframes_pos_inv();

    void reset_sent_flag_for_all_landmarks();

private:
    // For multi-slam system. It's necessary to remind server those part of map has beed erased

    std::mutex mtx_erased_map_;

    std::vector<KeyframeID> erazed_redundant_keyframes_id_;
    std::vector<LandmarkID> erazed_redundant_landmarks_id_;

    void find_next_available_map_id();

    /**
     * Decode JSON and register keyframe information to the map database
     * (NOTE: objects which are not constructed yet will be set as nullptr)
     * @param cam_db
     * @param bow_vocab
     * @param bow_db
     * @param id
     * @param json_keyfrm
     */
    void register_keyframe(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                           const KeyframeID id, const nlohmann::json& json_keyfrm);
    void register_keyframe_tracker(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                           const KeyframeID id, const nlohmann::json& json_keyfrm);

    void register_keyframe_server(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                           const KeyframeID id, const nlohmann::json& json_keyfrm);

    /**
     * Decode JSON and register landmark information to the map database
     * (NOTE: objects which are not constructed yet will be set as nullptr)
     * @param id
     * @param json_landmark
     */
    void register_landmark(const LandmarkID id, const nlohmann::json& json_landmark);
    void register_landmark_tracker(const LandmarkID id, const nlohmann::json& json_landmark);

    void register_landmark_server(const LandmarkID id, const nlohmann::json& json_landmark);

    /**
     * Decode JSON and register essential graph information
     * (NOTE: keyframe database must be completely constructed before calling this function)
     * @param id
     * @param json_keyfrm
     */
    void register_graph(const KeyframeID id, const nlohmann::json& json_keyfrm);
    void register_graph_tracker(const KeyframeID id, const nlohmann::json& json_keyfrm);

    void register_graph_server(const KeyframeID id, const nlohmann::json& json_keyfrm);

    /**
     * Decode JSON and register keyframe-landmark associations
     * (NOTE: keyframe and landmark database must be completely constructed before calling this function)
     * @param keyfrm_id
     * @param json_keyfrm
     */
    void register_association(const KeyframeID keyfrm_id, const nlohmann::json& json_keyfrm);
    void register_association_tracker(const KeyframeID keyfrm_id, const nlohmann::json& json_keyfrm);

    void register_association_server(const KeyframeID keyfrm_id, const nlohmann::json& json_keyfrm);

    void clear_delete();

    //! mutex for mutual exclusion controll between class methods
    mutable std::mutex mtx_map_access_;

    mutable std::mutex mtx_servermap_access_;

    mutable std::mutex mtx_mapgrid_access_;

    mutable std::mutex mtx_originkeyfrm_access_;

    //-----------------------------------------
    // map ID management
    MapID min_available_map_id_ = 0;
    std::set<MapID> registered_map_ids_;
    mutable std::mutex map_id_mutex_;

    //-----------------------------------------
    // keyframe and landmark database

    //! IDs and keyframes
    std::unordered_map<KeyframeID, keyframe*> keyframes_;
    //! IDs and landmarks
    std::unordered_map<LandmarkID, landmark*> landmarks_;

    //! IDs and server landmarks
    std::unordered_map<LandmarkID, std::shared_ptr<landmark>> server_landmarks_;

    /*
        Since none of the removed objects from database
        releases the memory since they are used by other
        components in the system, these collectors are
        saving pointers and removing them during the
        shutdown.
        Not the optimal solution, but any other requires rewritting
        entire code.
    */
    std::unordered_set<keyframe*> deleted_keyframes_;
    std::unordered_set<landmark*> deleted_landmarks_;

    //! local landmarks
    std::vector<landmark*> local_landmarks_;

    // origin_keyframes for each map, this map may be created by the same client during different session
    std::unordered_map<MapID, data::keyframe*> origin_keyfrms_;

    //! max keyframe ID
    KeyframeID max_keyfrm_id_ = 0;

    data::keyframe* server_virtual_keyframe_ = nullptr;

    //! local server landmarks vector
    std::vector<std::shared_ptr<landmark>> server_landmarks_vec_;

    std::set<LandmarkID> to_be_erased_server_landmark_id_;

    //-----------------------------------------
    // frame statistics for odometry evaluation

    //! frame statistics
    frame_statistics frm_stats_;

    std::map<gridxy_index_pair, std::unordered_map<LandmarkID, landmark*>> landmark_grid_;

    std::map<int, Eigen::Affine3d> constraints_;

    // clientID, id
    std::map<ClientID, std::set<KeyframeID>> loaded_keyframes_id_;
    std::map<ClientID, std::set<LandmarkID>> loaded_landmarks_id_;

    std::map<ClientID, std::vector<Eigen::Matrix4d>> loaded_keyframes_pose_inv_;
};

}  // namespace data
}  // namespace openvslam

#endif  // OPENVSLAM_DATA_MAP_DATABASE_H

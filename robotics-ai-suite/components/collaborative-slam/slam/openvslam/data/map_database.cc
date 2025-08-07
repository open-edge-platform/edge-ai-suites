// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/map_database.h"
#include "camera/base.h"
#include "data/camera_database.h"
#include "data/common.h"
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/landmark.h"
#include "util/converter.h"

#include <spdlog/spdlog.h>
#include <nlohmann/json.hpp>
#include <opencv2/imgproc.hpp>
#include <iomanip>

extern bool is_server_node;

namespace openvslam {
namespace data {

std::mutex map_database::mtx_database_;

std::map<MapID, std::mutex> map_database::mtx_map_database_;

std::map<std::pair<ClientID, MapID>, std::mutex> map_database::mtx_client_map_database_;

struct comp_grid {
    bool operator()(const gridxy_index_pair& grid1, const gridxy_index_pair& grid2) const
    {
        if (grid1.first > grid2.first)
            return true;
        else if (grid1.first < grid2.first)
            return false;
        else
            return grid1.second > grid2.second;
    }
};

map_database::map_database()
{ 
    spdlog::debug("CONSTRUCT: data::map_database");
}

//Server side
map_database::map_database(double grid_size) : grid_size_(grid_size)
{
    spdlog::debug("CONSTRUCT: data::map_database");
}

map_database::~map_database()
{
    clear();
    clear_delete();
    spdlog::debug("DESTRUCT: data::map_database");
}

MapID map_database::register_new_map_id()
{
    std::unique_lock lock(map_id_mutex_);
    MapID ret = min_available_map_id_;
    registered_map_ids_.insert(ret);
    min_available_map_id_++;
    find_next_available_map_id();
    return ret;
}

void map_database::unregister_map_id(MapID id)
{
    std::unique_lock lock(map_id_mutex_);
    registered_map_ids_.erase(id);
    if (min_available_map_id_ < id) min_available_map_id_ = id;
}

void map_database::find_next_available_map_id()
{
    while (true) {
        if (min_available_map_id_ == std::numeric_limits<MapID>::max()) {
            spdlog::critical("map_database: map ID is about to overflow! (now max ID is {})",
                             min_available_map_id_ - 1);
            throw std::overflow_error("map_id about to overflow");
        }
        if (registered_map_ids_.find(min_available_map_id_) == registered_map_ids_.end()) break;
        ++min_available_map_id_;
    }
}

std::set<MapID> map_database::get_all_registered_map_ids()
{
    std::scoped_lock<std::mutex> lock(map_id_mutex_);
    std::set<MapID> registered_map_ids;
    for (auto map_id : registered_map_ids_)
        registered_map_ids.emplace(map_id);

    return registered_map_ids;
}

void map_database::add_keyframe(keyframe* keyfrm)
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    keyframes_[keyfrm->id_] = keyfrm;
    if (keyfrm->id_ > max_keyfrm_id_) {
        max_keyfrm_id_ = keyfrm->id_;
    }

    spdlog::debug("keyframes_.size(): {} ", keyframes_.size());
}

void map_database::erase_keyframe_from_id(const KeyframeID id)
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    if (!keyframes_.count(id))
        return;

    keyframe* keyfrm = keyframes_[id];
    keyframes_.erase(id);
    // Add to delete list
    deleted_keyframes_.insert(keyfrm);
}

std::vector<keyframe*> map_database::get_all_keyframes(MapID map_id1, MapID map_id2) const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    std::vector<keyframe*> keyframes;
    keyframes.reserve(keyframes_.size());
    for (const auto& id_keyframe : keyframes_) {
        if (id_keyframe.second->get_map_id() == map_id1 || id_keyframe.second->get_map_id() == map_id2)
            keyframes.push_back(id_keyframe.second);
    }
    return keyframes;
}

void map_database::get_all_keyframes_map(std::map<KeyframeID, keyframe*>& all_keyframes_map, MapID map_id) const
{
    std::scoped_lock<std::mutex> lock(mtx_map_access_);
    for (const auto& id_keyframe : keyframes_) {
        if (id_keyframe.second->get_map_id() == map_id)
            all_keyframes_map.emplace(id_keyframe.first, id_keyframe.second);
    }
}

std::unordered_map<KeyframeID, keyframe*> map_database::get_all_keyframes_map() const {
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    return keyframes_;
}

data::keyframe* map_database::get_origin_keyframe(MapID map_id) const
{
    std::scoped_lock<std::mutex> lock(mtx_originkeyfrm_access_);
    if (!origin_keyfrms_.count(map_id)) return nullptr;

    return origin_keyfrms_.at(map_id);
}

std::unordered_map<MapID, data::keyframe*> map_database::get_all_origin_keyframes() const
{
    std::scoped_lock<std::mutex> lock(mtx_originkeyfrm_access_);
    std::unordered_map<MapID, data::keyframe*> all_origin_keyframes;
    for (const auto& id_keyfrm_pair : origin_keyfrms_) {
        all_origin_keyframes.emplace(id_keyfrm_pair.first, id_keyfrm_pair.second);
    }
    return all_origin_keyframes;
}

void map_database::add_origin_keyframe(MapID map_id, data::keyframe* keyframe)
{
    std::scoped_lock<std::mutex> lock(mtx_originkeyfrm_access_);
    origin_keyfrms_.emplace(map_id, keyframe);
}

void map_database::set_origin_keyframe(MapID map_id, data::keyframe* keyframe)
{
    std::scoped_lock<std::mutex> lock(mtx_originkeyfrm_access_);
    origin_keyfrms_.at(map_id) = keyframe;
}

void map_database::erase_origin_keyframe(MapID map_id)
{
    std::scoped_lock<std::mutex> lock(mtx_originkeyfrm_access_);
    origin_keyfrms_.erase(map_id);
}

std::vector<landmark*> map_database::get_all_landmarks(MapID map_id1, MapID map_id2) const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    std::vector<landmark*> landmarks;
    landmarks.reserve(landmarks_.size());
    for (const auto& id_landmark : landmarks_) {
        if (id_landmark.second->get_map_id() == map_id1 || id_landmark.second->get_map_id() == map_id2)
            landmarks.push_back(id_landmark.second);
    }
    return landmarks;
}

void map_database::get_all_landmarks_map(std::map<LandmarkID, landmark*>& all_landmarks_map, MapID map_id) const
{
    std::scoped_lock<std::mutex> lock(mtx_map_access_);
    for (const auto& id_landmark : landmarks_) {
        if (id_landmark.second->get_map_id() == map_id)
            all_landmarks_map.emplace(id_landmark.first, id_landmark.second);
    }
}

std::vector<landmark*> map_database::get_landmarks_in_frustum(Eigen::Matrix4d curr_pose, camera::base* curr_camera,
                                                              MapID curr_map_id, KeyframeID curr_kf_id,
                                                              bool kf_id_is_valid, std::vector<cv::Point3f>& point_3d,
                                                              std::vector<cv::Point2f>& point_2d,
                                                              std::vector<cv::Point2f>& convex_hull, double near,
                                                              double far, double back)
{
    camera::image_bounds bounds = curr_camera->compute_image_bounds();
    const std::vector<cv::KeyPoint> pixels{
        cv::KeyPoint(bounds.min_x_, bounds.min_y_, 1.0),                   // left top
        cv::KeyPoint(bounds.max_x_, bounds.min_y_, 1.0),                   // right top
        cv::KeyPoint(bounds.min_x_, bounds.max_y_, 1.0),                   // left bottom
        cv::KeyPoint(bounds.max_x_, bounds.max_y_, 1.0),                   // right bottom
        /*cv::KeyPoint(bounds.max_x_ * 0.5, bounds.max_y_ * 0.5, 1.0)*/};  // middle - not needed
    eigen_alloc_vector<Vec3_t> bearings;
    curr_camera->convert_keypoints_to_bearings(pixels, bearings);

    // Calculate the world coorindates of the near and far point of each bearing,
    // find out their boundaries and convex hull
    std::vector<cv::Point2f> points2d, hull;
    double min_x = std::numeric_limits<double>::max();
    double max_x = std::numeric_limits<double>::min();
    double min_y = std::numeric_limits<double>::max();
    double max_y = std::numeric_limits<double>::min();
    auto update_boundary = [&min_x, &max_x, &min_y, &max_y](double x, double y) {
        if (x < min_x) min_x = x;
        if (x > max_x) max_x = x;
        if (y < min_y) min_y = y;
        if (y > max_y) max_y = y;
    };

    // obtain inverse pose
    const Eigen::Matrix3d rot_cw = curr_pose.block<3, 3>(0, 0);
    const Eigen::Vector3d trans_cw = curr_pose.block<3, 1>(0, 3);
    const Eigen::Matrix3d rot_wc = rot_cw.transpose();
    Eigen::Vector3d cam_center = -rot_wc * trans_cw;

    Eigen::Matrix4d Twc = Eigen::Matrix4d::Identity();
    Twc.block<3, 3>(0, 0) = rot_wc;
    Twc.block<3, 1>(0, 3) = cam_center + rot_wc * Eigen::Vector3d(0, 0, -back);

    // const Eigen::Matrix4d Twc = camera_frame->get_cam_pose_inv(); // T(world, camera)
    Eigen::Vector4d tcp;  // t(camera, point)
    tcp << 0, 0, 0, 1;
    for (const auto& bearing : bearings) {
        tcp.block<3, 1>(0, 0) = bearing * near;
        Eigen::Vector4d twp = Twc * tcp;
        points2d.emplace_back(twp(0), twp(1));
        point_3d.emplace_back(twp(0), twp(1), twp(2));
        update_boundary(twp(0), twp(1));
        tcp.block<3, 1>(0, 0) = bearing * far;
        twp = Twc * tcp;
        points2d.emplace_back(twp(0), twp(1));
        point_3d.emplace_back(twp(0), twp(1), twp(2));
        update_boundary(twp(0), twp(1));
    }
    // nice formulation!!
    cv::convexHull(points2d, hull);
    for (const auto& p2d : points2d) point_2d.push_back(p2d);
    for (const auto& ch : hull) convex_hull.push_back(ch);

    // Iterate all the grid cells within the boundary
    int min_grid_x = std::floor(min_x / grid_size_);
    int min_grid_y = std::floor(min_y / grid_size_);
    int max_grid_x = std::ceil(max_x / grid_size_);
    int max_grid_y = std::ceil(max_y / grid_size_);

    auto pose_can_observe = [&curr_pose, &curr_camera](data::landmark* lm, float x_expand, float y_expand) {
        const Vec3_t pos_w = lm->get_pos_in_world();
        Vec2_t reproj;
        float right_x;
        return curr_camera->reproject_to_image_bound(curr_pose.block(0, 0, 3, 3), curr_pose.block(0, 3, 3, 1), pos_w, reproj,
                                               right_x, x_expand, y_expand);
    };

    std::vector<landmark*> landmarks;
    for (int x = min_grid_x; x <= max_grid_x; ++x) {
        for (int y = min_grid_y; y <= max_grid_y; ++y) {
            if (pointPolygonTest(hull, cv::Point2f(x * grid_size_, y * grid_size_), false) < 0)
                continue;  // outside the hull

            gridxy_index_pair cell(x, y);
            std::unique_lock<std::mutex> lock(mtx_mapgrid_access_);
            if (landmark_grid_.find(cell) == landmark_grid_.end()) {
                lock.unlock();
                continue;
            }
            const auto landmarks_in_grid = landmark_grid_[cell];
            lock.unlock();

            for (auto& item : landmarks_in_grid) {
                // Ignore invalid landmarks and landmarks on other maps
                if (!item.second || item.second->get_map_id() != curr_map_id) continue;

                // Ignore landmarks outside of the current camera view (with a tolerance of 10 pixels)
                if (!pose_can_observe(item.second, 10, 10)) continue;

                // Ignore landmarks recently observed by the target client (likely be in their local map)
                auto last_obs_id = item.second->get_identifier_last_observation_id();
                if (kf_id_is_valid && (curr_kf_id <= last_obs_id + 3) && (last_obs_id <= curr_kf_id + 3)) continue;

                landmarks.push_back(item.second);
            }
        }
    }
    return landmarks;
}

std::vector<landmark*> map_database::get_landmarks_in_frustum(keyframe* camera_frame,
                                                              std::vector<cv::Point3f>& point_3d,
                                                              std::vector<cv::Point2f>& point_2d,
                                                              std::vector<cv::Point2f>& convex_hull, double near,
                                                              double far, double back)
{
    return get_landmarks_in_frustum(camera_frame->get_cam_pose(), camera_frame->camera_, camera_frame->get_map_id(),
                                    camera_frame->id_, true, point_3d, point_2d, convex_hull, near, far, back);
}

void map_database::set_constraint(int constraint_id, const Eigen::Matrix4d T)
{
    assert(constraints_.find(constraint_id) != constraints_.end());
    constraints_[constraint_id] = Eigen::Affine3d(T);
}

void map_database::add_landmark(landmark* lm)
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    landmarks_[lm->id_] = lm;
}

keyframe* map_database::get_keyframe(KeyframeID id) const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    auto iter = keyframes_.find(id);
    if (iter == keyframes_.end())
        return nullptr;
    else
        return iter->second;
}

data::keyframe* map_database::get_server_virtual_keyframe()
{
    std::unique_lock<std::mutex> lock_map_access(mtx_map_access_);

    return server_virtual_keyframe_;
}

std::vector<std::shared_ptr<landmark>> map_database::get_server_landmarks() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    return server_landmarks_vec_;
}

unsigned int map_database::get_server_landmarks_num()
{
    std::lock_guard<std::mutex> lock(mtx_servermap_access_);  // May be no need
    return server_landmarks_.size();
}

std::shared_ptr<landmark> map_database::get_server_landmark(LandmarkID id)
{
    std::lock_guard<std::mutex> lock(mtx_servermap_access_);  // May be no need
    if (server_landmarks_.find(id) == server_landmarks_.end())
        return nullptr;
    else
        return server_landmarks_[id];
}

void map_database::add_server_landmark(std::shared_ptr<landmark> lm)
{
    std::lock_guard<std::mutex> lock(mtx_servermap_access_);  // May be no need
    server_landmarks_[lm->id_] = lm;
}

void map_database::update_server_landmarks_vec()
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    // update server landmark vector
    server_landmarks_vec_.clear();

    server_landmarks_vec_.resize(server_landmarks_.size());

    unsigned int idx = 0;
    for (auto id_lm : server_landmarks_) {
        server_landmarks_vec_[idx] = id_lm.second;
        idx++;
    }
}

void map_database::add_erased_server_landmark(LandmarkID id)
{
    std::unique_lock<std::mutex> lock(mtx_map_access_);
    to_be_erased_server_landmark_id_.emplace(id);
    if (server_landmarks_.count(id)) server_landmarks_[id]->set_to_be_erased();
}

void map_database::remove_to_be_erased_server_landmarks()
{
    spdlog::debug("Start to remove {} to_be_erased_server_landmarks!", to_be_erased_server_landmark_id_.size());
    std::unique_lock<std::mutex> lock(mtx_map_access_);

    for (auto id : to_be_erased_server_landmark_id_) {
        if (server_landmarks_.count(id)) {
            server_landmarks_[id]->prepare_for_erasing(true, true);
            server_landmarks_.erase(id);
        }
    }
    to_be_erased_server_landmark_id_.clear();
}

std::vector<KeyframeID> map_database::get_erazed_redundant_keyframes_id()
{
    std::unique_lock<std::mutex> lock(mtx_erased_map_);
    return erazed_redundant_keyframes_id_;
}

std::vector<LandmarkID> map_database::get_erazed_redundant_landmarks_id()
{
    std::unique_lock<std::mutex> lock(mtx_erased_map_);
    return erazed_redundant_landmarks_id_;
}

void map_database::clear_erazed_redundant_keyframes_id()
{
    std::unique_lock<std::mutex> lock(mtx_erased_map_);
    erazed_redundant_keyframes_id_.clear();
}

void map_database::delete_from_grid(const landmark* lm)
{
    Vec3_t pos_w = lm->get_pos_in_world();

    // keep mtx_position_ and mtx_mapgrid_access_ in the same order as other place
    std::lock_guard<std::mutex> lock(mtx_mapgrid_access_);
    landmark_grid_[std::pair<int, int>(pos_w[0] / grid_size_, pos_w[1] / grid_size_)].erase(lm->id_);
}

void map_database::delete_from_grid(const LandmarkID id, const int grid_x, const int grid_y)
{
    std::lock_guard<std::mutex> lock(mtx_mapgrid_access_);
    landmark_grid_[std::pair<int, int>(grid_x, grid_y)].erase(id);
}

void map_database::insert_into_grid(landmark* lm, int grid_x, int grid_y)
{
    std::lock_guard<std::mutex> lock(mtx_mapgrid_access_);
    landmark_grid_[std::pair<int, int>(grid_x, grid_y)][lm->id_] = lm;
}

void map_database::clear_erazed_redundant_landmarks_id()
{
    std::unique_lock<std::mutex> lock(mtx_erased_map_);
    erazed_redundant_landmarks_id_.clear();
}



void map_database::erase_keyframe(keyframe* keyfrm, bool is_redundant)
{
    std::scoped_lock<std::mutex> lock_access(mtx_map_access_);
    assert(keyframes_.find(keyfrm->id_) != keyframes_.end());

    if (is_server_node) {
        if (loaded_keyframes_id_.count(keyfrm->client_id_) > 0) {
            loaded_keyframes_id_[keyfrm->client_id_].erase(keyfrm->id_);
        }
    } else if (is_redundant) {
        std::unique_lock<std::mutex> lock_erase_redundant(mtx_erased_map_);
        erazed_redundant_keyframes_id_.push_back(keyfrm->id_);
    }

    keyframes_.erase(keyfrm->id_);
    // Add to delete list
    deleted_keyframes_.insert(keyfrm);

    // update max keyframe id while erase keyframe
    if (max_keyfrm_id_ <= keyfrm->id_) {
        max_keyfrm_id_ = 0;
        for (const auto& id_kf : keyframes_) {
            if (id_kf.first > max_keyfrm_id_) {
                max_keyfrm_id_ = id_kf.first;
            }
        }
    }
}

void map_database::update_server_virtual_keyframe(data::keyframe* server_virtual_keyframe)
{
    if (server_virtual_keyframe_) {
        // delete server_virtual_keyframe_;
        server_virtual_keyframe_ = nullptr;
    }
    server_virtual_keyframe_ = server_virtual_keyframe;
}


landmark* map_database::get_landmark(LandmarkID id)
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    auto iter = landmarks_.find(id);
    if (iter == landmarks_.end())
        return nullptr;
    else
        return iter->second;
}

std::unordered_map<KeyframeID, keyframe*> map_database::get_map_keyframes() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    return keyframes_;
}

void map_database::erase_landmark(landmark* lm, bool is_redundant)
{
    if (is_server_node) {
        std::lock_guard<std::mutex> lock(mtx_map_access_);
        delete_from_grid(lm->id_, lm->last_grid_x_, lm->last_grid_y_);
        landmarks_.erase(lm->id_);
        // Add to delete list
        deleted_landmarks_.insert(lm);
    } else {
        std::lock_guard<std::mutex> lock(mtx_map_access_);
        if (is_redundant) {
            std::unique_lock<std::mutex> lock(mtx_erased_map_);
            erazed_redundant_landmarks_id_.push_back(lm->id_);
        }
        landmarks_.erase(lm->id_);

        deleted_landmarks_.insert(lm);
    }
}

void map_database::erase_landmark_from_id(const LandmarkID id, bool is_redundant)
{
    if (is_server_node) {
        std::lock_guard<std::mutex> lock(mtx_map_access_);
        landmark* lm = landmarks_[id];
        delete_from_grid(lm);
        landmarks_.erase(id);
        // Add to delete list
        deleted_landmarks_.insert(lm);
    } else {
        std::lock_guard<std::mutex> lock(mtx_map_access_);
        if (is_redundant) {
            std::unique_lock<std::mutex> lock(mtx_erased_map_);
            erazed_redundant_landmarks_id_.push_back(id);
        }
        landmarks_.erase(id);
        landmark *lm = landmarks_[id];
        deleted_landmarks_.insert(lm);
    }
}

void map_database::set_local_landmarks(const std::vector<landmark*>& local_lms)
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    local_landmarks_.clear();
    local_landmarks_ = local_lms;
}

std::vector<landmark*> map_database::get_local_landmarks() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    return local_landmarks_;
}

void map_database::remove_old_map()
{
    spdlog::debug("Start remove_old_map!");
    std::unique_lock<std::mutex> lock(mtx_map_access_);
    std::set<LandmarkID> erased_landmarks_id;
    const unsigned int out_of_local_map_times_thr = 2;
    // Remove old map
    for (auto& id_lm : landmarks_) {
        if (!id_lm.second) {
            erased_landmarks_id.insert(id_lm.first);
            continue;
        }

        if (id_lm.second->out_of_local_map_times_ >= out_of_local_map_times_thr)
            erased_landmarks_id.insert(id_lm.first);
        else
            id_lm.second->out_of_local_map_times_++;
    }

    // Remove old keyframes
    std::set<KeyframeID> erased_keyframes_id;

    for (auto& id_kf : keyframes_) {
        if (!id_kf.second) {
            erased_keyframes_id.insert(id_kf.first);
            spdlog::warn("No this keyframe: {}", id_kf.first);
            continue;
        }

        if (id_kf.second->out_of_local_map_times_ >= out_of_local_map_times_thr) {
            erased_keyframes_id.insert(id_kf.first);
            id_kf.second->set_will_be_erased();
        } else
            id_kf.second->out_of_local_map_times_++;
    }

    lock.unlock();

    spdlog::debug("Remove {} old landmarks", erased_landmarks_id.size());
    spdlog::debug("Remove {} old keyframes", erased_keyframes_id.size());
    std::lock_guard<std::mutex> lock_database(mtx_database_);
    lock.lock();
    // false means this object is not rebundant, so we won't inform server to erase it
    // Firstly created, firstly to be erazed, or it may occur mistake
    for (auto keyframe_id : erased_keyframes_id) {
        // keyframes_[keyframe_id]->prepare_for_erasing(false);  // Here has some problem, so we don't erase it
        // now
        // keyframes_.at(keyframe_id)->set_will_be_erased();
        keyframes_.at(keyframe_id)->update_imu_link();
        // if (keyframes_.at(keyframe_id)->next_keyframe_) {
        //     std::shared_ptr<IMU_Preintegration> next_imu_constraint =
        //         keyframes_.at(keyframe_id)->next_keyframe_->get_imu_constraint().second;
        //     next_imu_constraint->merge_preintegration(keyframes_.at(keyframe_id)->get_imu_constraint().second);
        //     keyframes_.at(keyframe_id)
        //         ->next_keyframe_->set_imu_constraint(keyframes_.at(keyframe_id)->get_imu_constraint().first,
        //                                              next_imu_constraint);
        //     keyframes_.at(keyframe_id)->next_keyframe_->pre_keyframe_ = nullptr;
        //     if (keyframes_.at(keyframe_id)->pre_keyframe_) {
        //         keyframes_.at(keyframe_id)->next_keyframe_->pre_keyframe_ =
        //         keyframes_.at(keyframe_id)->pre_keyframe_; keyframes_.at(keyframe_id)->pre_keyframe_->next_keyframe_
        //         = keyframes_.at(keyframe_id)->next_keyframe_;
        //     }
        // }
        keyframes_.erase(keyframe_id);
    }
    lock.unlock();

    for (auto lm_id : erased_landmarks_id) {
        if (landmarks_.count(lm_id)) {
            landmarks_[lm_id]->prepare_for_erasing(false);
            // delete landmarks_[lm_id];
        }
    }

    for (auto id_server_landmark : server_landmarks_) {
        if (id_server_landmark.second->out_of_local_map_times_ >= out_of_local_map_times_thr * 2) {
            to_be_erased_server_landmark_id_.insert(id_server_landmark.first);
            id_server_landmark.second->set_to_be_erased();
        } else
            id_server_landmark.second->out_of_local_map_times_++;
    }

    spdlog::debug("Finished remove_old_map!");
}

std::vector<keyframe*> map_database::get_all_keyframes() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    std::vector<keyframe*> keyframes;
    keyframes.reserve(keyframes_.size());
    for (const auto& id_keyframe : keyframes_) {
        keyframes.push_back(id_keyframe.second);
    }
    return keyframes;
}

unsigned int map_database::get_num_keyframes() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    return keyframes_.size();
}

std::vector<landmark*> map_database::get_all_landmarks() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    std::vector<landmark*> landmarks;
    landmarks.reserve(landmarks_.size());
    for (const auto& id_landmark : landmarks_) {
        landmarks.push_back(id_landmark.second);
    }
    return landmarks;
}

unsigned int map_database::get_num_landmarks() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    return landmarks_.size();
}

KeyframeID map_database::get_max_keyframe_id() const
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    return max_keyfrm_id_;
}

void map_database::clear_delete() {
    std::lock_guard<std::mutex> lock(mtx_map_access_);

    for (auto& lm : landmarks_) {
        delete lm.second;
        lm.second = nullptr;
    }

    for (auto& keyfrm : keyframes_) {
        delete keyfrm.second;
        keyfrm.second = nullptr;
    }

    for (auto lm : deleted_landmarks_) {
        delete lm;
        lm = nullptr;
    }

    for (auto keyfrm : deleted_keyframes_) {
        delete keyfrm;
        keyfrm = nullptr;
    }

    landmarks_.clear();
    keyframes_.clear();
    deleted_landmarks_.clear();
    deleted_keyframes_.clear();
}

void map_database::clear()
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);

    for (auto& lm : landmarks_)
        deleted_landmarks_.insert(lm.second);

    for (auto& keyfrm : keyframes_)
        deleted_keyframes_.insert(keyfrm.second);

    landmarks_.clear();
    keyframes_.clear();
    server_virtual_keyframe_ = nullptr;
    max_keyfrm_id_ = 0;
    local_landmarks_.clear();
    origin_keyfrm_ = nullptr;

    frm_stats_.clear();

    server_landmarks_vec_.clear();
    server_landmarks_.clear();

    spdlog::info("clear map database");
}

void map_database::save_map_to_jsonfile(std::string keyframe_jsonfile_name, std::string landmark_jsonfile_name)
{
    nlohmann::json json_keyframes, json_landmarks;
    to_json(json_keyframes, json_landmarks);
    std::ofstream map_keyframe_file(keyframe_jsonfile_name);
    map_keyframe_file << std::setw(8) << json_keyframes << std::endl;
    map_keyframe_file.close();
    std::ofstream map_landmark_file(landmark_jsonfile_name);
    map_landmark_file << std::setw(8) << json_landmarks << std::endl;
    map_landmark_file.close();
    spdlog::info("Sucessfully save map to json file and exit!");
}

void map_database::load_map_from_jsonfile(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                                          std::string keyframe_jsonfile_name, std::string landmark_jsonfile_name)
{
    nlohmann::json json_keyframes, json_landmarks;
    std::ifstream map_keyframe_file(keyframe_jsonfile_name);
    std::ifstream map_landmark_file(landmark_jsonfile_name);
    if (map_keyframe_file.is_open() && map_landmark_file.is_open()) {
        map_keyframe_file >> json_keyframes;
        map_landmark_file >> json_landmarks;
        from_json(cam_db, bow_vocab, bow_db, json_keyframes, json_landmarks);
        spdlog::info("Sucessfully load map from json file!");
    } else {
        spdlog::info("No map to be loaded!");
    }
}

void map_database::from_json(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                             const nlohmann::json& json_keyfrms, const nlohmann::json& json_landmarks)
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);

    // Step 1. delete all the data in map database
    for (auto& lm : landmarks_) {
        delete lm.second;
        lm.second = nullptr;
    }

    for (auto& keyfrm : keyframes_) {
        delete keyfrm.second;
        keyfrm.second = nullptr;
    }

    landmarks_.clear();
    keyframes_.clear();
    max_keyfrm_id_ = 0;
    local_landmarks_.clear();
    origin_keyfrm_ = nullptr;
    registered_map_ids_.clear();

    // Step 2. Register keyframes
    // If the object does not exist at this step, the corresponding pointer is set as nullptr.
    spdlog::info("decoding {} keyframes to load", json_keyfrms.size());
    for (const auto& json_id_keyfrm : json_keyfrms.items()) {
        const auto id = std::stoul(json_id_keyfrm.key());
        const auto json_keyfrm = json_id_keyfrm.value();

        register_keyframe(cam_db, bow_vocab, bow_db, id, json_keyfrm);
    }

    // Step 3. Register 3D landmark point
    // If the object does not exist at this step, the corresponding pointer is set as nullptr.
    spdlog::info("decoding {} landmarks to load", json_landmarks.size());
    for (const auto& json_id_landmark : json_landmarks.items()) {
        const auto id = std::stoul(json_id_landmark.key());
        const auto json_landmark = json_id_landmark.value();

        register_landmark(id, json_landmark);
    }

    // Step 4. Register graph information
    spdlog::info("registering essential graph");
    for (const auto& json_id_keyfrm : json_keyfrms.items()) {
        const auto id = std::stoul(json_id_keyfrm.key());
        const auto json_keyfrm = json_id_keyfrm.value();

        register_graph(id, json_keyfrm);
    }

    // Step 5. Register association between keyframs and 3D points
    spdlog::info("registering keyframe-landmark association");
    for (const auto& json_id_keyfrm : json_keyfrms.items()) {
        const auto id = std::stoul(json_id_keyfrm.key());
        const auto json_keyfrm = json_id_keyfrm.value();

        register_association(id, json_keyfrm);
    }

    // Step 6. Update graph
    spdlog::info("updating covisibility graph");
    for (const auto& json_id_keyfrm : json_keyfrms.items()) {
        const auto id = std::stoul(json_id_keyfrm.key());

        assert(keyframes_.count(id));
        auto keyfrm = keyframes_.at(id);

        keyfrm->graph_node_->update_connections();
        keyfrm->graph_node_->update_covisibility_orders();
    }

    // Step 7. Update geometry
    spdlog::info("updating landmark geometry");
    for (const auto& json_id_landmark : json_landmarks.items()) {
        const auto id = std::stoul(json_id_landmark.key());

        assert(landmarks_.count(id));
        auto lm = landmarks_.at(id);

        lm->update_normal_and_depth();
        lm->compute_descriptor();
    }

    if (is_server_node) {
        // Step 8. Update min available map ID
        min_available_map_id_ = 0;
        find_next_available_map_id();
    }
}

void map_database::register_keyframe(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                                     const KeyframeID id, const nlohmann::json& json_keyfrm)
{
    if (is_server_node)
        register_keyframe_server(cam_db, bow_vocab, bow_db,
                                     id, json_keyfrm);
    else
        register_keyframe_tracker(cam_db, bow_vocab, bow_db,
                                     id, json_keyfrm);
}

void map_database::register_keyframe_tracker(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                                     const KeyframeID id, const nlohmann::json& json_keyfrm)
{
    // Metadata
    const auto src_frm_id = json_keyfrm.at("src_frm_id").get<KeyframeID>();
    const auto timestamp = json_keyfrm.at("ts").get<double>();
    const auto camera_name = json_keyfrm.at("cam").get<std::string>();
    const auto camera = cam_db->get_camera(camera_name);
    const auto depth_thr = json_keyfrm.at("depth_thr").get<float>();

    // Pose information
    const Mat33_t rot_cw = convert_json_to_rotation(json_keyfrm.at("rot_cw"));
    const Vec3_t trans_cw = convert_json_to_translation(json_keyfrm.at("trans_cw"));
    const auto cam_pose_cw = util::converter::to_eigen_cam_pose(rot_cw, trans_cw);

    // Keypoints information
    const auto num_keypts = json_keyfrm.at("n_keypts").get<unsigned int>();
    // keypts
    const auto json_keypts = json_keyfrm.at("keypts");
    const auto keypts = convert_json_to_keypoints(json_keypts);
    assert(keypts.size() == num_keypts);
    // undist_keypts
    const auto json_undist_keypts = json_keyfrm.at("undists");
    const auto undist_keypts = convert_json_to_undistorted(json_undist_keypts);
    assert(undist_keypts.size() == num_keypts);
    // bearings
    auto bearings = eigen_alloc_vector<Vec3_t>(num_keypts);
    assert(bearings.size() == num_keypts);
    camera->convert_keypoints_to_bearings(undist_keypts, bearings);
    // stereo_x_right
    const auto stereo_x_right = json_keyfrm.at("x_rights").get<std::vector<float>>();
    assert(stereo_x_right.size() == num_keypts);
    // depths
    const auto depths = json_keyfrm.at("depths").get<std::vector<float>>();
    assert(depths.size() == num_keypts);
    // descriptors
    const auto json_descriptors = json_keyfrm.at("descs");
    const auto descriptors = convert_json_to_descriptors(json_descriptors);
    assert(descriptors.rows == static_cast<int>(num_keypts));

    // Scale information in ORB
    const auto num_scale_levels = json_keyfrm.at("n_scale_levels").get<unsigned int>();
    const auto scale_factor = json_keyfrm.at("scale_factor").get<float>();

    // Construct a new object
    auto keyfrm = new data::keyframe(id, src_frm_id, timestamp, cam_pose_cw, camera, depth_thr, num_keypts, keypts,
                                     undist_keypts, bearings, stereo_x_right, depths, descriptors, num_scale_levels,
                                     scale_factor, bow_vocab, bow_db, this);

    // Append to map database
    assert(!keyframes_.count(id));
    keyframes_[keyfrm->id_] = keyfrm;
    if (keyfrm->id_ > max_keyfrm_id_) {
        max_keyfrm_id_ = keyfrm->id_;
    }
    if (id == 0) {
        origin_keyfrm_ = keyfrm;  // need to be modified
    }
}

void map_database::register_keyframe_server(camera_database* cam_db, bow_vocabulary* bow_vocab, bow_database* bow_db,
                           const KeyframeID id, const nlohmann::json& json_keyfrm) {
    // Metadata
    const ClientID client_id = json_keyfrm.at("client_id").get<ClientID>();
    const KeyframeID src_frm_id = std::stoul(json_keyfrm.at("src_frm_id").get<std::string>());
    const auto timestamp = json_keyfrm.at("ts").get<double>();
    const auto camera_name = json_keyfrm.at("cam").get<std::string>();
    const auto camera = cam_db->get_client_camera(client_id);
    const auto depth_thr = json_keyfrm.at("depth_thr").get<float>();

    // Pose information
    const Mat33_t rot_cw = convert_json_to_rotation(json_keyfrm.at("rot_cw"));
    const Vec3_t trans_cw = convert_json_to_translation(json_keyfrm.at("trans_cw"));
    const auto cam_pose_cw = util::converter::to_eigen_cam_pose(rot_cw, trans_cw);

    // Keypoints information
    const auto num_keypts = json_keyfrm.at("n_keypts").get<unsigned int>();
    // keypts
    const auto json_keypts = json_keyfrm.at("keypts");
    const auto keypts = convert_json_to_keypoints(json_keypts);
    assert(keypts.size() == num_keypts);
    // undist_keypts
    const auto json_undist_keypts = json_keyfrm.at("undists");
    const auto undist_keypts = convert_json_to_undistorted(json_undist_keypts);
    assert(undist_keypts.size() == num_keypts);
    // bearings
    auto bearings = eigen_alloc_vector<Vec3_t>(num_keypts);
    assert(bearings.size() == num_keypts);
    camera->convert_keypoints_to_bearings(undist_keypts, bearings);
    // stereo_x_right
    const auto stereo_x_right = json_keyfrm.at("x_rights").get<std::vector<float>>();
    assert(stereo_x_right.size() == num_keypts);
    // depths  has no usage anymore! depths vector will be empty
    // const auto depths = json_keyfrm.at("depths").get<std::vector<float>>();
    // if (depths.size() != num_keypts) {
    //     std::cout << depths.size() << " " << num_keypts << std::endl;
    // }
    // assert(depths.size() == num_keypts);

    // descriptors
    const auto json_descriptors = json_keyfrm.at("descs");
    const auto descriptors = convert_json_to_descriptors(json_descriptors);
    assert(descriptors.rows == static_cast<int>(num_keypts));

    // Scale information in ORB
    const auto num_scale_levels = json_keyfrm.at("n_scale_levels").get<unsigned int>();
    const auto scale_factor = json_keyfrm.at("scale_factor").get<float>();
    const auto map_id = static_cast<MapID>(std::stoi(json_keyfrm.at("map_id").get<std::string>()));
    registered_map_ids_.insert(map_id);

    std::vector<float> depths(num_keypts, 0);

    // Construct a new object
    auto keyfrm = new data::keyframe(id, src_frm_id, timestamp, cam_pose_cw, camera, depth_thr, num_keypts, keypts,
                                     undist_keypts, bearings, stereo_x_right, depths, descriptors, num_scale_levels,
                                     scale_factor, bow_vocab, bow_db, this, client_id, map_id);

    // Append to map database
    assert(!keyframes_.count(id));
    keyframes_[keyfrm->id_] = keyfrm;

    if (keyfrm->id_ > max_keyfrm_id_) {
        max_keyfrm_id_ = keyfrm->id_;
    }
    loaded_keyframes_id_[client_id].insert(id);
}

bool map_database::is_keyframe_loaded(keyframe* keyfrm) const
{
    if (!keyfrm) {
        spdlog::warn("[{}]: the input keyframe is nullptr, directly return false!", __func__);
        return false;
    }

    std::scoped_lock<std::mutex> lock(mtx_map_access_);
    if (!loaded_keyframes_id_.count(keyfrm->client_id_)) return false;
    if (!loaded_keyframes_id_.at(keyfrm->client_id_).count(keyfrm->id_)) return false;
    return true;
}

std::map<ClientID, std::vector<Eigen::Matrix4d>> map_database::get_loaded_keyframes_pos_inv()
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);
    if (loaded_keyframes_pose_inv_.empty()) {
        for (const auto& item : loaded_keyframes_id_) {
            unsigned int size = item.second.size();
            ClientID client_id = item.first;
            loaded_keyframes_pose_inv_[client_id].resize(size);
            unsigned int idx = 0;
            for (const auto& id : item.second) {
                loaded_keyframes_pose_inv_[client_id][idx] = keyframes_[id]->get_cam_pose_inv();
                idx++;
            }
        }
    }
    return loaded_keyframes_pose_inv_;
}

void map_database::register_landmark(const LandmarkID id, const nlohmann::json& json_landmark)
{
    if (is_server_node)
        register_landmark_server(id, json_landmark);
    else
        register_landmark_tracker(id, json_landmark);
}

void map_database::register_landmark_tracker(const LandmarkID id, const nlohmann::json& json_landmark)
{
    const auto first_keyfrm_id = std::stoul(json_landmark.at("1st_keyfrm").get<std::string>());
    const auto pos_w = Vec3_t(json_landmark.at("pos_w").get<std::vector<Vec3_t::value_type>>().data());
    const auto ref_keyfrm_id = std::stoul(json_landmark.at("ref_keyfrm").get<std::string>());
    const auto ref_keyfrm = keyframes_.at(ref_keyfrm_id);
    const auto num_visible = json_landmark.at("n_vis").get<unsigned int>();
    const auto num_found = json_landmark.at("n_fnd").get<unsigned int>();

    auto lm = new data::landmark(id, first_keyfrm_id, pos_w, ref_keyfrm, num_visible, num_found, this);
    assert(!landmarks_.count(id));
    landmarks_[lm->id_] = lm;
}

void map_database::register_landmark_server(const LandmarkID id, const nlohmann::json& json_landmark) {
    const KeyframeID first_keyfrm_id = std::stoul(json_landmark.at("1st_keyfrm").get<std::string>());
    const auto pos_w = Vec3_t(json_landmark.at("pos_w").get<std::vector<Vec3_t::value_type>>().data());
    KeyframeID ref_keyfrm_id = std::stoul(json_landmark.at("ref_keyfrm").get<std::string>());
    const ClientID client_id = json_landmark.at("client_id").get<ClientID>();
    const auto map_id = static_cast<MapID>(std::stoi(json_landmark.at("map_id").get<std::string>()));
    // Invalid ref_keyfrm_id, it's strange!
    data::keyframe* ref_keyfrm = nullptr;
    // This will rarely happen when landing map from local disk! It's atrange!
    if (!keyframes_.count(ref_keyfrm_id)) {
        spdlog::debug("Invalid ref_keyfrm_id {} for this landmark {}", ref_keyfrm_id, id);
    } else {
        ref_keyfrm = keyframes_.at(ref_keyfrm_id);
    }

    const auto num_visible = json_landmark.at("n_vis").get<unsigned int>();
    const auto num_found = json_landmark.at("n_fnd").get<unsigned int>();
    registered_map_ids_.insert(map_id);

    assert(!landmarks_.count(id));
    auto lm =
        new data::landmark(id, first_keyfrm_id, pos_w, ref_keyfrm, num_visible, num_found, this, client_id, map_id);
    assert(!landmarks_.count(id));
    landmarks_[lm->id_] = lm;

    loaded_landmarks_id_[client_id].insert(id);
}

bool map_database::is_landmark_loaded(landmark* landmark) const
{
    if (!landmark) {
        spdlog::warn("[{}]: the input landmark is nullptr, directly return false!", __func__);
        return false;
    }

    std::scoped_lock<std::mutex> lock(mtx_map_access_);
    if (!loaded_landmarks_id_.count(landmark->client_id_)) return false;
    if (!loaded_landmarks_id_.at(landmark->client_id_).count(landmark->id_)) return false;
    return true;
}

void map_database::register_graph(const KeyframeID id, const nlohmann::json& json_keyfrm) {
    if (is_server_node)
        register_graph_server(id, json_keyfrm);
    else
        register_graph_tracker(id, json_keyfrm);
}

void map_database::register_graph_server(const KeyframeID id, const nlohmann::json& json_keyfrm) {
    // Graph information
    const auto spanning_parent_id = json_keyfrm.at("span_parent").get<std::string>();
    const auto spanning_children_ids = json_keyfrm.at("span_children").get<std::vector<std::string>>();
    const auto loop_edge_ids = json_keyfrm.at("loop_edges").get<std::vector<std::string>>();

    assert(keyframes_.count(id));
    assert(spanning_parent_id == "-1" || keyframes_.count(std::stoul(spanning_parent_id)));
    keyframes_.at(id)->graph_node_->set_spanning_parent(
        (spanning_parent_id == "-1") ? nullptr : keyframes_.at(std::stoul(spanning_parent_id)));
    for (const auto &spanning_child_id : spanning_children_ids) {
        assert(keyframes_.count(std::stoul(spanning_child_id)));
        keyframes_.at(id)->graph_node_->add_spanning_child(keyframes_.at(std::stoul(spanning_child_id)));
    }
    for (const auto &loop_edge_id : loop_edge_ids) {
        assert(keyframes_.count(std::stoul(loop_edge_id)));
        keyframes_.at(id)->graph_node_->add_loop_edge(keyframes_.at(std::stoul(loop_edge_id)));
    }

    if (spanning_parent_id == "-1") {
        auto kf = keyframes_.at(id);
        spdlog::info("In the loaded map, Map {}, Client {}: Origin keyframe {}", kf->get_map_id(), kf->client_id_, id);
        kf->set_origin();
        if (!origin_keyfrms_.count(kf->get_map_id()) || origin_keyfrms_[kf->get_map_id()]->timestamp_ > kf->timestamp_)
            origin_keyfrms_[kf->get_map_id()] = kf;
    }

    const auto front_and_rear_constraint_keyframe_id_string =
        json_keyfrm.at("front_and_rear_constraint_keyframe_id").get<std::string>();
    if (front_and_rear_constraint_keyframe_id_string != "-1") {
        if (!keyframes_.count(std::stoul(front_and_rear_constraint_keyframe_id_string))) {
            spdlog::debug("front_and_rear_constraint_keyframe_id_string: {}",
                          front_and_rear_constraint_keyframe_id_string);
        } else {
            auto kf = keyframes_.at(std::stoul(front_and_rear_constraint_keyframe_id_string));
            keyframes_.at(id)->graph_node_->add_constraint_edge(std::stoul(front_and_rear_constraint_keyframe_id_string),
                                                                kf);
        }
    }
}

void map_database::register_graph_tracker(const KeyframeID id, const nlohmann::json& json_keyfrm)
{
    // Graph information
    const auto spanning_parent_id = json_keyfrm.at("span_parent").get<int>();
    const auto spanning_children_ids = json_keyfrm.at("span_children").get<std::vector<int>>();
    const auto loop_edge_ids = json_keyfrm.at("loop_edges").get<std::vector<int>>();

    assert(keyframes_.count(id));
    assert(spanning_parent_id == -1 || keyframes_.count(spanning_parent_id));
    keyframes_.at(id)->graph_node_->set_spanning_parent((spanning_parent_id == -1) ? nullptr
                                                                                   : keyframes_.at(spanning_parent_id));
    for (const auto spanning_child_id : spanning_children_ids) {
        assert(keyframes_.count(spanning_child_id));
        keyframes_.at(id)->graph_node_->add_spanning_child(keyframes_.at(spanning_child_id));
    }
    for (const auto loop_edge_id : loop_edge_ids) {
        assert(keyframes_.count(loop_edge_id));
        keyframes_.at(id)->graph_node_->add_loop_edge(keyframes_.at(loop_edge_id));
    }
}

void map_database::register_association(const KeyframeID keyfrm_id, const nlohmann::json& json_keyfrm)
{
    if (is_server_node)
        register_association_server(keyfrm_id, json_keyfrm);
    else
        register_association_tracker(keyfrm_id, json_keyfrm);
}

void map_database::register_association_tracker(const KeyframeID keyfrm_id, const nlohmann::json& json_keyfrm)
{
    // Key points information
    const auto num_keypts = json_keyfrm.at("n_keypts").get<unsigned int>();
    const auto landmark_ids = json_keyfrm.at("lm_ids").get<std::vector<LandmarkID>>();
    assert(landmark_ids.size() == num_keypts);

    assert(keyframes_.count(keyfrm_id));
    auto keyfrm = keyframes_.at(keyfrm_id);
    for (unsigned int idx = 0; idx < num_keypts; ++idx) {
        const auto lm_id = landmark_ids.at(idx);
        if (!landmarks_.count(lm_id)) {
            spdlog::warn("landmark {}: not found in the database", lm_id);
            continue;
        }

        auto lm = landmarks_.at(lm_id);
        keyfrm->add_landmark(lm, idx);
        lm->add_observation(keyfrm, idx);
    }
}

void map_database::register_association_server(const KeyframeID keyfrm_id, const nlohmann::json& json_keyfrm) {
    // Key points information
    const auto num_keypts = json_keyfrm.at("n_keypts").get<unsigned int>();
    const auto landmark_ids = json_keyfrm.at("lm_ids").get<std::vector<std::string>>();
    assert(landmark_ids.size() == num_keypts);

    assert(keyframes_.count(keyfrm_id));
    auto keyfrm = keyframes_.at(keyfrm_id);
    for (unsigned int idx = 0; idx < num_keypts; ++idx) {
        auto str_id = landmark_ids.at(idx);
        if (str_id == "-1")
            continue;
        auto lm_id = std::stoul(str_id);
        if (!landmarks_.count(lm_id)) {
            spdlog::warn("landmark {}: not found in the database", landmark_ids.at(idx));
            continue;
        }

        auto lm = landmarks_.at(lm_id);
        keyfrm->add_landmark(lm, idx);
        lm->add_observation(keyfrm, idx);
    }
}

void map_database::to_json(nlohmann::json& json_keyfrms, nlohmann::json& json_landmarks)
{
    std::lock_guard<std::mutex> lock(mtx_map_access_);

    // Save each keyframe as json
    spdlog::info("encoding {} keyframes to store", keyframes_.size());
    std::map<std::string, nlohmann::json> keyfrms;
    for (auto& id_keyfrm : keyframes_) {
        const auto id = id_keyfrm.first;
        auto keyfrm = id_keyfrm.second;
        assert(keyfrm);
        assert(id == keyfrm->id_);
        assert(!keyfrm->will_be_erased());
        keyfrm->graph_node_->update_connections();
        assert(!keyfrms.count(std::to_string(id)));
        keyfrms[std::to_string(id)] = keyfrm->to_json();
    }
    json_keyfrms = keyfrms;

    // Save each 3D point as json
    spdlog::info("encoding {} landmarks to store", landmarks_.size());
    std::map<std::string, nlohmann::json> landmarks;
    for (auto& id_lm : landmarks_) {
        const auto id = id_lm.first;
        auto lm = id_lm.second;
        assert(lm);
        assert(id == lm->id_);
        assert(!lm->will_be_erased());
        lm->update_normal_and_depth();
        assert(!landmarks.count(std::to_string(id)));
        landmarks[std::to_string(id)] = lm->to_json();
    }
    json_landmarks = landmarks;
}

void map_database::apply_scaled_rotation(const Mat44_t& Tiw, const double scale)
{
    Mat33_t rotation_iw = Tiw.block(0, 0, 3, 3);
    Vec3_t translation_iw = Tiw.block(0, 3, 3, 1);

    std::scoped_lock<std::mutex> lock(mtx_map_access_);
    for (auto& id_keyframe : keyframes_) {
        keyframe* item = id_keyframe.second;
        Mat44_t Twc = item->get_cam_pose_inv();
        Twc.block(0, 3, 3, 1) = Twc.block(0, 3, 3, 1) * scale;
        Mat44_t Tic = Tiw * Twc;
        item->set_cam_pose(Tic.inverse());
        Vec3_t velocity = item->get_imu_velocity();
        item->set_imu_velocity(rotation_iw * velocity * scale);
    }

    for (auto& id_landmark : landmarks_) {
        landmark* item = id_landmark.second;
        item->set_pos_in_world(scale * rotation_iw * item->get_pos_in_world() + translation_iw);
        item->update_normal_and_depth();
    }
}

void map_database::reset_sent_flag_for_all_landmarks()
{
    std::scoped_lock<std::mutex> lock(mtx_map_access_);
    for (auto& lm : landmarks_) {
        lm.second->set_previously_sent_flag(false);
    }
}

}  // namespace data
}  // namespace openvslam

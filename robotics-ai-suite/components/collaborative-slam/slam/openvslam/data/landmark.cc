// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/landmark.h"
#include <spdlog/spdlog.h>
#include "data/frame.h"
#include "data/keyframe.h"
#include "data/map_database.h"
#include "match/base.h"

#include <nlohmann/json.hpp>

extern bool is_server_node;

namespace openvslam {
namespace data {

std::atomic<LandmarkID> landmark::next_id_{0};

// default constructor
landmark::landmark(const Vec3_t& pos_w, keyframe* ref_keyfrm, map_database* map_db)
    : 
      client_id_(0xFF),
      replace_other_id_(0),
      id_(next_id_++),
      first_keyfrm_id_(ref_keyfrm->id_),
      is_considered_(false),
      is_fixed_(false),
      pos_w_(pos_w),
      mean_normal_(Vec3_t::Zero()),
      ref_keyfrm_(ref_keyfrm),
      map_db_(map_db),
      come_from_server_(false),
      map_id_(0xFFFFFFFF)
{
}

// constructor for creating server landmark during insert_new_keyframe
landmark::landmark(const Vec3_t& pos_w, keyframe* ref_keyfrm, map_database* map_db, LandmarkID id,
                   bool come_from_server)
    : 
      client_id_(0xFF),
      new_created_(false),
      replace_other_id_(0),
      id_(id),
      first_keyfrm_id_(ref_keyfrm->id_),
      is_considered_(false),
      is_fixed_(false),
      pos_w_(pos_w),
      mean_normal_(Vec3_t::Zero()),
      ref_keyfrm_(ref_keyfrm),
      map_db_(map_db),
      come_from_server_(come_from_server),
      map_id_(0xFFFFFFFF)
{
}

// constructor for map loading
landmark::landmark(const LandmarkID id, const KeyframeID first_keyfrm_id, const Vec3_t& pos_w, keyframe* ref_keyfrm,
                   const unsigned int num_visible, const unsigned int num_found, map_database* map_db)
    : 
      client_id_(0xFF),
      replace_other_id_(0),
      id_(id),
      first_keyfrm_id_(first_keyfrm_id),
      is_considered_(false),
      is_fixed_(false),
      pos_w_(pos_w),
      mean_normal_(Vec3_t::Zero()),
      ref_keyfrm_(ref_keyfrm),
      num_observable_(num_visible),
      num_observed_(num_found),
      map_db_(map_db),
      come_from_server_(false),
      map_id_(0xFFFFFFFF)
{
}

// constructor for processing server landmark in Client module
landmark::landmark(const LandmarkID id, const ClientID client_id, const Vec3_t& pos_w, const cv::Mat& descriptor,
                   const float max_valid_dist, const float min_valid_dist, const Vec3_t mean_normal,
                   map_database* map_db, bool come_from_server)
    : 
      client_id_(client_id),
      replace_other_id_(0),
      id_(id),
      is_considered_(false),
      is_fixed_(false),
      pos_w_(pos_w),
      mean_normal_(mean_normal),
      ref_keyfrm_(nullptr),
      min_valid_dist_(min_valid_dist),
      max_valid_dist_(max_valid_dist),
      map_db_(map_db),
      come_from_server_(come_from_server),
      map_id_(0xFFFFFFFF)
{
      descriptor_ = descriptor.clone();
}

// constructor on the server side
landmark::landmark(const LandmarkID id, const KeyframeID first_keyfrm_id, const Vec3_t& pos_w, keyframe* ref_keyfrm,
                   const unsigned int num_visible, const unsigned int num_found, map_database* map_db,
                   ClientID client_id, MapID map_id)
    : client_id_(client_id),
      replace_other_id_(0),
      id_(id),
      first_keyfrm_id_(first_keyfrm_id),
      is_considered_(false),
      is_fixed_(false),
      pos_w_(pos_w),
      mean_normal_(Vec3_t::Zero()),
      ref_keyfrm_(ref_keyfrm),
      num_observable_(num_visible),
      num_observed_(num_found),
      map_db_(map_db),
      come_from_server_(false),
      map_id_(map_id)
{
    assign_to_grid();
}

void landmark::set_pos_in_world(const Vec3_t& pos_w)
{
    std::lock_guard<std::mutex> lock(mtx_position_);
    pos_w_ = pos_w;
    if (is_server_node) {
        int cur_grid_x = pos_w_[0] / map_db_->grid_size_;
        int cur_grid_y = pos_w_[1] / map_db_->grid_size_;
        if (cur_grid_x != last_grid_x_ || cur_grid_y != last_grid_y_) {
            map_db_->delete_from_grid(id_, last_grid_x_, last_grid_y_);
            map_db_->insert_into_grid(this, cur_grid_x, cur_grid_y);
            last_grid_x_ = cur_grid_x;
            last_grid_y_ = cur_grid_y;
        }
    }
}

void landmark::set_map_id(const MapID map_id)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    map_id_ = map_id;
}

MapID landmark::get_map_id()
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return map_id_;
}

void landmark::set_identifier_last_observation_id(KeyframeID identifier_last_observation_id)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    identifier_last_observation_id_ = identifier_last_observation_id;
}

KeyframeID landmark::get_identifier_last_observation_id()
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return identifier_last_observation_id_;
}

void landmark::set_descriptor(cv::Mat& descriptor)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    descriptor_ = descriptor.clone();
}

void landmark::change_to_new_map(data::map_database* new_map_db) { map_db_ = new_map_db; }

void landmark::assign_to_grid()
{
    last_grid_x_ = pos_w_[0] / map_db_->grid_size_;
    last_grid_y_ = pos_w_[1] / map_db_->grid_size_;
    map_db_->insert_into_grid(this, last_grid_x_, last_grid_y_);

}

void landmark::initial_start_id(const LandmarkID start_id) { next_id_ = start_id; }

void landmark::set_existed_in_server_map(bool existed_in_server_map)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    existed_in_server_map_ = existed_in_server_map;
}
bool landmark::come_from_server()
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return come_from_server_;
}

bool landmark::is_existed_in_server_map()
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return existed_in_server_map_;
}

void landmark::set_existed_in_tracking(bool existed_in_tracking)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    existed_in_tracking_ = existed_in_tracking;
}

bool landmark::is_existed_in_tracking()
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return existed_in_tracking_;
}

void landmark::set_ref_keyframe(data::keyframe* keyframe)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    ref_keyfrm_ = keyframe;
}

bool landmark::is_new_created()
{
    std::lock_guard<std::mutex> lock(mtx_newcreated_);
    return new_created_;
}

void landmark::set_update_from_server(bool update_from_server) { update_from_server_ = update_from_server; }

bool landmark::is_update_from_server() { return update_from_server_; }

void landmark::set_not_new_created()
{
    std::lock_guard<std::mutex> lock(mtx_newcreated_);
    new_created_ = false;
}

Vec3_t landmark::get_pos_in_world() const
{
    std::lock_guard<std::mutex> lock(mtx_position_);
    return pos_w_;
}

Vec3_t landmark::get_obs_mean_normal() const
{
    std::lock_guard<std::mutex> lock(mtx_position_);
    return mean_normal_;
}

keyframe* landmark::get_ref_keyframe() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return ref_keyfrm_;
}

void landmark::add_observation(keyframe* keyfrm, unsigned int idx, bool is_relocalization)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);

    if (observations_.count(keyfrm)) {
        return;
    }

    if (!is_server_node) {
        if ((!ref_keyfrm_ || observations_.empty()) && come_from_server_) {
            ref_keyfrm_ = keyfrm;
            // spdlog::debug("Set current keyframe {} as this server landmark {} reference keyframe", keyfrm->id_, id_);
        }
    }

    observations_[keyfrm] = idx;

    if (!is_server_node) {
        if (0 <= keyfrm->stereo_x_right_.at(idx) || is_relocalization) {
            num_observations_ += 2;
        } else {
            num_observations_ += 1;
        }
    } else {
        if (0 <= keyfrm->stereo_x_right_.at(idx)) {
            num_observations_ += 2;
        } else {
            num_observations_ += 1;
        }
    }
}

void landmark::erase_observation(keyframe* keyfrm, bool is_server)
{
    bool discard = false;
    {
        std::lock_guard<std::mutex> lock(mtx_observations_);

        if (observations_.count(keyfrm)) {
            int idx = observations_.at(keyfrm);
            if (0 <= keyfrm->stereo_x_right_.at(idx)) {
                num_observations_ -= 2;
            } else {
                num_observations_ -= 1;
            }

            observations_.erase(keyfrm);

            if (ref_keyfrm_ == keyfrm) {
                ref_keyfrm_ = observations_.begin()->first;
            }

            // If only 2 observations or less, discard point
            if (num_observations_ <= 2) {
                discard = true;
            }
        }
    }
    
    if (!is_server_node){
        if (!is_server && discard) {
            prepare_for_erasing();
        }
    } else {
        if (discard) {
            prepare_for_erasing();
        }
    }
}

std::map<keyframe*, unsigned int> landmark::get_observations() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return observations_;
}

unsigned int landmark::num_observations() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return num_observations_;
}

bool landmark::has_observation() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return 0 < num_observations_;
}

int landmark::get_index_in_keyframe(keyframe* keyfrm) const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    if (observations_.count(keyfrm)) {
        return observations_.at(keyfrm);
    } else {
        return -1;
    }
}

bool landmark::is_observed_in_keyframe(keyframe* keyfrm) const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return static_cast<bool>(observations_.count(keyfrm));
}

cv::Mat landmark::get_descriptor() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return descriptor_.clone();
}

void landmark::set_to_be_erased()
{
    std::lock_guard<std::mutex> lock1(mtx_observations_);
    std::lock_guard<std::mutex> lock2(mtx_position_);
    will_be_erased_ = true;
}

void landmark::compute_descriptor()
{
    std::map<keyframe*, unsigned int> observations;
    {
        std::lock_guard<std::mutex> lock1(mtx_observations_);
        if (will_be_erased_) {
            return;
        }
        observations = observations_;
    }

    if (observations.empty()) {
        return;
    }

    // Append features of corresponding points
    std::vector<cv::Mat> descriptors;
    descriptors.reserve(observations.size());
    for (const auto& observation : observations) {
        auto keyfrm = observation.first;
        const auto idx = observation.second;

        if (!keyfrm->will_be_erased()) {
            descriptors.push_back(keyfrm->descriptors_.row(idx));
        }
    }

    // Get median of Hamming distance
    // Calculate all the Hamming distances between every pair of the features
    const auto num_descs = descriptors.size();
    std::vector<std::vector<unsigned int>> hamm_dists(num_descs, std::vector<unsigned int>(num_descs));
    for (unsigned int i = 0; i < num_descs; ++i) {
        hamm_dists.at(i).at(i) = 0;
        for (unsigned int j = i + 1; j < num_descs; ++j) {
            const auto dist = match::compute_descriptor_distance_32(descriptors.at(i), descriptors.at(j));
            hamm_dists.at(i).at(j) = dist;
            hamm_dists.at(j).at(i) = dist;
        }
    }

    // Get the nearest value to median
    unsigned int best_median_dist = match::MAX_HAMMING_DIST;
    unsigned int best_idx = 0;
    for (unsigned idx = 0; idx < num_descs; ++idx) {
        std::vector<unsigned int> partial_hamm_dists(hamm_dists.at(idx).begin(),
                                                     hamm_dists.at(idx).begin() + num_descs);
        std::sort(partial_hamm_dists.begin(), partial_hamm_dists.end());
        const auto median_dist = partial_hamm_dists.at(static_cast<unsigned int>(0.5 * (num_descs - 1)));

        if (median_dist < best_median_dist) {
            best_median_dist = median_dist;
            best_idx = idx;
        }
    }

    {
        std::lock_guard<std::mutex> lock(mtx_observations_);
        descriptor_ = descriptors.at(best_idx).clone();
    }
}

void landmark::update_normal_and_depth()
{
    if (is_server_node) {
        std::scoped_lock<std::mutex> lock(mtx_observations_);

        if (!observations_.count(ref_keyfrm_)) {  // This will rarely happen when landing map from local disk!
            for (const auto& observation : observations_) {
                if (!observation.first) continue;
                ref_keyfrm_ = observation.first;
                break;
            }
        }
    }

    std::map<keyframe*, unsigned int> observations;
    keyframe* ref_keyfrm;
    Vec3_t pos_w;
    {
        std::lock_guard<std::mutex> lock1(mtx_observations_);
        std::lock_guard<std::mutex> lock2(mtx_position_);
        if (will_be_erased_) {
            return;
        }
        observations = observations_;
        ref_keyfrm = ref_keyfrm_;
        pos_w = pos_w_;
    }

    if (observations.empty()) {
        return;
    }

    Vec3_t mean_normal = Vec3_t::Zero();
    unsigned int num_observations = 0;
    for (const auto& observation : observations) {
        auto keyfrm = observation.first;
        const Vec3_t cam_center = keyfrm->get_cam_center();
        const Vec3_t normal = pos_w_ - cam_center;
        mean_normal = mean_normal + normal.normalized();
        ++num_observations;
    }

    assert(ref_keyfrm);
    const Vec3_t cam_to_lm_vec = pos_w - ref_keyfrm->get_cam_center();
    const auto dist = cam_to_lm_vec.norm();

    assert(observations.count(ref_keyfrm));

    const auto scale_level = ref_keyfrm->undist_keypts_.at(observations.at(ref_keyfrm)).octave;
    const auto scale_factor = ref_keyfrm->scale_factors_.at(scale_level);
    const auto num_scale_levels = ref_keyfrm->num_scale_levels_;

    {
        std::lock_guard<std::mutex> lock3(mtx_position_);
        max_valid_dist_ = dist * scale_factor;
        min_valid_dist_ = max_valid_dist_ / ref_keyfrm->scale_factors_.at(num_scale_levels - 1);
        mean_normal_ = mean_normal.normalized();
    }
}

float landmark::get_min_valid_distance() const
{
    std::lock_guard<std::mutex> lock(mtx_position_);
    return 0.7 * min_valid_dist_;
}

float landmark::get_max_valid_distance() const
{
    std::lock_guard<std::mutex> lock(mtx_position_);
    return 1.3 * max_valid_dist_;
}

float landmark::get_distance_to_cam_center() const
{
    std::scoped_lock<std::mutex> lock1(mtx_observations_);
    std::scoped_lock<std::mutex> lock2(mtx_position_);
    const Vec3_t pos_c = ref_keyfrm_->get_rotation() * pos_w_ + ref_keyfrm_->get_translation();
    const float distance = pos_c.norm();
    return distance;
}

unsigned int landmark::predict_scale_level(const float cam_to_lm_dist, const frame* frm) const
{
    float ratio;
    {
        std::lock_guard<std::mutex> lock(mtx_position_);
        ratio = max_valid_dist_ / cam_to_lm_dist;
    }

    const auto pred_scale_level = static_cast<int>(std::ceil(std::log(ratio) / frm->log_scale_factor_));
    if (pred_scale_level < 0) {
        return 0;
    } else if (frm->num_scale_levels_ <= static_cast<unsigned int>(pred_scale_level)) {
        return frm->num_scale_levels_ - 1;
    } else {
        return static_cast<unsigned int>(pred_scale_level);
    }
}

unsigned int landmark::predict_scale_level(const float cam_to_lm_dist, const keyframe* keyfrm) const
{
    float ratio;
    {
        std::lock_guard<std::mutex> lock(mtx_position_);
        ratio = max_valid_dist_ / cam_to_lm_dist;
    }

    const auto pred_scale_level = static_cast<int>(std::ceil(std::log(ratio) / keyfrm->log_scale_factor_));
    if (pred_scale_level < 0) {
        return 0;
    } else if (keyfrm->num_scale_levels_ <= static_cast<unsigned int>(pred_scale_level)) {
        return keyfrm->num_scale_levels_ - 1;
    } else {
        return static_cast<unsigned int>(pred_scale_level);
    }
}

void landmark::prepare_for_erasing(bool is_redundant, bool is_server)
{
    std::map<keyframe*, unsigned int> observations;
    {
        std::lock_guard<std::mutex> lock1(mtx_observations_);
        std::lock_guard<std::mutex> lock2(mtx_position_);
        observations = observations_;
        observations_.clear();
        will_be_erased_ = true;
    }

    for (const auto& keyfrm_and_idx : observations) {
        keyfrm_and_idx.first->erase_landmark_with_index(keyfrm_and_idx.second);
    }
    if (!is_server_node) {
        if (!is_server) map_db_->erase_landmark(this, is_redundant);
    } else {
        map_db_->erase_landmark(this);
    }
}

bool landmark::will_be_erased()
{
    std::lock_guard<std::mutex> lock1(mtx_observations_);
    std::lock_guard<std::mutex> lock2(mtx_position_);
    return will_be_erased_;
}

void landmark::replace(landmark* lm)
{
    if (lm->id_ == this->id_) {
        return;
    }

    lm->replace_other_id_ = this->id_;

    unsigned int num_observable, num_observed;
    std::map<keyframe*, unsigned int> observations;
    {
        std::lock_guard<std::mutex> lock1(mtx_observations_);
        std::lock_guard<std::mutex> lock2(mtx_position_);
        observations = observations_;
        observations_.clear();
        will_be_erased_ = true;
        num_observable = num_observable_;
        num_observed = num_observed_;
        replaced_ = lm;
    }

    if (!is_server_node) {
        // If this replacing landmark comes from server, we set the replaced ref_keyfrm as its ref_keyfrm
        if (lm->come_from_server() && !lm->get_ref_keyframe()) lm->set_ref_keyframe(ref_keyfrm_);
    }
    for (const auto& keyfrm_and_idx : observations) {
        keyframe* keyfrm = keyfrm_and_idx.first;

        if (!lm->is_observed_in_keyframe(keyfrm)) {
            keyfrm->replace_landmark(lm, keyfrm_and_idx.second);
            lm->add_observation(keyfrm, keyfrm_and_idx.second);
        } else {
            keyfrm->erase_landmark_with_index(keyfrm_and_idx.second);
        }
    }

    lm->increase_num_observed(num_observed);
    lm->increase_num_observable(num_observable);
    if (!is_server_node) {
        if (!lm->come_from_server() || lm->has_observation()) lm->compute_descriptor();
    } else {
        lm->compute_descriptor();
    }
    
    map_db_->erase_landmark(this, true);
}

landmark* landmark::get_replaced() const
{
    std::lock_guard<std::mutex> lock1(mtx_observations_);
    std::lock_guard<std::mutex> lock2(mtx_position_);
    return replaced_;
}

void landmark::increase_num_observable(unsigned int num_observable)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    num_observable_ += num_observable;
}

void landmark::increase_num_observed(unsigned int num_observed)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    num_observed_ += num_observed;
}

float landmark::get_observed_ratio() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return static_cast<float>(num_observed_) / num_observable_;
}

nlohmann::json landmark::to_json() const
{
    if (is_server_node) {
        return {{"1st_keyfrm", std::to_string(first_keyfrm_id_)},
            {"pos_w", {pos_w_(0), pos_w_(1), pos_w_(2)}},
            {"ref_keyfrm", std::to_string(ref_keyfrm_->id_)},
            {"n_vis", num_observable_},
            {"n_fnd", num_observed_},
            {"map_id", std::to_string(map_id_)},
            {"client_id", client_id_}};
    } else {
        return {{"1st_keyfrm", first_keyfrm_id_},
            {"pos_w", {pos_w_(0), pos_w_(1), pos_w_(2)}},
            {"ref_keyfrm", ref_keyfrm_->id_},
            {"n_vis", num_observable_},
            {"n_fnd", num_observed_}};
    }
}

void landmark::set_previously_sent_flag(const bool value)
{
    std::scoped_lock<std::mutex> lock(mtx_observations_);
    is_previously_sent_ = value;
}

bool landmark::get_previously_sent_flag()
{
    std::scoped_lock<std::mutex> lock(mtx_observations_);
    return is_previously_sent_;
}

}  // namespace data
}  // namespace openvslam

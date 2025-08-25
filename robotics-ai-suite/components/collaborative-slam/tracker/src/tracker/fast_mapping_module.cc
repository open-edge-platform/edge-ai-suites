// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include "fast_mapping_module.h"

#include <se/node_iterator.hpp>
#include <se/functors/projective_functor.hpp>
#include <se/bfusion/mapping_impl.hpp>
#include <univloc_tracker/ImageFrame.h>

#include "UserConfig.h"
#include "data/map_database.h"
#include "tracker/Client.h"

#include <spdlog/spdlog.h>
#include "spdlog/fmt/ostr.h"

namespace fast_mapping {

static double euclidian_distance(const Eigen::Matrix4d& first, const Eigen::Matrix4d& second)
{
    const Eigen::Vector3d p1 = first.topRightCorner<3,1>();
    const Eigen::Vector3d p2 = second.topRightCorner<3,1>();

    const double x = (p1(0) - p2(0)) * (p1(0) - p2(0));
    const double y = (p1(1) - p2(1)) * (p1(1) - p2(1));
    const double z = (p1(2) - p2(2)) * (p1(2) - p2(2));

    return x + y + z;
}

// Class constructor
fast_mapping_module::fast_mapping_module(std::shared_ptr<univloc_tracker::Config> cfg,
                                         RequestQueue& reconstruction_queue) :
    cfg_(cfg),
    reconstruction_queue_(reconstruction_queue)
{
    intrinsics_ = std::make_unique<camera_intrinsics>(cfg->width_, cfg->height_, cfg->cx_, cfg->cy_, cfg->fx_, cfg->fy_);

    octree_cfg_.compute_size_ratio = cfg_->depth_scaling_factor_;
    octree_cfg_.depth_max_range = cfg_->depth_max_range_;
    octree_cfg_.voxel_per_side = cfg_->map_size_;
    octree_cfg_.volume_size_meter =  octree_cfg_.voxel_per_side * cfg_->voxel_size_;
    octree_cfg_.noise_factor = 0.02;
    octree_cfg_.logodds_lower = -5.;
    octree_cfg_.logodds_upper = 10.;
    octree_cfg_.zmin = cfg_->zmin_;
    octree_cfg_.zmax = cfg_->zmax_;
    octree_cfg_.correction_threshold = cfg_->correction_threshold_;

    octree_ = std::make_shared<se::Octree<SE_FIELD_TYPE>>();

    const auto vol = -octree_cfg_.volume_size_meter * 0.5;
    Eigen::Vector3f origin_position =
        Eigen::Vector3f(vol, vol, std::isfinite(octree_cfg_.zmax) ? octree_cfg_.zmax : vol);
    octree_->init(octree_cfg_.voxel_per_side, octree_cfg_.volume_size_meter, origin_position);
    offset_.block(0, 3, 3, 1) = -origin_position;

    client_id_ = cfg->client_id_;
    auto root_pose_id = uint64_t(client_id_) << BIT_SHIFTS;
    octree_->set_root_pose_id(root_pose_id);
}

fast_mapping_module::~fast_mapping_module()
{
    octree_->clear();
}

se::Octree<SE_FIELD_TYPE>& fast_mapping_module::get_octree()
{
    std::scoped_lock lock(octree_mutex_);
    return *octree_;
}

void fast_mapping_module::get_octree_block_list(std::vector<se::VoxelBlock<SE_FIELD_TYPE>*>& blocklist, bool active)
{
    std::scoped_lock lock(octree_mutex_);
    return octree_->getBlockList(blocklist, active);
}

const struct camera_intrinsics& fast_mapping_module::get_camera_intrinsics() const
{
    return *intrinsics_;
}

const struct se_cfg& fast_mapping_module::get_octree_cfg() const
{
    return octree_cfg_;
}

// Check if the world points are exceeding the Octree boundary
Eigen::Vector3i fast_mapping_module::check_map_boundary(const std::vector<Eigen::Vector3f>& points_world) const
{
    const float inverse_voxel_size = octree_->size() / octree_->dim();
    int x_dir = 0, y_dir = 0, z_dir = 0;
    for (const auto& point : points_world) {
        Eigen::Vector3i voxel_scaled = (point * inverse_voxel_size).array().floor().cast<int>();
        if (!within_map_boundary(octree_, voxel_scaled, x_dir, y_dir, z_dir)) break;
    }
    return Eigen::Vector3i(x_dir, y_dir, z_dir);
}

bool fast_mapping_module::correct_octree_from_loop_closure(const Eigen::Matrix4d& cam_pose_wc_before_correction,
                                                           const Eigen::Matrix4d& cam_pose_wc_after_correction,
                                                           const uint64_t pose_id)
{
    const double rotation_correction_min = 30.0 * M_PI / 180.0, rotation_correction_max = 330.0 * M_PI / 180;
    const double inverse_voxel_size = octree_->size() / octree_->dim();

    const double translation_correction = euclidian_distance(cam_pose_wc_after_correction, cam_pose_wc_before_correction);
    const int translation_correction_in_voxels = translation_correction * inverse_voxel_size;

    spdlog::debug("Pose {} correction: {}m, voxels {}", pose_id, translation_correction, translation_correction_in_voxels);
    if (translation_correction_in_voxels >= octree_cfg_.correction_threshold) return true;

    const Eigen::Matrix3d rot_before_correction = cam_pose_wc_before_correction.block(0, 0, 3, 3);
    const Eigen::Matrix3d rot_after_correction = cam_pose_wc_after_correction.block(0, 0, 3, 3);

    const auto RPY_before_correction = rot_before_correction.eulerAngles(0, 1, 2);
    const auto RPY_after_correction = rot_after_correction.eulerAngles(0, 1, 2);

    const double R = std::abs(RPY_after_correction(0) - RPY_before_correction(0));
    const double P = std::abs(RPY_after_correction(1) - RPY_before_correction(1));
    const double Y = std::abs(RPY_after_correction(2) - RPY_before_correction(2));

    if ((R >= rotation_correction_min && R <= rotation_correction_max) ||
        (P >= rotation_correction_min && P <= rotation_correction_max) ||
        (Y >= rotation_correction_min && Y <= rotation_correction_max)) {
        spdlog::info("Pose {} R: {} , P {}, Y {}", pose_id, R, P, Y);
        return true;
    }

    return false;
}

void fast_mapping_module::update_local_octree_from_server(std::shared_ptr<se::Octree<SE_FIELD_TYPE>> global_octree)
{
    spdlog::info("Updating octree with merged octree from server!");
    std::scoped_lock lock(octree_mutex_);
    octree_->clear();
    octree_ = global_octree;
    ++tracker_octree_merged_times_;

    // Update offset_ and dynamic_offset_ member variables correspondingly
    Eigen::Vector3f new_origin_position = octree_->get_origin_position();
    offset_.block(0, 3, 3, 1) = -new_origin_position;
    dynamic_offset_ = Eigen::Vector3f::Zero();
}

void fast_mapping_module::queue_map_message(univloc_msgs::MapConstPtr map_msg)
{
    mapmsg_queue_.force_push(map_msg);
}

void fast_mapping_module::construct_remapping_region(std::vector<double> vertexes)
{
    if (vertexes.empty()) return;

    struct fast_mapping::point_2d remapping_region_vertexes[4];
    for (unsigned int i = 0; i < 4; i++) {
         remapping_region_vertexes[i].x_ = cfg_->remapping_region_vertexes_[2 * i];
         remapping_region_vertexes[i].y_ = cfg_->remapping_region_vertexes_[2 * i + 1];
    }
    remapping_region_ = std::make_unique<fast_mapping::remapping_region>(remapping_region_vertexes);
}

void fast_mapping_module::run()
{
    timer_.setName("Fast Mapping Module");
    timer_.start();

    std::shared_ptr<univloc_tracker::ImageFrame> curr_frame;
    univloc_msgs::MapConstPtr map_msg;

    while(true)
    {
        if (mapmsg_queue_.try_pop(map_msg))
        {
            if (map_msg->is_request_octree)
            {
                spdlog::info("Server requested octree");

                univloc_msgs::Octree octree_msg;
                std::scoped_lock lock(octree_mutex_);
                octree_->toROSMsg(octree_msg);
                univloc_tracker::Client::get_instance().send_octree_to_server(octree_msg);
            }
            else if (map_msg->is_merged_octree && !map_msg->octree.empty())
            {
                spdlog::info("Received merged octree from server");

                auto global_octree = std::make_shared<se::Octree<SE_FIELD_TYPE>>();
                global_octree->fromROSMsgToOctree(map_msg->octree[0]);
                update_local_octree_from_server(global_octree);
                // tracker's octree has been replaced by merged octree from server, so stop skip processing frames
                set_skip_processing_frame(false);

                if (cfg_->mode_ == "remapping") {
                    spdlog::debug("Set flag to stop integrate frame when it is outside remappin region in remapping mode!");
                    coordinate_is_aligned_ = true;
                }
            }
        }

        timer_.startFirstProc("wait for a new frame");

        if(!reconstruction_queue_.wait_pop(curr_frame)) break;

        /*
           During map merge, for the map to be aligned, it needs to skip processing frames in fast mapping
           during the time interval from the tracker's local map is about to transform coordinate to
           tracker's octree map has been replaced by merged octree from server. Because in this time interval,
           octree's coordinate doesn't align with the local map's coordinate.
        */
        if (get_skip_processing_frame()) {
            timer_.endCycle();
            continue;
        }

        /*
            If the input remapping_region parameter is given and the tracker coordinate has been aligned with
            the pre-constructed coordinate (global map), then the Octree integration operation is avoided
            since it can better improve the efficency of tracker node and avoid modify the octree map outside
            the remapping region.
        */

        if (coordinate_is_aligned_ && remapping_region_) {
            Eigen::Matrix4d T_cw = *(curr_frame->maybe_pose);
            Eigen::Matrix4d T_wc = T_cw.inverse();
            if (!remapping_region_->within_remapping_region({T_wc(0, 3), T_wc(1, 3)})) {
                timer_.endCycle();
                continue;
            }
        }

        octree_integrate(curr_frame);

        timer_.endCycle();
    }
    timer_.finish();
    std::cout << timer_.result();
}

void fast_mapping_module::update_octree_from_server(std::vector<openvslam::data::keyframe*> keyfrms)
{
    std::scoped_lock lock(octree_mutex_);
    const float inverse_voxel_size = octree_->size() / octree_->dim();
    bool do_octree_correction = false;
    std::map<uint64_t, Eigen::Matrix4d> transforms;

    std::optional<Eigen::Matrix4d> coordinate_transform = coordinate_transform_;
    coordinate_transform_.reset();

    if (coordinate_transform) {
        spdlog::info(
            "The world coordinate of the reference map to the world coordinate of the map to be aligned is \n {}",
            *coordinate_transform);
    }

    for (const auto keyfrm : keyfrms) {
        if (!keyfrm || keyfrm->will_be_erased()) {
            continue;
        }

        auto pose_id = convert_timestamp_to_pose_id(client_id_, keyfrm->timestamp_);
        auto pose_id_timestamp = convert_pose_id_to_masked_timestamp(pose_id);

        // get the keyfrm pose in its world coordinate before correction
        Eigen::Matrix4d cam_pose_wc_before_correction = keyfrm->cam_pose_wc_before_replacing_;
        // get the keyfrm pose in its world coordinate after correction
        Eigen::Matrix4d cam_pose_wc_after_correction = keyfrm->get_cam_pose_inv();
        if (coordinate_transform) {
            // Twc_aligned = Tww_aligned_ref * Twc_ref
            cam_pose_wc_after_correction = (*coordinate_transform) * cam_pose_wc_after_correction;
        }

        Eigen::Matrix4d correction_transform = Eigen::Matrix4d::Identity();
        if (correct_octree_from_loop_closure(cam_pose_wc_before_correction, cam_pose_wc_after_correction, pose_id)) {
            // get the transform for 3D position update of landmark
            // P'w = T'cw.inverse() * Tcw * Pw = T'wc * Tcw * Pw
            correction_transform = cam_pose_wc_after_correction * cam_pose_wc_before_correction.inverse();
            correction_transform.topRightCorner<3, 1>() *= inverse_voxel_size;
            do_octree_correction = true;
        }
        transforms.insert(std::make_pair(pose_id_timestamp, correction_transform));
    }

    if (!do_octree_correction)
    {
        spdlog::info("The coordinate changes of loop closure/map merging (except coordinate alignment) is too small"
                     " to trigger octree reconstruction");
        return;
    }

    spdlog::info("Detected Loop closure or map merging: begin octree reconstruction");

    std::shared_ptr<se::Octree<SE_FIELD_TYPE>> corrected_octree = std::make_shared<se::Octree<SE_FIELD_TYPE>>();
    corrected_octree->init(octree_->size(), octree_->dim(), octree_->get_origin_position());
    const int size = corrected_octree->size();

    se::node_iterator<SE_FIELD_TYPE> it(*octree_);
    auto node = it.next();
    for (; node != nullptr; node = it.next()) {
        /*
            In larger maps, after loop closure/ map merge happens, not all the keyframes (newest 200)
            are updated and sent to the tracker. Therefore the octree might consist of
            voxels coming from poses which are not present. For most of the cases, we will
            keep those poses unchanged (identity matrix for transform); for nearby frames
            of updated keyframes, we will find the closest transform to update 3D location of voxels
        */
        auto [pose_id, trans] = find_closest_transform(transforms, node);
        const Eigen::Vector3d pos = se::keyops::decode(node->code_).cast<double>();
        const Eigen::Vector3i pos_after_correction = (trans * pos.homogeneous()).block<3, 1>(0, 0).cast<int>();

        auto is_voxel_valid = [size](const Eigen::Vector3i& v) {
            return ((v.x() >= 0) && (v.x() < size) && (v.y() >= 0) && (v.y() < size) && (v.z() >= 0) && (v.z() < size));
        };

        if (!is_voxel_valid(pos_after_correction)) continue;

        if (node->isLeaf()) {
            auto block = static_cast<se::VoxelBlock<SE_FIELD_TYPE>*>(node);
            const int max_blocks = se::VoxelBlock<SE_FIELD_TYPE>::sideSq * se::VoxelBlock<SE_FIELD_TYPE>::side;

            auto voxel_block = corrected_octree->insert(pos_after_correction(0), pos_after_correction(1),
                                                        pos_after_correction(2), pose_id);
            std::memcpy(voxel_block->getBlockRawPtr(), block->getBlockRawPtr(),
                        max_blocks * sizeof(*block->getBlockRawPtr()));
        } else {
            auto n = corrected_octree->insert(pos_after_correction(0), pos_after_correction(1), pos_after_correction(2),
                                              se::keyops::level(node->code_), pose_id);
            std::memcpy(n->value_, node->value_, sizeof(node->value_));
        }
    }

    octree_->clear();
    octree_ = corrected_octree;

    spdlog::info ("Loop closure or map merging: finish octree reconstrution");
}

void fast_mapping_module::octree_integrate(std::shared_ptr<univloc_tracker::ImageFrame> frame)
{
    cv::Mat depth = frame->image2;
    if (depth.empty()) return;

    std::optional<Eigen::Matrix4d> Tcw = frame->maybe_pose;
    if (!Tcw) return;

    Eigen::Matrix4d T_wc = Tcw->inverse();

    timer_.startNextProc("preprocess frame ");

    const auto depth_ptr = depth.ptr<float>();
    const auto scaled_intrinsics = get_scaled_intrinsics();
    const int scale_ratio = octree_cfg_.compute_size_ratio;
    const unsigned int out_w = depth.size().width / scale_ratio;
    const unsigned int out_h = depth.size().height / scale_ratio;
    const unsigned int width_multiply_ratio = depth.size().width * scale_ratio;

    // Extract points from depth image and scale to meters
    std::vector<float>points(out_w * out_h);
    for (unsigned int y = 0; y < out_h; y++)
    {
        unsigned int in_offset = width_multiply_ratio * y;
        unsigned int out_offset = out_w * y;
        for (unsigned int x = 0; x < out_w; x++)
        {
            float dist = depth_ptr[x * scale_ratio + in_offset];
            points[x + out_offset] = dist < octree_cfg_.depth_max_range ? dist : 0;
        }
    }

    // Convert to pointcloud
    Eigen::Matrix4f k_pose = T_wc.cast<float>() * scaled_intrinsics.invK4();
    Eigen::Vector3f offset = offset_.topRightCorner<3, 1>() + dynamic_offset_;
    int i = 0;

    if (!world_points_.empty()) world_points_.clear();

    for (unsigned int y = 0; y < out_h; y++)
    {
        for (unsigned int x = 0; x < out_w; x++)
        {
            auto depth = std::abs(points[i++]);
            if (depth == 0) continue;
            Eigen::Vector3f point = (k_pose * (Eigen::Vector3f(x, y, 1) * depth).homogeneous()).head<3>();
            world_points_.push_back(point + offset);
        }
    }

    // Add Octree offset to camera
    Eigen::Matrix4f octree_pose = T_wc.cast<float>() + offset_;
    octree_pose.topRightCorner<3, 1>() += dynamic_offset_;

    // check whether we need to extend the octree
    world_points_.push_back(octree_pose.topRightCorner<3, 1>());

    Eigen::Vector3i direction = check_map_boundary(world_points_);
    if (direction(0) != 0 || direction(1) != 0 || direction(2) != 0)
    {
        std::unique_lock lock(octree_mutex_);
        auto new_offset = octree_->expand(direction);
        auto root_pose_id = uint64_t(client_id_) << BIT_SHIFTS;
        octree_->set_root_pose_id(root_pose_id);
        lock.unlock();

        dynamic_offset_ += new_offset;
        Eigen::Vector3f origin_position = octree_->get_origin_position();
        origin_position -= new_offset;
        octree_->set_origin_position(origin_position);

        octree_pose.topRightCorner<3, 1>() += new_offset;
        for (auto& point : world_points_)
        {
            point += new_offset;
        }
    }
    world_points_.pop_back();

    // compute the max and min height with respect to the octree position
    float zmin = octree_cfg_.zmin + dynamic_offset_(2) + offset_(2, 3);
    float zmax = octree_cfg_.zmax + dynamic_offset_(2) + offset_(2, 3);

    Eigen::Matrix4f K = scaled_intrinsics.K4();
    float n = 6 * octree_cfg_.noise_factor; // band around the depth points

    auto pose_id = convert_timestamp_to_pose_id(client_id_, frame->timestamp);

    // integrate the pointcloud in the octree
    timer_.startNextProc("Allocate octree");
    std::unique_lock lock(octree_mutex_);
    octree_->allocate_points(world_points_, octree_pose, zmin, zmax, n, pose_id);
    lock.unlock();

    timer_.startNextProc("Update probabilities");

    // Update proabilities of each occupied Node/VoxelBlock
    Eigen::Vector2i computation_size = Eigen::Vector2i(out_w, out_h);
    float timestamp = (1.f / 30.f) * frame->timestamp;
    struct bfusion_update funct(points.data(), computation_size, octree_cfg_.noise_factor, timestamp, octree_cfg_.logodds_lower, octree_cfg_.logodds_upper);
    lock.lock();
    se::functor::projective_map(*octree_, zmin, zmax, octree_pose.inverse(), K, computation_size, funct);
    lock.unlock();

    spdlog::debug("Totally integrate {} frames in the octree map", id_);

    id_++;
}

void fast_mapping_module::set_coordinate_transform_matrix(const std::optional<Eigen::Matrix4d>& Tww_aligned_ref)
{
    coordinate_transform_ = Tww_aligned_ref;
}

std::pair<uint64_t, Eigen::Matrix4d> fast_mapping_module::find_closest_transform(
    const std::map<uint64_t, Eigen::Matrix4d>& transforms, const se::Node<SE_FIELD_TYPE>* node)
{
    Eigen::Matrix4d transform = Eigen::Matrix4d::Identity();
    auto pose_id_timestamp = convert_pose_id_to_masked_timestamp(node->pose_id_);
    // The node's timestamp is zero which indicates it didn't have corresponding frame.
    if (pose_id_timestamp == 0) {
        return std::make_pair(node->pose_id_, transform);
    }

    if (transforms.find(pose_id_timestamp) != transforms.end()) {
        return std::make_pair(node->pose_id_, transforms.at(pose_id_timestamp));
    }

    // If the timestamps in transforms and the node's timestamp are within 0.5s, we think they are reliable to update
    // the node of the octree.
    auto itup = transforms.lower_bound(pose_id_timestamp + uint64_t(OCTREE_CORRECT_THRESHOLD));
    auto itlow = transforms.lower_bound(pose_id_timestamp - uint64_t(OCTREE_CORRECT_THRESHOLD));

    // All the timestamps in transforms are at leaset 0.5s smaller or bigger than the node's timestamp.
    if (itlow == transforms.end() || itup == transforms.begin()) {
        return std::make_pair(node->pose_id_, transform);
    }

    // Find the transform corresponding to the timestamp which is the closest to the node's timestamp.
    auto nearest_it = itlow;
    uint64_t nearest_timestamp = std::llabs(nearest_it->first - pose_id_timestamp);
    for (auto it = itlow; it != itup; it++) {
        uint64_t nearest_timestamp_tmp = std::llabs(it->first - pose_id_timestamp);
        if (nearest_timestamp_tmp < nearest_timestamp) {
            nearest_timestamp = nearest_timestamp_tmp;
            nearest_it = it;
        }
    }
    if (nearest_timestamp > uint64_t(OCTREE_CORRECT_THRESHOLD)) {
        return std::make_pair(node->pose_id_, transform);
    }
    return std::make_pair(node->pose_id_, nearest_it->second);
}

void fast_mapping_module::set_skip_processing_frame(bool skip_frame)
{
    std::scoped_lock lock(mtx_skip_frame_);
    skip_frame_ = skip_frame;
}

bool fast_mapping_module::get_skip_processing_frame() const
{
    std::scoped_lock lock(mtx_skip_frame_);
    return skip_frame_;
}

unsigned int fast_mapping_module::get_tracker_octree_merged_times() { return tracker_octree_merged_times_; }

} // namespace fast_mapping

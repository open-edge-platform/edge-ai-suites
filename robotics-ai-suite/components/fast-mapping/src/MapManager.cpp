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

#include "MapManager.h"

#define ROS_INFO_THROTTLE(sec, ...) RCUTILS_LOG_INFO_THROTTLE(RCUTILS_STEADY_TIME, sec, __VA_ARGS__)

static std_msgs::msg::ColorRGBA scaledFloatToColor(float val)
{
    int idx;
    float s = 1.0;
    float v = 1.0;
    float x, y, z;
    std_msgs::msg::ColorRGBA clr;
    clr.a = 1.0;

    if (val < 0.)
    {
        val = 0.;
    }
    if (val > 1.)
    {
        val = 1.;
    }
    val *= 6;

    idx = floor(val);
    z = val - idx;
    if (!(idx & 1))
    {
      /* if i is even. */
      z = 1 - z;
    }
    x = v * (1 - s);
    y = v * (1 - s * z);

    switch (idx)
    {
    case 6:
    case 0:
        clr.r = v;
        clr.g = y;
        clr.b = x;
        break;
    case 1:
        clr.r = y;
        clr.g = v;
        clr.b = x;
        break;
    case 2:
        clr.r = x;
        clr.g = v;
        clr.b = y;
        break;
    case 3:
        clr.r = x;
        clr.g = y;
        clr.b = v;
        break;
    case 4:
      clr.r = y;
      clr.g = x;
      clr.b = v;
      break;
    case 5:
        clr.r = v;
        clr.g = x;
        clr.b = y;
        break;
    default:
        clr.r = 1;
        clr.g = 0.5;
        clr.b = 0.5;
        break;
    }

    return clr;
}

static void addColorToMarkerPoints(
    visualization_msgs::msg::Marker &marker,
    std::string color_axis,
    float color_axis_min,
    float color_axis_max)
{
    std::function<double(const geometry_msgs::msg::Point &)> get_value;
    if (color_axis == "x")
        get_value = [](const geometry_msgs::msg::Point &p) { return p.x; };
    else if (color_axis == "y")
        get_value = [](const geometry_msgs::msg::Point &p) { return p.y; };
    else if (color_axis == "z")
        get_value = [](const geometry_msgs::msg::Point &p) { return p.z; };
    else
        return;

    float min = color_axis_min;
    float range = color_axis_max - min;
    if (range <= 0)
    {
        // decide the value range with current data
        auto compare_value = [get_value](const geometry_msgs::msg::Point &a, const geometry_msgs::msg::Point &b) { return get_value(a) < get_value(b); };
        auto minmax = std::minmax_element(marker.points.begin(), marker.points.end(), compare_value);
        min = get_value(*minmax.first);
        range = get_value(*minmax.second) - min;
    }
    size_t size = marker.points.size();
    marker.colors.clear();
    marker.colors.reserve(size);
    for (size_t i = 0; i < size; ++i)
    {
        const auto color = scaledFloatToColor((get_value(marker.points[i]) - min) / range);
        marker.colors.push_back(color);
    }
}

void MapManager::clearMarkers()
{
    visualization_msgs::msg::MarkerArray msg;
    msg.markers.resize(1);
    msg.markers[0].action = visualization_msgs::msg::Marker::DELETEALL;
    msg.markers[0].header.frame_id = std::string(config_.p_map_frame_);
    pub_fused_map_->publish(msg);
    pub_occupancy_->publish(msg);
}

MapManager::MapManager(std::shared_ptr<OctoMap> octomap, struct NodeConfig& config)
    : Node("maps_publisher_node")
{
    octomap_ = octomap;
    config_ = config;

    grid_template_ = std::make_shared<nav_msgs::msg::OccupancyGrid>();
    nav_msgs::msg::OccupancyGrid &og = *grid_template_;
    se::Octree<SE_FIELD_TYPE>& octree = octomap_->getOctree();

    og.info.resolution =  octree.dim() / octree.size();
    og.info.width = og.info.height = octree.size();
    og.info.origin.position.x = -0.5 * og.info.width * og.info.resolution;
    og.info.origin.position.y = -0.5 * og.info.height * og.info.resolution;
    og.data.resize(og.info.width * og.info.height, -1);

    auto map_qos = rclcpp::QoS(rclcpp::KeepLast(1)).transient_local().reliable();
    pub_fused_map_ = create_publisher<visualization_msgs::msg::MarkerArray>("world/fused_map", map_qos);
    pub_occupancy_ = create_publisher<visualization_msgs::msg::MarkerArray>("world/occupancy", map_qos);
    pub_planar_map_ = create_publisher<nav_msgs::msg::OccupancyGrid>("world/map", map_qos);

    clearMarkers();
}

MapManager::~MapManager()
{
    try {
	    RCLCPP_INFO(get_logger(),"Exiting...cleaning the RVIZ markers");
	    clearMarkers();
    } catch (std::runtime_error& errmsg) {
	    std::cerr << errmsg.what() << std::endl;
    }
}

void MapManager::updateFreeOrUnknownSpace(std::shared_ptr<ImageFrame> currFrame)
{
    std::optional<Eigen::Matrix4d> Tcw = currFrame->maybe_pose;
    if (!Tcw) return;

    Eigen::Affine3f pose;
    pose.matrix() = Tcw->cast<float>();
    const Eigen::Vector3f camera = pose.translation();
    const auto intrinsics = octomap_->getScaledIntrinsics();
    const int width = intrinsics.width, height = intrinsics.height;

    nav_msgs::msg::OccupancyGrid &og = *grid_template_;
    const float resolution = og.info.resolution;
    const int og_width = og.info.width, og_height = og.info.height;
    const float p_robot_radius = config_.p_robot_radius_;

    // check the horizontal camera assumption
    // TODO: this implementation may be unnecessarily strict since it does not allow pitch
    {
        const float projection_tol = 0.1;
        Eigen::Vector3f camera_y_axis = pose.linear() * Eigen::Vector3f::UnitY();
        if (std::abs(camera_y_axis(0)) > projection_tol || std::abs(camera_y_axis(1)) > projection_tol)
            ROS_INFO_THROTTLE(1, "Non-horizontal camera orientation! Free space modeling may be insufficient.");
    }

    // mark the robot itself as free space
    {
        float r2 = p_robot_radius * p_robot_radius;
        float xlim = p_robot_radius;
        for (float x = -xlim; x <= xlim; x += resolution)
        {
            int vx = (int)((camera(0) + x - og.info.origin.position.x) / resolution);
            if (vx < 0)
                continue;
            if (vx > og_width)
                break;
            float ylim = std::sqrt(r2 - x * x);
            for (float y = -ylim; y <= ylim; y += resolution)
            {
                int vy = (int)((camera(1) + y - og.info.origin.position.y) / resolution);
                if (vy < 0)
                    continue;
                if (vy >= og_height)
                    break;
                const int index = vy * og_width + vx;
                if (index >= og_height * og_width)
                    break;
                og.data[index] = 0;
            }
        }
    }


    // find the furtherest point on each column of the depth image, which can
    // be used to model corresponding line in 2D under the horizontal camera
    // assumption
    std::vector<float> max_depth_d(width, 0);
    std::vector<int> max_depth_y(width);
    {
        const auto imagePtr = currFrame->image2.ptr<float>();
        int id = 0;
        for (int y = 0; y < height; y++)
        {
            for (int x = 0; x < width; x++)
            {
                float d = imagePtr[id++];
                if (d > max_depth_d[x])
                {
                    max_depth_d[x] = d;
                    max_depth_y[x] = y;
                }
            }
        }
    }
    {
        const Eigen::Matrix3f invK = intrinsics.invK();
        for (int x = 0; x < width; x++)
        {
            int y = max_depth_y[x];
            float d = max_depth_d[x];
            Eigen::Vector3f point = pose * (invK * Eigen::Vector3f(x + 0.5, y + 0.5, 1) * d);
            const float x0 = camera(0), y0 = camera(1);
            const float tan = (point(1) - camera(1)) / (point(0) - camera(0));
            if (std::abs(tan) <= 1.)
            {
                if (point(0) > camera(0))
                {
                    for (float x = camera(0) + p_robot_radius; x < point(0); x += resolution)
                    {
                        float y = y0 + (x - x0) * tan;
                        int vx = (int)((x - og.info.origin.position.x) / resolution);
                        int vy = (int)((y - og.info.origin.position.y) / resolution);
                        if (vx < 0 || vy < 0)
                            continue;
                        if (vx >= og_width || vy >= og_height)
                            break;
                        const int index = vy * og_width + vx;
                        if (index >= og_height * og_width)
                            break;
                        og.data[index] = 0;
                    }
                }
                else
                {
                    for (float x = camera(0) - p_robot_radius; x > point(0); x -= resolution)
                    {
                        float y = y0 + (x - x0) * tan;
                        int vx = (int)((x - og.info.origin.position.x) / resolution);
                        int vy = (int)((y - og.info.origin.position.y) / resolution);
                        if (vx >= og_width || vy >= og_height)
                            continue;
                        if (vx < 0 || vy < 0)
                            break;
                        og.data[(size_t)vy * og_width + vx] = 0;
                    }
                }
            }
            else
            {
                if (point(1) > camera(1))
                {
                    for (float y = camera(1) + p_robot_radius; y < point(1); y += resolution)
                    {
                        float x = x0 + (y - y0) / tan;
                        int vx = (int)((x - og.info.origin.position.x) / resolution);
                        int vy = (int)((y - og.info.origin.position.y) / resolution);
                        if (vx < 0 || vy < 0)
                            continue;
                        if (vx >= og_width || vy >= og_height)
                            break;
                        og.data[(size_t)vy * og_width + vx] = 0;
                    }
                }
                else
                {
                    for (float y = camera(1) - p_robot_radius; y > point(1); y -= resolution)
                    {
                        float x = x0 + (y - y0) / tan;
                        int vx = (int)((x - og.info.origin.position.x) / resolution);
                        int vy = (int)((y - og.info.origin.position.y) / resolution);
                        if (vx >= og_width || vy >= og_height)
                            continue;
                        if (vx < 0 || vy < 0)
                            break;
                        og.data[(size_t)vy * og_width + vx] = 0;
                    }
                }
            }
        }
    }
}

void MapManager::publish_volumetric_map()
{
    bool publishFused = pub_fused_map_->get_subscription_count() != 0;
    if (!publishFused) return;

    se::Octree<SE_FIELD_TYPE>& octree = octomap_->getOctree();
    const int block_side = octree.blockSide;
    const unsigned int octree_size = octree.size();
    const float octree_dim = octree.dim();
    const double voxel_dim = octree_dim / octree_size;

    auto set_marker_scale = [](visualization_msgs::msg::Marker &marker, double scale)
    {
        marker.scale.x = marker.scale.y = marker.scale.z = scale;
    };
    auto set_marker_color = [](visualization_msgs::msg::Marker &marker, float r, float g, float b, float a = 1.0)
    {
        marker.color.r = r; marker.color.g = g; marker.color.b = b; marker.color.a = a;
    };

    visualization_msgs::msg::Marker empty_marker;
    empty_marker.header.frame_id = std::string(config_.p_map_frame_);
    empty_marker.header.stamp = this->now();
    empty_marker.id = 0;
    empty_marker.type = visualization_msgs::msg::Marker::CUBE_LIST;
    empty_marker.action = visualization_msgs::msg::Marker::ADD;
    empty_marker.pose.orientation.w = 1.0;
    set_marker_scale(empty_marker, voxel_dim);
    set_marker_color(empty_marker, 1.0, 1.0, 1.0, 1.0); // white

    // Fused Markers
    visualization_msgs::msg::MarkerArray msg_fused;
    msg_fused.markers.resize(1, empty_marker);
    auto fused_marker = msg_fused.markers.begin();
    fused_marker->ns = "default";

    // Interate through the list of blocks
    std::vector<se::VoxelBlock<SE_FIELD_TYPE> *> blocks;
    octree.getBlockList(blocks, false);

    const Eigen::Vector3f ov = octomap_->getOriginPosition();
    geometry_msgs::msg::Point origin;
    origin.x = ov(0);
    origin.y = ov(1);
    origin.z = ov(2);

    for (const auto& block : blocks) {
        Eigen::Vector3i coords = block->coordinates();
        for (int i = 0; i < block_side; ++i) {
            for (int j = 0; j < block_side; ++j) {
                int vx = coords.x() + i;
                int vy = coords.y() + j;

                geometry_msgs::msg::Point center = origin;
                center.x += (vx + 0.5) * voxel_dim;
                center.y += (vy + 0.5) * voxel_dim;
                center.z += (coords.z() + 0.5) * voxel_dim;
                int dataid = i + j * block->side;
                if (dataid >= static_cast<int>(block->side * block->sideSq)) break;

                for (int k = 0; k < block_side; ++k, center.z += voxel_dim, dataid += block->sideSq) {
                    se::Node<SE_FIELD_TYPE>::value_type data = block->data(dataid);
                    const float prob = data.x;
                    if (prob > unknown_upper)
                    {
                        fused_marker->points.push_back(center);
                    }
                }
            }
        }
    }

    addColorToMarkerPoints(*fused_marker, config_.p_voxel_color_axis_,
        config_.p_voxel_color_axis_min_,
        config_.p_voxel_color_axis_max_);

    pub_fused_map_->publish(msg_fused);
}

void MapManager::publish_occupancy_map()
{
    bool publishOccupancy = pub_planar_map_->get_subscription_count() != 0;
    if (!publishOccupancy) return;

    se::Octree<SE_FIELD_TYPE>& octree = octomap_->getOctree();
    const unsigned int octree_size = octree.size();
    const float octree_dim = octree.dim();
    const double voxel_dim = octree_dim / octree_size;
    const int block_side = octree.blockSide;

    // Occupancy Grid Values
    static const int8_t occupied_prob = 100;
    static const int8_t free_prob = 0;
    static const int8_t unknown_prob = -1;
    static const int8_t max_node_size = 64;

    const Eigen::Vector3f ov = octomap_->getOriginPosition();
    geometry_msgs::msg::Point origin;
    origin.x = ov(0);
    origin.y = ov(1);
    origin.z = ov(2);

    // Allocate or expand the occupancy grid
    if (!grid_template_->data.size()) {

        nav_msgs::msg::OccupancyGrid &og = *grid_template_;
        og.info.resolution =  voxel_dim;
        og.info.width = og.info.height = octree_size;
        og.info.origin.position.x = origin.x;
        og.info.origin.position.y = origin.y;
        og.data.resize(og.info.width * og.info.height, unknown_prob);
    }
    if (octree_size != grid_template_->info.width) {

        auto grid_template_new = std::make_shared<nav_msgs::msg::OccupancyGrid>();
        nav_msgs::msg::OccupancyGrid &og = *grid_template_new;
        og.info.resolution = voxel_dim;
        og.info.width = og.info.height = octree_size;
        og.info.origin.position.x = origin.x;
        og.info.origin.position.y = origin.y;
        og.data.resize(og.info.width * og.info.height, unknown_prob);
        int dx = std::nearbyint((grid_template_->info.origin.position.x - og.info.origin.position.x) / og.info.resolution);
        int dy = std::nearbyint((grid_template_->info.origin.position.y - og.info.origin.position.y) / og.info.resolution);
        if (dx < 0 && dy < 0) {
            RCLCPP_ERROR(get_logger(), "Error: enlarged octree does not cover the old one");
            return;
        }
        for (unsigned int y = 0; y < grid_template_->info.height; ++y) {
            std::memcpy(&og.data[(y + dy) * og.info.width + dx],
                &grid_template_->data[y * grid_template_->info.width],
                grid_template_->info.width * sizeof(og.data[0]));
        }
        grid_template_ = grid_template_new;
    }

    nav_msgs::msg::OccupancyGrid og = *grid_template_;
    og.header.frame_id = std::string(config_.p_map_frame_);
    og.header.stamp = this->now();

    std::vector<se::VoxelBlock<SE_FIELD_TYPE> *> blocks;
    octree.getBlockList(blocks, false);

    // Iterate through the list of blocks and update occupied space.
    for (const auto &block : blocks) {
        auto coords = block->coordinates();
        for (int i = 0; i < block_side; ++i) {
            for (int j = 0; j < block_side; ++j) {
                int vx = coords.x() + i;
                int vy = coords.y() + j;
                if (vx < 0 || vy < 0) break;
                if (vx >= (int)og.info.width || vy >= (int)og.info.height) break;

                geometry_msgs::msg::Point center = origin;
                center.x += (vx + 0.5) * voxel_dim;
                center.y += (vy + 0.5) * voxel_dim;
                center.z += (coords.z() + 0.5) * voxel_dim;

                int dataid = i + j * block->side;
                if (dataid >= static_cast<int>(block->side * block->sideSq)) break;

                for (int k = 0; k < block_side; ++k, center.z += voxel_dim, dataid += block->sideSq) {
                    if (center.z >= config_.p_projection_max_z_ || center.z <= config_.p_projection_min_z_) continue;

                    const size_t index = vy * og.info.width + vx;
                    if (index >= og.data.size()) break;

                    auto &ogdata = og.data[index];

                    const float prob = block->data(dataid).x;
                    if (prob > unknown_upper) ogdata = occupied_prob; // Occupied
                    else if (prob < unknown_lower) {
                        if (ogdata == unknown_prob) ogdata = free_prob; // if unknown, mark as free space
                    }
                }
            }
        }
    }

    const int leaves_level = octree.max_node_level() + 1;
    std::vector<int> node_side(leaves_level, block_side);
    for (auto it = node_side.rbegin() + 1; it != node_side.rend(); ++it) {
        *it = *(it - 1) * 2;
    }

    std::vector<float> node_dim(leaves_level, voxel_dim);
    for (auto it = node_dim.rbegin() + 1; it != node_dim.rend(); ++it) {
        *it = *(it - 1) * 2;
    }

    // Iterate though the list of nodes and update the free space of the occupancy map
    std::vector<se::LeafNode<SE_FIELD_TYPE>> nodes;
    auto filter = [](se::Node<SE_FIELD_TYPE>::value_type data)->bool { return data.x < 0; };
    octree.getLeafNodeList(nodes, filter);

    for (const auto& node : nodes) {
        int side = node_side[node.level - 1];
        if (side > max_node_size) continue; // If node side is too coarse, skip it.

        geometry_msgs::msg::Point center = origin;
        double half_dim = node_dim[node.level] * 0.5;
        center.x += node.coordinates(0) * voxel_dim + half_dim;
        center.y += node.coordinates(1) * voxel_dim + half_dim;
        center.z += node.coordinates(2) * voxel_dim + half_dim;

        for (int i = 0; i < side; i++) {
            for (int j = 0; j < side; j++) {
                int vx = node.coordinates(0) + i;
                int vy = node.coordinates(1) + j;
                if (vx < 0 || vy < 0) continue;
                if (vx >= (int)og.info.width || vy >= (int)og.info.height) break;
                const size_t index = vy * og.info.width + vx;
                if(index >= og.data.size()) break;
                auto &ogdata = og.data[index];
                if (ogdata == unknown_prob) ogdata = free_prob; // If unknown, mark as free space
            }
        }
    }
    pub_planar_map_->publish(og);
}

void MapManager::publish_maps(std::shared_ptr<ImageFrame> currFrame)
{
    publish_volumetric_map();
    publish_occupancy_map();
    if(0) updateFreeOrUnknownSpace(currFrame);
}

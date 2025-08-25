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

#pragma once

#include <string>
#include <stdexcept>

#include <pcl/io/vtk_lib_io.h> // for loadPCDFile

#include <pcl/features/fpfh.h>
#include <pcl/features/normal_3d.h>

#include <pcl/filters/voxel_grid.h>
#include <pcl/filters/passthrough.h>

#include <pcl/registration/sample_consensus_prerejective.h>
#include <pcl/filters/statistical_outlier_removal.h>
#include <pcl/registration/ia_ransac.h>
#include <pcl/registration/icp.h>
#include <pcl/io/pcd_io.h>
#include <rclcpp/rclcpp.hpp>
#include <pcl/features/normal_3d_omp.h>
#include <pcl/features/fpfh_omp.h>
#include <omp.h>

#include <pcl/point_cloud.h>
#include <pcl/point_types.h>

typedef pcl::PointXYZ PointT;
//typedef pcl::PointXYZRGB PointT;
//typedef pcl::PointXYZRGBNormal PointT;
//typedef pcl::PointNormal PointT;

namespace RVC 
{
struct MatchSettings
{
    float downsampling = 0.004f;//0.005f;
    float downsample_clouds = 0.004f;//0.006f;//0.005f;

    float normal_search_radius = 0.04f;//0.07808f;
    float fpfh_search_radius = 0.025f;//0.009f;//0.008020f;
    float stddev_mul_threshold = 4.0f;
    float z_threshold = 0.5f;//CH 0.8f;//KA 0.667491f;

    float inlier_fraction = 0.4f;//0.627f;
    float similarity_threshold = 0.9f;//0.8f;
    float max_corresp_randomness = 8.0f;//5.0f;
    // max corr distance is recommended to be 2.5 multiple of downsample
    float max_corresp_distance = 0.01f;//0.015f;
    size_t max_iterations = 30000;//50000;
    size_t num_samples = 3;

    float icp_max_corresp_distance = 0.1f;
    float icp_xform_epsilon = 1e-9f;
    float icp_fitness_epsilon = 6e-6f;
    size_t icp_max_iterations = 50;
};

struct MatchResult
{
    // Whether a match was successful
    //
    // If false, none of the other members are valid.
    bool matched;

    float ransac_score;
    float icp_score;

    Eigen::Vector3f position;
    Eigen::Matrix4f xform;
    pcl::PointCloud<PointT>::Ptr registered_cloud;
};

class ObjectMatcher
{
private:
    std::string m_name;
    MatchSettings m_config;
    pcl::PointCloud<PointT>::Ptr m_points;
    pcl::PointCloud<pcl::FPFHSignature33>::Ptr m_signature;

public:
    /**
     * @brief Create an ObjectMatcher by loading a point-cloud from the filesystem.
     *
     * The passed path must be a filesystem path to a `.pcd` point-cloud file.
     */
    ObjectMatcher(
        const std::string name, const std::string & load_path,
        MatchSettings settings);

    /**
     * @brief Create an ObjectMatcher from an in-memory point-cloud.
     */
    ObjectMatcher(
        const std::string name, pcl::PointCloud<PointT>::Ptr points,
        MatchSettings settings);

    /**
     * @brief Try to match a given point cloud against the one stored in this object.
     */
    MatchResult match(pcl::PointCloud<PointT>::Ptr cloud);
    /**
     * @brief compute features of the pointclouds
     *
     * @param points input pointcloud
     * @param config configuration Matching settings
     * @param out
     */
    void compute_fpfh_features(
        pcl::PointCloud<PointT>::ConstPtr points,
        const MatchSettings & config,
        pcl::PointCloud<pcl::FPFHSignature33> & out);

};
}

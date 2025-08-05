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

#include "matcher.hpp"

using namespace RVC;

// this may seem like unnecessary indirection, but returning the cloud by value
// here lets us implement ObjectMatcher(filename) using C++11 ctor delegation
// instead of replicating matcher-initalization logic
pcl::PointCloud<PointT>::Ptr load_pcd_file(const std::string & path)
{
    pcl::PointCloud<PointT>::Ptr cloud = std::make_shared<pcl::PointCloud<PointT>>();

    if (pcl::io::loadPCDFile<PointT>(path, *cloud) != 0)
    {
        throw new std::runtime_error("Failed to load point-cloud file");
    }

    RCLCPP_INFO(rclcpp::get_logger("PCL"), "loading %s", path.c_str());
    return cloud;
}

// TODO this entire blocks of computing normal and fast point feature
// histograms is part of ros-perception/perception_pcl
// At the moment, keeping here as it is but it makes sense to change
// to leverage that and reduce technical debt
void ObjectMatcher::compute_fpfh_features(
    pcl::PointCloud<PointT>::ConstPtr points,
    const MatchSettings & config,
    pcl::PointCloud<pcl::FPFHSignature33> & out)
{
    auto point_normals = std::make_shared<pcl::PointCloud<pcl::Normal>>();
    auto tree = std::make_shared<pcl::search::KdTree<PointT>>();

    pcl::NormalEstimationOMP<PointT, pcl::Normal> est_normal;
    pcl::FPFHEstimationOMP<PointT, pcl::Normal, pcl::FPFHSignature33> est_sig;

    // estimate normals at each point
    //est_normal.setNumberOfThreads(omp_get_num_procs());
    est_normal.setNumberOfThreads(4);

    est_normal.setSearchMethod(tree);
    est_normal.setRadiusSearch(config.normal_search_radius);
    est_normal.setInputCloud(points);
    est_normal.compute(*point_normals);

    // compute shape descriptor
    //est_sig.setNumberOfThreads(omp_get_num_procs());
    est_sig.setNumberOfThreads(4);
    est_sig.setInputCloud(points);
    est_sig.setInputNormals(point_normals);
    est_sig.setSearchMethod(tree);
    est_sig.setRadiusSearch(config.fpfh_search_radius);
    est_sig.compute(out);
}

ObjectMatcher::ObjectMatcher(
    const std::string name,
    const std::string & load_path,
    MatchSettings settings
)
  : ObjectMatcher(name, load_pcd_file(load_path), std::move(settings))
{
    RCLCPP_INFO(rclcpp::get_logger("matcher"), "constructor 1");
}

ObjectMatcher::ObjectMatcher(
    const std::string name,
    pcl::PointCloud<PointT>::Ptr points,
    MatchSettings settings
)
  : m_name(name),
    m_config(settings),
    m_points(std::move(points)),
    m_signature(std::make_shared<pcl::PointCloud<pcl::FPFHSignature33>>())
{
    RCLCPP_INFO(rclcpp::get_logger("matcher"), "constructor 2");

    // Compute matching features. For speed, first downsample the point cloud
    // using a voxel grid.
    if (m_config.downsampling > 0)
    {
        pcl::VoxelGrid<PointT> voxels;
        voxels.setInputCloud(m_points);
        // use same resolution on X, Y, Z
        voxels.setLeafSize(
            m_config.downsampling,
            m_config.downsampling,
            m_config.downsampling);
        voxels.filter(*m_points);
    }

    RCLCPP_INFO(rclcpp::get_logger("matcher"), "compute_fpfh_features");
    // precompute FPFH features for later matches
    compute_fpfh_features(m_points, m_config, *m_signature);
}

MatchResult ObjectMatcher::match(pcl::PointCloud<PointT>::Ptr input_rs_cloud)
{
    MatchResult out = {};
    auto downsampled_rs_cloud = std::make_shared<pcl::PointCloud<PointT>>();
    auto filtered_rs_cloud = std::make_shared<pcl::PointCloud<PointT>>();
    auto thresholded_rs_cloud = std::make_shared<pcl::PointCloud<PointT>>();


    // downsample if needed
    if (m_config.downsample_clouds > 0)
    {
        pcl::VoxelGrid<PointT> voxels;
        voxels.setInputCloud(input_rs_cloud);
        voxels.setLeafSize(
            m_config.downsample_clouds,
            m_config.downsample_clouds,
            m_config.downsample_clouds);
        voxels.filter(*downsampled_rs_cloud);
    }

    if (downsampled_rs_cloud->size() == 0)
    {
        MatchResult out = {};
        out.position << 0.0, 0.0, 0.0;
        out.xform << 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0;
        out.matched = false;
        RCLCPP_INFO(rclcpp::get_logger("matcher"), "Downsample filter output size 0 for %s", m_name.c_str() );
        return out;
    }


    if (m_config.stddev_mul_threshold > 0.0)
    {
        // remove statistical outliers in input cloud
        pcl::StatisticalOutlierRemoval<PointT> filter;
        filter.setInputCloud(downsampled_rs_cloud);
        filter.setMeanK(50);
        filter.setStddevMulThresh(m_config.stddev_mul_threshold);
        filter.filter(*filtered_rs_cloud);
    }
    else
    {
        filtered_rs_cloud = downsampled_rs_cloud;
        //RCLCPP_INFO(rclcpp::get_logger("matcher"), "stddev_mul_threshold 0 for %s, size %ld", m_name.c_str(),filtered_rs_cloud->size() );
    }

    // remove Z outliers
    if (m_config.z_threshold > 0.0)
    {
        pcl::PassThrough<PointT> filter;
        filter.setInputCloud(filtered_rs_cloud);
        filter.setFilterFieldName("z");
        filter.setFilterLimits(0.0, m_config.z_threshold);
        filter.filter(*thresholded_rs_cloud);
    }
    else
    {
        thresholded_rs_cloud = filtered_rs_cloud;
        //RCLCPP_INFO(rclcpp::get_logger("matcher"), "z_threshold 0 for %s, size %ld", m_name.c_str(), thresholded_rs_cloud->size() );
    }


    if (thresholded_rs_cloud->size() == 0)
    {
        MatchResult out = {};
        out.position << 0.0, 0.0, 0.0;
        out.xform << 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0;
        out.matched = false;
        RCLCPP_INFO(rclcpp::get_logger("matcher"), "Z filter output size 0  for %s", m_name.c_str() );

        return out;
    }


    // compute input's features and try to do the initial match
    auto input_sig = std::make_shared<pcl::PointCloud<pcl::FPFHSignature33>>();
    compute_fpfh_features(thresholded_rs_cloud, m_config, *input_sig);
    //std::cout << "Source points after fpfh " << m_points->size()  << std::endl;
    //std::cout << "Source feature points after fpfh " << m_signature->size()  << std::endl;
    //std::cout << "Target points after fpfh " << thresholded_rs_cloud->size()  << std::endl;
    //std::cout << "Target feature points after fpfh " << input_sig->size()  << std::endl;


    pcl::SampleConsensusPrerejective<PointT, PointT, pcl::FPFHSignature33> sac_ia;
    sac_ia.setInlierFraction(m_config.inlier_fraction);
    sac_ia.setSimilarityThreshold(m_config.similarity_threshold);

    sac_ia.setCorrespondenceRandomness(
        std::min(
            m_config.max_corresp_randomness,
            (float)thresholded_rs_cloud->size()));
    sac_ia.setMaximumIterations(m_config.max_iterations);
    sac_ia.setNumberOfSamples(m_config.num_samples);
    //sac_ia.setMaxCorrespondenceDistance(m_config.max_corresp_distance);
    sac_ia.setMaxCorrespondenceDistance(2.5f * m_config.downsample_clouds);

    sac_ia.setInputSource(m_points);
    sac_ia.setSourceFeatures(m_signature);

    sac_ia.setInputTarget(thresholded_rs_cloud);
    sac_ia.setTargetFeatures(input_sig);


    // TODO: provide a way to use the previous transform
    auto aligned_cloud = std::make_shared<pcl::PointCloud<PointT>>();
    sac_ia.align(*aligned_cloud);

    float ransac_score = sac_ia.getFitnessScore();

    if (!sac_ia.hasConverged())
    {
        MatchResult out = {};
        out.position << 0.0, 0.0, 0.0;
        out.xform << 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0;
        out.matched = false;
        RCLCPP_DEBUG_STREAM(
            rclcpp::get_logger("matcher"), "Using RANSAC not converged for " << m_name
                                                                             << __FUNCTION__ << ":" << __LINE__);

        return out;
    }

    auto xform = sac_ia.getFinalTransformation();

    auto refined_cloud = std::make_shared<pcl::PointCloud<PointT>>();
    // improve RANSAC guess using ICP (Iterative Closest Point)
    pcl::IterativeClosestPoint<PointT, PointT> icp;
    icp.setMaxCorrespondenceDistance(m_config.icp_max_corresp_distance);
    icp.setMaximumIterations(m_config.icp_max_iterations);
    icp.setTransformationEpsilon(m_config.icp_xform_epsilon);
    icp.setEuclideanFitnessEpsilon(m_config.icp_fitness_epsilon);
    icp.setInputSource(aligned_cloud);
    icp.setInputTarget(thresholded_rs_cloud);
    icp.align(*refined_cloud);

    float icp_score = icp.getFitnessScore();

    if (!icp.hasConverged())
    {
        MatchResult out = {};
        out.position << 0.0, 0.0, 0.0;
        out.xform << 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0;
        out.matched = false;
        RCLCPP_INFO_STREAM(
            rclcpp::get_logger("matcher"), "Using ICP not converged for " << m_name <<
                __FUNCTION__ << ":" << __LINE__);
        return out;
    }

    // combine the previous transform matrix with the one ICP worked out
    //
    // the old transform happens first, then the ICP transform happens
    xform = icp.getFinalTransformation() * xform;

    // Compute centroid from PCL
    Eigen::Vector4f centroid;
    pcl::compute3DCentroid(*refined_cloud, centroid);
    out.position = centroid.block<3, 1>(0, 0);

    // format result and return
    out.matched = true;
    //out.xform = xform.cast<double>();
    out.xform = xform;
    out.ransac_score = ransac_score;
    out.icp_score = icp_score;
    //*reg_cloud += *cloud;
    out.registered_cloud = refined_cloud;
    //out.registered_cloud = cloud;
    return out;
}

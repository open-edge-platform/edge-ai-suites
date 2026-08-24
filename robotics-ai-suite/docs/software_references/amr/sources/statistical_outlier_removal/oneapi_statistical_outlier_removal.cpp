// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/filters/statistical_outlier_removal.h>
#include <pcl/point_types.h>
#include <pcl/point_cloud.h>
#include <pcl/io/pcd_io.h>


using namespace pcl::oneapi;

int main (int argc, char** argv)
{
  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud( new pcl::PointCloud<pcl::PointXYZ>() );
  // Fill in the cloud data
  pcl::io::loadPCDFile ("table_scene_lms400.pcd", *cloud);

  std::cerr << "Cloud before filtering: " << std::endl;
  std::cerr << *cloud << std::endl;

  pcl::PointCloud<pcl::PointXYZ>::Ptr oneapi_cloud_filtered (new pcl::PointCloud<pcl::PointXYZ>);

  // Create the filtering object
  pcl::oneapi::StatisticalOutlierRemoval<pcl::PointXYZ> oneapi_sor;
  oneapi_sor.setInputCloud(cloud);
  oneapi_sor.setMeanK(50);
  oneapi_sor.setStddevMulThresh(1.0);
  oneapi_sor.filter(*oneapi_cloud_filtered);

  std::cerr << "Cloud after filtering: " << std::endl;
  std::cerr << *oneapi_cloud_filtered << std::endl;

  pcl::PCDWriter writer;
  writer.write<pcl::PointXYZ> ("table_scene_lms400_inliers.pcd", *oneapi_cloud_filtered, false);

  oneapi_sor.setNegative (true);
  oneapi_sor.filter (*oneapi_cloud_filtered);
  writer.write<pcl::PointXYZ> ("table_scene_lms400_outliers.pcd", *oneapi_cloud_filtered, false);

  return (0);
}


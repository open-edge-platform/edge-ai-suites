// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/filters/voxel_grid.h>
#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>
#include <pcl/point_cloud.h>


int main (int argc, char** argv)
{
  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  // Read Point Cloud
  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_( new pcl::PointCloud<pcl::PointXYZ>() );
  int result = pcl::io::loadPCDFile("table_scene_lms400.pcd", *cloud_);
  if (result != 0)
  {
    pcl::console::print_info ("Load pcd file failed.\n");
    return result;
  }

  // Prepare Point Cloud Memory (output)
  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_filtered_( new pcl::PointCloud<pcl::PointXYZ>() );

  // GPU calculate
  pcl::oneapi::VoxelGrid<pcl::PointXYZ> vg_oneapi;
  vg_oneapi.setInputCloud(cloud_);
  float leafsize= 0.005f;
  vg_oneapi.setLeafSize (leafsize, leafsize, leafsize);
  vg_oneapi.filter(*cloud_filtered_);

  // print log
  std::cout << "[oneapi voxel grid] PointCloud before filtering: " << cloud_->size() << std::endl;
  std::cout << "[oneapi voxel grid] PointCloud after filtering: " << cloud_filtered_->size() << std::endl;
}

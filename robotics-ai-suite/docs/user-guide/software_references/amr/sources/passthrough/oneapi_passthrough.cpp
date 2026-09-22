// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/filters/passthrough.h>
#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>
#include <pcl/point_cloud.h>


int main (int argc, char** argv)
{

  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  // Read Point Cloud
  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_( new pcl::PointCloud<pcl::PointXYZ>() );
  int result = pcl::io::loadPCDFile("using_kinfu_large_scale_output.pcd", *cloud_);
  if (result != 0)
  {
    pcl::console::print_info ("Load pcd file failed.\n");
    return result;
  }

  // Prepare Point Cloud Memory (output)
  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_filtered_( new pcl::PointCloud<pcl::PointXYZ>() );

  // GPU calculate
  pcl::oneapi::PassThrough<pcl::PointXYZ> ps;
  ps.setInputCloud(cloud_);
  ps.setFilterFieldName ("z");
  ps.setFilterLimits (0.0, 1.0);
  ps.filter(*cloud_filtered_);

  // print log
  std::cout << "[oneapi passthrough] PointCloud before filtering: " << cloud_->size() << std::endl;
  std::cout << "[oneapi passthrough] PointCloud after filtering: " << cloud_filtered_->size() << std::endl;
}

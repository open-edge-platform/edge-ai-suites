// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/surface/mls.h>
#include <pcl/oneapi/search/kdtree.h>
#include <pcl/point_types.h>
#include <pcl/io/pcd_io.h>


using namespace pcl::oneapi;

int main (int argc, char** argv)
{
  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_ptr( new pcl::PointCloud<pcl::PointXYZ>() );

  // Load bun0.pcd
  pcl::io::loadPCDFile ("bun0.pcd", *cloud_ptr);

  pcl::oneapi::KdTreeFLANN<pcl::PointXYZ>::Ptr tree (new pcl::oneapi::KdTreeFLANN<pcl::PointXYZ>);

  // Output has the PointNormal type in order to store the normals calculated by MLS
  pcl::PointCloud<pcl::PointNormal> mls_points;

  // Init object (second point type is for the normals, even if unused)
  pcl::oneapi::MovingLeastSquares<pcl::PointXYZ, pcl::PointNormal> mls;

  mls.setComputeNormals (true);

  // Set parameters
  mls.setInputCloud (cloud_ptr);
  mls.setPolynomialOrder (2);
  mls.setSearchMethod (tree);
  mls.setSearchRadius (0.03);

  // Reconstruct
  mls.process (mls_points);

  // Save output
  pcl::io::savePCDFile ("bun0-mls.pcd", mls_points);
}


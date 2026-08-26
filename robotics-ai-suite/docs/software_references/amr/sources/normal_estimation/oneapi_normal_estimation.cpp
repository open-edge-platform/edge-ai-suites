// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/io/pcd_io.h>
#include <pcl/oneapi/features/normal_3d.h>
#include <pcl/oneapi/kdtree/kdtree_flann.h>
#include <pcl/oneapi/point_cloud.h>

int main (int argc, char** argv)
{
  int k = 10;
  float radius = 0.01;

  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  // load point cloud
  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_ptr( new pcl::PointCloud<pcl::PointXYZ>() );

  int result = pcl::io::loadPCDFile("bun0.pcd", *cloud_ptr);
  if (result != 0)
  {
    pcl::console::print_info ("Load pcd file failed.\n");
    return result;
  }

  // estimate normals with knn search
  pcl::oneapi::NormalEstimation<pcl::PointXYZ, pcl::Normal> ne;
  ne.setSearchMethod (pcl::oneapi::KdTreeFLANN<pcl::PointXYZ>::Ptr (new pcl::oneapi::KdTreeFLANN<pcl::PointXYZ>));
  ne.setInputCloud(cloud_ptr);
  ne.setKSearch(k);

  // save normal estimation to CPU memory point cloud
  pcl::PointCloud<pcl::Normal>::Ptr normals_knn(new pcl::PointCloud<pcl::Normal>);
  ne.compute(*normals_knn);

  std::cout << "normals_knn.size (): " << normals_knn->size () << std::endl;

  // estimate normals with radius search
  ne.setSearchMethod (pcl::oneapi::KdTreeFLANN<pcl::PointXYZ>::Ptr (new pcl::oneapi::KdTreeFLANN<pcl::PointXYZ>));
  ne.setInputCloud(cloud_ptr);
  ne.setRadiusSearch(radius);
  ne.setKSearch(0);

  // save normal estimation output to device shared memory point cloud
  pcl::oneapi::PointCloudDev<pcl::Normal>::Ptr normals_radius(new pcl::oneapi::PointCloudDev<pcl::Normal>) ;
  ne.compute(*normals_radius);

  std::cout << "normals_radius.size (): " << normals_radius->size () << std::endl;

  return 0;
}

// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/search/kdtree.h> // for KdTree
#include <pcl/point_cloud.h>

#include <vector>
#include <iostream>

int
main (int argc, char** argv)
{
  srand (time (NULL));

  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud (new pcl::PointCloud<pcl::PointXYZ>);

  // Generate pointcloud data
  cloud->width = 1000;
  cloud->height = 1;
  cloud->points.resize (cloud->width * cloud->height);

  for (std::size_t i = 0; i < cloud->size (); ++i)
  {
    (*cloud)[i].x = static_cast<float>(1024.0f * rand () / (RAND_MAX + 1.0));
    (*cloud)[i].y = static_cast<float>(1024.0f * rand () / (RAND_MAX + 1.0));
    (*cloud)[i].z = static_cast<float>(1024.0f * rand () / (RAND_MAX + 1.0));
  }

  pcl::PointCloud<pcl::PointXYZ>::Ptr searchPoints (new pcl::PointCloud<pcl::PointXYZ>);

  // Generate pointcloud data
  searchPoints->width = 3;
  searchPoints->height = 1;
  searchPoints->points.resize (searchPoints->width * searchPoints->height);

  for (std::size_t i = 0; i < searchPoints->size (); ++i)
  {
    (*searchPoints)[i].x = static_cast<float>(1024.0f * rand () / (RAND_MAX + 1.0));
    (*searchPoints)[i].y = static_cast<float>(1024.0f * rand () / (RAND_MAX + 1.0));
    (*searchPoints)[i].z = static_cast<float>(1024.0f * rand () / (RAND_MAX + 1.0));
  }

  pcl::oneapi::search::KdTree<pcl::PointXYZ> kdtree;
  kdtree.setInputCloud (cloud);

  // K nearest neighbor search
  int K = 5;

  std::vector< std::vector< float > > pointsSquaredDistance (searchPoints->size()) ;
  std::vector< pcl::Indices > pointsIdxKnnSearch (searchPoints->size());

  kdtree.nearestKSearch(*searchPoints, K, pointsIdxKnnSearch, pointsSquaredDistance);

  for (std::size_t j = 0; j < pointsIdxKnnSearch.size(); ++j)
  {
    std::cout << "K=" << K << " neighbors from (" << (*searchPoints)[j].x << ","
                                                 << (*searchPoints)[j].y << ","
                                                 << (*searchPoints)[j].z << ")" << std::endl;
    for (std::size_t i = 0; i < pointsIdxKnnSearch.at(j).size(); ++i)
    {
      std::cout << "    "  <<   (*cloud)[ pointsIdxKnnSearch.at(j)[i] ].x
                << " " <<  (*cloud)[ pointsIdxKnnSearch.at(j)[i] ].y
                << " " <<  (*cloud)[ pointsIdxKnnSearch.at(j)[i] ].z
                << " (squared distance: " << pointsSquaredDistance.at(j)[i] << ")" << std::endl;
    }
  }

  // Neighbors within radius search
  float radius = 100.f;

  std::vector< std::vector< float > > pointsRadiusSquaredDistance (searchPoints->size()) ;
  std::vector< pcl::Indices > pointsIdxRadiusSearch (searchPoints->size());

  kdtree.radiusSearch(*searchPoints, radius, pointsIdxRadiusSearch,  pointsRadiusSquaredDistance, 10);

  for (std::size_t j = 0; j < pointsIdxRadiusSearch.size(); ++j)
  {
    std::cout << "Kdtree Radius Search Radius=" << radius << " neighbors from (" << (*searchPoints)[j].x << ","
                                                 << (*searchPoints)[j].y << ","
                                                 << (*searchPoints)[j].z << ")" << std::endl;
    for (std::size_t i = 0; i < pointsIdxRadiusSearch.at(j).size(); ++i)
    {
      std::cout << "    "  <<   (*cloud)[ pointsIdxRadiusSearch.at(j)[i] ].x
                << " " <<  (*cloud)[ pointsIdxRadiusSearch.at(j)[i] ].y
                << " " <<  (*cloud)[ pointsIdxRadiusSearch.at(j)[i] ].z
                << " (squared distance: " << pointsRadiusSquaredDistance.at(j)[i] << ")" << std::endl;
    }
  }

  // Fixed radius search
  // Only support radius use to build the table

  std::vector<int> pointsFixedRadiusIdx;
  std::vector<float> pointsFixedRadiusSquaredDistance;
  std::vector<int> pointsFixedRadiusSplit;

  kdtree.setInputCloud(cloud, radius);

  kdtree.fixedRadiusSearch(searchPoints, pointsFixedRadiusIdx, pointsFixedRadiusSquaredDistance,
      pointsFixedRadiusSplit);

  for (std::size_t j = 0; j < pointsFixedRadiusSplit.size() - 1; ++j)
  {
    std::cout << "Fixed Radius Search Radius=" << radius << " neighbors from (" << (*searchPoints)[j].x << ","
                                                 << (*searchPoints)[j].y << ","
                                                 << (*searchPoints)[j].z << ")" << std::endl;

    std::size_t cur_idx = pointsFixedRadiusSplit[j];
    std::size_t elements = pointsFixedRadiusSplit[j+1] - cur_idx;
    for (std::size_t i = 0; i < elements; ++i)
    {
      std::cout << "    "  <<   (*cloud)[pointsFixedRadiusIdx.at(cur_idx+i)].x
                << " " <<  (*cloud)[ pointsFixedRadiusIdx.at(cur_idx+i)].y
                << " " <<  (*cloud)[ pointsFixedRadiusIdx.at(cur_idx+i)].z
                << " (squared distance: " << pointsFixedRadiusSquaredDistance.at(cur_idx+i) << ")" << std::endl;

    }
  }

  return 0;
}

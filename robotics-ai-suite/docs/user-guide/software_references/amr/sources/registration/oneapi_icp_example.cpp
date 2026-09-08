// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/registration/icp.h>
#include <pcl/console/parse.h>
#include <pcl/point_types.h>
#include <pcl/point_cloud.h>
#include <pcl/point_representation.h>
#include <pcl/io/pcd_io.h>


using namespace pcl;
using namespace pcl::io;
using namespace pcl::console;

/* ---[ */
int
main (int argc, char** argv)
{
  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  // Load the files
  PointCloud<PointXYZ>::Ptr src, tgt;
  src.reset (new PointCloud<PointXYZ>);
  tgt.reset (new PointCloud<PointXYZ>);
  if (loadPCDFile ("test_P.pcd", *src) == -1 || loadPCDFile ("test_Q.pcd", *tgt) == -1)
  {
    print_error ("Error reading the input files!\n");
    return (-1);
  }

  PointCloud<PointXYZ> output;
  // Compute the best transformtion
  pcl::oneapi::IterativeClosestPoint<PointXYZ, PointXYZ> reg;
  reg.setMaximumIterations(20);
  reg.setTransformationEpsilon(1e-12);
  reg.setMaxCorrespondenceDistance(2);

  reg.setInputSource(src);
  reg.setInputTarget(tgt);

  // Register
  reg.align(output); //point cloud output of alignment i.e source cloud after transformation is applied.

  Eigen::Matrix4f transform = reg.getFinalTransformation();

  std::cerr << "Transform Matrix:" << std::endl;
  std::cerr << transform << std::endl;
  // Write transformed data to disk
  savePCDFileBinary ("source_transformed.pcd", output);
}
/* ]--- */

// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/registration/ia_ransac.h>
#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>
#include <pcl/point_cloud.h>


using namespace pcl;
using namespace pcl::io;

int main (int argc, char** argv)
{
  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

  // Read Point Cloud
  PointCloud<PointXYZ> cloud_source, cloud_target;
  PointCloud<FPFHSignature33> FPFH_cloud_source, FPFH_cloud_target;

  if (loadPCDFile<PointXYZ>("../../data/scia_source.pcd", cloud_source) < 0)
  {
    std::cerr << "Failed to read alignment source point cloud, please check scia_source.pcd" << std::endl;
    return (-1);
  }
  if (loadPCDFile<PointXYZ>("../../data/scia_target.pcd", cloud_target) < 0)
  {
    std::cerr << "Failed to read alignment target point cloud, please check scia_target.pcd" << std::endl;
    return (-1);
  }
  if (loadPCDFile<FPFHSignature33>("../../data/scia_source_fpfh33.pcd", FPFH_cloud_source) < 0)
  {
    std::cerr << "Failed to read FPFH feature cloud of alignment source point cloud, please check scia_source_fpfh33.pcd" << std::endl;
    return (-1);
  }
  if (loadPCDFile<FPFHSignature33>("../../data/scia_target_fpfh33.pcd", FPFH_cloud_target) < 0)
  {
    std::cerr << "Failed to read FPFH feature cloud of alignment target point cloud, please check scia_target_fpfh33.pcd" << std::endl;
    return (-1);
  }

  // GPU calculate
  pcl::oneapi::SampleConsensusInitialAlignment<PointXYZ, PointXYZ, FPFHSignature33> scia;
  scia.setInputSource(cloud_source.makeShared());
  scia.setInputTarget(cloud_target.makeShared());
  scia.setSourceFeatures(FPFH_cloud_source.makeShared());
  scia.setTargetFeatures(FPFH_cloud_target.makeShared());

  constexpr float SACdismin = 0.02f;
  constexpr int SCANum = 20;
  constexpr int SCAradomn = 100;
  scia.setMinSampleDistance(SACdismin);
  scia.setNumberOfSamples(SCANum);
  scia.setCorrespondenceRandomness(SCAradomn);

  PointCloud<PointXYZ> cloud_result;
  Eigen::Matrix4f sac_trans;
  scia.align(cloud_result);
  sac_trans = scia.getFinalTransformation();

  // print log
  std::cout << "[oneapi SCIA] Transformation Matrix 4x4 = " << std::endl << sac_trans << std::endl;
}

/*
 * Software License Agreement (BSD License)
 *
 *  Point Cloud Library (PCL) - www.pointclouds.org
 *  Copyright (c) 2010-2012, Willow Garage, Inc.
 *  Copyright (c) 2014-, Open Perception, Inc.
 *
 *  All rights reserved.
 *
 *  Redistribution and use in source and binary forms, with or without
 *  modification, are permitted provided that the following conditions
 *  are met:
 *
 *   * Redistributions of source code must retain the above copyright
 *     notice, this list of conditions and the following disclaimer.
 *   * Redistributions in binary form must reproduce the above
 *     copyright notice, this list of conditions and the following
 *     disclaimer in the documentation and/or other materials provided
 *     with the distribution.
 *   * Neither the name of the copyright holder(s) nor the names of its
 *     contributors may be used to endorse or promote products derived
 *     from this software without specific prior written permission.
 *
 *  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 *  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 *  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 *  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 *  COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 *  INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
 *  BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
 *  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
 *  CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 *  LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
 *  ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *  POSSIBILITY OF SUCH DAMAGE.
 *
 */

#include <pcl/oneapi/sample_consensus/sac_model_plane.h>
#include <pcl/oneapi/sample_consensus/ransac.h>
#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>
#include <pcl/point_cloud.h>


int main (int argc, char** argv)
{
  std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";
  // Read Point Cloud
  pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_ptr( new pcl::PointCloud<pcl::PointXYZ>() );
  pcl::PointCloud<pcl::PointXYZ>::Ptr convex_ptr;
  int result = pcl::io::loadPCDFile("test59.pcd", *cloud_ptr);
  if (result != 0)
  {
    pcl::console::print_info ("Load pcd file failed.\n");
    return result;
  }

  // Prepare Device Point Cloud Memory
  pcl::oneapi::SampleConsensusModel::PointCloud_xyz cloud_device_xyz;
  cloud_device_xyz.upload(cloud_ptr->points);
  pcl::oneapi::SampleConsensusModel::PointCloud & cloud_device = (pcl::oneapi::SampleConsensusModel::PointCloud &)cloud_device_xyz;

  // Algorithm tests
  typename pcl::oneapi::SampleConsensusModelPlane::Ptr sac_model (new pcl::oneapi::SampleConsensusModelPlane (cloud_device));
  pcl::oneapi::RandomSampleConsensus sac (sac_model);
  sac.setMaxIterations (10000);
  sac.setDistanceThreshold (0.03);
  result = sac.computeModel ();

  // Best model
  pcl::oneapi::SampleConsensusModelPlane::Indices sample;
  sac.getModel (sample);

  // Coefficient
  pcl::oneapi::SampleConsensusModelPlane::Coefficients coeffs;
  sac.getModelCoefficients (coeffs);

  // Inliers
  pcl::Indices pcl_inliers;
  int inliers_size = sac.getInliersSize ();
  pcl_inliers.resize(inliers_size);

  pcl::oneapi::SampleConsensusModelPlane::IndicesPtr inliers = sac.getInliers ();
  inliers->download(pcl_inliers.data(), 0, inliers_size);

  // Refined coefficient
  pcl::oneapi::SampleConsensusModelPlane::Coefficients coeff_refined;
  sac_model->optimizeModelCoefficients (*cloud_ptr, pcl_inliers, coeffs, coeff_refined);

  // print log
  std::cout << "input cloud size: " << cloud_ptr->points.size() << std::endl;
  std::cout << "inliers size    : " << inliers_size << std::endl;
  std::cout << "  plane model coefficient: " << coeffs[0] << ", " << coeffs[1] << ", " << coeffs[2] << ", " << coeffs[3] << std::endl;
  std::cout << "  Optimized coefficient  : " << coeff_refined[0] << ", " << coeff_refined[1] << ", " << coeff_refined[2] << ", " << coeff_refined[3] << std::endl;
}

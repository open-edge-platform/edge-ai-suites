// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <pcl/oneapi/segmentation/segmentation.h>
#include <pcl/io/pcd_io.h>
#include <pcl/point_types.h>

int main (int argc, char **argv)
{
    std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

    //Read Point Cloud
    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud_input (new pcl::PointCloud<pcl::PointXYZ> ());

    //Load a standard PCD file from disk
    int result = pcl::io::loadPCDFile("test59.pcd", *cloud_input);
    if (result != 0)
    {
        pcl::console::print_info ("Load pcd file failed.\n");
        return result;
    }

    //Create the oneapi_segmentation object
    pcl::oneapi::SACSegmentation seg;

    //Configure oneapi_segmentation class 
    seg.setInputCloud(cloud_input);
    seg.setProbability(0.99);
    seg.setMaxIterations(50);
    seg.setDistanceThreshold(0.01);
    //Optional  
    seg.setOptimizeCoefficients(true);
    //Set algorithm method and model type 
    seg.setMethodType(pcl::oneapi::SAC_RANSAC);
    seg.setModelType (pcl::oneapi::SACMODEL_PLANE);

    //Out parameter declaration for getting inliers and model coefficients  
    pcl::PointIndices::Ptr inliers (new pcl::PointIndices);
    double coeffs[4]={0,0,0,0};

    //Getting inliers and model coefficients
    seg.segment(*inliers, coeffs);

    std::cout << "input cloud size   : " << seg.getCloudSize() << std::endl;
    std::cout << "inliers size       : " << seg.getInliersSize() << std::endl;
    std::cout << "model coefficients : " << coeffs[0] << ", " << coeffs[1] << ", " << coeffs[2] << ", " << coeffs[3] << std::endl;

    return 0;
}

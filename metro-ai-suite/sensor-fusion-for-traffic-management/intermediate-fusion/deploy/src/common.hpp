#ifndef  COMMON_HPP
#define  COMMON_HPP
#include <opencv2/opencv.hpp>
#include <openvino/openvino.hpp>
#include <iostream>
#include <vector>
#include <memory>
#include <chrono>
#include <fstream>
std::vector<float> readFeatureWithShape(const std::string& bin_file, 
                                       const std::vector<int>& expected_shape);

std::vector<float> readBinFile(const std::string& bin_file);   
bool validateShape(const std::vector<float>& data, const std::vector<int>& expected_shape);
std::vector<float> readCameraFeature(const std::string& bin_file);
std::vector<float> readLidarFeature(const std::string& bin_file);                                    
#endif // COMMON_HPP

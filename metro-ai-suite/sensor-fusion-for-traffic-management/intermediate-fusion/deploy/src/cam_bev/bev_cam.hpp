#ifndef BEV_CAM_HPP
#define BEV_CAM_HPP

#include <opencv2/opencv.hpp>
#include <openvino/openvino.hpp>
#include <iostream>
#include <vector>
#include <memory>
#include <chrono>
#include <fstream>
#include <numeric>
#include <algorithm>
#include <sycl/sycl.hpp>
#include <filesystem>
#include <string>
#include <map>
#include "camera-geometry.hpp"
#include "gpu_context_manager.hpp"

struct CameraBackboneOutput {
    std::vector<float> camera_features;
    std::vector<float> depth_weights;
    // Zero-copy path: OpenVINO GPU writes directly into these USM buffers.
    float* camera_ptr = nullptr;
    float* depth_ptr = nullptr;
    bool is_usm = false;
    ov::Shape camera_shape;
    ov::Shape depth_shape;
};

class BEVFusionCam {
public:
    BEVFusionCam(const std::string& model_path, sycl::queue& queue, bool use_gpu = true);

    ~BEVFusionCam();
    
    CameraBackboneOutput processImage(const cv::Mat& image, bool zero_copy_outputs = true);

    // Public methods to get output shapes
    ov::Shape getCameraOutputShape() const;
    ov::Shape getDepthWeightsShape() const;

private:
    cv::Mat preprocessImage(const cv::Mat& image);

    void ensure_output_usm(size_t camera_elems, size_t depth_elems);
    
    std::shared_ptr<ov::Core> core_;
    std::shared_ptr<ov::Model> model_;
    ov::CompiledModel compiled_model_;
    ov::InferRequest infer_request_;
    ov::Output<const ov::Node> input_port_;
    ov::Output<const ov::Node> camera_output_port_;
    ov::Output<const ov::Node> depth_output_port_;
    std::string device_name_;
    bool use_gpu_inference_ = false;
    std::shared_ptr<ov::intel_gpu::ocl::ClContext> remote_context_;
    sycl::queue* opencl_queue_ = nullptr;

    float* camera_out_usm_ = nullptr;
    size_t camera_out_cap_ = 0;
    float* depth_out_usm_ = nullptr;
    size_t depth_out_cap_ = 0;
    void* last_camera_out_ptr_ = nullptr;
    void* last_depth_out_ptr_ = nullptr;
    ov::Tensor camera_remote_tensor_;
    ov::Tensor depth_remote_tensor_;
};
#endif // BEV_CAM_HPP
#ifndef BEV_FUSER_HPP
#define BEV_FUSER_HPP

#include <opencv2/opencv.hpp>
#include <openvino/openvino.hpp>
#include <iostream>
#include <vector>
#include <memory>
#include <chrono>
#include <fstream>
#include <stdexcept>
#include <numeric>
#include <algorithm>
#include <sycl/sycl.hpp>
#include <filesystem>
#include <map>
#include <sstream>
#include <string>
#include "common.hpp"
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>
#include "gpu_context_manager.hpp"

struct FuserOutput {
    std::vector<float> fused_features;
    ov::Shape fused_shape;
    float* fused_features_ptr = nullptr;
    bool owns_data = true;
    
    // Add GPU tensor support
    ov::Tensor gpu_tensor;  // Save GPU tensor
    bool is_gpu_tensor = false;  // Flag to indicate if it's a GPU tensor
};

struct FuserInput {
    // Vector data (for CPU or created from CPU)
    std::vector<float> camera_bev_features;
    std::vector<float> lidar_features;
    
    // Pointer data (for directly pointing to GPU or CPU memory)
    float* camera_bev_ptr = nullptr;
    float* lidar_ptr = nullptr;
    // Optional: provide fused output buffer (USM device pointer) for zero-copy output binding
    float* fused_output_ptr = nullptr;
    
    // Shape information
    ov::Shape camera_bev_shape;
    ov::Shape lidar_shape;

    // Constructor
    FuserInput() = default;
};

class BEVFusionFuser {
public:
    BEVFusionFuser(const std::string& model_path, sycl::queue& queue, bool use_gpu = true);
    
    FuserOutput fuseFeatures(const FuserInput& input);

    // Stable path: feed host tensors to OpenVINO, optionally keep fused output as an OpenVINO-managed tensor
    // (remote when running on GPU). This avoids binding raw USM/device pointers into RemoteTensor.
    ov::Tensor fuseHostToOvTensor(const std::vector<float>& camera_bev,
                                 const std::vector<float>& lidar,
                                 bool keep_on_gpu = true);
    
    // Helper method to create FuserInput from separate components
    FuserInput createFuserInput(const std::vector<float>& camera_bev_features,
                               const std::vector<float>& lidar_features,
                               const ov::Shape& camera_bev_shape,
                               const ov::Shape& lidar_shape);
    
    // Helper method to create FuserInput from pointers (zero-copy)
    FuserInput createFuserInputFromPointers(float* camera_bev_ptr,
                                           float* lidar_ptr,
                                           const ov::Shape& camera_bev_shape,
                                           const ov::Shape& lidar_shape);

    FuserInput createFuserInputFromGPU(float* gpu_bev_features, 
                                       float* gpu_lidar_features,
                                       const ov::Shape& bev_shape, 
                                       const ov::Shape& lidar_shape,
                                       sycl::queue& queue);

    // Public methods to get input/output shapes
    ov::Shape getCameraBEVInputShape() const;
    ov::Shape getLidarInputShape() const;
    ov::Shape getFusedOutputShape() const;
    std::shared_ptr<ov::intel_gpu::ocl::ClContext> getRemoteContext() const;

private:
    // Initialize pre-allocated tensors
    void initializeTensors();
    void validateModelShapes() const;
    void validateInput(const FuserInput& input) const;
    
    std::shared_ptr<ov::Core> core_;
    std::shared_ptr<ov::Model> model_;
    ov::CompiledModel compiled_model_;
    ov::InferRequest infer_request_;
    ov::Output<const ov::Node> camera_bev_input_port_;
    ov::Output<const ov::Node> lidar_input_port_;
    ov::Output<const ov::Node> fused_output_port_;
    std::string device_name_;
    bool use_gpu_inference_ = false;
    sycl::queue* opencl_queue_ = nullptr;

    // Pre-allocated tensors
    ov::Tensor fused_output_tensor_;
    
    // Cached dynamic tensors for zero-copy pointers
    void* last_camera_bev_ptr_ = nullptr;
    void* last_lidar_ptr_ = nullptr;
    void* last_fused_output_ptr_ = nullptr;
    ov::Tensor cached_camera_tensor_;
    ov::Tensor cached_lidar_tensor_;
    ov::Tensor cached_output_tensor_;
    
    // Cached host tensors for gpu_infer_with_host_input path
    ov::Tensor host_camera_tensor_;
    ov::Tensor host_lidar_tensor_;
    ov::Tensor host_output_tensor_;

    // GPU remote context (only used in GPU mode)
    std::shared_ptr<ov::intel_gpu::ocl::ClContext> remote_context_;
};

#endif // BEV_FUSER_HPP
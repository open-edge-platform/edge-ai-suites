#ifndef BEV_HEAD_HPP
#define BEV_HEAD_HPP

#include <opencv2/opencv.hpp>
#include <openvino/openvino.hpp>
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>
#include <iostream>
#include <vector>
#include <memory>
#include <chrono>
#include <fstream>
#include <stdexcept>
#include <numeric>
#include <algorithm>
#include <array>
#include <filesystem>
#include <map>
#include <sstream>
#include <string>
#include "common.hpp"
#include <sycl/sycl.hpp>
#include "gpu_context_manager.hpp"

// Head inference result structure - supports 12 outputs
struct HeadResults {
    // First set of outputs
    std::vector<float> score;      // (1, 5, 128, 128)
    std::vector<float> rot;        // (1, 2, 128, 128)
    std::vector<float> dim;        // (1, 3, 128, 128)
    std::vector<float> reg;        // (1, 2, 128, 128)
    std::vector<float> height;     // (1, 1, 128, 128)
    std::vector<float> vel;        // (1, 2, 128, 128)
    
    // Second set of outputs
    std::vector<float> score2;     // (1, 5, 128, 128)
    std::vector<float> rot2;       // (1, 2, 128, 128)
    std::vector<float> dim2;       // (1, 3, 128, 128)
    std::vector<float> reg2;       // (1, 2, 128, 128)
    std::vector<float> height2;    // (1, 1, 128, 128)
    std::vector<float> vel2;       // (1, 2, 128, 128)
    
    // Shape information
    ov::Shape score_shape, rot_shape, dim_shape, reg_shape, height_shape, vel_shape;
    ov::Shape score2_shape, rot2_shape, dim2_shape, reg2_shape, height2_shape, vel2_shape;
    
    // Pointer version (for GPU inference to avoid copying)
    float* score_ptr = nullptr;
    float* rot_ptr = nullptr;
    float* dim_ptr = nullptr;
    float* reg_ptr = nullptr;
    float* height_ptr = nullptr;
    float* vel_ptr = nullptr;
    
    float* score2_ptr = nullptr;
    float* rot2_ptr = nullptr;
    float* dim2_ptr = nullptr;
    float* reg2_ptr = nullptr;
    float* height2_ptr = nullptr;
    float* vel2_ptr = nullptr;
    
    // GPU tensor support
    ov::Tensor score_tensor, rot_tensor, dim_tensor, reg_tensor, height_tensor, vel_tensor;
    ov::Tensor score2_tensor, rot2_tensor, dim2_tensor, reg2_tensor, height2_tensor, vel2_tensor;
    
    bool owns_data = true;
    bool is_gpu_results = false;
};

struct HeadInput {
    std::vector<float> fuser_features;
    ov::Shape fuser_shape;
    float* fuser_features_ptr = nullptr;
    bool owns_data = true;
    
    // Add GPU tensor support
    ov::Tensor gpu_tensor;
    bool is_gpu_tensor = false;
    
    // Add GPU pointer support (similar to Fuser implementation)
    float* fused_ptr = nullptr;
    ov::Shape fused_shape;
    
};

class BEVFusionHead {
public:
    ~BEVFusionHead();
    BEVFusionHead(const std::string& model_path, sycl::queue& queue, bool use_gpu = false);
    HeadResults inferHead(const HeadInput& input);
    HeadResults inferHeadGPU(const HeadInput& input, bool keep_on_gpu = true);
    
    // Helper method to create HeadInput from bin file
    HeadInput createHeadInputFromBin(const std::string& bin_file);
    std::vector<float> readBinFile(const std::string& bin_file);
    
    // Helper method to create HeadInput from pointer (zero-copy)
    HeadInput createHeadInputFromPointer(float* fuser_ptr, const ov::Shape& fuser_shape);
    
    // GPU tensor methods
    HeadInput createHeadInputFromGPUTensor(const ov::Tensor& gpu_tensor, const ov::Shape& shape);
    
    std::shared_ptr<ov::intel_gpu::ocl::ClContext> getRemoteContext() const {
        return remote_context_;
    }
    
    // Get input shape
    ov::Shape getFuserInputShape() const;
    
    // Print detailed information of all outputs
    void printOutputInfo() const;

private:
    struct OutputBinding {
        const char *name;
        ov::Output<const ov::Node> *port;
        ov::Tensor *host_cache;
        ov::Tensor *remote_cache;
        float **usm_ptr;
        size_t *usm_cap;
        void **last_bound_ptr;
        std::vector<float> HeadResults::*data_member;
        float *HeadResults::*ptr_member;
        ov::Shape HeadResults::*shape_member;
    };

    HeadResults runInference(const HeadInput& input, bool use_gpu, bool keep_on_gpu);
    std::array<OutputBinding, 12> outputBindings();
    void assignOutputPortByName(const std::string& output_name, const ov::Output<const ov::Node>& output);
    void assignOutputPortsByIndex(const std::vector<ov::Output<const ov::Node>>& outputs);
    void validateModelShapes() const;
    void validateInput(const HeadInput& input) const;
    void ensureHostOutputTensor(const ov::Output<const ov::Node>& port, ov::Tensor& cache);
    void bindHostOutputTensors();

    // Zero-copy helpers: bind OpenVINO GPU outputs to USM shared pointers.
    void ensure_usm_shared(float*& ptr, size_t& cap, size_t elems);

    std::shared_ptr<ov::Core> core_;
    std::shared_ptr<ov::Model> model_;
    ov::CompiledModel compiled_model_;
    ov::InferRequest infer_request_;

    // Input port
    ov::Output<const ov::Node> fuser_input_port_;
    
    // First set of output ports
    ov::Output<const ov::Node> score_output_port_;
    ov::Output<const ov::Node> rot_output_port_;
    ov::Output<const ov::Node> dim_output_port_;
    ov::Output<const ov::Node> reg_output_port_;
    ov::Output<const ov::Node> height_output_port_;
    ov::Output<const ov::Node> vel_output_port_;
    
    // Second set of output ports
    ov::Output<const ov::Node> score2_output_port_;
    ov::Output<const ov::Node> rot2_output_port_;
    ov::Output<const ov::Node> dim2_output_port_;
    ov::Output<const ov::Node> reg2_output_port_;
    ov::Output<const ov::Node> height2_output_port_;
    ov::Output<const ov::Node> vel2_output_port_;
    
    // Map to store all output ports
    std::map<std::string, ov::Output<const ov::Node>> output_ports_;
    
    std::string device_name_;
    bool use_gpu_inference_ = true;
    
    // GPU remote context
    std::shared_ptr<ov::intel_gpu::ocl::ClContext> remote_context_;
    sycl::queue* opencl_queue_;

    float* score_usm_ = nullptr;   size_t score_cap_ = 0;
    float* rot_usm_ = nullptr;     size_t rot_cap_ = 0;
    float* dim_usm_ = nullptr;     size_t dim_cap_ = 0;
    float* reg_usm_ = nullptr;     size_t reg_cap_ = 0;
    float* height_usm_ = nullptr;  size_t height_cap_ = 0;
    float* vel_usm_ = nullptr;     size_t vel_cap_ = 0;

    float* score2_usm_ = nullptr;  size_t score2_cap_ = 0;
    float* rot2_usm_ = nullptr;    size_t rot2_cap_ = 0;
    float* dim2_usm_ = nullptr;    size_t dim2_cap_ = 0;
    float* reg2_usm_ = nullptr;    size_t reg2_cap_ = 0;
    float* height2_usm_ = nullptr; size_t height2_cap_ = 0;
    float* vel2_usm_ = nullptr;    size_t vel2_cap_ = 0;

    void* last_score_usm_ptr_ = nullptr;
    void* last_rot_usm_ptr_ = nullptr;
    void* last_dim_usm_ptr_ = nullptr;
    void* last_reg_usm_ptr_ = nullptr;
    void* last_height_usm_ptr_ = nullptr;
    void* last_vel_usm_ptr_ = nullptr;

    void* last_score2_usm_ptr_ = nullptr;
    void* last_rot2_usm_ptr_ = nullptr;
    void* last_dim2_usm_ptr_ = nullptr;
    void* last_reg2_usm_ptr_ = nullptr;
    void* last_height2_usm_ptr_ = nullptr;
    void* last_vel2_usm_ptr_ = nullptr;

    void* last_input_usm_ptr_ = nullptr;
    ov::Tensor cached_input_tensor_;

    ov::Tensor score_remote_tensor_;
    ov::Tensor rot_remote_tensor_;
    ov::Tensor dim_remote_tensor_;
    ov::Tensor reg_remote_tensor_;
    ov::Tensor height_remote_tensor_;
    ov::Tensor vel_remote_tensor_;

    ov::Tensor score2_remote_tensor_;
    ov::Tensor rot2_remote_tensor_;
    ov::Tensor dim2_remote_tensor_;
    ov::Tensor reg2_remote_tensor_;
    ov::Tensor height2_remote_tensor_;
    ov::Tensor vel2_remote_tensor_;

    ov::Tensor score_host_tensor_;
    ov::Tensor rot_host_tensor_;
    ov::Tensor dim_host_tensor_;
    ov::Tensor reg_host_tensor_;
    ov::Tensor height_host_tensor_;
    ov::Tensor vel_host_tensor_;

    ov::Tensor score2_host_tensor_;
    ov::Tensor rot2_host_tensor_;
    ov::Tensor dim2_host_tensor_;
    ov::Tensor reg2_host_tensor_;
    ov::Tensor height2_host_tensor_;
    ov::Tensor vel2_host_tensor_;
    
    // Initialize all output ports to empty
    void initializeOutputPorts();
    
    // Extract CPU results
    void extractCPUResults(HeadResults& results);
};

// Helper function to save HeadResults to bin files - supports 12 outputs
void saveHeadResultsToBin(const HeadResults& results, const std::string& output_dir);

#endif // BEV_HEAD_HPP
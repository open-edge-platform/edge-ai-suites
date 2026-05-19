#include "bev_fuser.hpp"
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>
#include <sycl/sycl.hpp>

namespace {

std::string shape_to_string(const ov::Shape &shape)
{
    std::ostringstream os;
    os << "[";
    for (size_t i = 0; i < shape.size(); ++i) {
        if (i != 0)
            os << ", ";
        os << shape[i];
    }
    os << "]";
    return os.str();
}

}  // namespace

BEVFusionFuser::BEVFusionFuser(const std::string &model_path, sycl::queue &queue, bool use_gpu)
    : opencl_queue_(&queue), use_gpu_inference_(use_gpu)
{
    std::cout << "Initializing BEVFusionFuser with unified context..." << std::endl;

    // Get global context manager
    auto &context_manager = GPUContextManager::getInstance();

    if (!context_manager.isInitialized()) {
        throw std::runtime_error("Global GPU context manager not initialized");
    }

    // Share the Core object from the global context manager (avoids duplication).
    core_ = context_manager.getCore();
    model_ = core_->read_model(model_path);

    ov::preprocess::PrePostProcessor ppp(model_);
    // Configure first input (camera BEV features)
    auto &input0 = ppp.input(0);
    input0.tensor().set_element_type(ov::element::f32).set_layout("NCHW");
    input0.model().set_layout("NCHW");

    // Configure second input (lidar features)
    auto &input1 = ppp.input(1);
    input1.tensor().set_element_type(ov::element::f32).set_layout("NCHW");
    input1.model().set_layout("NCHW");

    ppp.output(0).tensor().set_element_type(ov::element::f32);

    model_ = ppp.build();

    std::string device = GPUContextManager::cpuDeviceName();
    if (use_gpu) {
        try {
            // Use global shared GPU context
            remote_context_ = context_manager.getSharedContext();

            if (remote_context_) {
                std::cout << "Using shared GPU context for Fuser" << std::endl;

                compiled_model_ = core_->compile_model(
                    model_, *remote_context_,
                    context_manager.getCompileConfig());

                device = GPUContextManager::sharedGpuContextLabel();
                device_name_ = GPUContextManager::gpuDeviceName();
                use_gpu_inference_ = true;

                std::cout << "✓ Fuser compiled with unified GPU context" << std::endl;
            }
            else {
                throw std::runtime_error("Shared GPU context not available");
            }
        }
        catch (const std::exception &e) {
            std::cout << "GPU initialization failed for Fuser, fallback to CPU: " << e.what() << std::endl;

            compiled_model_ = core_->compile_model(model_, GPUContextManager::cpuDeviceName(), context_manager.getCompileConfig());
            device = GPUContextManager::cpuDeviceName();
            device_name_ = GPUContextManager::cpuDeviceName();
            use_gpu_inference_ = false;
            remote_context_ = nullptr;
        }
    }
    else {
        compiled_model_ = core_->compile_model(model_, GPUContextManager::cpuDeviceName(), context_manager.getCompileConfig());
        device_name_ = GPUContextManager::cpuDeviceName();
        use_gpu_inference_ = false;
        remote_context_ = nullptr;
    }

    std::cout << "Fuser OpenVINO device: " << device << std::endl;

    // Create inference request with timing
    const auto if_req_t1 = std::chrono::high_resolution_clock::now();
    infer_request_ = compiled_model_.create_infer_request();
    const auto if_req_t2 = std::chrono::high_resolution_clock::now();
    std::cout << "Fuser InferRequest create " << std::chrono::duration_cast<std::chrono::milliseconds>(if_req_t2 - if_req_t1).count() << "ms" << std::endl;

    // Get input/output information
    auto inputs = compiled_model_.inputs();
    auto outputs = compiled_model_.outputs();

    std::cout << "Fuser model has " << inputs.size() << " inputs and " << outputs.size() << " outputs:" << std::endl;

    // Identify inputs based on names or order
    for (size_t i = 0; i < inputs.size(); ++i) {
        auto input_name = inputs[i].get_any_name();
        auto input_shape = inputs[i].get_shape();
        std::cout << "  Input " << i << ": " << input_name << ", shape: " << input_shape << std::endl;

        // Identify camera BEV and lidar inputs based on names
        if (input_name.find("camera") != std::string::npos || input_name.find("bev") != std::string::npos || input_name.find("img") != std::string::npos) {
            camera_bev_input_port_ = inputs[i];
            std::cout << "    -> Identified as camera BEV input" << std::endl;
        }
        else if (input_name.find("lidar") != std::string::npos || input_name.find("pts") != std::string::npos ||
                 input_name.find("point") != std::string::npos) {
            lidar_input_port_ = inputs[i];
            std::cout << "    -> Identified as lidar input" << std::endl;
        }
    }

    // If name-based identification fails, use index-based identification
    if (camera_bev_input_port_.get_node() == nullptr || lidar_input_port_.get_node() == nullptr) {
        std::cout << "Fallback to index-based identification for inputs..." << std::endl;
        if (inputs.size() >= 2) {
            camera_bev_input_port_ = inputs[0];  // First input as camera BEV
            lidar_input_port_ = inputs[1];       // Second input as lidar
            std::cout << "  Input 0 -> camera BEV features" << std::endl;
            std::cout << "  Input 1 -> lidar features" << std::endl;
        }
    }

    // Get output port
    if (outputs.size() > 0) {
        fused_output_port_ = outputs[0];  // Assume first output is fused features
        std::cout << "  Output 0: " << outputs[0].get_any_name() << ", shape: " << outputs[0].get_shape() << std::endl;
    }

    // Verify that all ports were found
    if (camera_bev_input_port_.get_node() == nullptr) {
        throw std::runtime_error("Could not identify camera BEV input");
    }
    if (lidar_input_port_.get_node() == nullptr) {
        throw std::runtime_error("Could not identify lidar input");
    }
    if (fused_output_port_.get_node() == nullptr) {
        throw std::runtime_error("Could not identify fused output");
    }

    validateModelShapes();

    // Initialize pre-allocated tensors
    initializeTensors();

    std::cout << "Fuser model loaded successfully!" << std::endl;
    std::cout << "Camera BEV input shape: " << camera_bev_input_port_.get_shape() << std::endl;
    std::cout << "Lidar input shape: " << lidar_input_port_.get_shape() << std::endl;
    std::cout << "Fused output shape: " << fused_output_port_.get_shape() << std::endl;
}

void BEVFusionFuser::initializeTensors()
{
    auto output_shape = fused_output_port_.get_shape();

    if (use_gpu_inference_) {
        try {
            if (!remote_context_) {
                throw std::runtime_error("remote_context_ is null while GPU inference is enabled");
            }

            fused_output_tensor_ = remote_context_->create_tensor(fused_output_port_.get_element_type(), output_shape);

            std::cout << "Pre-allocated GPU output tensor created successfully" << std::endl;
        }
        catch (const std::exception &e) {
            std::cerr << "Failed to create GPU tensors, fallback to CPU tensors: " << e.what() << std::endl;
            fused_output_tensor_ = ov::Tensor(fused_output_port_.get_element_type(), output_shape);
        }
    }
    else {
        fused_output_tensor_ = ov::Tensor(fused_output_port_.get_element_type(), output_shape);

        std::cout << "Pre-allocated CPU output tensor created successfully" << std::endl;
    }
}

void BEVFusionFuser::validateModelShapes() const
{
    const auto camera_shape = camera_bev_input_port_.get_shape();
    const auto lidar_shape = lidar_input_port_.get_shape();
    const auto output_shape = fused_output_port_.get_shape();

    if (camera_shape.size() != 4 || lidar_shape.size() != 4 || output_shape.size() != 4) {
        throw std::runtime_error(
            "Fuser expects 4D NCHW tensors, got camera=" + shape_to_string(camera_shape) +
            ", lidar=" + shape_to_string(lidar_shape) + ", output=" + shape_to_string(output_shape));
    }
}

void BEVFusionFuser::validateInput(const FuserInput &input) const
{
    const bool has_host_camera = !input.camera_bev_features.empty();
    const bool has_host_lidar = !input.lidar_features.empty();
    const bool has_ptr_camera = input.camera_bev_ptr != nullptr;
    const bool has_ptr_lidar = input.lidar_ptr != nullptr;

    if (has_host_camera != has_host_lidar) {
        throw std::runtime_error("FuserInput must provide both host camera and host lidar tensors together");
    }
    if (has_ptr_camera != has_ptr_lidar) {
        throw std::runtime_error("FuserInput must provide both zero-copy camera and zero-copy lidar pointers together");
    }

    const bool pure_host = has_host_camera && !has_ptr_camera;
    const bool pure_zero_copy = has_ptr_camera && !has_host_camera;
    if (!pure_host && !pure_zero_copy) {
        throw std::runtime_error("FuserInput must be either pure host input or pure zero-copy input");
    }

    const auto expected_camera_shape = camera_bev_input_port_.get_shape();
    const auto expected_lidar_shape = lidar_input_port_.get_shape();

    if (!input.camera_bev_shape.empty() && input.camera_bev_shape != expected_camera_shape) {
        throw std::runtime_error(
            "camera BEV shape mismatch: expected " + shape_to_string(expected_camera_shape) +
            ", got " + shape_to_string(input.camera_bev_shape));
    }
    if (!input.lidar_shape.empty() && input.lidar_shape != expected_lidar_shape) {
        throw std::runtime_error(
            "lidar BEV shape mismatch: expected " + shape_to_string(expected_lidar_shape) +
            ", got " + shape_to_string(input.lidar_shape));
    }

    if (pure_host) {
        const size_t camera_bytes = ov::shape_size(expected_camera_shape) * sizeof(float);
        const size_t lidar_bytes = ov::shape_size(expected_lidar_shape) * sizeof(float);
        if (input.camera_bev_features.size() * sizeof(float) != camera_bytes) {
            throw std::runtime_error("camera host tensor size mismatch: expected " + std::to_string(camera_bytes) +
                                     " bytes, got " + std::to_string(input.camera_bev_features.size() * sizeof(float)));
        }
        if (input.lidar_features.size() * sizeof(float) != lidar_bytes) {
            throw std::runtime_error("lidar host tensor size mismatch: expected " + std::to_string(lidar_bytes) +
                                     " bytes, got " + std::to_string(input.lidar_features.size() * sizeof(float)));
        }
        if (input.fused_output_ptr != nullptr) {
            throw std::runtime_error("fused_output_ptr is only valid for zero-copy fuser inputs");
        }
    }

    if (pure_zero_copy && (!use_gpu_inference_ || remote_context_ == nullptr)) {
        throw std::runtime_error("Zero-copy fuser input requires GPU inference with a valid shared context");
    }
}

ov::Tensor BEVFusionFuser::fuseHostToOvTensor(const std::vector<float>& camera_bev,
                                             const std::vector<float>& lidar,
                                             bool keep_on_gpu)
{
    const auto cam_shape = camera_bev_input_port_.get_shape();
    const auto lidar_shape = lidar_input_port_.get_shape();
    const auto out_shape = fused_output_port_.get_shape();

    ov::Tensor cam_tensor(camera_bev_input_port_.get_element_type(), cam_shape);
    ov::Tensor lidar_tensor(lidar_input_port_.get_element_type(), lidar_shape);

    if (camera_bev.size() * sizeof(float) != cam_tensor.get_byte_size()) {
        throw std::runtime_error("camera_bev size mismatch for fuser input");
    }
    if (lidar.size() * sizeof(float) != lidar_tensor.get_byte_size()) {
        throw std::runtime_error("lidar size mismatch for fuser input");
    }

    std::memcpy(cam_tensor.data<float>(), camera_bev.data(), cam_tensor.get_byte_size());
    std::memcpy(lidar_tensor.data<float>(), lidar.data(), lidar_tensor.get_byte_size());

    infer_request_.set_tensor(camera_bev_input_port_, cam_tensor);
    infer_request_.set_tensor(lidar_input_port_, lidar_tensor);

    if (use_gpu_inference_ && keep_on_gpu) {
        if (!remote_context_) {
            throw std::runtime_error("GPU inference requested but remote_context_ is null");
        }
        if (!fused_output_tensor_ || fused_output_tensor_.get_shape().empty()) {
            fused_output_tensor_ = remote_context_->create_tensor(fused_output_port_.get_element_type(), out_shape);
        }
        infer_request_.set_tensor(fused_output_port_, fused_output_tensor_);
        infer_request_.start_async();
        infer_request_.wait();
        return fused_output_tensor_;
    }

    ov::Tensor out_tensor(fused_output_port_.get_element_type(), out_shape);
    infer_request_.set_tensor(fused_output_port_, out_tensor);
    infer_request_.start_async();
    infer_request_.wait();
    return out_tensor;
}

FuserOutput BEVFusionFuser::fuseFeatures(const FuserInput &input)
{
    validateInput(input);

    const bool pure_host = !input.camera_bev_features.empty() && input.camera_bev_ptr == nullptr;
    const bool use_zero_copy_gpu_ptrs = input.camera_bev_ptr != nullptr && input.lidar_ptr != nullptr;

    ov::Tensor camera_tensor;
    ov::Tensor lidar_tensor;
    ov::Tensor output_tensor;

    if (use_zero_copy_gpu_ptrs) {
        // Zero-copy GPU pointers using shared remote context
        auto camera_shape = camera_bev_input_port_.get_shape();
        auto lidar_shape = lidar_input_port_.get_shape();

        if (input.camera_bev_ptr != last_camera_bev_ptr_ || !cached_camera_tensor_) {
            cached_camera_tensor_ = remote_context_->create_tensor(
                camera_bev_input_port_.get_element_type(), camera_shape, input.camera_bev_ptr);
            last_camera_bev_ptr_ = input.camera_bev_ptr;
        }

        if (input.lidar_ptr != last_lidar_ptr_ || !cached_lidar_tensor_) {
            cached_lidar_tensor_ = remote_context_->create_tensor(
                lidar_input_port_.get_element_type(), lidar_shape, input.lidar_ptr);
            last_lidar_ptr_ = input.lidar_ptr;
        }

        camera_tensor = cached_camera_tensor_;
        lidar_tensor = cached_lidar_tensor_;

        // Output: either bind to a provided USM pointer (true zero-copy output), or let plugin allocate.
        if (input.fused_output_ptr != nullptr) {
            if (input.fused_output_ptr != last_fused_output_ptr_ || !cached_output_tensor_) {
                cached_output_tensor_ = remote_context_->create_tensor(
                    fused_output_port_.get_element_type(), fused_output_port_.get_shape(), input.fused_output_ptr);
                last_fused_output_ptr_ = input.fused_output_ptr;
            }
            output_tensor = cached_output_tensor_;
        }
        else {
            // Ensure fused output tensor lives on GPU
            if (!fused_output_tensor_ || fused_output_tensor_.get_shape().empty()) {
                fused_output_tensor_ = remote_context_->create_tensor(
                    fused_output_port_.get_element_type(), fused_output_port_.get_shape());
            }
            output_tensor = fused_output_tensor_;
        }

        infer_request_.set_tensor(camera_bev_input_port_, camera_tensor);
        infer_request_.set_tensor(lidar_input_port_, lidar_tensor);
        infer_request_.set_tensor(fused_output_port_, output_tensor);
    }
    else if (pure_host) {
        // Pure host input path: works for both CPU and GPU inference.
        if (!host_camera_tensor_ || host_camera_tensor_.get_shape() != camera_bev_input_port_.get_shape()) {
            host_camera_tensor_ = ov::Tensor(camera_bev_input_port_.get_element_type(), camera_bev_input_port_.get_shape());
        }
        if (!host_lidar_tensor_ || host_lidar_tensor_.get_shape() != lidar_input_port_.get_shape()) {
            host_lidar_tensor_ = ov::Tensor(lidar_input_port_.get_element_type(), lidar_input_port_.get_shape());
        }
        if (!host_output_tensor_ || host_output_tensor_.get_shape() != fused_output_port_.get_shape()) {
            host_output_tensor_ = ov::Tensor(fused_output_port_.get_element_type(), fused_output_port_.get_shape());
        }
        
        camera_tensor = host_camera_tensor_;
        lidar_tensor = host_lidar_tensor_;
        output_tensor = host_output_tensor_;

        std::memcpy(camera_tensor.data<float>(), input.camera_bev_features.data(), camera_tensor.get_byte_size());
        std::memcpy(lidar_tensor.data<float>(), input.lidar_features.data(), lidar_tensor.get_byte_size());

        infer_request_.set_tensor(camera_bev_input_port_, camera_tensor);
        infer_request_.set_tensor(lidar_input_port_, lidar_tensor);
        infer_request_.set_tensor(fused_output_port_, output_tensor);
    }

    auto start = std::chrono::high_resolution_clock::now();
    infer_request_.start_async();
    infer_request_.wait();
    auto end = std::chrono::high_resolution_clock::now();

    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
#ifdef _DEBUG
    std::cout << "Fuser inference time: " << duration.count() << " ms" << std::endl;
#endif

    FuserOutput output;
    if (use_zero_copy_gpu_ptrs) {
        // Keep GPU result opaque; avoid RemoteTensor data()
        output.fused_features_ptr = input.fused_output_ptr;
        output.owns_data = false;
        output.is_gpu_tensor = true;
        output.gpu_tensor = input.fused_output_ptr != nullptr ? output_tensor : fused_output_tensor_;
    }
    else {
        // Host result accessible
        float *fused_data = output_tensor.data<float>();
        size_t fused_size = output_tensor.get_size();
        output.fused_features.assign(fused_data, fused_data + fused_size);
        output.fused_features_ptr = output.fused_features.data();
        output.owns_data = true;
        output.is_gpu_tensor = false;
    }

    output.fused_shape = fused_output_port_.get_shape();
    return output;
}

FuserInput BEVFusionFuser::createFuserInput(const std::vector<float> &camera_bev_features,
                                            const std::vector<float> &lidar_features,
                                            const ov::Shape &camera_bev_shape,
                                            const ov::Shape &lidar_shape)
{
    FuserInput input;
    input.camera_bev_features = camera_bev_features;
    input.lidar_features = lidar_features;
    input.camera_bev_shape = camera_bev_shape;
    input.lidar_shape = lidar_shape;
    input.camera_bev_ptr = nullptr;
    input.lidar_ptr = nullptr;
    return input;
}

FuserInput
BEVFusionFuser::createFuserInputFromPointers(float *camera_bev_ptr, float *lidar_ptr, const ov::Shape &camera_bev_shape, const ov::Shape &lidar_shape)
{
    FuserInput input;
    input.camera_bev_ptr = camera_bev_ptr;
    input.lidar_ptr = lidar_ptr;
    input.camera_bev_shape = camera_bev_shape;
    input.lidar_shape = lidar_shape;
    return input;
}

FuserInput BEVFusionFuser::createFuserInputFromGPU(float *gpu_bev_features,
                                                   float *gpu_lidar_features,
                                                   const ov::Shape &bev_shape,
                                                   const ov::Shape &lidar_shape,
                                                   sycl::queue &queue)
{
    (void)queue;
    // Avoid copying to CPU. Use device pointers directly for zero-copy.
    FuserInput input;
    input.camera_bev_ptr = gpu_bev_features;
    input.lidar_ptr = gpu_lidar_features;
    input.camera_bev_shape = bev_shape;
    input.lidar_shape = lidar_shape;
    return input;
}

ov::Shape BEVFusionFuser::getCameraBEVInputShape() const
{
    return camera_bev_input_port_.get_shape();
}

ov::Shape BEVFusionFuser::getLidarInputShape() const
{
    return lidar_input_port_.get_shape();
}

ov::Shape BEVFusionFuser::getFusedOutputShape() const
{
    return fused_output_port_.get_shape();
}
std::shared_ptr<ov::intel_gpu::ocl::ClContext> BEVFusionFuser::getRemoteContext() const
{
    return remote_context_;
}
#include "bev_cam.hpp"
#include <sstream>

BEVFusionCam::~BEVFusionCam() {
    if (opencl_queue_) {
        try {
            if (camera_out_usm_) {
                sycl::free(camera_out_usm_, *opencl_queue_);
                camera_out_usm_ = nullptr;
                camera_out_cap_ = 0;
            }
            if (depth_out_usm_) {
                sycl::free(depth_out_usm_, *opencl_queue_);
                depth_out_usm_ = nullptr;
                depth_out_cap_ = 0;
            }
        }
        catch (...) {
            // Best-effort cleanup; avoid throwing from destructor.
        }
    }
}

void BEVFusionCam::ensure_output_usm(size_t camera_elems, size_t depth_elems) {
    if (!opencl_queue_) {
        throw std::runtime_error("BEVFusionCam: SYCL queue is null");
    }
    if (camera_out_cap_ < camera_elems) {
        if (camera_out_usm_) {
            sycl::free(camera_out_usm_, *opencl_queue_);
        }
        camera_out_usm_ = sycl::malloc_device<float>(camera_elems, *opencl_queue_);
        if (!camera_out_usm_) {
            throw std::runtime_error("BEVFusionCam: failed to allocate camera_out_usm_");
        }
        camera_out_cap_ = camera_elems;
    }
    if (depth_out_cap_ < depth_elems) {
        if (depth_out_usm_) {
            sycl::free(depth_out_usm_, *opencl_queue_);
        }
        depth_out_usm_ = sycl::malloc_device<float>(depth_elems, *opencl_queue_);
        if (!depth_out_usm_) {
            throw std::runtime_error("BEVFusionCam: failed to allocate depth_out_usm_");
        }
        depth_out_cap_ = depth_elems;
    }
}

BEVFusionCam::BEVFusionCam(const std::string& model_path, sycl::queue& queue, bool use_gpu) {
    // Use unified Core/Context managed by GPUContextManager
    auto& context_manager = GPUContextManager::getInstance();
    if (!context_manager.isInitialized()) {
        throw std::runtime_error("GPUContextManager not initialized. Call initialize(queue) first.");
    }

    opencl_queue_ = &queue;
    // Share the Core object from the global context manager (avoids duplication).
    core_ = context_manager.getCore();
    model_ = core_->read_model(model_path);

    auto original_inputs = model_->inputs();
    if (original_inputs.empty()) {
        throw std::runtime_error("Model has no inputs");
    }
    
    auto original_shape = original_inputs[0].get_shape();
    std::cout << "Original model input shape: ";
    for (auto dim : original_shape) {
        std::cout << dim << " ";
    }
    std::cout << std::endl;
    
    // Configure preprocessing using OpenVINO PPP
    ov::preprocess::PrePostProcessor ppp(model_);
    
    // Configure input preprocessing
    auto& input_info = ppp.input();
    
    // Derive the PPP resize target from the model's static input shape so
    // camera backbones with different native resolutions (e.g. 864×1536 for
    // DAIR-V2X, 384×1280 for KITTI) work without per-dataset rebuilds.
    // Model layout is NCHW, so [N,C,H,W] → H=shape[2], W=shape[3].
    int target_h = static_cast<int>(original_shape.size() == 4 ? original_shape[2] : 864);
    int target_w = static_cast<int>(original_shape.size() == 4 ? original_shape[3] : 1536);

    if (original_shape.size() == 4) {

        input_info.tensor()
            .set_element_type(ov::element::u8)
            .set_layout("NHWC")
            .set_color_format(ov::preprocess::ColorFormat::BGR)  
            .set_shape({1, -1, -1, 3});  
        
        input_info.model()
            .set_layout("NCHW");
        
        input_info.preprocess()
            .convert_element_type(ov::element::f32)
            .resize(ov::preprocess::ResizeAlgorithm::RESIZE_LINEAR, target_h, target_w)
            .convert_color(ov::preprocess::ColorFormat::RGB)  // BGR -> RGB
            .mean({123.675f, 116.28f, 103.53f})              // BGR format mean
            .scale({58.395f, 57.12f, 57.375f});              // BGR format scale
    }
    ppp.output(0).tensor()
        .set_element_type(ov::element::f32)
        .set_layout("NHWC"); 
    
    // Output 1: depth_weights -> NCHW layout
    ppp.output(1).tensor()
        .set_element_type(ov::element::f32)
        .set_layout("NCHW");  
    ppp.output(0).tensor().set_element_type(ov::element::f32);
    ppp.output(1).tensor().set_element_type(ov::element::f32);
    // Build the model with preprocessing
    model_ = ppp.build();
    
    std::cout << "Camera feature layout: NHWC" << std::endl;
    std::cout << "Depth weights layout: NCHW" << std::endl;
    std::string device = GPUContextManager::cpuDeviceName();
    if (use_gpu) {
        try {
            auto shared_context = context_manager.getSharedContext();
            if (!shared_context) {
                throw std::runtime_error("Shared GPU context is null");
            }
            // Compile model using shared OpenCL context to share queue/resources
            compiled_model_ = core_->compile_model(model_, *shared_context, context_manager.getCompileConfig());
            remote_context_ = shared_context;
            device_name_ = GPUContextManager::gpuDeviceName();
            use_gpu_inference_ = true;
            device = GPUContextManager::sharedGpuContextLabel();
            std::cout << "Using OpenVINO GPU inference with shared context" << std::endl;
        } catch (const std::exception& e) {
            std::cout << "GPU not available for OpenVINO, fallback to CPU: " << e.what() << std::endl;
            compiled_model_ = core_->compile_model(model_, GPUContextManager::cpuDeviceName(), context_manager.getCompileConfig());
            device_name_ = GPUContextManager::cpuDeviceName();
            use_gpu_inference_ = false;
        }
    } else {
        compiled_model_ = core_->compile_model(model_, GPUContextManager::cpuDeviceName(), context_manager.getCompileConfig());
        device_name_ = GPUContextManager::cpuDeviceName();
        use_gpu_inference_ = false;
    }

    std::cout << "OpenVINO device: " << device << std::endl;
    infer_request_ = compiled_model_.create_infer_request();
    
    // Get input/output information
    input_port_ = compiled_model_.input();
    std::cout << "After PPP - Input element type: " << input_port_.get_element_type() << std::endl;
    std::cout << "After PPP - Input shape: " << input_port_.get_partial_shape() << std::endl;    
    // Get all output ports
    auto outputs = compiled_model_.outputs();
    std::cout << "Model has " << outputs.size() << " outputs:" << std::endl;
    
    for (size_t i = 0; i < outputs.size(); ++i) {
        auto output_name = outputs[i].get_any_name();
        auto output_shape = outputs[i].get_shape();
        std::cout << "  Output " << i << ": " << output_name 
                  << ", shape: " << output_shape << std::endl;
        
        // Identify camera_feature and camera_depth_weights based on output names
        if (output_name.find("camera_feature") != std::string::npos || 
            (output_name.find("camera") != std::string::npos && 
             output_name.find("depth") == std::string::npos)) {
            camera_output_port_ = outputs[i];
            std::cout << "    -> Identified as camera_feature output" << std::endl;
        } else if (output_name.find("camera_depth_weights") != std::string::npos ||
                  output_name.find("depth_weights") != std::string::npos ||
                  output_name.find("weights") != std::string::npos) {
            depth_output_port_ = outputs[i];
            std::cout << "    -> Identified as camera_depth_weights output" << std::endl;
        }
    }
    
    // If name-based identification fails, use index-based identification
    if (camera_output_port_.get_node() == nullptr || depth_output_port_.get_node() == nullptr) {
        std::cout << "Fallback to index-based identification..." << std::endl;
        if (outputs.size() >= 2) {
            camera_output_port_ = outputs[0];  // First output as camera_feature
            depth_output_port_ = outputs[1];   // Second output as camera_depth_weights
            std::cout << "  Output 0 -> camera_feature" << std::endl;
            std::cout << "  Output 1 -> camera_depth_weights" << std::endl;
        }
    }
    
    // Verify that both outputs were found
    if (camera_output_port_.get_node() == nullptr) {
        throw std::runtime_error("Could not identify camera_feature output");
    }
    if (depth_output_port_.get_node() == nullptr) {
        throw std::runtime_error("Could not identify camera_depth_weights output");
    }
    
    std::cout << "Camera backbone model loaded successfully!" << std::endl;
    std::cout << "Input shape: " << input_port_.get_partial_shape() << std::endl;
    std::cout << "Camera feature shape: " << camera_output_port_.get_shape() << std::endl;
    std::cout << "Camera depth weights shape: " << depth_output_port_.get_shape() << std::endl;
}


CameraBackboneOutput BEVFusionCam::processImage(const cv::Mat& image, bool zero_copy_outputs) {
    cv::Mat bgr_image;
    if (image.channels() == 3) {
        bgr_image = image;
    } else {
        cv::cvtColor(image, bgr_image, cv::COLOR_GRAY2BGR);
    }
    auto input_partial_shape = input_port_.get_partial_shape();
    auto input_element_type = input_port_.get_element_type();

    ov::Shape tensor_shape = {1,
                              static_cast<size_t>(bgr_image.rows),
                              static_cast<size_t>(bgr_image.cols),
                              3};

    size_t expected_size = tensor_shape[1] * tensor_shape[2] * tensor_shape[3];
    size_t actual_size = bgr_image.total() * bgr_image.elemSize();
    if (expected_size != actual_size) {
        throw std::runtime_error("Size mismatch: tensor expects " + std::to_string(expected_size) +
                                 " bytes, but image has " + std::to_string(actual_size) + " bytes");
    }

    ov::Tensor input_tensor;
    if (input_element_type == ov::element::u8) {
        input_tensor = ov::Tensor(ov::element::u8, tensor_shape);
        uint8_t* input_data = input_tensor.data<uint8_t>();
        if (bgr_image.isContinuous()) {
            std::memcpy(input_data, bgr_image.data, bgr_image.total() * bgr_image.elemSize());
        } else {
            size_t row_size = bgr_image.cols * bgr_image.channels();
            for (int i = 0; i < bgr_image.rows; ++i) {
                std::memcpy(input_data + i * row_size, bgr_image.ptr(i), row_size);
            }
        }
    } else if (input_element_type == ov::element::f32) {
        // PPP expects f32 input; path used when PPP is not configured to convert from u8.
        if (input_partial_shape.is_static()) {
            auto static_shape = input_partial_shape.to_shape();
            if (static_shape[1] == 864 && static_shape[2] == 1536) {
                cv::Mat resized_image;
                cv::resize(bgr_image, resized_image, cv::Size(1536, 864));
                tensor_shape = {1, 864, 1536, 3};
                input_tensor = ov::Tensor(ov::element::u8, tensor_shape);
                uint8_t* input_data = input_tensor.data<uint8_t>();
                if (resized_image.isContinuous()) {
                    std::memcpy(input_data, resized_image.data, resized_image.total() * resized_image.elemSize());
                } else {
                    size_t row_size = resized_image.cols * resized_image.channels();
                    for (int i = 0; i < resized_image.rows; ++i) {
                        std::memcpy(input_data + i * row_size, resized_image.ptr(i), row_size);
                    }
                }
            }
        }
    } else {
        throw std::runtime_error("Unsupported input element type: " + input_element_type.to_string());
    }

    infer_request_.set_input_tensor(input_tensor);

    // Defensive dtype guard: USM remote tensor binding below uses f32 element
    // type (malloc_device<float>). If a future quantized xml emits non-f32
    // output (e.g. u8/f16 direct output), fall back to the host-copy path
    // automatically instead of crashing in create_tensor.
    const bool can_zero_copy = zero_copy_outputs
        && use_gpu_inference_
        && remote_context_ != nullptr
        && opencl_queue_ != nullptr
        && camera_output_port_.get_element_type() == ov::element::f32
        && depth_output_port_.get_element_type() == ov::element::f32;
    if (can_zero_copy) {
        const ov::Shape camera_shape = camera_output_port_.get_shape();
        const ov::Shape depth_shape = depth_output_port_.get_shape();
        const size_t camera_elems = ov::shape_size(camera_shape);
        const size_t depth_elems = ov::shape_size(depth_shape);

        ensure_output_usm(camera_elems, depth_elems);
        if (!camera_remote_tensor_ || last_camera_out_ptr_ != camera_out_usm_ || camera_remote_tensor_.get_shape() != camera_shape) {
            camera_remote_tensor_ = remote_context_->create_tensor(ov::element::f32, camera_shape, camera_out_usm_);
            last_camera_out_ptr_ = camera_out_usm_;
        }
        if (!depth_remote_tensor_ || last_depth_out_ptr_ != depth_out_usm_ || depth_remote_tensor_.get_shape() != depth_shape) {
            depth_remote_tensor_ = remote_context_->create_tensor(ov::element::f32, depth_shape, depth_out_usm_);
            last_depth_out_ptr_ = depth_out_usm_;
        }

        infer_request_.set_tensor(camera_output_port_, camera_remote_tensor_);
        infer_request_.set_tensor(depth_output_port_, depth_remote_tensor_);
    }

    infer_request_.infer();

    CameraBackboneOutput output;
    output.camera_shape = camera_output_port_.get_shape();
    output.depth_shape = depth_output_port_.get_shape();

    if (can_zero_copy) {
        output.is_usm = true;
        output.camera_ptr = camera_out_usm_;
        output.depth_ptr = depth_out_usm_;
        return output;
    }

    auto camera_tensor = infer_request_.get_tensor(camera_output_port_);
    auto depth_tensor = infer_request_.get_tensor(depth_output_port_);
    {
        const ov::Shape camera_shape = camera_tensor.get_shape();
        const ov::Shape depth_shape = depth_tensor.get_shape();

        const size_t camera_size = camera_tensor.get_size();
        const size_t depth_size = depth_tensor.get_size();

        output.camera_features.resize(camera_size);
        output.depth_weights.resize(depth_size);

        ov::Tensor camera_host(ov::element::f32, camera_shape, output.camera_features.data());
        ov::Tensor depth_host(ov::element::f32, depth_shape, output.depth_weights.data());

        camera_tensor.copy_to(camera_host);
        depth_tensor.copy_to(depth_host);
    }
    output.is_usm = false;
    output.camera_ptr = nullptr;
    output.depth_ptr = nullptr;
    return output;
}

ov::Shape BEVFusionCam::getCameraOutputShape() const {
    return camera_output_port_.get_shape();
}

ov::Shape BEVFusionCam::getDepthWeightsShape() const {
    return depth_output_port_.get_shape();
}

// cv::Mat BEVFusionCam::preprocessImage(const cv::Mat& image) {
//     cv::Mat resized, normalized, blob;
    
//     // Resize to model input dimensions
//     auto input_shape = input_port_.get_shape();
//     int input_h = input_shape[3];
//     int input_w = input_shape[4];
    
//     cv::resize(image, resized, cv::Size(input_w, input_h));
    
//     // Normalize
//     resized.convertTo(normalized, CV_32F, 1.0/255.0);
    
//     // Convert to NCHW format blob
//     cv::dnn::blobFromImage(normalized, blob, 1.0, cv::Size(input_w, input_h), 
//                           cv::Scalar(0.485, 0.456, 0.406), true, false, CV_32F);
    
//     return blob;
// }

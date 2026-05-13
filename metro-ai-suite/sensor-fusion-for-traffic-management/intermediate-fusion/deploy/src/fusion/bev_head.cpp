#include "bev_head.hpp"
#include "common.hpp"
#include <array>
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

BEVFusionHead::BEVFusionHead(const std::string& model_path, sycl::queue& queue,
     bool use_gpu): opencl_queue_(&queue), use_gpu_inference_(use_gpu) {
    std::cout << "Initializing BEVFusionHead with unified context..." << std::endl;
    
    // Get global context manager
    auto& context_manager = GPUContextManager::getInstance();
    
    if (!context_manager.isInitialized()) {
        throw std::runtime_error("Global GPU context manager not initialized");
    }
    
    // Share the Core object from the global context manager (avoids duplication).
    // cache_dir must be set before compile_model for model caching to take effect.
    core_ = context_manager.getCore();
    core_->set_property(ov::cache_dir("head_cache"));
    model_ = core_->read_model(model_path);

    
    // *** Add preprocessing configuration ***
    ov::preprocess::PrePostProcessor ppp(model_);
    auto &input = ppp.input();
    input.tensor().set_element_type(ov::element::f32).set_layout("NCHW");
    input.model().set_layout("NCHW");

    model_ = ppp.build();    
    
    std::string device = GPUContextManager::cpuDeviceName();
    if (use_gpu) {
        try {
            remote_context_ = context_manager.getSharedContext();
            if (remote_context_) {
                // Use shared context
               std::cout << "Using shared GPU context for Head" << std::endl;
                compiled_model_ = core_->compile_model(model_, *remote_context_,
                    context_manager.getCompileConfig());

            } else {
                // Create new context (original logic)
                auto opencl_queue = sycl::get_native<sycl::backend::opencl>(queue);
                auto remote_context = ov::intel_gpu::ocl::ClContext(*core_, opencl_queue);
                compiled_model_ = core_->compile_model(model_, remote_context,
                        context_manager.getCompileConfig());
                remote_context_ = std::make_shared<ov::intel_gpu::ocl::ClContext>(remote_context);
            }
            
            device = GPUContextManager::sharedGpuContextLabel();
            device_name_ = GPUContextManager::gpuDeviceName();
            use_gpu_inference_ = true;
            std::cout << "Using OpenVINO GPU inference for Head with SYCL queue" << std::endl;
            
        } catch (const std::exception& e) {
            std::cout << "GPU with SYCL queue failed, trying direct GPU: " << e.what() << std::endl;
            
            try {
                // Fallback: use GPU device directly
                compiled_model_ = core_->compile_model(model_, GPUContextManager::gpuDeviceName(),
                    context_manager.getCompileConfig());
                device = GPUContextManager::gpuDeviceName();
                device_name_ = GPUContextManager::gpuDeviceName();
                use_gpu_inference_ = true;
                std::cout << "Using OpenVINO GPU inference for Head (direct GPU)" << std::endl;
                
            } catch (const std::exception& e2) {
                std::cout << "GPU not available for OpenVINO Head, fallback to CPU: " << e2.what() << std::endl;
                compiled_model_ = core_->compile_model(model_, GPUContextManager::cpuDeviceName(),
                    context_manager.getCompileConfig());
                device_name_ = GPUContextManager::cpuDeviceName();
                use_gpu_inference_ = false;
            }
        }
    } else {
        compiled_model_ = core_->compile_model(model_, GPUContextManager::cpuDeviceName(),
            context_manager.getCompileConfig());
        device_name_ = GPUContextManager::cpuDeviceName();
        use_gpu_inference_ = false;
    }
    
    std::cout << "Head OpenVINO device: " << device << std::endl;
    
    // Create inference request with timing
    const auto if_req_t1 = std::chrono::high_resolution_clock::now();
    infer_request_ = compiled_model_.create_infer_request();
    const auto if_req_t2 = std::chrono::high_resolution_clock::now();
    std::cout << "Head InferRequest create " << 
        std::chrono::duration_cast<std::chrono::milliseconds>(if_req_t2 - if_req_t1).count() << "ms" << std::endl;
    
    // Get input/output information
    auto inputs = compiled_model_.inputs();
    auto outputs = compiled_model_.outputs();
    
    std::cout << "Head model has " << inputs.size() << " inputs and " 
              << outputs.size() << " outputs:" << std::endl;
    
    // Get input port (should have only one input: fuser features)
    if (inputs.size() > 0) {
        fuser_input_port_ = inputs[0];
        
        // *** Fix: For dynamic shapes, use get_partial_shape() ***
        auto partial_shape = inputs[0].get_partial_shape();
        std::cout << "  Input: " << inputs[0].get_any_name() 
                  << ", partial_shape: " << partial_shape << std::endl;
        
        // Check if it's a dynamic shape
        if (partial_shape.is_dynamic()) {
            std::cout << "    -> Input has dynamic shape" << std::endl;
        } else {
            std::cout << "    -> Input has static shape: " << partial_shape.to_shape() << std::endl;
        }
    } else {
        throw std::runtime_error("Head model has no inputs");
    }
    
    // Initialize all output ports to empty
    initializeOutputPorts();
    
    // Get output ports and classify by name
    for (size_t i = 0; i < outputs.size(); ++i) {
        auto output_name = outputs[i].get_any_name();
        auto output_shape = outputs[i].get_shape();
        std::cout << "  Output " << i << ": " << output_name 
                  << ", shape: " << output_shape << std::endl;
        assignOutputPortByName(output_name, outputs[i]);
        
        // Store all output ports
        output_ports_[output_name] = outputs[i];
    }
    
    // If name-based identification fails, use index identification
    if (outputs.size() >= 12 && score_output_port_.get_node() == nullptr) {
        std::cout << "Fallback to index-based identification for outputs..." << std::endl;
        assignOutputPortsByIndex(outputs);
    }

    validateModelShapes();

    std::cout << "Head model loaded successfully!" << std::endl;
    std::cout << "Fuser input shape: " << fuser_input_port_.get_shape() << std::endl;
}

BEVFusionHead::~BEVFusionHead() {
    // Best-effort cleanup of USM shared outputs (used in zero-copy mode).
    if (!opencl_queue_) {
        return;
    }
    try {
        auto& q = *opencl_queue_;
        if (score_usm_) sycl::free(score_usm_, q);
        if (rot_usm_) sycl::free(rot_usm_, q);
        if (dim_usm_) sycl::free(dim_usm_, q);
        if (reg_usm_) sycl::free(reg_usm_, q);
        if (height_usm_) sycl::free(height_usm_, q);
        if (vel_usm_) sycl::free(vel_usm_, q);

        if (score2_usm_) sycl::free(score2_usm_, q);
        if (rot2_usm_) sycl::free(rot2_usm_, q);
        if (dim2_usm_) sycl::free(dim2_usm_, q);
        if (reg2_usm_) sycl::free(reg2_usm_, q);
        if (height2_usm_) sycl::free(height2_usm_, q);
        if (vel2_usm_) sycl::free(vel2_usm_, q);
    }
    catch (...) {
        // Never throw from destructor.
    }
}

void BEVFusionHead::ensure_usm_shared(float*& ptr, size_t& cap, size_t elems) {
    if (!opencl_queue_) {
        throw std::runtime_error("BEVFusionHead: SYCL queue is null");
    }
    if (cap >= elems && ptr != nullptr) {
        return;
    }
    if (ptr) {
        sycl::free(ptr, *opencl_queue_);
        ptr = nullptr;
        cap = 0;
    }
    ptr = sycl::malloc_shared<float>(elems, *opencl_queue_);
    if (!ptr) {
        throw std::runtime_error("BEVFusionHead: failed to allocate USM shared output");
    }
    cap = elems;
}

std::array<BEVFusionHead::OutputBinding, 12> BEVFusionHead::outputBindings()
{
    return {
        OutputBinding{"Score", &score_output_port_, &score_host_tensor_, &score_remote_tensor_, &score_usm_, &score_cap_, &last_score_usm_ptr_, &HeadResults::score, &HeadResults::score_ptr, &HeadResults::score_shape},
        OutputBinding{"Rot", &rot_output_port_, &rot_host_tensor_, &rot_remote_tensor_, &rot_usm_, &rot_cap_, &last_rot_usm_ptr_, &HeadResults::rot, &HeadResults::rot_ptr, &HeadResults::rot_shape},
        OutputBinding{"Dim", &dim_output_port_, &dim_host_tensor_, &dim_remote_tensor_, &dim_usm_, &dim_cap_, &last_dim_usm_ptr_, &HeadResults::dim, &HeadResults::dim_ptr, &HeadResults::dim_shape},
        OutputBinding{"Reg", &reg_output_port_, &reg_host_tensor_, &reg_remote_tensor_, &reg_usm_, &reg_cap_, &last_reg_usm_ptr_, &HeadResults::reg, &HeadResults::reg_ptr, &HeadResults::reg_shape},
        OutputBinding{"Height", &height_output_port_, &height_host_tensor_, &height_remote_tensor_, &height_usm_, &height_cap_, &last_height_usm_ptr_, &HeadResults::height, &HeadResults::height_ptr, &HeadResults::height_shape},
        OutputBinding{"Vel", &vel_output_port_, &vel_host_tensor_, &vel_remote_tensor_, &vel_usm_, &vel_cap_, &last_vel_usm_ptr_, &HeadResults::vel, &HeadResults::vel_ptr, &HeadResults::vel_shape},
        OutputBinding{"Score2", &score2_output_port_, &score2_host_tensor_, &score2_remote_tensor_, &score2_usm_, &score2_cap_, &last_score2_usm_ptr_, &HeadResults::score2, &HeadResults::score2_ptr, &HeadResults::score2_shape},
        OutputBinding{"Rot2", &rot2_output_port_, &rot2_host_tensor_, &rot2_remote_tensor_, &rot2_usm_, &rot2_cap_, &last_rot2_usm_ptr_, &HeadResults::rot2, &HeadResults::rot2_ptr, &HeadResults::rot2_shape},
        OutputBinding{"Dim2", &dim2_output_port_, &dim2_host_tensor_, &dim2_remote_tensor_, &dim2_usm_, &dim2_cap_, &last_dim2_usm_ptr_, &HeadResults::dim2, &HeadResults::dim2_ptr, &HeadResults::dim2_shape},
        OutputBinding{"Reg2", &reg2_output_port_, &reg2_host_tensor_, &reg2_remote_tensor_, &reg2_usm_, &reg2_cap_, &last_reg2_usm_ptr_, &HeadResults::reg2, &HeadResults::reg2_ptr, &HeadResults::reg2_shape},
        OutputBinding{"Height2", &height2_output_port_, &height2_host_tensor_, &height2_remote_tensor_, &height2_usm_, &height2_cap_, &last_height2_usm_ptr_, &HeadResults::height2, &HeadResults::height2_ptr, &HeadResults::height2_shape},
        OutputBinding{"Vel2", &vel2_output_port_, &vel2_host_tensor_, &vel2_remote_tensor_, &vel2_usm_, &vel2_cap_, &last_vel2_usm_ptr_, &HeadResults::vel2, &HeadResults::vel2_ptr, &HeadResults::vel2_shape},
    };
}

void BEVFusionHead::assignOutputPortByName(const std::string& output_name, const ov::Output<const ov::Node>& output)
{
    const auto bindings = std::array<std::pair<const char *, ov::Output<const ov::Node> *>, 12>{
        std::make_pair("score", &score_output_port_),
        std::make_pair("rot", &rot_output_port_),
        std::make_pair("dim", &dim_output_port_),
        std::make_pair("reg", &reg_output_port_),
        std::make_pair("height", &height_output_port_),
        std::make_pair("vel", &vel_output_port_),
        std::make_pair("score2", &score2_output_port_),
        std::make_pair("rot2", &rot2_output_port_),
        std::make_pair("dim2", &dim2_output_port_),
        std::make_pair("reg2", &reg2_output_port_),
        std::make_pair("height2", &height2_output_port_),
        std::make_pair("vel2", &vel2_output_port_),
    };

    for (const auto &[name, port] : bindings) {
        if (output_name == name) {
            *port = output;
            std::cout << "    -> Identified as " << name << " output" << std::endl;
            return;
        }
    }
}

void BEVFusionHead::assignOutputPortsByIndex(const std::vector<ov::Output<const ov::Node>>& outputs)
{
    const auto bindings = std::array<std::pair<size_t, ov::Output<const ov::Node> *>, 12>{
        std::make_pair(0u, &score_output_port_),
        std::make_pair(1u, &rot_output_port_),
        std::make_pair(2u, &height_output_port_),
        std::make_pair(3u, &dim_output_port_),
        std::make_pair(4u, &vel_output_port_),
        std::make_pair(5u, &reg_output_port_),
        std::make_pair(6u, &score2_output_port_),
        std::make_pair(7u, &rot2_output_port_),
        std::make_pair(8u, &height2_output_port_),
        std::make_pair(9u, &dim2_output_port_),
        std::make_pair(10u, &vel2_output_port_),
        std::make_pair(11u, &reg2_output_port_),
    };

    for (const auto &[idx, port] : bindings) {
        *port = outputs[idx];
    }
}

HeadResults BEVFusionHead::runInference(const HeadInput& input, bool use_gpu, bool keep_on_gpu) {
    validateInput(input);
    const bool gpu_path = use_gpu && use_gpu_inference_ && remote_context_ != nullptr;
    const auto output_bindings = outputBindings();

    if (gpu_path) {
        try {
            std::cout << "Starting GPU tensor inference for Head..." << std::endl;

            ov::Tensor actual_tensor;
            const auto expected_shape = fuser_input_port_.get_shape();

            if (input.is_gpu_tensor) {
                actual_tensor = input.gpu_tensor;
                // Stability-first: only accept OpenVINO-managed tensors here.
                // If tensor assignment fails, do not attempt to copy via RemoteTensor::data() (unsafe).
                infer_request_.set_tensor(fuser_input_port_, actual_tensor);
                std::cout << "✓ Using ov::Tensor input" << std::endl;
            } else if (input.fused_ptr != nullptr) {
                // Zero-copy: bind USM device pointer directly as RemoteTensor input.
                if (!cached_input_tensor_ || last_input_usm_ptr_ != input.fused_ptr || cached_input_tensor_.get_shape() != expected_shape) {
                    cached_input_tensor_ = remote_context_->create_tensor(
                        fuser_input_port_.get_element_type(), expected_shape, input.fused_ptr);
                    last_input_usm_ptr_ = input.fused_ptr;
                }
                actual_tensor = cached_input_tensor_;
                infer_request_.set_tensor(fuser_input_port_, actual_tensor);
                std::cout << "✓ Using USM device pointer input (zero-copy)" << std::endl;
            } else {
                // CPU data path while model runs on GPU: stage data in a host tensor and let plugin copy
                ov::Tensor host_tensor(fuser_input_port_.get_element_type(), expected_shape);
                auto byte_size = host_tensor.get_byte_size();

                float *dst = host_tensor.data<float>();
                if (input.fuser_features_ptr != nullptr) {
                    std::memcpy(dst, input.fuser_features_ptr, byte_size);
                } else {
                    std::memcpy(dst, input.fuser_features.data(), byte_size);
                }

                infer_request_.set_tensor(fuser_input_port_, host_tensor);
                std::cout << "✓ Uploaded CPU fused features to GPU input" << std::endl;
            }

            if (keep_on_gpu) {
                // Zero-copy outputs: bind all requested outputs to USM shared buffers so CPU postprocess can read directly.
                // (USM shared avoids an explicit device->host copy; it is accessible on host.)
                for (const auto &binding : output_bindings) {
                    if (!binding.port->get_node())
                        continue;
                    const auto shape = binding.port->get_shape();
                    const size_t elems = ov::shape_size(shape);
                    float *&usm_ptr = *binding.usm_ptr;
                    size_t &cap = *binding.usm_cap;
                    void *&last_bound_ptr = *binding.last_bound_ptr;
                    ensure_usm_shared(usm_ptr, cap, elems);
                    if (!*binding.remote_cache || last_bound_ptr != usm_ptr || binding.remote_cache->get_shape() != shape) {
                        *binding.remote_cache = remote_context_->create_tensor(binding.port->get_element_type(), shape, usm_ptr);
                        last_bound_ptr = usm_ptr;
                    }
                    infer_request_.set_tensor(*binding.port, *binding.remote_cache);
                }
            }
            else {
                bindHostOutputTensors();
            }

            auto start = std::chrono::high_resolution_clock::now();
            infer_request_.start_async();
            infer_request_.wait();
            auto end = std::chrono::high_resolution_clock::now();

            auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
            std::cout << "GPU Head inference time: " << duration.count() << " ms" << std::endl;

            HeadResults results;

            if (keep_on_gpu) {
                // Results are in USM shared buffers.
                results.owns_data = false;
                results.is_gpu_results = true;
                for (const auto &binding : output_bindings) {
                    if (!binding.port->get_node())
                        continue;
                    results.*(binding.shape_member) = binding.port->get_shape();
                    results.*(binding.ptr_member) = *binding.usm_ptr;
                }
                return results;
            }

            results.owns_data = true;
            results.is_gpu_results = false;
            extractCPUResults(results);
            return results;

        } catch (const ov::Exception& e) {
            std::cerr << "GPU Head inference failed: " << e.what() << std::endl;
            throw;
        }
    }

    // CPU path
    ov::Tensor input_tensor(fuser_input_port_.get_element_type(), fuser_input_port_.get_shape());
    float* dst = input_tensor.data<float>();
    if (input.fuser_features_ptr != nullptr) {
        std::memcpy(dst, input.fuser_features_ptr, input_tensor.get_byte_size());
    } else {
        std::memcpy(dst, input.fuser_features.data(), input_tensor.get_byte_size());
    }

    infer_request_.set_tensor(fuser_input_port_, input_tensor);
    bindHostOutputTensors();

    auto start = std::chrono::high_resolution_clock::now();
    infer_request_.infer();
    auto end = std::chrono::high_resolution_clock::now();

    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end - start);
    std::cout << "Head inference time: " << duration.count() << " ms" << std::endl;

    HeadResults results;
    results.owns_data = true;
    results.is_gpu_results = false;
    extractCPUResults(results);
    return results;
}

HeadResults BEVFusionHead::inferHead(const HeadInput& input) {
    return runInference(input, use_gpu_inference_, false);
}

HeadResults BEVFusionHead::inferHeadGPU(const HeadInput& input, bool keep_on_gpu) {
    if (!use_gpu_inference_) {
        throw std::runtime_error("GPU inference not enabled for Head");
    }
    return runInference(input, true, keep_on_gpu);
}
HeadInput BEVFusionHead::createHeadInputFromBin(const std::string& bin_file) {
    HeadInput input;
    input.fuser_features = readBinFile(bin_file);
    input.fuser_shape = fuser_input_port_.get_shape(); 
    input.fuser_features_ptr = nullptr;
    input.owns_data = true;
    return input;
}
std::vector<float> BEVFusionHead::readBinFile(const std::string& bin_file) {
    std::ifstream file(bin_file, std::ios::binary);
    if (!file.is_open()) {
        throw std::runtime_error("Cannot open file: " + bin_file);
    }
    
    file.seekg(0, std::ios::end);
    std::streamsize file_size = file.tellg();
    file.seekg(0, std::ios::beg);
    
    size_t num_floats = file_size / sizeof(float);
    std::vector<float> data(num_floats);
    file.read(reinterpret_cast<char*>(data.data()), file_size);
    
    if (!file) {
        throw std::runtime_error("Error reading file: " + bin_file);
    }
    
    file.close();
    std::cout << "Read " << num_floats << " floats from " << bin_file << std::endl;
    return data;
}

HeadInput BEVFusionHead::createHeadInputFromGPUTensor(const ov::Tensor& gpu_tensor, const ov::Shape& shape) {
    HeadInput input;
    
    auto actual_tensor_shape = gpu_tensor.get_shape();
    std::cout << "Creating Head input from GPU tensor:" << std::endl;
    std::cout << "  Actual tensor shape: " << actual_tensor_shape << std::endl;
    std::cout << "  Provided shape: " << shape << std::endl;
    
    std::cout << "  Target shape: " << shape << std::endl;
    
    input.gpu_tensor = gpu_tensor;
    input.fuser_shape = shape;
    input.is_gpu_tensor = true;
    input.owns_data = false;
    input.fuser_features_ptr = nullptr;  // GPU tensor doesn't provide pointer
    // Note: any shape mismatches should be handled by callers before binding.
    
    std::cout << "✓ Head input created from GPU tensor" << std::endl;
    return input;
}
HeadInput BEVFusionHead::createHeadInputFromPointer(float* fuser_ptr, const ov::Shape& fuser_shape) {
    HeadInput input;
    // Prefer treating this as a GPU/USM pointer (zero-copy input binding path).
    input.fused_ptr = fuser_ptr;
    input.fused_shape = fuser_shape;
    // Keep backward-compatibility: some callers still expect fuser_features_ptr.
    input.fuser_features_ptr = fuser_ptr;
    input.fuser_shape = fuser_shape;
    input.owns_data = false;
    return input;
}

ov::Shape BEVFusionHead::getFuserInputShape() const {
    return fuser_input_port_.get_shape();
}

void BEVFusionHead::printOutputInfo() const {
    std::cout << "\n=== Head Model Output Information ===" << std::endl;
    for (const auto& [name, port] : output_ports_) {
        std::cout << "Output '" << name << "': shape " << port.get_shape() << std::endl;
    }
}

void BEVFusionHead::initializeOutputPorts() {
    score_output_port_ = ov::Output<const ov::Node>();
    rot_output_port_ = ov::Output<const ov::Node>();
    dim_output_port_ = ov::Output<const ov::Node>();
    reg_output_port_ = ov::Output<const ov::Node>();
    height_output_port_ = ov::Output<const ov::Node>();
    vel_output_port_ = ov::Output<const ov::Node>();
    
    score2_output_port_ = ov::Output<const ov::Node>();
    rot2_output_port_ = ov::Output<const ov::Node>();
    dim2_output_port_ = ov::Output<const ov::Node>();
    reg2_output_port_ = ov::Output<const ov::Node>();
    height2_output_port_ = ov::Output<const ov::Node>();
    vel2_output_port_ = ov::Output<const ov::Node>();
}

void BEVFusionHead::validateModelShapes() const {
    const auto input_shape = fuser_input_port_.get_shape();
    if (input_shape.size() != 4) {
        throw std::runtime_error("Head expects a 4D input tensor, got " + shape_to_string(input_shape));
    }

    const auto validate_output = [&](const ov::Output<const ov::Node>& port, const char* name) {
        if (!port.get_node()) {
            throw std::runtime_error(std::string("Missing head output: ") + name);
        }
        const auto shape = port.get_shape();
        if (shape.size() != 4) {
            throw std::runtime_error(std::string("Head output ") + name + " must be 4D, got " + shape_to_string(shape));
        }
        if (shape[0] != input_shape[0] || shape[2] != input_shape[2] || shape[3] != input_shape[3]) {
            throw std::runtime_error(std::string("Head output ") + name + " shape mismatch: expected batch/H/W to match input " +
                                     shape_to_string(input_shape) + ", got " + shape_to_string(shape));
        }
    };

    validate_output(score_output_port_, "score");
    validate_output(rot_output_port_, "rot");
    validate_output(dim_output_port_, "dim");
    validate_output(reg_output_port_, "reg");
    validate_output(height_output_port_, "height");
    validate_output(vel_output_port_, "vel");
    validate_output(score2_output_port_, "score2");
    validate_output(rot2_output_port_, "rot2");
    validate_output(dim2_output_port_, "dim2");
    validate_output(reg2_output_port_, "reg2");
    validate_output(height2_output_port_, "height2");
    validate_output(vel2_output_port_, "vel2");
}

void BEVFusionHead::validateInput(const HeadInput& input) const {
    const auto expected_shape = fuser_input_port_.get_shape();
    const bool has_gpu_tensor = input.is_gpu_tensor;
    const bool has_zero_copy_ptr = input.fused_ptr != nullptr;
    const bool has_host_vector = !input.fuser_features.empty();
    const bool has_host_ptr = input.fuser_features_ptr != nullptr && !has_zero_copy_ptr;

    const int active_sources = static_cast<int>(has_gpu_tensor) + static_cast<int>(has_zero_copy_ptr) +
                               static_cast<int>(has_host_vector || has_host_ptr);
    if (active_sources != 1) {
        throw std::runtime_error("HeadInput must provide exactly one input source: gpu tensor, zero-copy pointer, or host data");
    }

    auto validate_shape = [&](const ov::Shape& shape, const char* name) {
        if (!shape.empty() && shape != expected_shape) {
            throw std::runtime_error(std::string(name) + " shape mismatch: expected " +
                                     shape_to_string(expected_shape) + ", got " + shape_to_string(shape));
        }
    };

    if (has_gpu_tensor) {
        validate_shape(input.fuser_shape, "Head input");
        if (input.gpu_tensor.get_shape() != expected_shape) {
            throw std::runtime_error("GPU head input tensor shape mismatch: expected " +
                                     shape_to_string(expected_shape) + ", got " + shape_to_string(input.gpu_tensor.get_shape()));
        }
        return;
    }

    if (has_zero_copy_ptr) {
        const ov::Shape& provided_shape = !input.fused_shape.empty() ? input.fused_shape : input.fuser_shape;
        if (provided_shape.empty()) {
            throw std::runtime_error("Zero-copy HeadInput must provide fused_shape or fuser_shape metadata");
        }
        validate_shape(provided_shape, "Zero-copy head input");
        return;
    }

    validate_shape(input.fuser_shape, "Host head input");
    const size_t expected_bytes = ov::shape_size(expected_shape) * sizeof(float);
    if (has_host_vector && input.fuser_features.size() * sizeof(float) != expected_bytes) {
        throw std::runtime_error("Host head input size mismatch: expected " + std::to_string(expected_bytes) +
                                 " bytes, got " + std::to_string(input.fuser_features.size() * sizeof(float)));
    }
}

void BEVFusionHead::ensureHostOutputTensor(const ov::Output<const ov::Node>& port, ov::Tensor& cache) {
    if (!port.get_node()) {
        return;
    }
    if (!cache || cache.get_shape() != port.get_shape() || cache.get_element_type() != port.get_element_type()) {
        cache = ov::Tensor(port.get_element_type(), port.get_shape());
    }
}

void BEVFusionHead::bindHostOutputTensors() {
    for (const auto &binding : outputBindings()) {
        ensureHostOutputTensor(*binding.port, *binding.host_cache);
        if (binding.port->get_node()) {
            infer_request_.set_tensor(*binding.port, *binding.host_cache);
        }
    }
}

void BEVFusionHead::extractCPUResults(HeadResults& results) {
    const auto output_bindings = outputBindings();

    for (const auto &binding : output_bindings) {
        if (binding.port->get_node() == nullptr) {
            continue;
        }
        ov::Tensor tensor = *binding.host_cache ? *binding.host_cache : infer_request_.get_tensor(*binding.port);
        float* data = tensor.data<float>();
        size_t size = tensor.get_size();
        auto &dst = results.*(binding.data_member);
        dst.assign(data, data + size);
        results.*(binding.ptr_member) = dst.data();
        results.*(binding.shape_member) = binding.port->get_shape();
        std::cout << binding.name << " output size: " << size << ", shape: " << (results.*(binding.shape_member)) << std::endl;
    }
}



// Helper function to save HeadResults to bin files - supports 12 outputs
void saveHeadResultsToBin(const HeadResults& results, const std::string& output_dir) {
    std::filesystem::create_directories(output_dir);
    
    auto saveTensor = [](const std::vector<float>& data, float* ptr, bool owns_data, 
                        const std::string& filename, const ov::Shape& shape) {
        std::ofstream file(filename, std::ios::binary);
        if (owns_data && !data.empty()) {
            file.write(reinterpret_cast<const char*>(data.data()), 
                      data.size() * sizeof(float));
            std::cout << "Saved " << data.size() << " floats to " << filename << std::endl;
        } else if (ptr != nullptr) {
            // Calculate tensor size
            size_t tensor_size = 1;
            for (auto dim : shape) {
                tensor_size *= dim;
            }
            file.write(reinterpret_cast<const char*>(ptr), 
                      tensor_size * sizeof(float));
            std::cout << "Saved " << tensor_size << " floats to " << filename << std::endl;
        }
        file.close();
    };
    
    // Save first set of outputs
    saveTensor(results.score, results.score_ptr, results.owns_data, 
               output_dir + "/score.bin", results.score_shape);
    saveTensor(results.rot, results.rot_ptr, results.owns_data, 
               output_dir + "/rot.bin", results.rot_shape);
    saveTensor(results.dim, results.dim_ptr, results.owns_data, 
               output_dir + "/dim.bin", results.dim_shape);
    saveTensor(results.reg, results.reg_ptr, results.owns_data, 
               output_dir + "/reg.bin", results.reg_shape);
    saveTensor(results.height, results.height_ptr, results.owns_data, 
               output_dir + "/height.bin", results.height_shape);
    saveTensor(results.vel, results.vel_ptr, results.owns_data, 
               output_dir + "/vel.bin", results.vel_shape);
    
    // Save second set of outputs
    saveTensor(results.score2, results.score2_ptr, results.owns_data, 
               output_dir + "/score2.bin", results.score2_shape);
    saveTensor(results.rot2, results.rot2_ptr, results.owns_data, 
               output_dir + "/rot2.bin", results.rot2_shape);
    saveTensor(results.dim2, results.dim2_ptr, results.owns_data, 
               output_dir + "/dim2.bin", results.dim2_shape);
    saveTensor(results.reg2, results.reg2_ptr, results.owns_data, 
               output_dir + "/reg2.bin", results.reg2_shape);
    saveTensor(results.height2, results.height2_ptr, results.owns_data, 
               output_dir + "/height2.bin", results.height2_shape);
    saveTensor(results.vel2, results.vel2_ptr, results.owns_data, 
               output_dir + "/vel2.bin", results.vel2_shape);
}
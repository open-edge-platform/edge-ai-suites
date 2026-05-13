// gpu_context_manager.hpp
#ifndef GPU_CONTEXT_MANAGER_HPP
#define GPU_CONTEXT_MANAGER_HPP

#include <openvino/openvino.hpp>
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>
#include <sycl/sycl.hpp>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>

class GPUContextManager {
public:
    static GPUContextManager& getInstance() {
        static GPUContextManager instance;
        return instance;
    }

    static constexpr const char* cpuDeviceName() noexcept {
        return "CPU";
    }

    static const std::string& gpuDeviceName() {
        return getInstance().resolved_gpu_device_name_;
    }

    static const std::string& sharedGpuContextLabel() {
        return getInstance().shared_gpu_context_label_;
    }
    
    // Initialize global GPU context.
    // use_fp32=true  : force GPU inference precision to fp32 for all compiled models
    //                  (required when running non-quantized fp32 ONNX/IR models —
    //                   the GPU plugin defaults to fp16, which causes Inf/NaN propagation
    //                   through the deep BEV pipeline and collapses all detections).
    // use_fp32=false : let the GPU plugin choose its default precision (fp16),
    //                  which is correct and faster for quantized/int8 models.
    // enable_model_cache=false : skip OV compiled-model cache setup for call sites
    //                            that hit incorrect cached GPU blobs.
    bool initialize(sycl::queue& queue, bool use_fp32 = false, bool enable_model_cache = true) {
        try {
            std::cout << "Initializing global GPU context (mode: "
                      << (use_fp32 ? "fp32" : "int8/fp16") << ")..." << std::endl;
            
            // Save SYCL queue reference
            sycl_queue_ = &queue;
            
            // Create OpenVINO Core
            core_ = std::make_shared<ov::Core>();

            if (enable_model_cache) {
                // Enable model cache for faster warm startup. OV_CACHE_DIR has
                // priority; otherwise use $HOME/.cache/bevfusion_ov.
                const char* cache_env = std::getenv("OV_CACHE_DIR");
                const std::string cache_dir = (cache_env && *cache_env)
                    ? std::string(cache_env)
                    : std::string(std::getenv("HOME") ? std::getenv("HOME") : "/tmp") +
                          "/.cache/bevfusion_ov";
                core_->set_property(ov::cache_dir(cache_dir));
                std::cout << "  cache_dir: " << cache_dir << std::endl;
            } else {
                std::cout << "  cache_dir: disabled" << std::endl;
            }
            
            // Global GPU performance configuration.
            core_->set_property(ov::hint::performance_mode(ov::hint::PerformanceMode::LATENCY));
            if (use_fp32) {
                // Prevent the GPU plugin from silently downcasting fp32 models to fp16.
                core_->set_property("GPU", ov::hint::inference_precision(ov::element::f32));
            }
            
            // Create the OpenVINO GPU context from the exact OpenCL queue that
            // the SYCL pipeline already uses, so both stacks target the same
            // physical card instead of relying on a fragile GPU.x index.
            auto opencl_queue_native = sycl::get_native<sycl::backend::opencl>(queue);
            auto raw_ctx = ov::intel_gpu::ocl::ClContext(*core_, opencl_queue_native);
            resolved_gpu_device_name_ = raw_ctx.get_device_name();
            if (resolved_gpu_device_name_.empty()) {
                resolved_gpu_device_name_ = "GPU";
            }
            shared_gpu_context_label_ = "GPU(shared:" + resolved_gpu_device_name_ + ")";
            shared_context_ = std::make_shared<ov::intel_gpu::ocl::ClContext>(raw_ctx);
            std::cout << "  OpenVINO GPU device: " << resolved_gpu_device_name_ << std::endl;
            
            std::cout << "✓ Global GPU context initialized successfully" << std::endl;
            return true;
            
        } catch (const std::exception& e) {
            std::cerr << "Failed to initialize global GPU context: " << e.what() << std::endl;
            return false;
        }
    }
    
    // Get shared GPU context
    std::shared_ptr<ov::intel_gpu::ocl::ClContext> getSharedContext() const {
        return shared_context_;
    }
    
    // Get OpenVINO Core
    std::shared_ptr<ov::Core> getCore() const {
        return core_;
    }
    
    // Get SYCL queue
    sycl::queue* getSYCLQueue() const {
        return sycl_queue_;
    }
    
    // Returns compile-time properties for compile_model() calls.
    // Precision is already governed globally by the use_fp32 flag passed to initialize(),
    // so this only needs to carry performance_mode.
    ov::AnyMap getCompileConfig() const {
        ov::AnyMap config;
        config[ov::hint::performance_mode.name()] = ov::hint::PerformanceMode::LATENCY;
        return config;
    }

    // Check if initialized
    bool isInitialized() const {
        return shared_context_ != nullptr && core_ != nullptr;
    }

private:
    GPUContextManager() = default;
    ~GPUContextManager() = default;
    GPUContextManager(const GPUContextManager&) = delete;
    GPUContextManager& operator=(const GPUContextManager&) = delete;
    
    std::shared_ptr<ov::intel_gpu::ocl::ClContext> shared_context_;
    std::shared_ptr<ov::Core> core_;
    sycl::queue* sycl_queue_ = nullptr;
    std::string resolved_gpu_device_name_{"GPU"};
    std::string shared_gpu_context_label_{"GPU(shared)"};
};

#endif // GPU_CONTEXT_MANAGER_HPP
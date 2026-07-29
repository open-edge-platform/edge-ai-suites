// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "pointpillars/pointpillars.hpp"
#include "gpu_context_manager.hpp"

#include <chrono>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <sycl/backend/opencl.hpp>
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>

namespace pointpillars {

PointPillars::PointPillars(const PointPillarsConfig& config,
                               const std::string& device,
                               sycl::queue& queue)
    : cfg_(config), device_(device), queue_(queue) {
    std::cout << "[PointPillars] device='" << device_ << "' model='"
              << cfg_.pfe_model_file << "'" << std::endl;

    // Build voxelizer from the same geometry the training uses.
    VoxelizerConfig vcfg;
    std::memcpy(vcfg.pc_range.data(), cfg_.pc_range, sizeof(cfg_.pc_range));
    std::memcpy(vcfg.voxel_size.data(), cfg_.voxel_size, sizeof(cfg_.voxel_size));
    vcfg.max_num_points_per_voxel = cfg_.max_num_points_per_voxel;
    vcfg.max_voxels = cfg_.max_voxels;
    vcfg.point_dim = cfg_.point_dim;
    voxelizer_ = std::make_unique<Voxelizer>(queue_, vcfg);

    scatter_ = std::make_unique<Scatter>(cfg_.num_features, cfg_.grid_x, cfg_.grid_y, queue_);

    allocate_();
    setup_pfe_network_();
}

PointPillars::~PointPillars() {
    try { free_(); } catch (...) {}
}

void PointPillars::allocate_() {
    const size_t V_max = cfg_.max_voxels;
    const size_t C     = cfg_.num_features;

    pfe_output_ = sycl::malloc_device<float>(V_max * C, queue_);
    dev_scattered_feature_ = sycl::malloc_device<float>(
        static_cast<size_t>(C) * cfg_.grid_x * cfg_.grid_y, queue_);
}

void PointPillars::free_() {
    auto rel = [&](auto*& p) { if (p) { sycl::free(p, queue_); p = nullptr; } };
    rel(dev_points_);
    rel(pfe_output_);
    rel(dev_scattered_feature_);
}

void PointPillars::setup_pfe_network_() {
    auto& ctx_mgr = GPUContextManager::getInstance();
    if (!ctx_mgr.isInitialized()) {
        throw std::runtime_error("GPUContextManager not initialized");
    }
    auto core = ctx_mgr.getCore();
    if (!core) {
        throw std::runtime_error("GPUContextManager returned null Core");
    }
    core->set_property(ov::cache_dir("pointpillars_cache"));

    std::string ov_device = queue_.get_device().is_gpu() ? device_ : std::string("CPU");

    auto model = core->read_model(cfg_.pfe_model_file);

    // Log input shapes to help spot schema drift.
    for (const auto& in : model->inputs()) {
        std::cout << "  [PFE input] " << in.get_any_name() << " "
                  << in.get_partial_shape() << " "
                  << in.get_element_type() << std::endl;
    }
    for (const auto& out : model->outputs()) {
        std::cout << "  [PFE output] " << out.get_any_name() << " "
                  << out.get_partial_shape() << " "
                  << out.get_element_type() << std::endl;
    }

    // Detect static-V ONNX: if "features" input has a fully specified rank
    // with concrete dim[0], the graph was exported with --fixed-v and we can
    // bind tensors once at startup (saves per-frame create_tensor/set_tensor).
    pfe_is_static_ = false;
    pfe_static_V_ = 0;
    for (const auto& in : model->inputs()) {
        if (in.get_any_name() == "features") {
            const auto ps = in.get_partial_shape();
            if (ps.is_static() && ps.size() == 3) {
                pfe_is_static_ = true;
                pfe_static_V_ = static_cast<int>(ps[0].get_length());
            }
            break;
        }
    }
    if (pfe_is_static_) {
        std::cout << "[PointPillars] PFE ONNX is static: V=" << pfe_static_V_
                  << "; will bind tensors once and skip per-frame reshape." << std::endl;
        if (pfe_static_V_ != cfg_.max_voxels) {
            std::cout << "[PointPillars] WARNING: PFE static V=" << pfe_static_V_
                      << " != voxelizer max_voxels=" << cfg_.max_voxels
                      << ". Setting voxelizer max_voxels to PFE V for consistency." << std::endl;
            cfg_.max_voxels = pfe_static_V_;
            // Rebuild the voxelizer with the corrected max_voxels. This
            // frees+reallocates its internal buffers; safe to do before
            // first run().
            VoxelizerConfig vcfg;
            std::memcpy(vcfg.pc_range.data(), cfg_.pc_range, sizeof(cfg_.pc_range));
            std::memcpy(vcfg.voxel_size.data(), cfg_.voxel_size, sizeof(cfg_.voxel_size));
            vcfg.max_num_points_per_voxel = cfg_.max_num_points_per_voxel;
            vcfg.max_voxels = cfg_.max_voxels;
            vcfg.point_dim = cfg_.point_dim;
            voxelizer_ = std::make_unique<Voxelizer>(queue_, vcfg);
            // pfe_output_ was sized to old max_voxels — rebuild too.
            if (pfe_output_) { sycl::free(pfe_output_, queue_); pfe_output_ = nullptr; }
            pfe_output_ = sycl::malloc_device<float>(
                static_cast<size_t>(cfg_.max_voxels) * cfg_.num_features, queue_);
        }
    } else {
        std::cout << "[PointPillars] PFE ONNX has dynamic V; using per-frame set_tensor." << std::endl;
    }

    // Compile.
    if (ov_device == "CPU") {
        pfe_compiled_ = core->compile_model(model, ov_device,
            ov::hint::performance_mode(ov::hint::PerformanceMode::LATENCY));
    } else {
        auto shared_context = ctx_mgr.getSharedContext();
        if (!shared_context) {
            throw std::runtime_error("Shared GPU context is null");
        }
        pfe_compiled_ = core->compile_model(model, *shared_context,
            ov::hint::performance_mode(ov::hint::PerformanceMode::LATENCY));
    }

    pfe_request_ = pfe_compiled_.create_infer_request();

    if (pfe_is_static_) {
        bind_static_tensors_();
    }
}

void PointPillars::bind_static_tensors_() {
    const auto el_f32 = ov::element::f32;
    const auto el_i32 = ov::element::i32;
    const int V = pfe_static_V_;
    const ov::Shape feat_shape{
        static_cast<size_t>(V),
        static_cast<size_t>(cfg_.max_num_points_per_voxel),
        static_cast<size_t>(cfg_.point_dim),
    };
    const ov::Shape num_shape{static_cast<size_t>(V)};
    const ov::Shape coors_shape{static_cast<size_t>(V), 4};
    const ov::Shape out_shape{static_cast<size_t>(V),
                              static_cast<size_t>(cfg_.num_features)};

    if (queue_.get_device().is_cpu()) {
        pfe_request_.set_tensor("features",
            ov::Tensor(el_f32, feat_shape,  voxelizer_->features_device()));
        pfe_request_.set_tensor("num_voxels",
            ov::Tensor(el_i32, num_shape,   voxelizer_->num_voxels_device()));
        pfe_request_.set_tensor("coors",
            ov::Tensor(el_i32, coors_shape, voxelizer_->coors_device()));
        pfe_request_.set_tensor("pillar_features",
            ov::Tensor(el_f32, out_shape,   pfe_output_));
    } else {
        auto remote_context = pfe_compiled_.get_context()
                                .as<ov::intel_gpu::ocl::ClContext>();
        pfe_request_.set_tensor("features", remote_context.create_tensor(
            el_f32, feat_shape, voxelizer_->features_device()));
        pfe_request_.set_tensor("num_voxels", remote_context.create_tensor(
            el_i32, num_shape, voxelizer_->num_voxels_device()));
        pfe_request_.set_tensor("coors", remote_context.create_tensor(
            el_i32, coors_shape, voxelizer_->coors_device()));
        pfe_request_.set_tensor("pillar_features", remote_context.create_tensor(
            el_f32, out_shape, pfe_output_));
    }
}

void PointPillars::run_pfe_(int V) {
    // Fast path: static V. Tensors were bound once in the ctor pointing at the
    // voxelizer's device buffers (which have a fresh memset(0) at each run()
    // call, so padding rows are well-defined zeros with num_voxels=0).
    if (pfe_is_static_) {
        pfe_request_.start_async();
        pfe_request_.wait();
        return;
    }

    // Dynamic V path.
    const auto el_f32 = ov::element::f32;
    const auto el_i32 = ov::element::i32;

    const ov::Shape feat_shape{
        static_cast<size_t>(V),
        static_cast<size_t>(cfg_.max_num_points_per_voxel),
        static_cast<size_t>(cfg_.point_dim),
    };
    const ov::Shape num_shape{static_cast<size_t>(V)};
    const ov::Shape coors_shape{static_cast<size_t>(V), 4};

    if (queue_.get_device().is_cpu()) {
        pfe_request_.set_tensor("features",
            ov::Tensor(el_f32, feat_shape, voxelizer_->features_device()));
        pfe_request_.set_tensor("num_voxels",
            ov::Tensor(el_i32, num_shape, voxelizer_->num_voxels_device()));
        pfe_request_.set_tensor("coors",
            ov::Tensor(el_i32, coors_shape, voxelizer_->coors_device()));
        const ov::Shape out_shape{static_cast<size_t>(V),
                                  static_cast<size_t>(cfg_.num_features)};
        pfe_request_.set_tensor("pillar_features",
            ov::Tensor(el_f32, out_shape, pfe_output_));
    } else {
        auto remote_context = pfe_compiled_.get_context()
                                .as<ov::intel_gpu::ocl::ClContext>();
        pfe_request_.set_tensor("features", remote_context.create_tensor(
            el_f32, feat_shape, voxelizer_->features_device()));
        pfe_request_.set_tensor("num_voxels", remote_context.create_tensor(
            el_i32, num_shape, voxelizer_->num_voxels_device()));
        pfe_request_.set_tensor("coors", remote_context.create_tensor(
            el_i32, coors_shape, voxelizer_->coors_device()));
        const ov::Shape out_shape{static_cast<size_t>(V),
                                  static_cast<size_t>(cfg_.num_features)};
        pfe_request_.set_tensor("pillar_features", remote_context.create_tensor(
            el_f32, out_shape, pfe_output_));
    }

    pfe_request_.start_async();
    pfe_request_.wait();
}

void PointPillars::Detect(const float* in_points_array, int in_num_points,
                            float* scattered_feature, PointPillarsTiming* timing) {
    if (timing) {
        *timing = {};
    }
    const auto t0 = std::chrono::high_resolution_clock::now();

    // 1. Stage points to device.
    const size_t needed = static_cast<size_t>(in_num_points) * cfg_.point_dim;
    if (dev_points_capacity_ < in_num_points) {
        if (dev_points_) {
            queue_.wait_and_throw();
            sycl::free(dev_points_, queue_);
            dev_points_ = nullptr;
        }
        dev_points_ = sycl::malloc_device<float>(needed, queue_);
        if (!dev_points_) throw std::runtime_error("PointPillars: malloc failed");
        dev_points_capacity_ = in_num_points;
    }
    queue_.memcpy(dev_points_, in_points_array, needed * sizeof(float)).wait();

    // 2. Voxelize.
    const int V = voxelizer_->run(dev_points_, in_num_points);
    queue_.wait_and_throw();
    const auto t1 = std::chrono::high_resolution_clock::now();
    const double pre_ms = std::chrono::duration_cast<
        std::chrono::duration<double, std::milli>>(t1 - t0).count();
    if (timing) timing->preprocess_ms = pre_ms;

    // 3. Kick canvas memset to sycl queue (overlaps with PFE, see DetectAndGetPointer).
    const size_t canvas_size = static_cast<size_t>(cfg_.num_features)
                             * cfg_.grid_x * cfg_.grid_y;
    queue_.memset(dev_scattered_feature_, 0, canvas_size * sizeof(float));

    // 4. PFE inference.
    if (V > 0) {
        run_pfe_(V);
    }
    const auto t2 = std::chrono::high_resolution_clock::now();
    const double pfe_ms = std::chrono::duration_cast<
        std::chrono::duration<double, std::milli>>(t2 - t1).count();
    if (timing) timing->pfe_ms = pfe_ms;

    // 5. Scatter.
    if (V > 0) {
        scatter_->run(V, voxelizer_->coors_device(), pfe_output_, dev_scattered_feature_);
    }
    queue_.wait_and_throw();
    const auto t3 = std::chrono::high_resolution_clock::now();
    const double scatter_ms = std::chrono::duration_cast<
        std::chrono::duration<double, std::milli>>(t3 - t2).count();
    if (timing) timing->scatter_ms = scatter_ms;

    latency_.add(pre_ms, pfe_ms, scatter_ms);

    // 5. Copy to host.
    queue_.memcpy(scattered_feature, dev_scattered_feature_,
                  canvas_size * sizeof(float)).wait();
}

void PointPillars::Detect(const float* in_points_array, int in_num_points,
                            float* scattered_feature, size_t* dur) {
    PointPillarsTiming timing;
    Detect(in_points_array, in_num_points, scattered_feature, &timing);
    if (dur) {
        dur[0] += static_cast<size_t>(timing.preprocess_ms);
        dur[1] += static_cast<size_t>(timing.pfe_ms);
        dur[2] += static_cast<size_t>(timing.scatter_ms);
    }
}

float* PointPillars::DetectAndGetPointer(const float* in_points_array,
                                           int in_num_points, PointPillarsTiming* timing) {
    if (timing) {
        *timing = {};
    }
    const auto t0 = std::chrono::high_resolution_clock::now();

    const size_t needed = static_cast<size_t>(in_num_points) * cfg_.point_dim;
    if (dev_points_capacity_ < in_num_points) {
        if (dev_points_) {
            queue_.wait_and_throw();
            sycl::free(dev_points_, queue_);
            dev_points_ = nullptr;
        }
        dev_points_ = sycl::malloc_device<float>(needed, queue_);
        if (!dev_points_) throw std::runtime_error("PointPillars: malloc failed");
        dev_points_capacity_ = in_num_points;
    }
    queue_.memcpy(dev_points_, in_points_array, needed * sizeof(float)).wait();

    const int V = voxelizer_->run(dev_points_, in_num_points);
    queue_.wait_and_throw();
    const auto t1 = std::chrono::high_resolution_clock::now();
    const double pre_ms = std::chrono::duration_cast<
        std::chrono::duration<double, std::milli>>(t1 - t0).count();
    if (timing) timing->preprocess_ms = pre_ms;

    // Kick off canvas zero-fill BEFORE PFE so it overlaps with PFE on the GPU
    // (sycl queue is in-flight; driver schedules the tiny 4MB memset in
    // parallel with PFE's compute kernels). No .wait() here — scatter is
    // serialized after it by the in-order sycl queue.
    const size_t canvas_size = static_cast<size_t>(cfg_.num_features)
                             * cfg_.grid_x * cfg_.grid_y;
    queue_.memset(dev_scattered_feature_, 0, canvas_size * sizeof(float));

    if (V > 0) run_pfe_(V);
    const auto t2 = std::chrono::high_resolution_clock::now();
    const double pfe_ms = std::chrono::duration_cast<
        std::chrono::duration<double, std::milli>>(t2 - t1).count();
    if (timing) timing->pfe_ms = pfe_ms;

    // Scatter reads pfe_output_. OV writes it on OV's internal GPU queue —
    // independent of our sycl queue. The first sycl kernel reading pfe_output_
    // implicitly stalls on the OV writes, so the cost reported as "scatter"
    // includes PFE's tail sync.
    if (V > 0) {
        scatter_->run(V, voxelizer_->coors_device(), pfe_output_, dev_scattered_feature_);
    }
    queue_.wait_and_throw();
    const auto t3 = std::chrono::high_resolution_clock::now();
    const double scatter_ms = std::chrono::duration_cast<
        std::chrono::duration<double, std::milli>>(t3 - t2).count();
    if (timing) timing->scatter_ms = scatter_ms;
    latency_.add(pre_ms, pfe_ms, scatter_ms);

    return dev_scattered_feature_;
}

float* PointPillars::DetectAndGetPointer(const float* in_points_array,
                                           int in_num_points, size_t* dur) {
    PointPillarsTiming timing;
    float* result = DetectAndGetPointer(in_points_array, in_num_points, &timing);
    if (dur) {
        dur[0] += static_cast<size_t>(timing.preprocess_ms);
        dur[1] += static_cast<size_t>(timing.pfe_ms);
        dur[2] += static_cast<size_t>(timing.scatter_ms);
    }
    return result;
}

}  // namespace pointpillars

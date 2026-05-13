// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// BEVFusionUnifiedPipeline — single-ONNX BEV fusion inference.
// GPUContextManager + RemoteTensor zero-copy + OpenVINO PPP image preprocess +
// camera-geometry.hpp V2XFusion ray method + histogram voxelizer.

#pragma once

#include <array>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

#include <opencv2/opencv.hpp>
#include <openvino/openvino.hpp>
#include <openvino/runtime/intel_gpu/ocl/ocl.hpp>
#include <sycl/sycl.hpp>

#include "configs.hpp"
#include "gpu_context_manager.hpp"
#include "latency_stats.hpp"
#include "pipeline/calib_metas.hpp"
#include "pipeline/dataset_preset.hpp"
#include "cam_bev/camera-geometry.hpp"
#include "bevfusion_unified/bevfusion_unified_configs.hpp"
#include "bevfusion_unified/voxelizer_sycl.hpp"
#include "postprocess_cpu.hpp"

namespace bevfusion_unified {

using UnifiedDatasetPreset = bevfusion::DatasetPreset;

struct PipelineConfig {
    std::string onnx_path;
    std::vector<int> filter_labels{7, 8};

    int image_width{1536};
    int image_height{864};
    int num_camera{1};
    std::array<float, 3> mean{123.675f, 116.28f, 103.53f};
    std::array<float, 3> std{58.395f, 57.12f, 57.375f};

    bevfusion::camera::GeometryParameter geom{};
    VoxelizeConfig voxel{};
    PostProcessParams post;

    PipelineConfig() {
        post = PostProcessParams::bevfusionDefaults();
        voxel.max_voxels = 80000;
        geom = bevfusion::camera::make_v2xfusion_geometry_parameter();
    }
};

inline const char* unified_dataset_preset_name(UnifiedDatasetPreset preset)
{
    return bevfusion::dataset_preset_name(preset);
}

inline bool unified_recompute_camera_metas(UnifiedDatasetPreset preset)
{
    return bevfusion::dataset_recompute_camera_metas(preset);
}

inline void apply_unified_dataset_preset(PipelineConfig& cfg, UnifiedDatasetPreset preset)
{
    cfg.post = PostProcessParams::bevfusionDefaults();
    cfg.voxel.voxel_size[0] = 0.1f;
    cfg.voxel.voxel_size[1] = 0.1f;
    cfg.voxel.voxel_size[2] = 0.2f;
    cfg.voxel.max_num_points = 10;
    cfg.voxel.max_voxels = 80000;
    cfg.voxel.reduce_mean = true;
    cfg.voxel.in_channels = 4;
    cfg.num_camera = 1;
    const auto& dims = bevfusion::dataset_preset_geometry(preset);
    cfg.image_width = dims.image_width;
    cfg.image_height = dims.image_height;
    cfg.geom = bevfusion::camera::make_v2xfusion_geometry_parameter(
        static_cast<unsigned int>(dims.feat_width),
        static_cast<unsigned int>(dims.feat_height),
        static_cast<unsigned int>(dims.image_width),
        static_cast<unsigned int>(dims.image_height),
        1);
    cfg.geom.xbound = dims.xbound;
    cfg.geom.ybound = dims.ybound;
    cfg.geom.zbound = dims.zbound;
    cfg.geom.dbound = dims.dbound;
    cfg.geom.geometry_dim = bevfusion::types::Int3(dims.bev_side, dims.bev_side, 80);

    cfg.voxel.pc_range_min[0] = dims.pc_range_min[0];
    cfg.voxel.pc_range_min[1] = dims.pc_range_min[1];
    cfg.voxel.pc_range_min[2] = dims.pc_range_min[2];
    cfg.voxel.pc_range_max[0] = dims.pc_range_max[0];
    cfg.voxel.pc_range_max[1] = dims.pc_range_max[1];
    cfg.voxel.pc_range_max[2] = dims.pc_range_max[2];
    cfg.voxel.grid_size[0] = dims.unified_grid_size[0];
    cfg.voxel.grid_size[1] = dims.unified_grid_size[1];
    cfg.voxel.grid_size[2] = dims.unified_grid_size[2];
    cfg.post.pc_range_min = dims.pc_range_min;
    cfg.post.pc_range_max = dims.pc_range_max;
    cfg.post.post_center_limit_range[0] = dims.post_center_min[0];
    cfg.post.post_center_limit_range[1] = dims.post_center_min[1];
    cfg.post.post_center_limit_range[2] = dims.post_center_min[2];
    cfg.post.post_center_limit_range[3] = dims.post_center_max[0];
    cfg.post.post_center_limit_range[4] = dims.post_center_max[1];
    cfg.post.post_center_limit_range[5] = dims.post_center_max[2];

}

class BEVFusionUnifiedPipeline {
public:
    struct PerfStats {
        std::size_t frames{0};
        double sum_voxelize_ms{0};
        double sum_preprocess_ms{0};
        double sum_geometry_ms{0};
        double sum_infer_ms{0};
        double sum_postprocess_ms{0};
        double sum_total_ms{0};
    };

    BEVFusionUnifiedPipeline(const PipelineConfig& cfg, sycl::queue& queue)
        : cfg_(cfg), queue_(queue), voxelizer_(queue_, cfg_.voxel)
    {
        auto& ctx_mgr = GPUContextManager::getInstance();
        if (!ctx_mgr.isInitialized())
            throw std::runtime_error("BEVFusionUnifiedPipeline: GPUContextManager not initialized");

        geometry_ = bevfusion::camera::create_geometry(cfg_.geom, queue_);
        if (!geometry_) throw std::runtime_error("BEVFusionUnifiedPipeline: geometry init failed");

        compile_();
    }

    ~BEVFusionUnifiedPipeline() {
        try {
            if (img_u8_device_) sycl::free(img_u8_device_, queue_);
            if (points_device_) sycl::free(points_device_, queue_);
        } catch (...) {}
    }

    BEVFusionUnifiedPipeline(const BEVFusionUnifiedPipeline&) = delete;
    BEVFusionUnifiedPipeline& operator=(const BEVFusionUnifiedPipeline&) = delete;

    std::vector<BBox3D> run(const cv::Mat& image,
                            const std::vector<float>& points,
                            const CalibField_t& calib,
                            const std::string& camera_key = "P2",
                            float ground_z_lidar = 0.0f,
                            bool recompute_geometry = true)
    {
        if (points.empty()) {
            throw std::runtime_error("BEVFusionUnifiedPipeline: empty point cloud");
        }
        const auto t0 = std::chrono::steady_clock::now();

        const int num_points = static_cast<int>(points.size()) / cfg_.voxel.in_channels;
        ensure_points_(points.size());
        queue_.memcpy(points_device_, points.data(), points.size() * sizeof(float));
        const int M = voxelizer_.run(points_device_, num_points);
        const auto t_vox = std::chrono::steady_clock::now();

        upload_image_(image);
        const auto t_pp = std::chrono::steady_clock::now();

        update_geometry_(image, calib, camera_key, ground_z_lidar, recompute_geometry);
        const auto t_geom = std::chrono::steady_clock::now();

        queue_.wait();

        auto& req = infer_request_;
        feat_rt_.set_shape({static_cast<size_t>(M), 4});
        vidx_rt_.set_shape({static_cast<size_t>(M), 4});
        req.set_tensor(in_img_, img_rt_);
        req.set_tensor(in_indices_, idx_rt_);
        req.set_tensor(in_intervals_, intv_rt_);
        req.set_tensor(in_features_, feat_rt_);
        req.set_tensor(in_voxel_indices_, vidx_rt_);
        req.infer();
        const auto t_inf = std::chrono::steady_clock::now();

        auto boxes = decode_(req);
        const auto t_post = std::chrono::steady_clock::now();

        if (!cfg_.filter_labels.empty()) {
            boxes.erase(std::remove_if(boxes.begin(), boxes.end(),
                [&](const BBox3D& b) {
                    return std::find(cfg_.filter_labels.begin(), cfg_.filter_labels.end(), b.label)
                           != cfg_.filter_labels.end();
                }), boxes.end());
        }

        auto ms = [](auto a, auto b) { return std::chrono::duration<double, std::milli>(b - a).count(); };
        perf_.frames++;
        perf_.sum_voxelize_ms += ms(t0, t_vox);
        perf_.sum_preprocess_ms += ms(t_vox, t_pp);
        perf_.sum_geometry_ms += ms(t_pp, t_geom);
        perf_.sum_infer_ms += ms(t_geom, t_inf);
        perf_.sum_postprocess_ms += ms(t_inf, t_post);
        perf_.sum_total_ms += ms(t0, t_post);

        return boxes;
    }

    void reset_perf_stats() { perf_ = {}; }
    PerfStats perf_stats() const { return perf_; }

    void print_perf_stats(std::ostream& os = std::cout) const {
        if (!perf_.frames) { os << "[perf] frames=0" << std::endl; return; }
        const auto f = os.flags();
        const auto p = os.precision();
        const double n = static_cast<double>(perf_.frames);
        os << "[perf] frames=" << perf_.frames
           << ", avg_voxelize=" << std::fixed << std::setprecision(3) << (perf_.sum_voxelize_ms / n) << " ms"
           << ", avg_preprocess=" << (perf_.sum_preprocess_ms / n) << " ms"
           << ", avg_geometry=" << (perf_.sum_geometry_ms / n) << " ms"
           << ", avg_infer=" << (perf_.sum_infer_ms / n) << " ms"
           << ", avg_postprocess=" << (perf_.sum_postprocess_ms / n) << " ms"
           << ", avg_total=" << (perf_.sum_total_ms / n) << " ms" << std::endl;
        os.flags(f);
        os.precision(p);
    }

    const PipelineConfig& config() const { return cfg_; }

private:
    // Raw BGR u8 upload into a USM buffer. The PPP graph baked into compile_()
    // handles resize + BGR->RGB + mean/std + HWC->CHW inside the compiled
    // model, so we skip the OV-managed host->device copy by binding the USM
    // directly via a RemoteTensor (rebuilt only when the source resolution
    // changes).
    void upload_image_(const cv::Mat& bgr) {
        if (bgr.empty()) throw std::runtime_error("BEVFusionUnifiedPipeline: empty input image");
        if (bgr.type() != CV_8UC3) throw std::runtime_error("BEVFusionUnifiedPipeline: expects 8UC3 BGR input");
        if (!bgr.isContinuous()) throw std::runtime_error("BEVFusionUnifiedPipeline: input image must be continuous");

        const size_t src_bytes = static_cast<size_t>(bgr.rows) * bgr.cols * 3;
        if (img_u8_cap_ < src_bytes) {
            if (img_u8_device_) sycl::free(img_u8_device_, queue_);
            img_u8_device_ = sycl::malloc_device<uint8_t>(src_bytes, queue_);
            if (!img_u8_device_) throw std::runtime_error("BEVFusionUnifiedPipeline: failed to allocate img_u8_device_");
            img_u8_cap_ = src_bytes;
            // Buffer pointer moved → drop the wrapper so we recreate it below.
            img_rt_ = ov::Tensor{};
            img_rt_rows_ = 0;
            img_rt_cols_ = 0;
        }
        queue_.memcpy(img_u8_device_, bgr.data, src_bytes);

        if (!img_rt_ || bgr.rows != img_rt_rows_ || bgr.cols != img_rt_cols_) {
            auto shared_ctx = GPUContextManager::getInstance().getSharedContext();
            const ov::Shape img_shape{1,
                                      static_cast<size_t>(bgr.rows),
                                      static_cast<size_t>(bgr.cols),
                                      3};
            img_rt_ = shared_ctx->create_tensor(ov::element::u8, img_shape, img_u8_device_);
            img_rt_rows_ = bgr.rows;
            img_rt_cols_ = bgr.cols;
        }
    }

    void compile_() {
        auto& ctx_mgr = GPUContextManager::getInstance();
        auto core = ctx_mgr.getCore();
        auto shared_ctx = ctx_mgr.getSharedContext();
        if (!std::filesystem::exists(cfg_.onnx_path)) {
            throw std::runtime_error("BEVFusionUnifiedPipeline: model file not found: " + cfg_.onnx_path);
        }
        auto model = core->read_model(cfg_.onnx_path);

        // Bake image preprocessing (resize + BGR->RGB + mean/std + HWC->CHW)
        // into the OV graph via PPP. Caller feeds raw u8 NHWC BGR at arbitrary
        // H/W; the model consumes f32 NCHW at (image_height, image_width).
        // Precondition: the ONNX image input is NCHW (the batch dim was stripped).
        {
            auto inputs = model->inputs();
            if (inputs.empty()) throw std::runtime_error("BEVFusionUnifiedPipeline: model has no inputs");
            ov::Output<ov::Node> img_input;
            for (const auto& in : inputs) {
                const auto& names = in.get_names();
                if (names.count("img") || names.count("images")) { img_input = in; break; }
            }
            if (img_input.get_node() == nullptr) img_input = inputs[0];

            const auto img_rank = img_input.get_partial_shape().rank();
            if (img_rank.is_static() && img_rank.get_length() != 4) {
                throw std::runtime_error("BEVFusionUnifiedPipeline: expected image input rank=4 (NCHW), got rank=" +
                                         std::to_string(img_rank.get_length()));
            }

            ov::preprocess::PrePostProcessor ppp(model);
            auto& input_info = ppp.input(img_input.get_any_name());
            input_info.tensor()
                .set_element_type(ov::element::u8)
                .set_layout("NHWC")
                .set_color_format(ov::preprocess::ColorFormat::BGR)
                .set_shape({1, -1, -1, 3});
            input_info.model().set_layout("NCHW");
            input_info.preprocess()
                .convert_element_type(ov::element::f32)
                .resize(ov::preprocess::ResizeAlgorithm::RESIZE_LINEAR,
                        static_cast<size_t>(cfg_.image_height),
                        static_cast<size_t>(cfg_.image_width))
                .convert_color(ov::preprocess::ColorFormat::RGB)
                .mean({cfg_.mean[0], cfg_.mean[1], cfg_.mean[2]})
                .scale({cfg_.std[0], cfg_.std[1], cfg_.std[2]});
            model = ppp.build();
        }

        compiled_ = core->compile_model(model, *shared_ctx,
            ov::hint::performance_mode(ov::hint::PerformanceMode::LATENCY),
            ov::hint::inference_precision(ov::element::f16));
        infer_request_ = compiled_.create_infer_request();
        std::cout << "[BEVFusionUnified] Compiled on GPU (shared context, f16)" << std::endl;

        auto find_in = [&](std::initializer_list<const char*> names) -> ov::Output<const ov::Node> {
            for (auto* n : names) { try { return compiled_.input(n); } catch (...) {} }
            throw std::runtime_error("BEVFusionUnified: input not found");
        };
        in_img_ = find_in({"img", "images"});
        in_indices_ = find_in({"indices"});
        in_intervals_ = find_in({"intervals"});
        in_features_ = find_in({"voxel_features", "feats", "features"});
        in_voxel_indices_ = find_in({"voxel_indices", "coords"});

        auto find_out = [&](const std::string& n) { return compiled_.output(n); };
        out_hm0_ = find_out("task0_heatmap"); out_reg0_ = find_out("task0_reg");
        out_ht0_ = find_out("task0_height");  out_dim0_ = find_out("task0_dim");
        out_rot0_ = find_out("task0_rot");    out_vel0_ = find_out("task0_vel");
        out_hm1_ = find_out("task1_heatmap"); out_reg1_ = find_out("task1_reg");
        out_ht1_ = find_out("task1_height");  out_dim1_ = find_out("task1_dim");
        out_rot1_ = find_out("task1_rot");    out_vel1_ = find_out("task1_vel");

        for (const auto& p : compiled_.inputs())
            std::cout << "  in: " << p.get_any_name() << " " << p.get_partial_shape() << std::endl;
        for (const auto& p : compiled_.outputs())
            std::cout << "  out: " << p.get_any_name() << " " << p.get_partial_shape() << std::endl;
    }

    void update_geometry_(const cv::Mat& img, const CalibField_t& calib,
                          const std::string& key, float gz, bool recompute) {
        if (!recompute && geom_valid_) return;
        auto metas = bevfusion::compute_camera_metas_from_kitti_calib(
            calib, img.size(), cfg_.image_width, cfg_.image_height, cfg_.num_camera, key, gz);
        geometry_->update(metas.camera2lidar.data(), metas.intrinsics.data(),
                         metas.img_aug.data(), metas.denorms.data(), &queue_);
        auto shared_ctx = GPUContextManager::getInstance().getSharedContext();
        idx_rt_ = shared_ctx->create_tensor(ov::element::i32,
            ov::Shape{static_cast<size_t>(geometry_->num_indices())}, geometry_->indices());
        intv_rt_ = shared_ctx->create_tensor(ov::element::i32,
            ov::Shape{static_cast<size_t>(geometry_->num_intervals()), 3}, geometry_->intervals());
        feat_rt_ = shared_ctx->create_tensor(ov::element::f32,
            ov::Shape{static_cast<size_t>(cfg_.voxel.max_voxels), 4}, voxelizer_.voxel_features_device());
        vidx_rt_ = shared_ctx->create_tensor(ov::element::i32,
            ov::Shape{static_cast<size_t>(cfg_.voxel.max_voxels), 4}, voxelizer_.voxel_indices_device());
        geom_valid_ = true;
    }

    std::vector<BBox3D> decode_(ov::InferRequest& req) {
        auto get = [&](const ov::Output<const ov::Node>& port) {
            auto t = req.get_tensor(port);
            std::vector<float> v(t.get_size());
            std::memcpy(v.data(), t.data<float>(), v.size() * sizeof(float));
            return v;
        };
        int H = static_cast<int>(req.get_tensor(out_hm0_).get_shape()[2]);
        int W = static_cast<int>(req.get_tensor(out_hm0_).get_shape()[3]);
        PostProcessInputChannels ch;
        auto hm0=get(out_hm0_),reg0=get(out_reg0_),ht0=get(out_ht0_),dm0=get(out_dim0_),rot0=get(out_rot0_),vel0=get(out_vel0_);
        PostProcessInput in0{hm0.data(),reg0.data(),ht0.data(),dm0.data(),rot0.data(),vel0.data()};
        auto b0 = post_cpu_.decodeTask(in0, 1, H, W, cfg_.post.task_configs[0], ch);
        auto hm1=get(out_hm1_),reg1=get(out_reg1_),ht1=get(out_ht1_),dm1=get(out_dim1_),rot1=get(out_rot1_),vel1=get(out_vel1_);
        PostProcessInput in1{hm1.data(),reg1.data(),ht1.data(),dm1.data(),rot1.data(),vel1.data()};
        auto b1 = post_cpu_.decodeTask(in1, 1, H, W, cfg_.post.task_configs[1], ch);
        b0.insert(b0.end(), b1.begin(), b1.end());
        std::sort(b0.begin(), b0.end(), [](const BBox3D& a, const BBox3D& b) { return a.score > b.score; });
        return b0;
    }

    void ensure_points_(size_t elems) {
        if (pts_cap_ < elems) {
            if (points_device_) sycl::free(points_device_, queue_);
            points_device_ = sycl::malloc_device<float>(elems, queue_);
            pts_cap_ = elems;
        }
    }

    PipelineConfig cfg_;
    sycl::queue& queue_;
    ov::CompiledModel compiled_;
    ov::InferRequest infer_request_;
    VoxelizerSYCL voxelizer_;
    PostProcessCPU post_cpu_{cfg_.post};
    std::shared_ptr<bevfusion::camera::Geometry> geometry_;
    bool geom_valid_{false};
    ov::Output<const ov::Node> in_img_, in_indices_, in_intervals_, in_features_, in_voxel_indices_;
    ov::Output<const ov::Node> out_hm0_, out_reg0_, out_ht0_, out_dim0_, out_rot0_, out_vel0_;
    ov::Output<const ov::Node> out_hm1_, out_reg1_, out_ht1_, out_dim1_, out_rot1_, out_vel1_;
    ov::Tensor img_rt_, idx_rt_, intv_rt_, feat_rt_, vidx_rt_;
    float* points_device_{nullptr};
    size_t pts_cap_{0};
    uint8_t* img_u8_device_{nullptr};
    size_t img_u8_cap_{0};
    int img_rt_rows_{0};
    int img_rt_cols_{0};
    PerfStats perf_{};
};

}  // namespace bevfusion_unified

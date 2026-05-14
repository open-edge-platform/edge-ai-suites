// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

#include "pipeline/bevfusion_unified.hpp"
#include "configs.hpp"
#include "gpu_context_manager.hpp"
#include "kitti_loader.hpp"
#include "utilization_monitor.hpp"
#include "visualization.hpp"
#include "test_utils.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <sstream>

using bevfusion_unified::BEVFusionUnifiedPipeline;
using bevfusion_unified::PipelineConfig;
using bevfusion_unified::UnifiedDatasetPreset;

namespace {

std::string to_kitti_class_name(int label) {
    static const std::vector<std::string> names = {
        "car","truck","construction_vehicle","bus","trailer",
        "barrier","motorcycle","bicycle","pedestrian","traffic_cone"};
    if (label < 0 || label >= static_cast<int>(names.size())) return "Unknown";
    const auto& n = names[static_cast<size_t>(label)];
    if (n == "traffic_cone") return "Trafficcone";
    if (n == "construction_vehicle") return "Construction_vehicle";
    std::string out = n;
    if (!out.empty()) out[0] = static_cast<char>(std::toupper(out[0]));
    return out;
}

UnifiedDatasetPreset parse_preset(const std::string& value) {
    if (value == "v2x" || value == "dair-v2x" || value == "V2X") {
        return UnifiedDatasetPreset::V2X;
    }
    if (value == "kitti" || value == "KITTI" || value == "kitti360" || value == "KITTI360") {
        return UnifiedDatasetPreset::KITTI;
    }
    throw std::runtime_error("Unknown preset: " + value + " (expected v2x|kitti)");
}

std::string default_unified_model_path(const char* argv0, bool use_fp16, UnifiedDatasetPreset preset) {
    const std::filesystem::path model_name = use_fp16 ? "bevfusion_unified_fp16.onnx" : "bevfusion_unified_int8.xml";
    const std::filesystem::path build_relative_path = bevfusion::dataset_default_unified_model_dir(preset) / model_name;
    const std::filesystem::path deploy_relative_path = (preset == UnifiedDatasetPreset::KITTI)
        ? std::filesystem::path("data/kitti/second") / model_name
        : std::filesystem::path("data/v2xfusion/second") / model_name;
    const std::filesystem::path executable_dir = std::filesystem::path(argv0).parent_path();
    for (const auto& candidate : {
            build_relative_path,
            deploy_relative_path,
            executable_dir / build_relative_path,
            executable_dir / ".." / deploy_relative_path}) {
        const auto normalized = candidate.lexically_normal();
        if (std::filesystem::exists(normalized)) {
            return normalized.string();
        }
    }
    return build_relative_path.string();
}

const char* default_unified_model_name(bool use_fp16) {
    return use_fp16 ? "fp16" : "int8";
}

void require_model_file(const std::string& model_path) {
    const std::filesystem::path path(model_path);
    if (!std::filesystem::exists(path)) {
        throw std::runtime_error("Unified model file not found: " + model_path);
    }
    if (path.extension() == ".xml") {
        auto bin_path = path;
        bin_path.replace_extension(".bin");
        if (!std::filesystem::exists(bin_path)) {
            throw std::runtime_error("Unified model weights not found: " + bin_path.string());
        }
    }
}

bool should_enable_unified_model_cache(const std::string& model_path) {
    std::string ext = std::filesystem::path(model_path).extension().string();
    std::transform(ext.begin(), ext.end(), ext.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return ext != ".xml";
}

void write_kitti_predictions(const std::string& path, const std::vector<BBox3D>& boxes) {
    std::ofstream out(path);
    if (!out) throw std::runtime_error("Failed to open: " + path);
    constexpr float kPi = 3.14159265358979323846f;
    for (const auto& b : boxes) {
        float ry = b.yaw;
        while (ry > kPi) ry -= 2.f * kPi;
        while (ry <= -kPi) ry += 2.f * kPi;
        out << to_kitti_class_name(b.label) << " 0 0 0 0 0 0 0 "
            << b.h << " " << b.l << " " << b.w << " "
            << b.x << " " << b.y << " " << b.z << " " << ry << " " << b.score << "\n";
    }
}

std::string csv_quote(const std::string& value) {
    std::string quoted;
    quoted.reserve(value.size() + 2);
    quoted.push_back('"');
    for (char ch : value) {
        if (ch == '"') quoted.push_back('"');
        quoted.push_back(ch);
    }
    quoted.push_back('"');
    return quoted;
}

}  // namespace

int main(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <dataset_path> [--preset v2x|kitti] [--model PATH] [--fp16]"
                  << " [--vis] [--save-image] [--save-video] [--display] [--util] [--repeat N]"
                  << " [--dump-pred] [--pred-dir DIR] [--vis-dir DIR]"
                  << " [--recompute-camera-metas] [--cache-camera-metas]"
                  << " [--filter-labels NAME,...] [--no-filter]" << std::endl;
        return -1;
    }

    const std::string dataset_path = argv[1];
    UnifiedDatasetPreset preset = UnifiedDatasetPreset::V2X;
    bool use_fp16 = false;
    bool has_model_override = false;
    std::string model_override;
    bool camera_metas_override_set = false;
    bool recompute_camera_metas_every_frame = false;
    bool enable_vis = false, save_images = false, save_video = false, enable_display = false;
    bool enable_util = false, dump_pred = false;
    int repeat_count = 1, num_samples = -1;
    std::filesystem::path vis_dir = "vis", pred_dir = "pred";
    std::vector<int> filter_labels{7, 8};

    for (int i = 2; i < argc; ++i) {
        const std::string arg = argv[i];
        auto next = [&]() -> std::string {
            if (i+1 >= argc) { std::cerr << arg << " needs value\n"; std::exit(-1); }
            return argv[++i];
        };
        if (arg == "--model" || arg == "--onnx") {
            model_override = next();
            has_model_override = true;
        }
        else if (arg == "--preset") {
            try {
                preset = parse_preset(next());
            } catch (const std::exception& error) {
                std::cerr << error.what() << "\n";
                return -1;
            }
        }
        else if (arg == "--fp16") use_fp16 = true;
        else if (arg == "--recompute-camera-metas") {
            recompute_camera_metas_every_frame = true;
            camera_metas_override_set = true;
        }
        else if (arg == "--cache-camera-metas") {
            recompute_camera_metas_every_frame = false;
            camera_metas_override_set = true;
        }
        else if (arg == "--vis" || arg == "--visualize") { enable_vis = true; save_video = true; }
        else if (arg == "--save-image") { enable_vis = true; save_images = true; }
        else if (arg == "--save-video") { enable_vis = true; save_video = true; }
        else if (arg == "--display") { enable_display = true; enable_vis = true; }
        else if (arg == "--util") enable_util = true;
        else if (arg == "--repeat") repeat_count = std::max(1, std::stoi(next()));
        else if (arg == "--dump-pred" || arg == "--acc") dump_pred = true;
        else if (arg == "--pred-dir") pred_dir = next();
        else if (arg == "--vis-dir") vis_dir = next();
        else if (arg == "--num-samples") num_samples = std::stoi(next());
        else if (arg == "--no-filter") filter_labels.clear();
        else if (arg == "--filter-labels") {
            static const std::vector<std::string> cn = {
                "car","truck","construction_vehicle","bus","trailer",
                "barrier","motorcycle","bicycle","pedestrian","traffic_cone"};
            filter_labels.clear();
            std::istringstream ss(next()); std::string tok;
            while (std::getline(ss, tok, ',')) {
                if (tok.empty()) continue;
                if (std::all_of(tok.begin(), tok.end(), ::isdigit)) filter_labels.push_back(std::stoi(tok));
                else {
                    auto it = std::find(cn.begin(), cn.end(), tok);
                    if (it == cn.end()) { std::cerr << "Unknown: " << tok << "\n"; return -1; }
                    filter_labels.push_back(static_cast<int>(std::distance(cn.begin(), it)));
                }
            }
        }
        else { std::cerr << "Unknown: " << arg << "\n"; return -1; }
    }

    if (!camera_metas_override_set) {
        recompute_camera_metas_every_frame = bevfusion_unified::unified_recompute_camera_metas(preset);
    }

    const std::string model_path = has_model_override ? model_override : default_unified_model_path(argv[0], use_fp16, preset);
    try {
        require_model_file(model_path);
    } catch (const std::exception& error) {
        std::cerr << error.what() << std::endl;
        return -1;
    }
    const bool enable_model_cache = should_enable_unified_model_cache(model_path);
    std::cout << "[info] Unified preset: " << bevfusion_unified::unified_dataset_preset_name(preset)
              << " (camera metas " << (recompute_camera_metas_every_frame ? "recomputed per frame" : "cached after first update")
              << ")" << std::endl;
    if (has_model_override) {
        std::cout << "[info] Unified model override: " << model_path << std::endl;
    } else {
        std::cout << "[info] Unified model: " << default_unified_model_name(use_fp16)
                  << " (" << model_path << ")" << std::endl;
    }
    if (!enable_model_cache) {
        std::cout << "[info] Disabling OpenVINO model cache for unified IR models because cached GPU blobs can return empty detections on rerun." << std::endl;
    }

    if (!filter_labels.empty()) {
        static const std::vector<std::string> cn = {
            "car","truck","construction_vehicle","bus","trailer",
            "barrier","motorcycle","bicycle","pedestrian","traffic_cone"};
        std::cout << "[info] Label filter:";
        for (int idx : filter_labels) {
            if (idx >= 0 && idx < static_cast<int>(cn.size())) std::cout << " " << cn[idx] << "(" << idx << ")";
            else std::cout << " " << idx;
        }
        std::cout << std::endl;
    }

    UtilizationMonitor::Options util_opts;
    util_opts.enable = enable_util;
    UtilizationMonitor util_monitor(util_opts);
    if (enable_util) { std::system("sudo -v"); util_monitor.start(); }

    VisualizerOptions vis_opts;
    vis_opts.enable = enable_vis;
    vis_opts.save_images = save_images;
    vis_opts.save_video = save_video;
    vis_opts.display = enable_display;
    vis_opts.output_dir = vis_dir;
    vis_opts.video_name = "bevfusion_unified.mp4";
    AsyncVisualizer visualizer(vis_opts);
    if (vis_opts.enable && !visualizer.initialize()) return -1;

    sycl::queue queue = create_opencl_queue();
    auto& ctx_mgr = GPUContextManager::getInstance();
    if (!ctx_mgr.initialize(queue, false, enable_model_cache)) { std::cerr << "GPU context init failed" << std::endl; return -1; }

    PipelineConfig cfg;
    bevfusion_unified::apply_unified_dataset_preset(cfg, preset);
    cfg.onnx_path = model_path;
    cfg.filter_labels = filter_labels;
    BEVFusionUnifiedPipeline pipeline(cfg, queue);

    KittiDataLoader loader(dataset_path, KittiDataLoader::createKittiConfig());
    auto samples = loader.getSampleList();
    if (samples.empty()) { std::cerr << "No samples" << std::endl; return -1; }
    if (num_samples > 0 && static_cast<size_t>(num_samples) < samples.size())
        samples.resize(static_cast<size_t>(num_samples));
    std::cout << "[info] " << samples.size() << " samples" << std::endl;

    bool geometry_ready = false;
    {
        const int warmup_iters = 3;
        std::cout << "\n=== Warmup (" << warmup_iters << " iters) ===" << std::endl;
        Data_t w = loader.getData(samples.front());
        if (!w.img.empty()) {
            for (int i = 0; i < warmup_iters; ++i) {
                const bool recompute = recompute_camera_metas_every_frame || !geometry_ready;
                pipeline.run(w.img, w.lidar, w.calib, "P2", 0.0f, recompute);
                geometry_ready = true;
            }
        }
    }
    pipeline.reset_perf_stats();
    if (enable_util) util_monitor.reset();
    if (dump_pred) std::filesystem::create_directories(pred_dir);

    bool stop_early = false;
    for (int rep = 0; rep < repeat_count && !stop_early; ++rep) {
        if (repeat_count > 1) std::cout << "\n=== Repeat " << (rep+1) << "/" << repeat_count << " ===" << std::endl;
        loader.prefetch(samples.front());

        for (size_t si = 0; si < samples.size() && !stop_early; ++si) {
            const auto& id = samples[si];
            Data_t sample = loader.getDataPrefetched(id);
            if (si+1 < samples.size()) loader.prefetch(samples[si+1]);
            else if (rep+1 < repeat_count) loader.prefetch(samples.front());
            if (sample.img.empty()) { std::cerr << "Empty: " << id << std::endl; continue; }

            const bool recompute = recompute_camera_metas_every_frame || !geometry_ready;
            auto boxes = pipeline.run(sample.img, sample.lidar, sample.calib, "P2", 0.0f, recompute);
            geometry_ready = true;
            std::cout << "  " << id << ": " << boxes.size() << " boxes" << std::endl;

            if (dump_pred) {
                try { write_kitti_predictions((pred_dir / (id + ".txt")).string(), boxes); }
                catch (const std::exception& e) { std::cerr << e.what() << "\n"; }
            }
            if (visualizer.isEnabled()) {
                visualizer.render(sample.img, sample.lidar, boxes, sample.calib,
                    {"car","truck","construction_vehicle","bus","trailer",
                     "barrier","motorcycle","bicycle","pedestrian","traffic_cone"}, id);
                if (visualizer.stopRequested()) stop_early = true;
            }
        }
    }

    if (enable_util) util_monitor.stop();
    if (visualizer.isEnabled()) {
        std::cout << "\n[vis] Flushing render queue..." << std::endl;
        visualizer.close();
    }

    pipeline.print_perf_stats();
    if (enable_util) {
        if (util_monitor.cpuSamples() > 0) std::cout << "[perf] avg_cpu=" << util_monitor.avgCpuUtil() << "%" << std::endl;
        if (util_monitor.gpuSamples() > 0) std::cout << "[perf] avg_gpu=" << util_monitor.avgGpuUtil() << "%" << std::endl;
    }

    {
        const std::string csv_path = "unified_perf_summary.csv";
        const std::string csv_header =
            "run_id,dataset_path,model_path,preset,device_request,gpu_name,visualization,dump_pred,requested_num_samples,repeat_count,samples,use_fp16,recompute_camera_metas,avg_e2e_ms,avg_voxelize_ms,avg_preprocess_ms,avg_geometry_ms,avg_infer_ms,avg_postprocess_ms,avg_cpu_util_pct,avg_gpu_util_pct";
        bool need_header = true;
        if (std::filesystem::exists(csv_path) && std::filesystem::file_size(csv_path) > 0) {
            std::ifstream existing(csv_path);
            std::string first_line;
            if (existing && std::getline(existing, first_line) && first_line == csv_header) {
                need_header = false;
            }
        }

        std::ofstream csv(csv_path, std::ios::app);
        if (!csv) {
            std::cerr << "[perf] failed to open CSV for writing: " << csv_path << std::endl;
        } else {
            if (need_header) {
                csv << csv_header << std::endl;
            }

            const auto now = std::chrono::system_clock::now();
            const auto now_time = std::chrono::system_clock::to_time_t(now);
            std::tm tm_buf{};
#if defined(_WIN32)
            localtime_s(&tm_buf, &now_time);
#else
            localtime_r(&now_time, &tm_buf);
#endif
            std::ostringstream run_id;
            run_id << std::put_time(&tm_buf, "%Y%m%d_%H%M%S");

            const auto perf = pipeline.perf_stats();
            const double n = perf.frames > 0 ? static_cast<double>(perf.frames) : 1.0;
            const std::string gpu_name = queue.get_device().get_info<sycl::info::device::name>();

            const double avg_e2e_ms = perf.sum_total_ms / n;
            const double avg_voxelize_ms = perf.sum_voxelize_ms / n;
            const double avg_preprocess_ms = perf.sum_preprocess_ms / n;
            const double avg_geometry_ms = perf.sum_geometry_ms / n;
            const double avg_infer_ms = perf.sum_infer_ms / n;
            const double avg_postprocess_ms = perf.sum_postprocess_ms / n;

            const double avg_cpu_util = enable_util ? util_monitor.avgCpuUtil() : -1.0;
            const double avg_gpu_util = enable_util ? util_monitor.avgGpuUtil() : -1.0;

            csv << run_id.str() << ','
                << csv_quote(dataset_path) << ','
                << csv_quote(model_path) << ','
                << csv_quote(bevfusion_unified::unified_dataset_preset_name(preset)) << ','
                << csv_quote(GPUContextManager::gpuDeviceName()) << ','
                << csv_quote(gpu_name) << ','
                << (enable_vis ? "1" : "0") << ','
                << (dump_pred ? "1" : "0") << ','
                << num_samples << ','
                << repeat_count << ','
                << perf.frames << ','
                << (use_fp16 ? "1" : "0") << ','
                << (recompute_camera_metas_every_frame ? "1" : "0") << ','
                << std::fixed << std::setprecision(3)
                << avg_e2e_ms << ','
                << avg_voxelize_ms << ','
                << avg_preprocess_ms << ','
                << avg_geometry_ms << ','
                << avg_infer_ms << ','
                << avg_postprocess_ms << ','
                << avg_cpu_util << ','
                << avg_gpu_util << std::endl;
        }
    }

    return 0;
}

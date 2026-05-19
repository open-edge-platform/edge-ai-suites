// Copyright (C) 2018-2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// End-to-end split-model BEVFusion driver using the decoupled PointPillars
// lidar path: raw points -> voxelizer -> 3-input PFE ONNX -> scatter.

#include "pipeline/bevfusion.hpp"
#include "common/dtype.hpp"
#include "configs.hpp"
#include "gpu_context_manager.hpp"
#include "kitti_loader.hpp"
#include "test_utils.hpp"
#include "pipeline/split_pipeline_config.hpp"
#include "utilization_monitor.hpp"
#include "visualization.hpp"

#include <algorithm>
#include <cctype>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <opencv2/opencv.hpp>
#include <sstream>
#include <string>
#include <sycl/sycl.hpp>
#include <vector>

using bevfusion::BEVFusionPipeline;
using bevfusion::PipelineConfig;

namespace {

const std::vector<std::string>& class_names()
{
    static const std::vector<std::string> names = {
        "car", "truck", "construction_vehicle", "bus", "trailer",
        "barrier", "motorcycle", "bicycle", "pedestrian", "traffic_cone"};
    return names;
}

struct Args {
    std::string dataset_path;
    bevfusion::SplitPipelinePreset preset = bevfusion::SplitPipelinePreset::V2X;
    std::filesystem::path model_dir;
    std::filesystem::path vis_dir = "vis";
    std::filesystem::path pred_dir = "pred";
    std::string device = GPUContextManager::gpuDeviceName();
    int num_samples = -1;
    int repeat_count = 1;
    bool enable_vis = false;
    bool save_image = false;
    bool save_video = false;
    bool enable_display = false;
    bool enable_util = false;
    bool dump_pred = false;
    bool use_int8_camera = true;
    bool use_int8_pfe = true;
    bool use_int8_fuser = true;
    bool use_int8_head = true;
    std::vector<int> filter_labels{7, 8};
    bool model_dir_set = false;

    bool any_int8() const
    {
        return use_int8_camera || use_int8_pfe || use_int8_fuser || use_int8_head;
    }
};

bool is_number(const std::string& token)
{
    return !token.empty() && std::all_of(token.begin(), token.end(), [](unsigned char ch) {
        return std::isdigit(ch) != 0;
    });
}

std::vector<int> parse_label_list(const std::string& value)
{
    std::vector<int> labels;
    std::istringstream stream(value);
    std::string token;
    while (std::getline(stream, token, ',')) {
        if (token.empty()) {
            continue;
        }
        if (is_number(token)) {
            labels.push_back(std::stoi(token));
            continue;
        }
        const auto& names = class_names();
        const auto it = std::find(names.begin(), names.end(), token);
        if (it == names.end()) {
            throw std::runtime_error("Unknown class name in --filter-labels: " + token);
        }
        labels.push_back(static_cast<int>(std::distance(names.begin(), it)));
    }
    return labels;
}

void print_usage(const char* argv0)
{
    std::cerr << "Usage: " << argv0 << " <dataset_path> [--preset v2x|kitti] "
              << "[--model-dir DIR] [--device DEVICE] [--num-samples N] [--repeat N] "
              << "[--vis] [--save-image] [--save-video] [--display] [--util] "
              << "[--dump-pred] [--pred-dir DIR] [--vis-dir DIR] "
              << "[--int8] [--fp32] [--int8-camera] [--int8-pfe] [--int8-fuser] [--int8-head] "
              << "[--filter-labels NAME,...] [--no-filter]\n";
}

Args parse(int argc, char** argv)
{
    Args args;
    if (argc < 2) {
        print_usage(argv[0]);
        std::exit(1);
    }
    args.dataset_path = argv[1];

    for (int i = 2; i < argc; ++i) {
        const std::string key = argv[i];
        auto next = [&]() -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error(key + " requires a value");
            }
            return argv[++i];
        };

        if (key == "--preset") {
            const std::string value = next();
            if (value == "v2x" || value == "dair-v2x" || value == "V2X") {
                args.preset = bevfusion::SplitPipelinePreset::V2X;
            } else if (value == "kitti" || value == "KITTI" || value == "kitti360" || value == "KITTI360") {
                args.preset = bevfusion::SplitPipelinePreset::KITTI;
            } else {
                throw std::runtime_error("Unknown preset: " + value + " (expected v2x|kitti)");
            }
        } else if (key == "--model-dir") {
            args.model_dir = next();
            args.model_dir_set = true;
        } else if (key == "--device") {
            args.device = next();
        } else if (key == "--vis-dir") {
            args.vis_dir = next();
        } else if (key == "--pred-dir") {
            args.pred_dir = next();
        } else if (key == "--num-samples") {
            args.num_samples = std::stoi(next());
        } else if (key == "--repeat") {
            args.repeat_count = std::max(1, std::stoi(next()));
        } else if (key == "--vis") {
            args.enable_vis = true;
            args.save_video = true;
        } else if (key == "--save-image") {
            args.enable_vis = true;
            args.save_image = true;
        } else if (key == "--save-video") {
            args.enable_vis = true;
            args.save_video = true;
        } else if (key == "--display") {
            args.enable_vis = true;
            args.enable_display = true;
        } else if (key == "--util") {
            args.enable_util = true;
        } else if (key == "--dump-pred" || key == "--acc") {
            args.dump_pred = true;
        } else if (key == "--int8") {
            args.use_int8_camera = true;
            args.use_int8_pfe = true;
            args.use_int8_fuser = true;
            args.use_int8_head = true;
        } else if (key == "--fp32") {
            args.use_int8_camera = false;
            args.use_int8_pfe = false;
            args.use_int8_fuser = false;
            args.use_int8_head = false;
        } else if (key == "--int8-camera") {
            args.use_int8_camera = true;
        } else if (key == "--int8-pfe") {
            args.use_int8_pfe = true;
        } else if (key == "--int8-fuser") {
            args.use_int8_fuser = true;
        } else if (key == "--int8-head") {
            args.use_int8_head = true;
        } else if (key == "--filter-labels") {
            args.filter_labels = parse_label_list(next());
        } else if (key == "--no-filter") {
            args.filter_labels.clear();
        } else {
            throw std::runtime_error("Unknown arg: " + key);
        }
    }

    if (!args.model_dir_set) {
        args.model_dir = bevfusion::split_pipeline_default_model_dir(args.preset);
    }
    return args;
}

std::string to_kitti_class_name(int label)
{
    const auto& names = class_names();
    if (label < 0 || label >= static_cast<int>(names.size())) {
        return "Unknown";
    }
    const std::string& name = names[static_cast<size_t>(label)];
    if (name == "traffic_cone") {
        return "Trafficcone";
    }
    if (name == "construction_vehicle") {
        return "Construction_vehicle";
    }
    std::string output = name;
    if (!output.empty()) {
        output[0] = static_cast<char>(std::toupper(static_cast<unsigned char>(output[0])));
    }
    return output;
}

void write_kitti_predictions(const std::string& file_path, const std::vector<BBox3D>& boxes)
{
    std::ofstream out(file_path);
    if (!out) {
        throw std::runtime_error("Failed to open prediction file: " + file_path);
    }

    constexpr float kPi = 3.14159265358979323846f;
    for (const auto& box : boxes) {
        float rot_y = box.yaw;
        while (rot_y > kPi) {
            rot_y -= 2.0f * kPi;
        }
        while (rot_y <= -kPi) {
            rot_y += 2.0f * kPi;
        }

        out << to_kitti_class_name(box.label) << " 0 0 0 0 0 0 0 "
            << box.h << " " << box.l << " " << box.w << " "
            << box.x << " " << box.y << " " << box.z << " "
            << rot_y << " " << box.score << "\n";
    }
}

void print_filter(const std::vector<int>& labels)
{
    if (labels.empty()) {
        std::cout << "[info] Label filter disabled (all classes output)" << std::endl;
        return;
    }

    std::cout << "[info] Label filter active:";
    const auto& names = class_names();
    for (int label : labels) {
        std::cout << " ";
        if (label >= 0 && label < static_cast<int>(names.size())) {
            std::cout << names[static_cast<size_t>(label)] << "(" << label << ")";
        } else {
            std::cout << label;
        }
    }
    std::cout << std::endl;
}

std::string csv_quote(const std::string& value)
{
    std::string quoted;
    quoted.reserve(value.size() + 2);
    quoted.push_back('"');
    for (char ch : value) {
        if (ch == '"') {
            quoted.push_back('"');
        }
        quoted.push_back(ch);
    }
    quoted.push_back('"');
    return quoted;
}

}  // namespace

int main(int argc, char** argv)
{
    Args args;
    try {
        args = parse(argc, argv);
    } catch (const std::exception& error) {
        std::cerr << error.what() << std::endl;
        print_usage(argv[0]);
        return 1;
    }

    const auto& D = bevfusion::split_pipeline_preset_dims(args.preset);
    const bool recompute_every_frame = bevfusion::split_pipeline_recompute_camera_metas(args.preset);

    std::cout << "[info] preset=" << D.name << "\n"
              << "[info] dataset=" << args.dataset_path << "\n"
              << "[info] model_dir=" << args.model_dir.string() << "\n"
              << "[info] image=" << D.image_width << "x" << D.image_height
              << " feat=" << D.feat_width << "x" << D.feat_height
              << " bev=" << D.bev_side << "x" << D.bev_side << "\n"
              << "[info] device=" << args.device << "\n"
              << "[info] vis=" << (args.enable_vis ? "on" : "off")
              << " vis_dir=" << args.vis_dir.string() << "\n"
              << "[info] num_samples=" << args.num_samples
              << " repeat=" << args.repeat_count << std::endl;
    print_filter(args.filter_labels);

    sycl::queue queue = create_opencl_queue();
    auto& ctx = GPUContextManager::getInstance();
    if (!ctx.isInitialized()) {
        if (!ctx.initialize(queue, !args.any_int8())) {
            std::cerr << "Failed to initialize GPUContextManager" << std::endl;
            return 1;
        }
    }

    UtilizationMonitor::Options util_opts;
    util_opts.enable = args.enable_util;
    UtilizationMonitor util_monitor(util_opts);
    if (args.enable_util) {
        const int rc = std::system("sudo -v");
        if (rc != 0) {
            std::cerr << "[perf] sudo -v failed; GPU utilization may be unavailable" << std::endl;
        }
        util_monitor.start();
    }

    VisualizerOptions vis_opts;
    vis_opts.enable = args.enable_vis;
    vis_opts.save_images = args.save_image;
    vis_opts.save_video = args.save_video;
    vis_opts.display = args.enable_display;
    vis_opts.output_dir = args.vis_dir;
    vis_opts.video_name = "bevfusion.mp4";
    AsyncVisualizer visualizer(vis_opts);
    if (vis_opts.enable && !visualizer.initialize()) {
        return -1;
    }

    bevfusion::SplitPipelineConfigOptions cfg_options;
    cfg_options.preset = args.preset;
    cfg_options.model_dir = args.model_dir;
    cfg_options.device = args.device;
    cfg_options.gpu_name = queue.get_device().get_info<sycl::info::device::name>();
    cfg_options.use_int8_camera = args.use_int8_camera;
    cfg_options.use_int8_pfe = args.use_int8_pfe;
    cfg_options.use_int8_fuser = args.use_int8_fuser;
    cfg_options.use_int8_head = args.use_int8_head;
    cfg_options.filter_labels = args.filter_labels;
    auto cfg_build = bevfusion::make_split_pipeline_config(cfg_options);
    if (cfg_build.int8_fuser_disabled_for_device) {
        std::cout << "[info] Battlemage GPU (" << cfg_options.gpu_name
                  << "): using fuser.onnx instead of quantized_fuser.xml "
                  << "for the known INT8 fuser issue" << std::endl;
    }
    PipelineConfig cfg = cfg_build.config;

    BEVFusionPipeline pipeline(cfg, queue);

    KittiDataLoader loader(args.dataset_path, KittiDataLoader::createKittiConfig());
    auto samples = loader.getSampleList();
    if (samples.empty()) {
        std::cerr << "No samples found at " << args.dataset_path << std::endl;
        return -1;
    }
    if (args.num_samples > 0 && static_cast<size_t>(args.num_samples) < samples.size()) {
        samples.resize(static_cast<size_t>(args.num_samples));
    }
    std::cout << "[info] " << samples.size() << " samples to process" << std::endl;

    bool v2x_geometry_ready = false;
    {
        const int warmup_iters = 3;
        const std::string warmup_id = samples.front();
        std::cout << "\n=== Warmup on " << warmup_id << " (" << warmup_iters << " iters) ===" << std::endl;
        Data_t warmup_sample = loader.getData(warmup_id);
        if (!warmup_sample.img.empty()) {
            bool recompute = true;
            for (int i = 0; i < warmup_iters; ++i) {
                (void)pipeline.run(warmup_sample.img, warmup_sample.lidar, warmup_sample.calib, "P2", 0.0f, recompute);
                recompute = false;
            }
            v2x_geometry_ready = !recompute_every_frame;
        }
    }
    pipeline.reset_perf_stats();
    pipeline.reset_latency_stats();
    if (args.enable_util) {
        util_monitor.reset();
    }

    if (args.dump_pred) {
        std::error_code ec;
        std::filesystem::create_directories(args.pred_dir, ec);
        if (ec) {
            std::cerr << "Failed to create pred dir: " << args.pred_dir.string()
                      << " error=" << ec.message() << std::endl;
            return -1;
        }
    }

    bool stop_early = false;
    for (int rep = 0; rep < args.repeat_count && !stop_early; ++rep) {
        if (args.repeat_count > 1) {
            std::cout << "\n=== Repeat " << (rep + 1) << "/" << args.repeat_count << " ===" << std::endl;
        }
        loader.prefetch(samples.front());

        for (size_t si = 0; si < samples.size() && !stop_early; ++si) {
            const auto& id = samples[si];
            std::cout << "\n=== Processing sample: " << id << " ===" << std::endl;

            Data_t sample = loader.getDataPrefetched(id);
            if (si + 1 < samples.size()) {
                loader.prefetch(samples[si + 1]);
            } else if (rep + 1 < args.repeat_count) {
                loader.prefetch(samples.front());
            }

            if (sample.img.empty()) {
                std::cerr << "Empty image for " << id << std::endl;
                continue;
            }

            const bool recompute_camera_metas = recompute_every_frame || !v2x_geometry_ready;
            auto boxes = pipeline.run(sample.img, sample.lidar, sample.calib, "P2", 0.0f, recompute_camera_metas);
            if (!recompute_every_frame) {
                v2x_geometry_ready = true;
            }
            std::cout << "Detected " << boxes.size() << " boxes" << std::endl;

            if (args.dump_pred) {
                const std::string out_path = (args.pred_dir / (id + ".txt")).string();
                try {
                    write_kitti_predictions(out_path, boxes);
                } catch (const std::exception& error) {
                    std::cerr << "Failed to write prediction file: " << out_path
                              << " error: " << error.what() << std::endl;
                }
            }

            if (visualizer.isEnabled()) {
                visualizer.render(sample.img, sample.lidar, boxes, sample.calib,
                                  class_names(), id);
                if (visualizer.stopRequested()) {
                    stop_early = true;
                }
            }
        }
    }

    if (args.enable_util) {
        util_monitor.stop();
    }

    if (visualizer.isEnabled()) {
        std::cout << "\n[vis] flushing render queue..." << std::endl;
        visualizer.close();
        std::cout << "[vis] done." << std::endl;
    }

    pipeline.print_perf_stats();
    pipeline.lidar().print_latency_stats();
    pipeline.camera_bev().print_latency_stats();
    pipeline.fusion().print_latency_stats();

    if (args.enable_util) {
        const std::size_t cpu_samples = util_monitor.cpuSamples();
        const std::size_t gpu_samples = util_monitor.gpuSamples();
        if (cpu_samples > 0) {
            std::cout << "[perf] avg_cpu_util=" << util_monitor.avgCpuUtil()
                      << "% (samples=" << cpu_samples << ")" << std::endl;
        } else {
            std::cout << "[perf] avg_cpu_util=n/a" << std::endl;
        }
        if (gpu_samples > 0) {
            std::cout << "[perf] avg_gpu_util=" << util_monitor.avgGpuUtil()
                      << "% (samples=" << gpu_samples << ")" << std::endl;
        } else {
            std::cout << "[perf] avg_gpu_util=n/a" << std::endl;
        }
    }

    {
        const std::string csv_path = "split_perf_summary.csv";
        const bool file_exists = std::filesystem::exists(csv_path);
        const bool need_header = !file_exists || std::filesystem::file_size(csv_path) == 0;

        std::ofstream csv(csv_path, std::ios::app);
        if (!csv) {
            std::cerr << "[perf] failed to open CSV for writing: " << csv_path << std::endl;
        } else {
            if (need_header) {
                csv << "run_id,dataset_path,model_dir,preset,device_request,gpu_name,visualization,dump_pred,requested_num_samples,repeat_count,samples,use_int8_camera,use_int8_pfe,use_int8_fuser,use_int8_head,avg_e2e_ms,avg_lidar_ms,avg_cam_bev_ms,avg_fusion_ms,avg_pre_ms,avg_pfe_ms,avg_scatter_ms,avg_geom_ms,avg_cam_ms,avg_bev_pool_ms,avg_fuser_ms,avg_head_ms,avg_post_ms,avg_cpu_util_pct,avg_gpu_util_pct"
                    << std::endl;
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
            const auto& lidar_stats = pipeline.lidar().latency_stats();
            const auto& cam_bev_stats = pipeline.camera_bev().latency_stats();
            const auto& fusion_stats = pipeline.fusion().latency_stats();
            const double n = perf.frames > 0 ? static_cast<double>(perf.frames) : 1.0;

            const double avg_e2e_ms = perf.sum_total_ms / n;
            const double avg_lidar_ms = perf.sum_lidar_ms / n;
            const double avg_cam_bev_ms = perf.sum_camera_bev_ms / n;
            const double avg_fusion_ms = perf.sum_fusion_ms / n;
            const double avg_pre_ms = lidar_stats.preprocess.avg();
            const double avg_pfe_ms = lidar_stats.pfe.avg();
            const double avg_scatter_ms = lidar_stats.scatter.avg();
            const double avg_geom_ms = cam_bev_stats.geom.avg();
            const double avg_cam_ms = cam_bev_stats.cam.avg();
            const double avg_bev_pool_ms = cam_bev_stats.bevpool.avg();
            const double avg_fuser_ms = fusion_stats.fuser.avg();
            const double avg_head_ms = fusion_stats.head.avg();
            const double avg_post_ms = fusion_stats.post.avg();
            const double avg_cpu_util = args.enable_util ? util_monitor.avgCpuUtil() : -1.0;
            const double avg_gpu_util = args.enable_util ? util_monitor.avgGpuUtil() : -1.0;

            csv << run_id.str() << ','
                << csv_quote(args.dataset_path) << ','
                << csv_quote(args.model_dir.string()) << ','
                << csv_quote(D.name) << ','
                << csv_quote(args.device) << ','
                << csv_quote(cfg_options.gpu_name) << ','
                << (args.enable_vis ? "1" : "0") << ','
                << (args.dump_pred ? "1" : "0") << ','
                << args.num_samples << ','
                << args.repeat_count << ','
                << perf.frames << ','
                << (args.use_int8_camera ? "1" : "0") << ','
                << (args.use_int8_pfe ? "1" : "0") << ','
                << (args.use_int8_fuser ? "1" : "0") << ','
                << (args.use_int8_head ? "1" : "0") << ','
                << std::fixed << std::setprecision(3)
                << avg_e2e_ms << ','
                << avg_lidar_ms << ','
                << avg_cam_bev_ms << ','
                << avg_fusion_ms << ','
                << avg_pre_ms << ','
                << avg_pfe_ms << ','
                << avg_scatter_ms << ','
                << avg_geom_ms << ','
                << avg_cam_ms << ','
                << avg_bev_pool_ms << ','
                << avg_fuser_ms << ','
                << avg_head_ms << ','
                << avg_post_ms << ','
                << avg_cpu_util << ','
                << avg_gpu_util << std::endl;
        }
    }

    return 0;
}

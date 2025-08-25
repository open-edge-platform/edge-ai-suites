// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "ServerSystem.h"
#include "config.h"
#include "server/univloc_global_optimization_module.h"
#include "camera/base.h"
#include "data/camera_database.h"
#include "data/map_database.h"
#include "data/bow_database.h"
#include "io/trajectory_io.h"
#include "io/map_database_io.h"
#include "fast_mapping_helper.h"

#include <thread>

#include <spdlog/spdlog.h>

namespace openvslam {
ServerSystem::ServerSystem(const std::shared_ptr<config>& cfg, rclcpp::Node *node_ptr) : cfg_(cfg), pnh_(node_ptr)
{
    spdlog::debug("CONSTRUCT: ServerSystem");

    // show configuration
    std::cout << *cfg_ << std::endl;

    if(!cfg_->is_config_valid()) {
        exit(EXIT_FAILURE);
    }

    // load ORB vocabulary
    spdlog::info("loading ORB vocabulary: {}", cfg_->vocabulary_path_);
#ifdef USE_DBOW2
    bow_vocab_ = new data::bow_vocabulary();
    try {
        bow_vocab_->loadFromBinaryFile(cfg_->vocabulary_path_);
    } catch (const std::exception& e) {
        spdlog::critical("wrong path to vocabulary");
        delete bow_vocab_;
        bow_vocab_ = nullptr;
        exit(EXIT_FAILURE);
    }
#else
    bow_vocab_ = new fbow::Vocabulary();
    bow_vocab_->readFromFile(cfg_->vocabulary_path_);
    if (!bow_vocab_->isValid()) {
        spdlog::critical("wrong path to vocabulary");
        delete bow_vocab_;
        bow_vocab_ = nullptr;
        exit(EXIT_FAILURE);
    }
#endif

    // database
    cam_db_ = new data::camera_database();
    if (!cam_db_)
        throw std::runtime_error("Failed to create camera database!");
    map_db_ = new data::map_database(cfg_->map_grid_size_);
    if (!map_db_)
        throw std::runtime_error("Failed to create map database!");
    bow_db_ = new data::bow_database(bow_vocab_);
    if (!bow_db_)
        throw std::runtime_error("Failed to create bow database!");

    // load pre-constructed keyframe and landmark map in localization and remapping modes
    if (cfg_->server_mode_ == "localization" || cfg_->server_mode_ == "relocalization" ||
        cfg_->server_mode_ == "remapping") {
        spdlog::info("Loading map from file " + cfg_->load_map_path_ + "...............");
        load_map_database(cfg_->load_map_path_);
    }
    save_map_path_ = cfg_->save_map_path_;

    // construct global optimization module and server module
    global_optimizer_ = new univloc_global_optimization_module(map_db_, bow_db_, bow_vocab_, cfg_->fix_scale_,
                                cfg_->front_rear_camera_constraint_thr_, cfg_->iteration_times_,
                                cfg_->segment_optimize_, cfg_->correct_loop_);
    slam_server_ = new univloc_server::Server(cam_db_, bow_vocab_, bow_db_, map_db_, pnh_, cfg_);

    // connect modules each other
    global_optimizer_->set_server(slam_server_);
    slam_server_->set_global_optimization_module(global_optimizer_);
}

ServerSystem::~ServerSystem()
{
    global_optimization_thread_.reset(nullptr);
    delete global_optimizer_;
    delete slam_server_;
    delete bow_db_;
    delete map_db_;
    delete cam_db_;
    global_optimizer_ = nullptr;
    bow_db_ = nullptr;
    map_db_ = nullptr;
    cam_db_ = nullptr;
    slam_server_ = nullptr;
    /*
        NOTE: when running with Valgrind it gets stuck at this delete
        Since it is coming from 3rd party library, will be not taken for further debugging
    */
    delete bow_vocab_;
    bow_vocab_ = nullptr;
    spdlog::debug("DESTRUCT: ServerSystem");
}

void ServerSystem::startup(const bool)
{
    spdlog::info("startup SLAM ServerSystem");
    system_is_running_ = true;

    global_optimization_thread_ =
        std::make_unique<std::thread>(&openvslam::univloc_global_optimization_module::run, global_optimizer_);
}

void ServerSystem::save_trajectory() { slam_server_->save_trajectory(); }

void ServerSystem::shutdown()
{
    // terminate the other threads
    global_optimizer_->request_terminate();
    // wait until the threads stop
    if (global_optimization_thread_)
        global_optimization_thread_->join();

    spdlog::info("shutdown SLAM ServerSystem");
    system_is_running_ = false;
    // save map and trajectory to files
    if (save_map_path_ != "") {
        spdlog::debug("Save_map to " + save_map_path_);
        save_map_database(save_map_path_);
    }
    spdlog::debug("Calling save_trajectory()");
    save_trajectory();
    slam_server_->shutdown();
}

void ServerSystem::save_frame_trajectory(const std::string& path, const std::string& format) const
{
    pause_other_threads();
    io::trajectory_io trajectory_io(map_db_);
    trajectory_io.save_frame_trajectory(path, format);
    resume_other_threads();
}

void ServerSystem::save_keyframe_trajectory(const std::string& path, const std::string& format) const
{
    pause_other_threads();
    io::trajectory_io trajectory_io(map_db_);
    trajectory_io.save_keyframe_trajectory(path, format);
    resume_other_threads();
}

void ServerSystem::load_map_database(const std::string& path) const
{
    pause_other_threads();
    io::map_database_io map_db_io(cam_db_, map_db_, bow_db_, bow_vocab_);
    map_db_io.load_message_pack(path);
    resume_other_threads();
}

void ServerSystem::save_map_database(const std::string& path) const
{
    if (path == "") {
        spdlog::debug("Invalid save map path!");
        return;
    }
    if (system_is_running_) pause_other_threads();
    /*
        temporarily disable the removing of keyframes and landmarks outside
        the remapping region since the loop keyframe (edge) when merging is
        also outside the remapping region and we want to keep this keyframe
        in our final updated keyframe/landmark map.
    */
    /*
    if (cfg_->server_mode_ == "remapping") {
        spdlog::warn("Remove keyframes/landmarks from clients which are outside remapping region before saving to file");
        slam_server_->remove_clients_pointcloud_outside_remapping_region();
    }
    */
    spdlog::debug("Save map to file " + path + " .....................");
    io::map_database_io map_db_io(cam_db_, map_db_, bow_db_, bow_vocab_);
    map_db_io.save_message_pack(path);
    spdlog::debug("Save map to file " + path + " successfully");
    if (system_is_running_) resume_other_threads();
}

void ServerSystem::enable_loop_detector()
{
    std::lock_guard<std::mutex> lock(mtx_loop_detector_);
    global_optimizer_->enable_loop_detector();
}

void ServerSystem::disable_loop_detector()
{
    std::lock_guard<std::mutex> lock(mtx_loop_detector_);
    global_optimizer_->disable_loop_detector();
}

bool ServerSystem::loop_detector_is_enabled() const { return global_optimizer_->loop_detector_is_enabled(); }

bool ServerSystem::loop_BA_is_running() const { return global_optimizer_->loop_BA_is_running(); }

void ServerSystem::abort_loop_BA() { global_optimizer_->abort_loop_BA(); }

void ServerSystem::request_reset()
{
    std::lock_guard<std::mutex> lock(mtx_reset_);
    reset_is_requested_ = true;
}

bool ServerSystem::reset_is_requested() const
{
    std::lock_guard<std::mutex> lock(mtx_reset_);
    return reset_is_requested_;
}

void ServerSystem::request_terminate()
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    terminate_is_requested_ = true;
}

bool ServerSystem::terminate_is_requested() const
{
    std::lock_guard<std::mutex> lock(mtx_terminate_);
    return terminate_is_requested_;
}

void ServerSystem::pause_other_threads() const
{
    // pause the global optimization module
    if (global_optimizer_ && !global_optimizer_->is_terminated()) {
        global_optimizer_->request_pause();
        while (!global_optimizer_->is_paused() && !global_optimizer_->is_terminated()) {
            std::this_thread::sleep_for(std::chrono::microseconds(5000));
        }
    }
}

void ServerSystem::resume_other_threads() const
{
    // resume the global optimization module
    if (global_optimizer_) {
        global_optimizer_->resume();
    }
}

}  // namespace openvslam

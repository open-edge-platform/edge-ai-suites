// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_SYSTEM_H
#define OPENVSLAM_SYSTEM_H

#include "type.h"
#include "data/bow_vocabulary.h"

#include <string>
#include <thread>
#include <mutex>
#include <atomic>

#include <opencv2/core/core.hpp>
#include "server/server.h"

namespace openvslam {

class config;
class univloc_global_optimization_module;

namespace camera {
class base;
}  // namespace camera

namespace data {
class camera_database;
class map_database;
class bow_database;
}  // namespace data

class ServerSystem {
public:
    //! Constructor
    ServerSystem(const std::shared_ptr<config>& cfg, rclcpp::Node *node_ptr);

    ServerSystem(const ServerSystem &) = delete;
    ServerSystem &operator=(const ServerSystem &) = delete;

    std::string save_map_path_ = "";

    //! Destructor
    ~ServerSystem();

    //-----------------------------------------
    // system startup and shutdown

    //! Startup the SLAM system
    void startup(const bool need_initialize = true);

    //! Shutdown the SLAM system
    void shutdown();

    //-----------------------------------------
    // data I/O

    //! Save the frame trajectory in the specified format
    void save_frame_trajectory(const std::string& path, const std::string& format) const;

    //! Save the keyframe trajectory in the specified format
    void save_keyframe_trajectory(const std::string& path, const std::string& format) const;

    //! Load the map database from the MessagePack file
    void load_map_database(const std::string& path) const;

    //! Save the map database to the MessagePack file
    void save_map_database(const std::string& path) const;

    //-----------------------------------------
    // module management

    //! Enable the loop detector
    void enable_loop_detector();

    //! Disable the loop detector
    void disable_loop_detector();

    //! The loop detector is enabled or not
    bool loop_detector_is_enabled() const;

    //! Loop BA is running or not
    bool loop_BA_is_running() const;

    //! Abort the loop BA externally
    void abort_loop_BA();

    //-----------------------------------------
    // management for reset

    //! Request to reset the system
    void request_reset();

    //! Reset of the system is requested or not
    bool reset_is_requested() const;

    //-----------------------------------------
    // management for terminate

    //! Request to terminate the system
    void request_terminate();

    //!! Termination of the system is requested or not
    bool terminate_is_requested() const;

    void save_trajectory();

private:
    //! Pause the mapping module and the global optimization module
    void pause_other_threads() const;

    //! Resume the mapping module and the global optimization module
    void resume_other_threads() const;

    //! config
    const std::shared_ptr<config> cfg_;

    //! camera database
    data::camera_database* cam_db_ = nullptr;

    //! map database
    data::map_database* map_db_ = nullptr;

    //! BoW vocabulary
    data::bow_vocabulary* bow_vocab_ = nullptr;

    //! BoW database
    data::bow_database* bow_db_ = nullptr;

    //! server module
    univloc_server::Server* slam_server_ = nullptr;

    //! global optimization module
    univloc_global_optimization_module* global_optimizer_ = nullptr;
    //! global optimization thread
    std::unique_ptr<std::thread> global_optimization_thread_ = nullptr;

    //! system running status flag
    std::atomic<bool> system_is_running_{false};

    //! mutex for reset flag
    mutable std::mutex mtx_reset_;
    //! reset flag
    bool reset_is_requested_ = false;

    //! mutex for terminate flag
    mutable std::mutex mtx_terminate_;
    //! terminate flag
    bool terminate_is_requested_ = false;

    //! mutex for flags of enable/disable mapping module
    mutable std::mutex mtx_mapping_;

    //! mutex for flags of enable/disable loop detector
    mutable std::mutex mtx_loop_detector_;

    //ros2 node handle
    rclcpp::Node *pnh_;
};

}  // namespace openvslam

#endif  // OPENVSLAM_SYSTEM_H

// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "camera/base.h"
#include "camera/perspective.h"
#include "camera/fisheye.h"
#include "camera/equirectangular.h"
#include "data/camera_database.h"

#include <spdlog/spdlog.h>
#include <nlohmann/json.hpp>

extern bool is_server_node;

namespace openvslam {
namespace data {

camera_database::camera_database(camera::base* curr_camera) : curr_camera_(curr_camera)
{
    spdlog::debug("CONSTRUCT: data::camera_database");
}

camera_database::~camera_database()
{
    for (const auto& name_camera : database_) {
        const auto& camera_name = name_camera.first;
        const auto camera = name_camera.second;

        // Since curr_camera is held in the config class, do not delete curr_camera here
        if (camera->name_ == curr_camera_->name_) {
            continue;
        }
        delete database_.at(camera_name);
        database_.at(camera_name) = nullptr;
    }
    database_.clear();
    for (auto it = clients_database_.begin(); it != clients_database_.end(); ++it) {
        delete it->second;
        it->second = nullptr;
    }
    clients_database_.clear();

    spdlog::debug("DESTRUCT: data::camera_database");
}

camera::base* camera_database::get_camera(const std::string& camera_name) const
{
    std::lock_guard<std::mutex> lock(mtx_database_);
    if (camera_name == curr_camera_->name_) {
        return curr_camera_;
    } else {
        assert(database_.count(camera_name));
        return database_.at(camera_name);
    }
}

camera::base* camera_database::get_client_camera(const ClientID client_id) const
{
    std::lock_guard<std::mutex> lock(mtx_database_);
    try {
        return clients_database_.at(client_id);
    } catch (std::out_of_range& ex) {
        std::string clients;
        for (const auto& it : clients_database_) clients = clients + ", " + std::to_string(it.first);
        spdlog::critical("Requesting non-exist camera for client {}. Existing cameras: ", client_id, clients);
        throw;
    }
}

bool camera_database::has_such_client_camera(ClientID client_id)
{
    std::lock_guard<std::mutex> lock(mtx_database_);
    return clients_database_.find(client_id) != clients_database_.end();
}

void camera_database::add_client_camera(ClientID client_id, camera::base* camera)
{
    std::lock_guard<std::mutex> lock(mtx_database_);
    clients_database_[client_id] = camera;
}

void camera_database::from_json(const nlohmann::json& json_cameras)
{
    std::lock_guard<std::mutex> lock(mtx_database_);

    spdlog::info("decoding {} camera(s) to load", json_cameras.size());
    for (const auto& json_id_camera : json_cameras.items()) {
        const auto& json_camera = json_id_camera.value();
        const std::string &camera_name = is_server_node ? json_camera.at("name").get<std::string>() : json_id_camera.key();
        if (is_server_node) {
            ClientID client_id = (ClientID)std::stoi(json_id_camera.key());
            spdlog::info("load a camera {}  \"{}\" from JSON", static_cast<int>(client_id), camera_name);
        } else {
            if (camera_name == curr_camera_->name_) {
                spdlog::info("load the tracking camera \"{}\" from JSON", camera_name);
                continue;
            }

            spdlog::info("load a camera \"{}\" from JSON", camera_name);
        }

        camera::base* camera = nullptr;
        const auto setup_type = camera::base::load_setup_type(json_camera.at("setup_type").get<std::string>());
        const auto model_type = camera::base::load_model_type(json_camera.at("model_type").get<std::string>());
        const auto color_order = camera::base::load_color_order(json_camera.at("color_order").get<std::string>());

        switch (model_type) {
            case camera::model_type_t::Perspective: {
                camera = new camera::perspective(
                    camera_name, setup_type, color_order, json_camera.at("cols").get<unsigned int>(),
                    json_camera.at("rows").get<unsigned int>(), json_camera.at("fps").get<double>(),
                    json_camera.at("fx").get<double>(), json_camera.at("fy").get<double>(),
                    json_camera.at("cx").get<double>(), json_camera.at("cy").get<double>(),
                    json_camera.at("k1").get<double>(), json_camera.at("k2").get<double>(),
                    json_camera.at("p1").get<double>(), json_camera.at("p2").get<double>(),
                    json_camera.at("k3").get<double>(), json_camera.at("focal_x_baseline").get<double>());
                break;
            }
            case camera::model_type_t::Fisheye: {
                camera = new camera::fisheye(
                    camera_name, setup_type, color_order, json_camera.at("cols").get<unsigned int>(),
                    json_camera.at("rows").get<unsigned int>(), json_camera.at("fps").get<double>(),
                    json_camera.at("fx").get<double>(), json_camera.at("fy").get<double>(),
                    json_camera.at("cx").get<double>(), json_camera.at("cy").get<double>(),
                    json_camera.at("k1").get<double>(), json_camera.at("k2").get<double>(),
                    json_camera.at("k3").get<double>(), json_camera.at("k4").get<double>(),
                    json_camera.at("focal_x_baseline").get<double>());
                break;
            }
            case camera::model_type_t::Equirectangular: {
                camera = new camera::equirectangular(
                    camera_name, color_order, json_camera.at("cols").get<unsigned int>(),
                    json_camera.at("rows").get<unsigned int>(), json_camera.at("fps").get<double>());
                break;
            }
        }

        if (is_server_node) {
            ClientID client_id = (ClientID)std::stoi(json_id_camera.key());
            assert(!clients_database_.count(client_id));
            clients_database_[client_id] = camera;
        } else {
            assert(!database_.count(camera_name));
            database_[camera_name] = camera;
        }
    }
}

nlohmann::json camera_database::to_json() const
{
    std::lock_guard<std::mutex> lock(mtx_database_);

    spdlog::info("encoding {} camera(s) to store", database_.size() + 1);
    std::map<std::string, nlohmann::json> cameras;
    if (is_server_node) {
        for (const auto& client_camera : clients_database_) {
            const auto& camera_name = std::to_string(client_camera.first);
            const auto camera = client_camera.second;
            cameras[camera_name] = camera->to_json();
        }
    } else {
        cameras[curr_camera_->name_] = curr_camera_->to_json();
        for (const auto& name_camera : database_) {
            const auto& camera_name = name_camera.first;
            const auto camera = name_camera.second;
            cameras[camera_name] = camera->to_json();
        }
    }
    return cameras;
}

}  // namespace data
}  // namespace openvslam

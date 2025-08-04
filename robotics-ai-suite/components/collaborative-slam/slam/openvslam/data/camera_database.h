// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_DATA_CAMERA_DATABASE_H
#define OPENVSLAM_DATA_CAMERA_DATABASE_H

#include <mutex>
#include <unordered_map>

#include <nlohmann/json_fwd.hpp>

namespace openvslam {

namespace camera {
class base;
}  // namespace camera

namespace data {

class camera_database {
public:

    explicit camera_database(camera::base* curr_camera = nullptr);

    ~camera_database();

    camera::base* get_camera(const std::string& camera_name) const;

    camera::base* get_client_camera(const ClientID client_id) const;

    void from_json(const nlohmann::json& json_cameras);

    nlohmann::json to_json() const;

    void add_client_camera(ClientID client_id, camera::base* camera);

    bool has_such_client_camera(ClientID client_id);

private:
    //-----------------------------------------
    //! mutex to access the database
    mutable std::mutex mtx_database_;
    //! pointer to the camera which used in the current tracking
    //! (NOTE: the object is owned by config class,
    //!  thus this class does NOT delete the object of curr_camera_)
    camera::base* curr_camera_;
    //! database (key: camera name, value: pointer of camera::base)
    //! (NOTE: tracking camera must NOT be contained in the database)
    std::unordered_map<std::string, camera::base*> database_;
    
    std::unordered_map<ClientID, camera::base*> clients_database_;
};

}  // namespace data
}  // namespace openvslam

#endif  // OPENVSLAM_DATA_CAMERA_DATABASE_H

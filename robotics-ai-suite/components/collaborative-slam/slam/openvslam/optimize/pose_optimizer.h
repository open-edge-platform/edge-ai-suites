// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_OPTIMIZE_POSE_OPTIMIZER_H
#define OPENVSLAM_OPTIMIZE_POSE_OPTIMIZER_H

namespace openvslam {

namespace data {
class frame;
class map_database;
}

namespace camera {
enum class setup_type_t;
}

namespace optimize {

class pose_optimizer {
public:
    /**
     * Constructor
     * @param num_trials
     * @param num_each_iter
     */
    explicit pose_optimizer(camera::setup_type_t camera_type, bool use_odom = false, bool is_localization = false, data::map_database* map_db = nullptr,
                            const unsigned int num_trials = 4, const unsigned int num_each_iter = 10);

    /**
     * Destructor
     */
    virtual ~pose_optimizer() = default;

    /**
     * Perform pose optimization
     * @param frm
     * @return
     */
    unsigned int optimize(data::frame& frm, bool compute_covariance = false, data::frame* last_lidar_frame = nullptr,
                          Eigen::Matrix4d* tf_lidar_camera = nullptr) const;

    void set_camera_type(camera::setup_type_t camera_type);

    bool use_odom_;

    bool is_localization_;

private:
    unsigned int optimize_tracker(data::frame& frm, bool compute_covariance, data::frame* last_lidar_frame,
                                  Eigen::Matrix4d* tf_lidar_camera) const;
    // Both last Lidar frame and transformation of Lidar to camera are not used on server side
    unsigned int optimize_server(data::frame& frm, bool /* compute_covariance */, data::frame* /* last_lidar_frame */,
                                 Eigen::Matrix4d* /* tf_lidar_camera */) const;
    typedef unsigned int (pose_optimizer::*optimize_node)(data::frame& frm, bool compute_covariance,
                                                          data::frame* last_lidar_frame,
                                                          Eigen::Matrix4d* tf_lidar_camera) const;
    optimize_node optimize_node_ = nullptr;
    //! map database
    data::map_database* map_db_ = nullptr;

    //! robust optimizationの試行回数
    const unsigned int num_trials_ = 4;

    //! 毎回のoptimizationのiteration回数
    const unsigned int num_each_iter_ = 10;

    //! observation threshold
    uint32_t obs_thr_ = 0;

    //! camera type
    camera::setup_type_t camera_type_;

    //! sqrt_chi_sq
    float sqrt_chi_sq_ = 0.0;
};

}  // namespace optimize
}  // namespace openvslam

#endif  // OPENVSLAM_OPTIMIZE_POSE_OPTIMIZER_H

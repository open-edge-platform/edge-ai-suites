// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef IMU_H
#define IMU_H

#include "UserConfig.h"

#include <Eigen/Core>

#include <queue>
#include <stdio.h>
#include <utility>
#include <mutex>
#include <memory>
#include <map>

namespace openvslam {

Eigen::Matrix3d skew(const Eigen::Vector3d& v);
Eigen::Matrix3d jacobian_right(const Eigen::Vector3d v);
Eigen::Matrix3d jacobian_right_inverse(const Eigen::Vector3d v);
Eigen::Vector3d vee(const Eigen::Matrix3d& t_hat);
Eigen::Matrix3d exp_so3(const Eigen::Vector3d& v);
Eigen::Vector3d log_so3(const Eigen::Matrix3d& R);
Eigen::Matrix3d normalize_rotation(const Eigen::Matrix3d& R);

class config;
namespace data {

//! IMU states, just setted for visualizing the imu states.It can be deleted if IMU has been successfully integrated!
struct IMU_States {
    double preintegration_duration_ = 0.0;
    double preintegration_R_[3];
    double preintegration_P_[3];
    double preintegration_V_[3];
    int initialize_times_ = 0;
};

class IMU_Preintegration {
    void pre_integrate_imu_measurement(const Eigen::VectorXd& imu_measurement, const double delta_time);
    static Eigen::MatrixXd Bias_walk_;
    void reset_value();
    std::mutex mtx_preintegration_;

public:
    enum IMU_State { Not_Initialized, Initializing, Initialized };
    double start_time_, end_time_;
    static double imu_initialize_timestamp_;
    static double second_initialize_time_interval_, third_initialize_time_interval_;
    static int imu_initialize_times_;

    static IMU_State state_;
    static void initialize(std::shared_ptr<univloc_tracker::Config> cfg);
    static void set_bias_walk(const Eigen::VectorXd& bias_walk_vec);
    // for vio, please use this func to set new imu bias
    void set_new_imu_bias(const Eigen::VectorXd imu_bias);
    static void reset();
    // imu: accel, gyro
    std::vector<std::pair<double, Eigen::VectorXd>> vec_imu_mearsurements_;

    void pre_integrate_imu_measurement();
    void re_pre_integrate_imu_measurement(const Eigen::VectorXd new_bias);
    Eigen::MatrixXd covariance_;
    static Eigen::VectorXd last_bias_;  // static
    static Eigen::MatrixXd noise_covaraince_;
    static void set_measurement_noise(const Eigen::VectorXd noise);
    static void set_measurement_bias(const Eigen::VectorXd bias);

    Eigen::VectorXd average_mearsument_;
    static Eigen::Matrix4d Tci_;
    // accel, gyro;
    Eigen::VectorXd bias_;
    Eigen::VectorXd delta_bias_;
    // static const Eigen::Vector3d g_w_;
    Eigen::Matrix3d preintegration_R_;
    Eigen::Vector3d preintegration_p_, preintegration_v_;
    double integration_time_ = 0.0;

    // Jocabians on bias
    Eigen::Matrix3d J_R_bg_, J_v_bg_, J_v_ba_, J_p_bg_, J_p_ba_;
    static void set_imu_state(IMU_Preintegration::IMU_State state);
    static void set_Tci(Eigen::Matrix4d Tci);

    IMU_Preintegration(const double start_time, const double end_time,
                       const std::vector<std::pair<double, Eigen::VectorXd>>& imu_measurements);
    IMU_Preintegration(const std::string filename);
    static Eigen::Matrix4d predict_velocity(const double start_time, const double end_time,
                                            const std::vector<std::pair<double, Eigen::VectorXd>>& imu_measurements,
                                            const Eigen::Matrix4d& curr_pose);
    void merge_preintegration(std::shared_ptr<IMU_Preintegration>);

    static IMU_States IMU_States_;
    static void set_imu_status(const double& duration, const Eigen::Matrix3d& preintegration_R,
                               const Eigen::Vector3d& preintegration_p, const Eigen::Vector3d& preintegration_v);

    void load_imu_preintegration_from_file_for_test(std::string filename);
    Eigen::VectorXd get_delta_bias(const Eigen::VectorXd& bias);
    Eigen::Matrix3d get_delta_rotation(const Eigen::VectorXd& bias);
    Eigen::Vector3d get_delta_velocity(const Eigen::VectorXd& bias);
    Eigen::Vector3d get_delta_position(const Eigen::VectorXd& bias);
    Eigen::Matrix3d get_updated_delta_rotation();
    Eigen::Vector3d get_updated_delta_velocity();
    Eigen::Vector3d get_updated_delta_position();
};

typedef std::shared_ptr<IMU_Preintegration> IMU_Preintegration_Ptr;
class IMU_data {
    // head: linearAcceleration  tail: angularVelocity
    std::map<double, Eigen::VectorXd> IMUBuf_;
    std::mutex mBufimu_;

public:
    void input_IMU(double t, const Eigen::Vector3d& linearAcceleration, const Eigen::Vector3d& angularVelocity);
    void get_imu_data(double start_time, double end_time, std::vector<std::pair<double, Eigen::VectorXd>>& imu_vec,
                      bool erase_data = true);
    bool is_imu_data_ready(double first_frame_timestamp);
};
}  // namespace data
}  // namespace openvslam

#endif

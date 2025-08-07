// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "imu.h"
#include "optimize/imu_edge.h"
#include <unsupported/Eigen/MatrixFunctions>
#include <spdlog/spdlog.h>
#include <fstream>

// TODO: May need different value for usages in imu_edge.cc
#define EPSILON              0.00001
#define DEFAULT_NOISE_COV    0.001
#define DEFAULT_BIAS_WALK    0.0001

namespace openvslam {

Eigen::Matrix3d skew(const Eigen::Vector3d& v)
{
    Eigen::Matrix3d v_hat;
    v_hat << 0.0, -v[2], v[1], v[2], 0.0, -v[0], -v[1], v[0], 0.0;
    return v_hat;
}

Eigen::Matrix3d jacobian_right(const Eigen::Vector3d v)
{
    Eigen::Matrix3d J_r;
    J_r.setIdentity();
    double norm = v.norm();
    if (norm > EPSILON) {
        Eigen::Matrix3d v_hat = skew(v);
        J_r += -(1.0 - std::cos(norm)) / (norm * norm) * v_hat +
               (norm - std::sin(norm)) / (norm * norm * norm) * v_hat * v_hat;
    }
    return J_r;
}

Eigen::Matrix3d jacobian_right_inverse(const Eigen::Vector3d v)
{
    Eigen::Matrix3d J_r_inverse;
    J_r_inverse.setIdentity();
    double norm = v.norm();
    if (norm > EPSILON) {
        Eigen::Matrix3d v_hat = skew(v);
        J_r_inverse +=
            0.5 * v_hat + (1.0 / (norm * norm) - 0.5 * (1.0 + std::cos(norm)) / (norm * std::sin(norm))) * (v_hat * v_hat);
    }
    return J_r_inverse;
}

Eigen::Vector3d vee(const Eigen::Matrix3d& t_hat)
{
    assert((t_hat + t_hat.transpose()).sum() < 0.001);
    Eigen::Vector3d t;
    t << t_hat(2, 1), t_hat(0, 2), t_hat(1, 0);
    return t;
}

Eigen::Vector3d log_so3(const Eigen::Matrix3d& R)
{
    const double tr = R(0, 0) + R(1, 1) + R(2, 2);
    Eigen::Vector3d w;
    w << (R(2, 1) - R(1, 2)) / 2.0, (R(0, 2) - R(2, 0)) / 2.0, (R(1, 0) - R(0, 1)) / 2.0;
    const double costheta = (tr - 1.0) * 0.5;
    if (costheta > 1.0 || costheta < -1.0) return w;
    const double theta = acos(costheta);
    const double s = sin(theta);
    if (fabs(s) < EPSILON)
        return w;
    else
        return theta * w / s;
}

Eigen::Matrix3d exp_so3(const Eigen::Vector3d& v)
{
    Eigen::Matrix3d I = Eigen::Matrix3d::Identity();
    double x = v[0], y = v[1], z = v[2];
    const double d2 = x * x + y * y + z * z;
    const double d = sqrt(d2);
    Eigen::Matrix3d W;
    W << 0.0, -z, y, z, 0.0, -x, -y, x, 0.0;
    if (d < EPSILON)
        return (I + W + 0.5 * W * W);
    else
        return (I + W * std::sin(d) / d + W * W * (1.0 - std::cos(d)) / d2);
}

Eigen::Matrix3d normalize_rotation(const Eigen::Matrix3d& R)
{
    Eigen::JacobiSVD<Eigen::Matrix3d> svd(R, Eigen::ComputeFullU | Eigen::ComputeFullV);
    return svd.matrixU() * svd.matrixV().transpose();
}

namespace data {

Eigen::VectorXd IMU_Preintegration::last_bias_ = Eigen::VectorXd::Zero(6);

Eigen::MatrixXd IMU_Preintegration::noise_covaraince_ = Eigen::MatrixXd::Identity(6, 6) * DEFAULT_NOISE_COV;

Eigen::MatrixXd IMU_Preintegration::Bias_walk_ = Eigen::MatrixXd::Identity(6, 6) * DEFAULT_BIAS_WALK;

Eigen::Matrix4d IMU_Preintegration::Tci_ = Eigen::Matrix4d::Identity();

IMU_Preintegration::IMU_State IMU_Preintegration::state_ = IMU_Preintegration::IMU_State::Not_Initialized;

double IMU_Preintegration::imu_initialize_timestamp_ = 0.0;

void IMU_Preintegration::set_imu_state(IMU_Preintegration::IMU_State state) { state_ = state; }

void IMU_Preintegration::set_Tci(Eigen::Matrix4d Tci) { Tci_ = Tci; }

IMU_States IMU_Preintegration::IMU_States_;

double IMU_Preintegration::second_initialize_time_interval_ = 5.0;

double IMU_Preintegration::third_initialize_time_interval_ = 10.0;

void IMU_Preintegration::set_imu_status(const double& duration, const Eigen::Matrix3d& preintegration_R,
                                        const Eigen::Vector3d& preintegration_P,
                                        const Eigen::Vector3d& preintegration_V)
{
    IMU_States_.preintegration_duration_ = duration;
    Vec3_t preintegration_vec_R = log_so3(preintegration_R);
    IMU_States_.preintegration_R_[0] = preintegration_vec_R[0];
    IMU_States_.preintegration_R_[1] = preintegration_vec_R[1];
    IMU_States_.preintegration_R_[2] = preintegration_vec_R[2];
    IMU_States_.preintegration_P_[0] = preintegration_P[0];
    IMU_States_.preintegration_P_[1] = preintegration_P[1];
    IMU_States_.preintegration_P_[2] = preintegration_P[2];
    IMU_States_.preintegration_V_[0] = preintegration_V[0];
    IMU_States_.preintegration_V_[1] = preintegration_V[1];
    IMU_States_.preintegration_V_[2] = preintegration_V[2];
    IMU_States_.initialize_times_ = imu_initialize_times_;
}

void IMU_Preintegration::initialize(std::shared_ptr<univloc_tracker::Config> cfg)
{
    Tci_ = cfg->tf_camera_imu_;

    last_bias_ = cfg->imu_bias_; // leave it now, not used in orbslam3

    // Refer: OpenVINS: Discrete-time IMU Propagation <https://docs.openvins.com/propagation.html#disc_prop>
    for (int i = 0; i < 6; i++) {
        Bias_walk_(i, i) = cfg->imu_bias_walk_[i] * cfg->imu_bias_walk_[i] / cfg->imu_frequency_;
    }

    for (int i = 0; i < 6; i++) {
        noise_covaraince_(i, i) = cfg->imu_noise_[i] * cfg->imu_noise_[i] * cfg->imu_frequency_;
    }

    std::cout << "Bias_walk_: \n" << Bias_walk_ << std::endl;
    std::cout << "noise_covaraince_: \n" << noise_covaraince_ << std::endl;
    std::cout << "imu frequency: " << cfg->imu_frequency_ << std::endl;
    std::cout << "imu noise: " << cfg->imu_noise_.transpose() << std::endl;
    std::cout << "imu bias walk noise: " << cfg->imu_bias_walk_.transpose() << std::endl;
}

IMU_Preintegration::IMU_Preintegration(const double start_time, const double end_time,
                                       const std::vector<std::pair<double, Eigen::VectorXd>>& imu_measurements)
    : start_time_(start_time), end_time_(end_time), integration_time_(end_time - start_time)
{
    // vec_imu_mearsurements_.assign(imu_measurements.begin(), imu_measurements.end());
    std::map<double, Eigen::VectorXd> imu_mearsurements_withtimestamp;

    for (const auto& item : imu_measurements) {
        // spdlog::info("imu timestamp: {}", item.first);
        imu_mearsurements_withtimestamp[item.first] = item.second;
    }
    for (const auto& item : imu_mearsurements_withtimestamp) {
        vec_imu_mearsurements_.push_back(std::make_pair(item.first, item.second));
    }

    if (vec_imu_mearsurements_.empty()) {
        spdlog::error("IMU_Preintegration, imu measurements num is 0!");
        return;
    }

    spdlog::debug(
        "IMU_Preintegration time interval {} ms, imu mearsurements num: {}, start_time: {}, end_time: {}, first imu "
        "time: {}, last imu time: {}",
        (end_time - start_time) * 1000, vec_imu_mearsurements_.size(), start_time_, end_time_,
        vec_imu_mearsurements_.front().first, vec_imu_mearsurements_.back().first);

    spdlog::debug("Measured IMU frequency is {} ", vec_imu_mearsurements_.size() / integration_time_);
    spdlog::debug("vec_imu_mearsurements_.size:{}, imu_measurements.size: {}, imu_mearsurements_withtimestamp.size: {}",
                  vec_imu_mearsurements_.size(), imu_measurements.size(), imu_mearsurements_withtimestamp.size());

    assert(start_time_ <= vec_imu_mearsurements_.front().first);
    if (start_time_ > vec_imu_mearsurements_.front().first) {
        spdlog::warn("Invalid imu vector start time");
        abort();
    }
    assert(end_time >= vec_imu_mearsurements_.back().first);

    if (end_time < vec_imu_mearsurements_.back().first) {
        spdlog::warn("Invalid imu vector end time");
        abort();
    }

    reset_value();

    // covariance_
    //                 R
    //                 V
    //                 P
    //                 ba
    //                 bg
    assert(start_time < end_time);
    assert(imu_measurements.back().first <= end_time && imu_measurements.front().first >= start_time);
    bias_ = last_bias_;
    pre_integrate_imu_measurement();
    average_mearsument_ = Eigen::VectorXd::Zero(6);
    for (auto& imu : vec_imu_mearsurements_) {
        average_mearsument_ += imu.second;
    }
    average_mearsument_ = average_mearsument_ / vec_imu_mearsurements_.size();

    set_imu_status(integration_time_, preintegration_R_, preintegration_p_, preintegration_v_);
    // std::cout << "average_mearsument_: " << average_mearsument_.transpose() << std::endl;
}

IMU_Preintegration::IMU_Preintegration(const std::string filename)
    : start_time_(0.0), end_time_(0.0), integration_time_(0.0)
{
    spdlog::info("Test IMU preintegration!");
    load_imu_preintegration_from_file_for_test(filename);
}

void IMU_Preintegration::set_bias_walk(const Eigen::VectorXd& bias_walk_vec)
{
    for (int i = 0; i < 6; i++) {
        Bias_walk_(i, i) = bias_walk_vec[i] * bias_walk_vec[i];
    }
}

void IMU_Preintegration::merge_preintegration(std::shared_ptr<IMU_Preintegration> merged_preintegration)
{
    std::unique_lock<std::mutex> lock1(mtx_preintegration_);
    std::unique_lock<std::mutex> lock2(merged_preintegration->mtx_preintegration_);
    const double max_integration_time = 10;  // Alomost no constraint

    auto older_vec_imu_mearsurements = merged_preintegration->end_time_ > end_time_
                                           ? vec_imu_mearsurements_
                                           : merged_preintegration->vec_imu_mearsurements_;
    auto newer_vec_imu_mearsurements = merged_preintegration->end_time_ < end_time_
                                           ? vec_imu_mearsurements_
                                           : merged_preintegration->vec_imu_mearsurements_;

    start_time_ = std::min(start_time_, merged_preintegration->start_time_);
    end_time_ = std::max(end_time_, merged_preintegration->end_time_);
    integration_time_ = end_time_ - start_time_;
    if (integration_time_ > max_integration_time)
        return;
    if (older_vec_imu_mearsurements.empty() || newer_vec_imu_mearsurements.empty())
        return;

    assert(older_vec_imu_mearsurements.back().first < newer_vec_imu_mearsurements.front().first);
    spdlog::debug("t1 {} t2 {} t3 {} t4 {}", older_vec_imu_mearsurements.front().first,
                  older_vec_imu_mearsurements[older_vec_imu_mearsurements.size() - 1].first,
                  newer_vec_imu_mearsurements.front().first,
                  newer_vec_imu_mearsurements[newer_vec_imu_mearsurements.size() - 1].first);

    spdlog::debug("older_vec_imu_mearsurements size {}", older_vec_imu_mearsurements.size());
    spdlog::debug("newer_vec_imu_mearsurements size {}", newer_vec_imu_mearsurements.size());
    vec_imu_mearsurements_.clear();

    vec_imu_mearsurements_.assign(older_vec_imu_mearsurements.begin(), older_vec_imu_mearsurements.end());
    vec_imu_mearsurements_.insert(vec_imu_mearsurements_.end(), newer_vec_imu_mearsurements.begin(),
                                  newer_vec_imu_mearsurements.end());
    assert(vec_imu_mearsurements_.front().first < vec_imu_mearsurements_.back().first);
    spdlog::debug("merged_vec_imu_mearsurements size {}", vec_imu_mearsurements_.size());

    // VIP! TODO: diff - orbslam3 doesn't use the mean result!
    bias_ = (merged_preintegration->bias_ + bias_) * 0.5;
    // avoid the use of re_pre_integrate_imu_measurement otherwise redundant lock would be added
    reset_value();
    pre_integrate_imu_measurement();
}

void IMU_Preintegration::reset_value()
{
    preintegration_R_.setIdentity();
    preintegration_p_.setZero();
    preintegration_v_.setZero();
    J_R_bg_.setZero();
    J_v_bg_.setZero();
    J_v_ba_.setZero();
    J_p_bg_.setZero();
    J_p_ba_.setZero();
    covariance_ = Eigen::MatrixXd::Zero(15, 15);
    delta_bias_ = Eigen::VectorXd::Zero(6);
}

void IMU_Preintegration::re_pre_integrate_imu_measurement(const Eigen::VectorXd new_bias)
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    bias_ = new_bias;
    reset_value();
    pre_integrate_imu_measurement();
}

void IMU_Preintegration::pre_integrate_imu_measurement()
{
    Eigen::VectorXd m_imu;
    double delta_t;
    size_t num = vec_imu_mearsurements_.size();
    // spdlog::debug("IMU meausurements  num: {}", num);
    for (unsigned int i = 0; i < num; i++) {
        if (i == 0) {
            delta_t = vec_imu_mearsurements_[i].first - start_time_;
            m_imu = vec_imu_mearsurements_[i].second - bias_;
            if (delta_t < 0) {
                spdlog::debug("Invalid delta T");
                continue;
            }
            pre_integrate_imu_measurement(m_imu, delta_t);
        } else {
            delta_t = vec_imu_mearsurements_[i].first - vec_imu_mearsurements_[i - 1].first;
            m_imu = (vec_imu_mearsurements_[i].second + vec_imu_mearsurements_[i - 1].second) * 0.5 - bias_;
            // m_imu = vec_imu_mearsurements_[i].second - bias_;
            if (delta_t < 0)
                spdlog::debug("Last imu timestamp {}, this timestamp: {}, time interval {}",
                              vec_imu_mearsurements_[i - 1].first, vec_imu_mearsurements_[i].first, delta_t);
            pre_integrate_imu_measurement(m_imu, delta_t);
        }
        if (i == num - 1) {
            delta_t = end_time_ - vec_imu_mearsurements_[i].first;
            m_imu = vec_imu_mearsurements_[i].second - bias_;
            pre_integrate_imu_measurement(m_imu, delta_t);
            // spdlog::info("delta_t: {}", delta_t);
        }
        assert(delta_t > 0);
    }
    // spdlog::debug("IMU meausurements time: {} ms",
    //              (vec_imu_mearsurements_.back().first - vec_imu_mearsurements_.front().first) * 1000);
}

void IMU_Preintegration::load_imu_preintegration_from_file_for_test(std::string str_filename)
{
    // To verify whether the IMU_Preintegration output is correct! the input and result can be aquired from ORB_SLAM3

    // Load IMU parameters from file
    char* filename = str_filename.data();
    std::ifstream fin(filename, std::ios::in);
    if (!fin) {
        std::cout << "Cannot open file for input.\n";
        return;
    }
    std::string s;
    int idx = 0;
    double timestamp = 0;

    while (!fin.eof()) {
        getline(fin, s);
        std::string t;
        std::istringstream in(s);
        std::vector<double> v;

        while (std::getline(in, t, ' ')) {
            v.push_back(double(stod(t)));
        }
        if (v.size() == 0) break;

        if (idx == 0) {
            assert(v.size() == 6);
            bias_ = Eigen::VectorXd(6);
            bias_ << v[0], v[1], v[2], v[3], v[4], v[5];
        } else if (idx == 1) {
            assert(v.size() == 4);
            double ng = v[0], na = v[1], ngw = v[2], naw = v[3];
            noise_covaraince_(0, 0) = na * na;
            noise_covaraince_(1, 1) = na * na;
            noise_covaraince_(2, 2) = na * na;
            noise_covaraince_(3, 3) = ng * ng;
            noise_covaraince_(4, 4) = ng * ng;
            noise_covaraince_(5, 5) = ng * ng;
            Bias_walk_(0, 0) = naw * naw;
            Bias_walk_(1, 1) = naw * naw;
            Bias_walk_(2, 2) = naw * naw;
            Bias_walk_(3, 3) = ngw * ngw;
            Bias_walk_(4, 4) = ngw * ngw;
            Bias_walk_(5, 5) = ngw * ngw;
        } else {
            assert(v.size() == 7);
            Eigen::VectorXd imu_vec = Eigen::VectorXd(6);
            imu_vec << v[1], v[2], v[3], v[4], v[5], v[6];
            timestamp += v[0];
            vec_imu_mearsurements_.push_back(std::make_pair(timestamp, imu_vec));
            std::cout << imu_vec.transpose() << std::endl;
        }
        idx++;
    }
    start_time_ = 0;
    end_time_ = vec_imu_mearsurements_.back().first;

    std::cout << "bias_: \n " << bias_.transpose() << "\n";
    re_pre_integrate_imu_measurement(bias_);
    std::cout << "preintegration_p: \n " << preintegration_p_.transpose() << "\n";
    std::cout << "preintegration_v: \n " << preintegration_v_.transpose() << "\n";
    std::cout << "preintegration_R: \n " << preintegration_R_ << "\n";
    std::cout << "J_R_bg: \n " << J_R_bg_ << "\n";
    std::cout << "J_p_ba: \n " << J_p_ba_ << "\n";
    std::cout << "J_p_bg: \n " << J_p_bg_ << "\n";
    std::cout << "J_v_ba: \n " << J_v_ba_ << "\n";
    std::cout << "J_v_bg: \n " << J_v_bg_ << "\n";
    std::cout << "Coviariance: \n " << covariance_ << "\n";
}

void IMU_Preintegration::pre_integrate_imu_measurement(const Eigen::VectorXd& imu_measurement, const double delta_t)
{
    // preintegration_R_ represents dR and delta_R represents dRi in ORB_SLAM3
    // Refer to <<On-Manifold Preintegration for Real-Time Visual–Inertial Odometry>>
    // https://ieeexplore.ieee.org/document/7557075
    // Pre_integration has been checked for many times, totally the same as ORB_SLAM3, no problem
    if (delta_t < 0) {
        spdlog::debug("Invalid delta_t: {}", delta_t);
        spdlog::debug("vec_imu_mearsurements_.size: {}", vec_imu_mearsurements_.size());
        spdlog::debug("start_time {}", start_time_);

        for (const auto& item : vec_imu_mearsurements_) {
            spdlog::debug("t {}", item.first);
        }
        spdlog::debug("end_time {}", end_time_);

        spdlog::debug("Abort");

        abort();
    }
    Eigen::Vector3d m_accel = imu_measurement.head(3), m_gyro = imu_measurement.tail(3);

    Eigen::Matrix3d delta_R, J_right;
    auto jacobian_right_of_deltaR = jacobian_right(m_gyro * delta_t);
    // W = skew(m_gyro * delta_t);
    delta_R = skew(m_gyro * delta_t).exp(); // TODO: check if correct, similar to IntegratedRotation in ORB_SLAM3
    preintegration_p_ += 0.5 * preintegration_R_ * m_accel * delta_t * delta_t + preintegration_v_ * delta_t;
    preintegration_v_ += preintegration_R_ * m_accel * delta_t;

    //  R
    //  V
    //  P
    Eigen::MatrixXd A = Eigen::MatrixXd::Identity(9, 9), B = Eigen::MatrixXd::Zero(9, 6);
    A.block(0, 0, 3, 3) = delta_R.transpose(); // update at the end in ORB_SLAM3, the basic logic is the same
    A.block(3, 0, 3, 3) = -preintegration_R_ * skew(m_accel) * delta_t;
    A.block(6, 0, 3, 3) = -0.5 * preintegration_R_ * skew(m_accel) * delta_t * delta_t;
    A.block(6, 3, 3, 3) = delta_t * Eigen::Matrix3d::Identity();

    // Another possible implementation
    // B.block(0, 3, 3, 3) = jacobian_right_of_deltaR * delta_t;
    // B.block(3, 0, 3, 3) = preintegration_R_ * delta_t;
    // B.block(6, 0, 3, 3) = 0.5 * preintegration_R_ * delta_t * delta_t;
    B.block(0, 0, 3, 3) = jacobian_right_of_deltaR * delta_t;
    B.block(3, 3, 3, 3) = preintegration_R_ * delta_t;
    B.block(6, 3, 3, 3) = 0.5 * preintegration_R_ * delta_t * delta_t;

    covariance_.block(0, 0, 9, 9) =
        A * covariance_.block(0, 0, 9, 9) * A.transpose() + B * noise_covaraince_ * B.transpose();

    covariance_.block(9, 9, 6, 6) +=
        Bias_walk_;  // Bias_walk_ is related to time interval, so no need to multiply delta_t

    J_p_ba_ += -0.5 * preintegration_R_ * delta_t * delta_t + J_v_ba_ * delta_t; 
    J_p_bg_ += -0.5 * preintegration_R_ * skew(m_accel) * J_R_bg_ * delta_t * delta_t + J_v_bg_ * delta_t;

    J_v_ba_ -= preintegration_R_ * delta_t;
    J_v_bg_ -= preintegration_R_ * skew(m_accel) * J_R_bg_ * delta_t;

    J_R_bg_ = delta_R.transpose() * J_R_bg_ - jacobian_right_of_deltaR * delta_t;

    preintegration_R_ =
        normalize_rotation(preintegration_R_ * delta_R);  // update is the same, ORB_SLAM3 use doublecheck(NORMALIZE)
}

int IMU_Preintegration::imu_initialize_times_ = 0;

void IMU_Preintegration::set_measurement_noise(const Eigen::VectorXd noise)
{
    for (int i = 0; i < 6; i++) {
        noise_covaraince_(i, i) = noise[i] * noise[i];
    }
}

void IMU_Preintegration::reset()
{
    state_ = IMU_State::Not_Initialized;
    last_bias_.setZero();
    spdlog::critical("Reset IMU");
    imu_initialize_times_ = 0;
    imu_initialize_timestamp_ = -1;
}

void IMU_Preintegration::set_measurement_bias(const Eigen::VectorXd bias) { last_bias_ = bias; }

void IMU_Preintegration::set_new_imu_bias(const Eigen::VectorXd imu_bias)
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    delta_bias_ = imu_bias - bias_;
    bias_ = imu_bias;
}

Eigen::VectorXd IMU_Preintegration::get_delta_bias(const Eigen::VectorXd& bias)
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    Eigen::VectorXd db = Eigen::VectorXd(6);
    db << bias[0] - bias_[0], bias[1] - bias_[1], bias[2] - bias_[2], bias[3] - bias_[3], bias[4] - bias_[4],
        bias[5] - bias_[5];
    return db;
}

Eigen::Matrix3d IMU_Preintegration::get_delta_rotation(const Eigen::VectorXd& bias)
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    Eigen::Vector3d dbg(bias[3] - bias_[3], bias[4] - bias_[4], bias[5] - bias_[5]);
    return normalize_rotation(preintegration_R_ * exp_so3(J_R_bg_ * dbg));
}

Eigen::Vector3d IMU_Preintegration::get_delta_velocity(const Eigen::VectorXd& bias)
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    Eigen::Vector3d dba(bias[0] - bias_[0], bias[1] - bias_[1], bias[2] - bias_[2]);
    Eigen::Vector3d dbg(bias[3] - bias_[3], bias[4] - bias_[4], bias[5] - bias_[5]);
    return preintegration_v_ + J_v_bg_ * dbg + J_v_ba_ * dba;
}

Eigen::Vector3d IMU_Preintegration::get_delta_position(const Eigen::VectorXd& bias)
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    Eigen::Vector3d dba(bias[0] - bias_[0], bias[1] - bias_[1], bias[2] - bias_[2]);
    Eigen::Vector3d dbg(bias[3] - bias_[3], bias[4] - bias_[4], bias[5] - bias_[5]);
    return preintegration_p_ + J_p_bg_ * dbg + J_p_ba_ * dba;
}

Eigen::Matrix3d IMU_Preintegration::get_updated_delta_rotation()
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    return normalize_rotation(preintegration_R_ * exp_so3(J_R_bg_ * delta_bias_.tail(3)));
}

Eigen::Vector3d IMU_Preintegration::get_updated_delta_velocity()
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    return preintegration_v_ + J_v_bg_ * delta_bias_.tail(3) + J_v_ba_ * delta_bias_.head(3);
}

Eigen::Vector3d IMU_Preintegration::get_updated_delta_position()
{
    std::unique_lock<std::mutex> lock(mtx_preintegration_);
    return preintegration_p_ + J_p_bg_ * delta_bias_.tail(3) + J_p_ba_ * delta_bias_.head(3);
}

void IMU_data::input_IMU(double t, const Eigen::Vector3d& linearAcceleration,
                         const Eigen::Vector3d& angularVelocity)
{
    std::scoped_lock<std::mutex> lock(mBufimu_);
    Eigen::VectorXd imu_data(6);
    imu_data.head(3) = linearAcceleration;
    imu_data.tail(3) = angularVelocity;
    IMUBuf_.emplace_hint(IMUBuf_.end(), t, imu_data);
}

/*
  if the end timestamp of the preintegration time duration is smaller
  than the smallest timestamp of IMU data in buffer, then it means we
  will no longer get validate IMU data since the timestamp is always
  increasing.
*/
bool IMU_data::is_imu_data_ready(double end_timestamp)
{
    std::scoped_lock<std::mutex> lock(mBufimu_);
    if (IMUBuf_.empty() || end_timestamp < IMUBuf_.begin()->first)
        return false;
    else
        return true;
}

void IMU_data::get_imu_data(double start_time, double end_time,
                            std::vector<std::pair<double, Eigen::VectorXd>>& imu_vec, bool erase_data)
{
    assert(start_time < end_time);

    std::scoped_lock<std::mutex> lock(mBufimu_);

    if (IMUBuf_.empty())
        return;

    auto start_it = IMUBuf_.lower_bound(start_time);
    if (start_it == IMUBuf_.end())
        return;
    if (erase_data)
        IMUBuf_.erase(IMUBuf_.begin(), start_it);

    for (auto it = start_it; it != IMUBuf_.end();) {
        if (it->first > end_time)
            break;
        else {
            imu_vec.emplace_back(*it);
            if (erase_data) it = IMUBuf_.erase(it);
            else ++it;
        }
    }
}

}  // namespace data
}  // namespace openvslam

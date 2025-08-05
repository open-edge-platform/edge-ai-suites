// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/window.h"
#include "data/keyframe.h"
#include "util/converter.h"
#include <spdlog/spdlog.h>

namespace openvslam {
namespace data {

window::window(unsigned int window_id)
: window_id_(window_id)
{}

window::~window()
{
    spdlog::debug("DESTRUCT: window");
}

/*slerp the quaternion with weight
  start*(1-t) + end*t*/
Quat_t window::quat_slerp(Quat_t start, Quat_t end, const float t)
{
    Quat_t result(0, 0, 0, 0);
    double cosa = start.w()*end.w() + start.x()*end.x() + start.y()*end.y() + start.z()*end.z();
    // If the dot product is negative, the quaternions have opposite handed-ness and slerp won't take
    // the shorter path. Fix by reversing one quaternion.
    if (cosa < 0.0f)
    {
        end.w() = -end.w();
        end.x() = -end.x();
        end.y() = -end.y();
        end.z() = -end.z();
        cosa = -cosa;
    }
    float k0, k1;
    // If the inputs are too close for comfort, linearly interpolate
    if (cosa > 0.9995f)
    {
        k0 = 1.0f - t;
        k1 = t;
    }
    else
    {
        float sina = sqrt(1.0f - cosa*cosa);
        float a = atan2(sina, cosa);
        k0 = sin((1.0f - t)*a) / sina;
        k1 = sin(t*a) / sina;
    }
    result.w() = start.w()*k0 + end.w()*k1;
    result.x() = start.x()*k0 + end.x()*k1;
    result.y() = start.y()*k0 + end.y()*k1;
    result.z() = start.z()*k0 + end.z()*k1;

    return result;
}

Quat_t window::calc_average_quart(const Mat44_t& quater_sum)
{
    Eigen::EigenSolver<Mat44_t> es(quater_sum);
    MatX_t evecs = es.eigenvectors().real();
    MatX_t evals = es.eigenvalues().real();
    MatX_t::Index evalsMax;
    evals.rowwise().sum().maxCoeff(&evalsMax);
    Quat_t average_quater(evecs.block<4, 1>(0, evalsMax));
    return average_quater;
}

Mat44_t window::get_pose_from_sim3(const ::g2o::Sim3& sim3_pose)
{
    const float s = sim3_pose.scale();
    const Mat33_t rot_cw = sim3_pose.rotation().toRotationMatrix();
    const Vec3_t trans_cw = sim3_pose.translation() / s;
    Mat44_t cam_pose_cw = util::converter::to_eigen_cam_pose(rot_cw, trans_cw);
    return cam_pose_cw;
}

::g2o::Sim3 window::get_sim3_from_pose(const Mat44_t& mat_pose)
{
    const Mat33_t rot_cw = mat_pose.block<3, 3>(0, 0);
    const Vec3_t trans_cw = mat_pose.block<3, 1>(0, 3);
    ::g2o::Sim3 sim3_pose(rot_cw, trans_cw, 1.0);
    return sim3_pose;
}

void window::insert_keyframe(keyframe* keyfrm){
    std::lock_guard<std::mutex> lock(mtx_kf_);
    keyframes_.insert(std::pair<KeyframeID, keyframe*>(keyfrm->id_, keyfrm));
}

void window::erase_keyframe(KeyframeID kefrm_id)
{
    std::lock_guard<std::mutex> lock(mtx_kf_);
    keyframes_.erase(kefrm_id);
}

void window::erase_final_kefrm(){
    std::lock_guard<std::mutex> lock(mtx_kf_);
    keyframes_.erase(keyframes_.rbegin()->first);
}

void window::get_opt_keframes(std::vector<keyframe*>& origin_keyframes, std::unordered_map<KeyframeID, keyframe*>& keyfrm_ids, const size_t edge_size){
    std::lock_guard<std::mutex> lock(mtx_kf_);
    auto iter_start = keyframes_.begin();
    auto iter_end = keyframes_.rbegin();
    for (size_t idx=0; idx<edge_size; idx++) {
        origin_keyframes.push_back(iter_start->second);
        origin_keyframes.push_back(iter_end->second);
        keyfrm_ids[iter_start->first] = iter_start->second;
        keyfrm_ids[iter_end->first] = iter_end->second;
        iter_start++;
        iter_end++;
    }
}

keyframe* window::get_final_kefrm(){
    std::lock_guard<std::mutex> lock(mtx_kf_);
    return keyframes_.rbegin()->second;
}

unsigned int window::get_window_size(){
    std::lock_guard<std::mutex> lock(mtx_kf_);
    return keyframes_.size();
}

bool window::empty(){
    std::lock_guard<std::mutex> lock(mtx_kf_);
    return keyframes_.empty();
}

void window::update_cam_pose_slerp(const std::vector<::g2o::Sim3, Eigen::aligned_allocator<::g2o::Sim3>>& cam_pose_cw_new,
                                   std::unordered_map<unsigned int, ::g2o::Sim3>& corrected_Sim3s_wc,
                                   size_t edge_size, unsigned int new_map_id, unsigned int loop_identifier)
{
    std::lock_guard<std::mutex> lock(mtx_kf_);
    // Calculate the average value of sim3
    std::vector<Vec3_t> trans_start;
    std::vector<Vec3_t> trans_end;
    std::vector<Mat44_t> quats_start;
    std::vector<Mat44_t> quats_end;
    double scale_start = 0, scale_end = 0;
    for (size_t idx=0; idx<edge_size; idx++){
        const auto sim3_start = cam_pose_cw_new.at(2*idx);
        const Quat_t quat_start(sim3_start.rotation());
        const Vec4_t quat_start_vec(quat_start.x(), quat_start.y(), quat_start.z(), quat_start.w());
        trans_start.push_back(sim3_start.translation());
        quats_start.push_back(quat_start_vec*quat_start_vec.transpose());
        scale_start += sim3_start.scale();

        const auto sim3_end = cam_pose_cw_new.at(2*idx+1);
        const Quat_t quat_end(sim3_end.rotation());
        const Vec4_t quat_end_vec(quat_end.x(), quat_end.y(), quat_end.z(), quat_end.w());
        trans_end.push_back(sim3_end.translation());
        quats_end.push_back(quat_end_vec*quat_end_vec.transpose());
        scale_end += sim3_end.scale();
    }
    const Mat44_t init = Mat44_t::Zero();
    Quat_t quat_res_start = calc_average_quart(std::accumulate(quats_start.begin(), quats_start.end(), init));
    Quat_t quat_res_end = calc_average_quart(std::accumulate(quats_end.begin(), quats_end.end(), init));
    Vec3_t tran_res_start = std::accumulate(trans_start.begin(), trans_start.end(), Vec3_t(0,0,0))/edge_size;
    Vec3_t tran_res_end = std::accumulate(trans_end.begin(), trans_end.end(), Vec3_t(0,0,0))/edge_size;
    scale_start /= edge_size;
    scale_end /= edge_size;
    const ::g2o::Sim3 opt_sim3_start(quat_res_start.normalized().toRotationMatrix(), tran_res_start, scale_start);
    const ::g2o::Sim3 opt_sim3_end(quat_res_end.normalized().toRotationMatrix(), tran_res_end, scale_end);

    // Calculate the average value of inv_mat and the average value of distance
    auto iter_start = keyframes_.begin();
    auto iter_end = keyframes_.end();

    trans_start.clear();
    trans_end.clear();
    quats_start.clear();
    quats_end.clear();
    double start_distance = 0;
    double end_distance = 0;
    for(size_t idx=0; idx<edge_size; idx++){
        iter_end--;
        const auto pose_start = iter_start->second->get_cam_pose();
        const Quat_t quat_start(pose_start.block<3, 3>(0, 0));
        const Vec4_t quat_start_vec(quat_start.x(), quat_start.y(), quat_start.z(), quat_start.w());
        trans_start.push_back(pose_start.block<3, 1>(0, 3));
        quats_start.push_back(quat_start_vec*quat_start_vec.transpose());

        const auto pose_end = iter_end->second->get_cam_pose();
        const Quat_t quat_end(pose_end.block<3, 3>(0, 0));
        const Vec4_t quat_end_vec(quat_end.x(), quat_end.y(), quat_end.z(), quat_end.w());
        trans_end.push_back(pose_end.block<3, 1>(0, 3));
        quats_end.push_back(quat_end_vec*quat_end_vec.transpose());

        start_distance += iter_start->second->window_distance_;
        end_distance += iter_end->second->window_distance_;

        //Set cam pose
        ::g2o::Sim3 pose_sim3 = cam_pose_cw_new.at(2*idx);
        Mat44_t cam_pose_cw = util::converter::to_eigen_cam_pose(pose_sim3.rotation().toRotationMatrix(), pose_sim3.translation()/pose_sim3.scale());
        // iter_start->second->set_cam_pose(cam_pose_cw);
        iter_start->second->set_map_id(new_map_id);
        iter_start->second->cam_pose_cw_after_loop_BA_ = cam_pose_cw;
        iter_start->second->cam_pose_cw_before_BA_ = iter_start->second->get_cam_pose();
        iter_start->second->loop_BA_identifier_ = loop_identifier;

        pose_sim3 = cam_pose_cw_new.at(2*idx+1);
        cam_pose_cw = util::converter::to_eigen_cam_pose(pose_sim3.rotation().toRotationMatrix(), pose_sim3.translation()/pose_sim3.scale());
        // iter_end->second->set_cam_pose(cam_pose_cw);
        iter_end->second->set_map_id(new_map_id);
        iter_end->second->cam_pose_cw_after_loop_BA_ = cam_pose_cw;
        iter_end->second->cam_pose_cw_before_BA_ = iter_end->second->get_cam_pose();
        iter_end->second->loop_BA_identifier_ = loop_identifier;

        iter_start++;
    }
    quat_res_start = calc_average_quart(std::accumulate(quats_start.begin(), quats_start.end(), init));
    quat_res_end = calc_average_quart(std::accumulate(quats_end.begin(), quats_end.end(), init));
    tran_res_start = std::accumulate(trans_start.begin(), trans_start.end(), Vec3_t(0,0,0))/edge_size;
    tran_res_end = std::accumulate(trans_end.begin(), trans_end.end(), Vec3_t(0,0,0))/edge_size;

    //Set start_pos_inv average pose
    Mat44_t start_pose_inv = Mat44_t::Identity();
    Mat33_t rot_wc = quat_res_start.normalized().toRotationMatrix().transpose();
    start_pose_inv.block<3, 3>(0, 0) = rot_wc;
    start_pose_inv.block<3, 1>(0, 3) = -rot_wc*tran_res_start;
    //Set end_pos_inv 的average pose
    Mat44_t end_pose_inv = Mat44_t::Identity();
    rot_wc = quat_res_end.normalized().toRotationMatrix().transpose();
    end_pose_inv.block<3, 3>(0, 0) = rot_wc;
    end_pose_inv.block<3, 1>(0, 3) = -rot_wc*tran_res_end;
    //Calculate the average distance
    start_distance /= edge_size;
    end_distance /= edge_size;

    // Calculate each pose obtained by interpolation
    // If there are only head and tail, it ends, no need to continue slerp
    if (keyframes_.size() <= 2*edge_size){
        return;
    }
    for (auto iter = iter_start; iter != iter_end; iter++) {
        auto keyfrm = iter->second;
        auto id = iter->first;
        Mat44_t kf_pose = keyfrm->get_cam_pose();

        ::g2o::Sim3 start_pos_sim3 = get_sim3_from_pose(kf_pose*start_pose_inv)*opt_sim3_start;
        ::g2o::Sim3 end_pos_sim3 = get_sim3_from_pose(kf_pose*end_pose_inv)*opt_sim3_end;

        Mat44_t start_pos_mat = get_pose_from_sim3(start_pos_sim3);
        Mat44_t end_pos_mat = get_pose_from_sim3(end_pos_sim3);

        // Calculate interpolation
        double weight_end = ((double)keyfrm->window_distance_-start_distance)/(end_distance-start_distance);
        double weight_start = 1-weight_end;

        Quat_t quat_end(end_pos_mat.block<3, 3>(0, 0));
        const Vec3_t trans_end = end_pos_mat.block<3, 1>(0, 3);

        Quat_t quat_start(start_pos_mat.block<3, 3>(0, 0));
        const Vec3_t trans_start = start_pos_mat.block<3, 1>(0, 3);

        Vec3_t trans_res = weight_start*trans_start + weight_end*trans_end;

        Quat_t quat_res = quat_slerp(quat_start, quat_end, weight_end);

        Mat44_t cam_pose_cw_res = Mat44_t::Identity();
        const Mat33_t rot_cw(quat_res.normalized().toRotationMatrix());
        const Vec3_t trans_cw(trans_res);
        cam_pose_cw_res.block<3, 3>(0, 0) = rot_cw;
        cam_pose_cw_res.block<3, 1>(0, 3) = trans_cw;

        // keyfrm->set_cam_pose(cam_pose_cw_res);
        keyfrm->set_map_id(new_map_id);
        keyfrm->cam_pose_cw_after_loop_BA_ = cam_pose_cw_res;
        keyfrm->cam_pose_cw_before_BA_ = keyfrm->get_cam_pose();
        keyfrm->loop_BA_identifier_ = loop_identifier;
        // create Sim3 from SE3
        float kf_scale = weight_start*opt_sim3_start.scale()+weight_end*opt_sim3_end.scale();
        corrected_Sim3s_wc[id] =g2o::Sim3(rot_cw, trans_cw*kf_scale, kf_scale).inverse();
    }
    // Update distance
    auto iter_last = keyframes_.begin();
    iter_last->second->window_distance_ = 0;

    auto iter_curr = keyframes_.begin();
    iter_curr++;
    while(iter_curr!=keyframes_.end()){
        const Mat44_t velocity_now = iter_curr->second->get_cam_pose() * iter_last->second->get_cam_pose_inv();
        Vec7_t distance_vec = ::g2o::Sim3(velocity_now.block<3, 3>(0, 0), velocity_now.block<3, 1>(0, 3), 1).log();
        iter_curr->second->window_distance_ = iter_last->second->window_distance_ + distance_vec.norm();
        iter_last++;
        iter_curr++;
    }
}

}
}

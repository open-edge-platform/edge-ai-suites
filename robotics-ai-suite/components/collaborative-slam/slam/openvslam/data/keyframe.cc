// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "data/keyframe.h"
#include "camera/equirectangular.h"
#include "camera/fisheye.h"
#include "camera/perspective.h"
#include "data/bow_database.h"
#include "data/common.h"
#include "data/frame.h"
#include "data/landmark.h"
#include "data/map_database.h"
#include "feature/orb_params.h"
#include "util/converter.h"
#include "data/imu.h"
#include "data/odom.h"
#include <nlohmann/json.hpp>
#include <spdlog/spdlog.h>

extern bool is_server_node;

namespace openvslam {
namespace data {

std::atomic<KeyframeID> keyframe::next_id_{0};

#ifdef ENABLE_SEMANTIC_SLAM
InferenceEngine::InferRequest keyframe::inferRequest;
int keyframe::outChannels;
int keyframe::outHeight;
int keyframe::outWidth;
std::string keyframe::inName;
std::string keyframe::outName;


keyframe::keyframe(frame& frm, map_database* map_db, bow_database* bow_db)
    :  // meta information
      ref_keyfrm_(frm.ref_keyfrm_),
      client_id_(0xFF),
      id_(next_id_++),
      src_frm_id_(frm.id_),
      timestamp_(frm.timestamp_),
      is_considered_(false),
      is_fixed_(false),
      // camera parameters
      camera_(frm.camera_),
      depth_thr_(frm.depth_thr_),
      // constant observations
      num_keypts_(frm.num_keypts_),
      keypts_(frm.keypts_),
      undist_keypts_(frm.undist_keypts_),
      bearings_(frm.bearings_),
      keypt_indices_in_cells_(frm.keypt_indices_in_cells_),
      stereo_x_right_(frm.stereo_x_right_),
      depths_(frm.depths_),
      descriptors_(frm.descriptors_.clone()),
      // BoW
      // bow_vec_(frm.bow_vec_),
      // bow_feat_vec_(frm.bow_feat_vec_),
      // covisibility graph node (connections is not assigned yet)
      graph_node_(std::unique_ptr<graph_node>(new graph_node(this, true))),
      // ORB scale pyramid
      num_scale_levels_(frm.num_scale_levels_),
      scale_factor_(frm.scale_factor_),
      log_scale_factor_(frm.log_scale_factor_),
      scale_factors_(frm.scale_factors_),
      level_sigma_sq_(frm.level_sigma_sq_),
      inv_level_sigma_sq_(frm.inv_level_sigma_sq_),
      // observations
      landmarks_(frm.landmarks_),
      // databases
      map_db_(map_db),
      bow_db_(bow_db),
      bow_vocab_(frm.bow_vocab_),
      update_from_server_(frm.update_from_server_),
      should_be_fixed_in_optimization_(false),
      map_id_(0xFFFFFFFF),
      is_origin_(false)
{
    if(id_ == 0)
        segment_video_init();
    segment_video_frame(frm.segment_rgb_);
    update_keypoint(frm);
    // set pose parameters (cam_pose_wc_, cam_center_) using frm.cam_pose_cw_
    set_cam_pose(frm.cam_pose_cw_);
    imu_velocity_.setZero();  // Or get it from frame? Maybe calculate from camera pose change is enough!
    imu_bias_ = IMU_Preintegration::last_bias_;
}
#else
keyframe::keyframe(const frame& frm, map_database* map_db, bow_database* bow_db)
    :  // meta information
      ref_keyfrm_(frm.ref_keyfrm_),
      client_id_(0xFF),
      update_from_server_(frm.update_from_server_),
      id_(next_id_++),
      src_frm_id_(frm.id_),
      timestamp_(frm.timestamp_),
      is_considered_(false),
      is_fixed_(false),
      // camera parameters
      camera_(frm.camera_),
      depth_thr_(frm.depth_thr_),
      // constant observations
      num_keypts_(frm.num_keypts_),
      keypts_(frm.keypts_),
      undist_keypts_(frm.undist_keypts_),
      bearings_(frm.bearings_),
      keypt_indices_in_cells_(frm.keypt_indices_in_cells_),
      stereo_x_right_(frm.stereo_x_right_),
      depths_(frm.depths_),
      descriptors_(frm.descriptors_.clone()),
      // covisibility graph node (connections is not assigned yet)
      graph_node_(std::unique_ptr<graph_node>(new graph_node(this, true))),
      // ORB scale pyramid
      num_scale_levels_(frm.num_scale_levels_),
      scale_factor_(frm.scale_factor_),
      log_scale_factor_(frm.log_scale_factor_),
      scale_factors_(frm.scale_factors_),
      level_sigma_sq_(frm.level_sigma_sq_),
      inv_level_sigma_sq_(frm.inv_level_sigma_sq_),
      should_be_fixed_in_optimization_(false),
      // observations
      landmarks_(frm.landmarks_),
      // databases
      map_db_(map_db),
      bow_db_(bow_db),
      bow_vocab_(frm.bow_vocab_),
      map_id_(0xFFFFFFFF),
      is_origin_(false)
{
    // set pose parameters (cam_pose_wc_, cam_center_) using frm.cam_pose_cw_
    set_cam_pose(frm.cam_pose_cw_);
    imu_velocity_.setZero();  // Or get it from frame? Maybe calculate from camera pose change is enough!
    imu_bias_ = IMU_Preintegration::last_bias_;
}
#endif

keyframe::keyframe(const frame& frm, map_database* map_db, bow_database* bow_db, ClientID client_id, MapID map_id)
    :  // meta information
      ref_keyfrm_(frm.ref_keyfrm_),
      client_id_(client_id),
      id_(next_id_++),
      src_frm_id_(frm.id_),
      timestamp_(frm.timestamp_),
      is_considered_(false),
      is_fixed_(false),
      // camera parameters
      camera_(frm.camera_),
      depth_thr_(frm.depth_thr_),
      // constant observations
      num_keypts_(frm.num_keypts_),
      keypts_(frm.keypts_),
      undist_keypts_(frm.undist_keypts_),
      bearings_(frm.bearings_),
      keypt_indices_in_cells_(frm.keypt_indices_in_cells_),
      stereo_x_right_(frm.stereo_x_right_),
      depths_(frm.depths_),
      descriptors_(frm.descriptors_.clone()),
      // BoW
      bow_vec_(frm.bow_vec_),
      bow_feat_vec_(frm.bow_feat_vec_),
      // covisibility graph node (connections is not assigned yet)
      graph_node_(std::make_unique<graph_node>(this, true)),
      // ORB scale pyramid
      num_scale_levels_(frm.num_scale_levels_),
      scale_factor_(frm.scale_factor_),
      log_scale_factor_(frm.log_scale_factor_),
      scale_factors_(frm.scale_factors_),
      level_sigma_sq_(frm.level_sigma_sq_),
      inv_level_sigma_sq_(frm.inv_level_sigma_sq_),
      should_be_fixed_in_optimization_(false),
      // observations
      landmarks_(frm.landmarks_),
      // databases
      map_db_(map_db),
      bow_db_(bow_db),
      bow_vocab_(frm.bow_vocab_),
      map_id_(map_id),
      is_origin_(false)
{
    // set pose parameters (cam_pose_wc_, cam_center_) using frm.cam_pose_cw_
    set_cam_pose(frm.cam_pose_cw_);
}

keyframe::keyframe(const KeyframeID id, const KeyframeID src_frm_id, const double timestamp,
                   const Mat44_t& cam_pose_cw, camera::base* camera, const float depth_thr,
                   const unsigned int num_keypts, const std::vector<cv::KeyPoint>& keypts,
                   const std::vector<cv::KeyPoint>& undist_keypts, const eigen_alloc_vector<Vec3_t>& bearings,
                   const std::vector<float>& stereo_x_right, const std::vector<float>& depths,
                   const cv::Mat& descriptors, const unsigned int num_scale_levels, const float scale_factor,
                   bow_vocabulary* bow_vocab, bow_database* bow_db, map_database* map_db)
    :  // meta information
      ref_keyfrm_(nullptr),
      client_id_(0xFF),
      id_(id),
      src_frm_id_(src_frm_id),
      timestamp_(timestamp),
      is_considered_(false),
      is_fixed_(false),
      // camera parameters
      camera_(camera),
      depth_thr_(depth_thr),
      // constant observations
      num_keypts_(num_keypts),
      keypts_(keypts),
      undist_keypts_(undist_keypts),
      bearings_(bearings),
      keypt_indices_in_cells_(assign_keypoints_to_grid(camera, undist_keypts)),
      stereo_x_right_(stereo_x_right),
      depths_(depths),
      descriptors_(descriptors.clone()),
      // graph node (connections is not assigned yet)
      graph_node_(std::unique_ptr<graph_node>(new graph_node(this, false))),
      // ORB scale pyramid
      num_scale_levels_(num_scale_levels),
      scale_factor_(scale_factor),
      log_scale_factor_(std::log(scale_factor)),
      scale_factors_(orb_params::calc_scale_factors(num_scale_levels, scale_factor)),
      level_sigma_sq_(orb_params::calc_level_sigma_sq(num_scale_levels, scale_factor)),
      inv_level_sigma_sq_(orb_params::calc_inv_level_sigma_sq(num_scale_levels, scale_factor)),
      // others
      should_be_fixed_in_optimization_(false),
      landmarks_(std::vector<landmark*>(num_keypts, nullptr)),
      // databases
      map_db_(map_db),
      bow_db_(bow_db),
      bow_vocab_(bow_vocab),
      map_id_(0xFFFFFFFF),
      is_origin_(false)
{
    // compute BoW (bow_vec_, bow_feat_vec_) using descriptors_
    compute_bow();
    // set pose parameters (cam_pose_wc_, cam_center_) using cam_pose_cw_
    set_cam_pose(cam_pose_cw);

    imu_velocity_.setZero();
    imu_bias_ = IMU_Preintegration::last_bias_;

    // TODO: should set the pointers of landmarks_ using add_landmark()

    // TODO: should compute connected_keyfrms_and_weights_
    // TODO: should compute ordered_connected_keyfrms_
    // TODO: should compute ordered_weights_

    // TODO: should set spanning_parent_ using set_spanning_parent()
    // TODO: should set spanning_children_ using add_spanning_child()
    // TODO: should set loop_edges_ using add_loop_edge()
}

keyframe::keyframe(const KeyframeID id, const KeyframeID src_frm_id, const double timestamp,
                   const Mat44_t& cam_pose_cw, camera::base* camera, const float depth_thr,
                   const unsigned int num_keypts, const std::vector<cv::KeyPoint>& keypts,
                   const std::vector<cv::KeyPoint>& undist_keypts, const eigen_alloc_vector<Vec3_t>& bearings,
                   const std::vector<float>& stereo_x_right, [[maybe_unused]] const std::vector<float>& depths,
                   const cv::Mat& descriptors, const unsigned int num_scale_levels, const float scale_factor,
                   bow_vocabulary* bow_vocab, bow_database* bow_db, map_database* map_db, ClientID client_id,
                   MapID map_id)

    :  // meta information
      ref_keyfrm_(nullptr),
      client_id_(client_id),
      id_(id),
      src_frm_id_(src_frm_id),
      timestamp_(timestamp),
      is_considered_(false),
      is_fixed_(false),
      // camera parameters
      camera_(camera),
      depth_thr_(depth_thr),
      // constant observations
      num_keypts_(num_keypts),
      keypts_(keypts),
      undist_keypts_(undist_keypts),
      bearings_(bearings),
      keypt_indices_in_cells_(assign_keypoints_to_grid(camera, undist_keypts)),
      stereo_x_right_(stereo_x_right),
      // depths_(depths),  //has no usage
      descriptors_(descriptors.clone()),
      // graph node (connections is not assigned yet)
      graph_node_(std::make_unique<graph_node>(this, true)),  // Modified here!
      // ORB scale pyramid
      num_scale_levels_(num_scale_levels),
      scale_factor_(scale_factor),
      log_scale_factor_(std::log(scale_factor)),
      scale_factors_(orb_params::calc_scale_factors(num_scale_levels, scale_factor)),
      level_sigma_sq_(orb_params::calc_level_sigma_sq(num_scale_levels, scale_factor)),
      inv_level_sigma_sq_(orb_params::calc_inv_level_sigma_sq(num_scale_levels, scale_factor)),
      should_be_fixed_in_optimization_(false),
      // others
      landmarks_(std::vector<landmark*>(num_keypts, nullptr)),
      // databases
      map_db_(map_db),
      bow_db_(bow_db),
      bow_vocab_(bow_vocab),
      map_id_(map_id),
      is_origin_(false)
{
    // compute BoW (bow_vec_, bow_feat_vec_) using descriptors_
    compute_bow();
    // set pose parameters (cam_pose_wc_, cam_center_) using cam_pose_cw_
    set_cam_pose(cam_pose_cw);

    // TODO: should set the pointers of landmarks_ using add_landmark()

    // TODO: should compute connected_keyfrms_and_weights_
    // TODO: should compute ordered_connected_keyfrms_
    // TODO: should compute ordered_weights_

    // TODO: should set spanning_parent_ using set_spanning_parent()
    // TODO: should set spanning_children_ using add_spanning_child()
    // TODO: should set loop_edges_ using add_loop_edge()
}
#ifdef ENABLE_SEMANTIC_SLAM
void keyframe::segment_video_init()
{
    //TO-DO :- Add the network model file path to config file
    network_path =  ros::package::getPath("univloc_tracker")+"/inference_model/model.xml";
    network = ie.ReadNetwork(network_path);
    inputShapes = network.getInputShapes();
    //if (inputShapes.size() != 1)
        //throw std::runtime_error("Demo supports topologies only with 1 input");
    inName = inputShapes.begin()->first;
    inSizeVector = inputShapes.begin()->second;
    //if (inSizeVector.size() != 4 || inSizeVector[1] != 3)
        //throw std::runtime_error("3-channel 4-dimensional model's input is expected");
    inSizeVector[0] = 1;  // set batch size to 1
    network.reshape(inputShapes);
    inputInfo = *network.getInputsInfo().begin()->second;
    inputInfo.getPreProcess().setResizeAlgorithm(InferenceEngine::ResizeAlgorithm::RESIZE_BILINEAR);
    inputInfo.setLayout(InferenceEngine::Layout::NHWC);
    inputInfo.setPrecision(InferenceEngine::Precision::U8);
    
    outputsDataMap = network.getOutputsInfo();
    //if (outputsDataMap.size() != 1) throw std::runtime_error("Demo supports topologies only with 1 output");
    outName = outputsDataMap.begin()->first;
    InferenceEngine::Data& data_IE = *outputsDataMap.begin()->second;
    // if the model performs ArgMax, its output type can be I32 but for models that return heatmaps for each
    // class the output is usually FP32. Reset the precision to avoid handling different types with switch in
    // postprocessing
    data_IE.setPrecision(InferenceEngine::Precision::FP32);
    outSizeVector = data_IE.getTensorDesc().getDims();

    switch(outSizeVector.size()) {
        case 3:
            outChannels = 0;
            outHeight = outSizeVector[1];
            outWidth = outSizeVector[2];
            break;
        case 4:
            outChannels = outSizeVector[1];
            outHeight = outSizeVector[2];
            outWidth = outSizeVector[3];
            break;
        default:
            break;
            //throw std::runtime_error("Unexpected output blob shape. Only 4D and 3D output blobs are"
            //    "supported.");
    }
    executableNetwork = ie.LoadNetwork(network, "GPU");
    inferRequest = executableNetwork.CreateInferRequest();
}

void keyframe::segment_video_frame(const cv::Mat& img)
{
    cv::Mat img_rgb;
    cv::resize(img,img_rgb,cv::Size(outWidth,outHeight));
    InferenceEngine::TensorDesc tDesc(InferenceEngine::Precision::U8,
                                      {1, img_rgb.channels(), img_rgb.rows,img_rgb.cols},InferenceEngine::Layout::NHWC);
    InferenceEngine::Blob::Ptr bptr = InferenceEngine::make_shared_blob<uint8_t>(tDesc, img_rgb.data);

    inferRequest.SetBlob(inName, bptr);
#ifdef DISPLAY_SEGMENTATION
    cv::Mat resImg, maskImg(outHeight, outWidth, CV_8UC3);
#endif
    cv::Mat maskout(outHeight, outWidth, CV_8UC1);

    inferRequest.Infer();
    
    InferenceEngine::LockedMemory<const void> outMapped = InferenceEngine::as<InferenceEngine::MemoryBlob>(inferRequest.GetBlob(keyframe::outName))->rmap();
    const float * const predictions = outMapped.as<float*>();
        for (int rowId = 0; rowId < outHeight; ++rowId)
        {
           for (int colId = 0; colId < outWidth; ++colId)
           {
               std::size_t classId = 0;
               if (outChannels < 2) 
               {  // assume the output is already ArgMax'ed
                   classId = static_cast<std::size_t>(predictions[rowId * outWidth + colId]);
               } 
               else 
               {
                   float maxProb = -1.0f;
                   for (int chId = 0; chId < outChannels; ++chId) {
                       float prob = predictions[chId * outHeight * outWidth + rowId * outWidth + colId];
                       if (prob > maxProb) {
                           classId = chId;
                           maxProb = prob;
                       }
                   }
               }
                if(classId == 11) 	
                {
#ifdef DISPLAY_SEGMENTATION
                    maskImg.at<cv::Vec3b>(rowId, colId) = colors[classId];
#endif
                    maskout.at<uchar>(rowId,colId) = 0;
                }            
                else
                {
#ifdef DISPLAY_SEGMENTATION
                    maskImg.at<cv::Vec3b>(rowId, colId) = colors[0];
#endif
                    maskout.at<uchar>(rowId,colId) = 1;
            }
            	
           }
        }
        cv::resize(maskout, segment_mask, cv::Size(img.cols,img.rows));
#ifdef DISPLAY_SEGMENTATION
        cv::resize(maskImg, resImg, img_rgb.size());
        double blending = 0.3;
        resImg = img_rgb * blending + resImg * (1 - blending);
        cv::resize(resImg, resImg, img.size());
        cv::imshow("Segment image", resImg);
        cv::waitKey(15);
#endif
}

void keyframe::update_keypoint(data::frame& frm)
{

    for(unsigned int i = 0; i < frm.keypts_.size(); i++)
    {
        cv::KeyPoint temp = frm.keypts_[i];
        if (segment_mask.at<uchar>(temp.pt.x,temp.pt.y) == 0)
        {
            frm.segment_outlier_flags_[i] = true;
        }
    }
    //std::cout<<"KeyFrame keypoint"<<num_keypts_<<std::endl;
}
#endif

void keyframe::set_will_be_erazed(bool will_be_erazed) { will_be_erased_ = will_be_erazed; }

void keyframe::change_to_new_map(data::map_database* new_map_db) { map_db_ = new_map_db; }

void keyframe::set_origin() { is_origin_ = true; }

void keyframe::clear_origin() { is_origin_ = false; }

bool keyframe::can_observe(const landmark* lm) const
{
    const Vec3_t pos_w = lm->get_pos_in_world();
    Vec2_t reproj;
    float right_x;
    return camera_->reproject_to_image(cam_pose_cw_.block(0, 0, 3, 3), cam_pose_cw_.block(0, 3, 3, 1), pos_w, reproj,
                                       right_x);
}

nlohmann::json keyframe::to_json() const {
    if (is_server_node)
        return to_json_server();
    else
        return to_json_tracker();
}

nlohmann::json keyframe::to_json_tracker() const
{
    // extract landmark IDs
    std::vector<LandmarkID> landmark_ids(landmarks_.size(), -1);
    for (unsigned int i = 0; i < landmark_ids.size(); ++i) {
        if (landmarks_.at(i) && !landmarks_.at(i)->will_be_erased()) {
            landmark_ids.at(i) = landmarks_.at(i)->id_;
        }
    }

    // extract spanning tree parent
    auto spanning_parent = graph_node_->get_spanning_parent();

    // extract spanning tree children
    const auto spanning_children = graph_node_->get_spanning_children();
    std::vector<KeyframeID> spanning_child_ids;
    spanning_child_ids.reserve(spanning_children.size());
    for (const auto& spanning_child : spanning_children) {
        spanning_child_ids.push_back(spanning_child->id_);
    }

    // extract loop edges
    const auto loop_edges = graph_node_->get_loop_edges();
    std::vector<KeyframeID> loop_edge_ids;
    for (const auto& loop_edge : loop_edges) {
        loop_edge_ids.push_back(loop_edge->id_);
    }

    return {{"src_frm_id", src_frm_id_},
            {"ts", timestamp_},
            {"cam", camera_->name_},
            {"depth_thr", depth_thr_},
            // camera pose
            {"rot_cw", convert_rotation_to_json(cam_pose_cw_.block<3, 3>(0, 0))},
            {"trans_cw", convert_translation_to_json(cam_pose_cw_.block<3, 1>(0, 3))},
            // features and observations
            {"n_keypts", num_keypts_},
            {"keypts", convert_keypoints_to_json(keypts_)},
            {"undists", convert_undistorted_to_json(undist_keypts_)},
            {"x_rights", stereo_x_right_},
            {"depths", depths_},
            {"descs", convert_descriptors_to_json(descriptors_)},
            {"lm_ids", landmark_ids},
            // orb scale information
            {"n_scale_levels", num_scale_levels_},
            {"scale_factor", scale_factor_},
            // graph information
            {"span_parent", spanning_parent ? spanning_parent->id_ : -1},
            {"span_children", spanning_child_ids},
            {"loop_edges", loop_edge_ids}};
}

nlohmann::json keyframe::to_json_server() const
{
    // extract landmark IDs

    std::vector<std::string> landmark_ids(landmarks_.size(), "-1");
    for (unsigned int i = 0; i < landmark_ids.size(); ++i) {
        if (landmarks_.at(i) && !landmarks_.at(i)->will_be_erased()) {
            landmark_ids.at(i) = std::to_string(landmarks_.at(i)->id_);
        }
    }

    // extract spanning tree parent
    auto spanning_parent = graph_node_->get_spanning_parent();

    // extract spanning tree children
    const auto spanning_children = graph_node_->get_spanning_children();
    std::vector<std::string> spanning_child_ids;
    spanning_child_ids.reserve(spanning_children.size());
    for (const auto& spanning_child : spanning_children) {
        spanning_child_ids.push_back(std::to_string(spanning_child->id_));
    }

    // extract loop edges
    const auto loop_edges = graph_node_->get_loop_edges();
    std::vector<std::string> loop_edge_ids;
    for (const auto& loop_edge : loop_edges) {
        loop_edge_ids.push_back(std::to_string(loop_edge->id_));
    }

    return {{"src_frm_id", std::to_string(src_frm_id_)},
            {"ts", timestamp_},
            {"cam", camera_->name_},
            {"depth_thr", depth_thr_},
            // camera pose
            {"rot_cw", convert_rotation_to_json(cam_pose_cw_.block<3, 3>(0, 0))},
            {"trans_cw", convert_translation_to_json(cam_pose_cw_.block<3, 1>(0, 3))},
            // features and observations
            {"n_keypts", num_keypts_},
            {"keypts", convert_keypoints_to_json(keypts_)},
            {"undists", convert_undistorted_to_json(undist_keypts_)},
            {"x_rights", stereo_x_right_},
            //{"depths", depths_}, depth has no usage!
            {"descs", convert_descriptors_to_json(descriptors_)},
            {"lm_ids", landmark_ids},
            // orb scale information
            {"n_scale_levels", num_scale_levels_},
            {"scale_factor", scale_factor_},
            // graph information
            {"span_parent", spanning_parent ? std::to_string(spanning_parent->id_) : "-1"},
            {"span_children", spanning_child_ids},
            {"loop_edges", loop_edge_ids},
            {"map_id", std::to_string(map_id_)},
            {"client_id", client_id_},
            {"front_and_rear_constraint_keyframe_id",
             graph_node_->get_front_rear_camera_constraint().first == -1
                 ? std::to_string(-1)
                 : std::to_string(graph_node_->get_front_rear_camera_constraint().second->id_)}};
}

void keyframe::initial_start_id(const KeyframeID start_id) { next_id_ = start_id; }

void keyframe::set_update_from_server(bool update_from_server) { update_from_server_ = update_from_server; }

bool keyframe::is_update_from_server() { return update_from_server_; }

void keyframe::set_will_be_erased() { will_be_erased_ = true; }

bool keyframe::is_new_created()
{
    std::lock_guard<std::mutex> lock(mtx_newcreated_);
    return new_created_;
}

void keyframe::set_not_new_created()
{
    std::lock_guard<std::mutex> lock(mtx_newcreated_);
    new_created_ = false;
}

void keyframe::set_cam_pose(const Mat44_t& cam_pose_cw)
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    cam_pose_cw_ = cam_pose_cw;

    const Mat33_t rot_cw = cam_pose_cw_.block<3, 3>(0, 0);
    const Vec3_t trans_cw = cam_pose_cw_.block<3, 1>(0, 3);
    const Mat33_t rot_wc = rot_cw.transpose();
    cam_center_ = -rot_wc * trans_cw;

    cam_pose_wc_ = Mat44_t::Identity();
    cam_pose_wc_.block<3, 3>(0, 0) = rot_wc;
    cam_pose_wc_.block<3, 1>(0, 3) = cam_center_;
}

void keyframe::set_cam_pose(const g2o::SE3Quat& cam_pose_cw)
{
    set_cam_pose(util::converter::to_eigen_mat(cam_pose_cw));
}

Mat44_t keyframe::get_cam_pose() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return cam_pose_cw_;
}

void keyframe::set_map_id(const MapID map_id)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    map_id_ = map_id;
}

MapID keyframe::get_map_id() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return map_id_;
}

Mat44_t keyframe::get_cam_pose_inv() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return cam_pose_wc_;
}

Vec3_t keyframe::get_cam_center() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return cam_center_;
}

Mat33_t keyframe::get_rotation() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return cam_pose_cw_.block<3, 3>(0, 0);
}

Vec3_t keyframe::get_translation() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return cam_pose_cw_.block<3, 1>(0, 3);
}

Mat33_t keyframe::get_imu_rotation() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return cam_pose_wc_.block(0, 0, 3, 3) * data::IMU_Preintegration::Tci_.block(0, 0, 3, 3);
}

Vec3_t keyframe::get_imu_position() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return cam_pose_wc_.block(0, 0, 3, 3) * data::IMU_Preintegration::Tci_.block(0, 3, 3, 1) -
           cam_pose_wc_.block(0, 0, 3, 3) * cam_pose_cw_.block(0, 3, 3, 1);
}

void keyframe::set_imu_constraint(data::keyframe* ref_keyframe,
                                  std::shared_ptr<data::IMU_Preintegration> imu_constraint)
{
    imu_constraint_ = std::make_pair(ref_keyframe, imu_constraint);
}

std::pair<data::keyframe*, std::shared_ptr<IMU_Preintegration>> keyframe::get_imu_constraint() const
{
    return imu_constraint_;
}

void keyframe::set_new_imu_bias(const Eigen::VectorXd imu_bias)
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    imu_bias_ = imu_bias;
    if (imu_constraint_.second.get()) {
        imu_constraint_.second->set_new_imu_bias(imu_bias_);
    }
}

Eigen::VectorXd keyframe::get_imu_bias() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return imu_bias_;
}

void keyframe::set_imu_velocity(const Eigen::Vector3d& v)
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    imu_velocity_ = v;
}

Eigen::Vector3d keyframe::get_imu_velocity() const
{
    std::lock_guard<std::mutex> lock(mtx_pose_);
    return imu_velocity_;
}

void keyframe::update_imu_link()
{
    if (next_keyframe_) next_keyframe_->pre_keyframe_ = nullptr;

    if (next_keyframe_ && pre_keyframe_) {
        spdlog::debug("Merge IMU data between keyframe {} and keyframe {}", next_keyframe_->id_,
                      imu_constraint_.first->id_);
        assert(*pre_keyframe_ == *(imu_constraint_.first));
        auto next_imu_constraint = next_keyframe_->get_imu_constraint();
        next_imu_constraint.second->merge_preintegration(imu_constraint_.second);
        next_keyframe_->set_imu_constraint(imu_constraint_.first, next_imu_constraint.second);
        pre_keyframe_->next_keyframe_ = next_keyframe_;
        next_keyframe_->pre_keyframe_ = pre_keyframe_;
    }
}

void keyframe::compute_bow()
{
    if (bow_vec_.empty() || bow_feat_vec_.empty()) {
#ifdef USE_DBOW2
        bow_vocab_->transform(util::converter::to_desc_vec(descriptors_), bow_vec_, bow_feat_vec_, 4);
#else
        bow_vocab_->transform(descriptors_, 4, bow_vec_, bow_feat_vec_);
#endif
    }
}

void keyframe::add_landmark(landmark* lm, const unsigned int idx)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    landmarks_.at(idx) = lm;
}

void keyframe::erase_landmark_with_index(const unsigned int idx)
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    landmarks_.at(idx) = nullptr;
}

void keyframe::erase_landmark(landmark* lm)
{
    int idx = lm->get_index_in_keyframe(this);
    if (0 <= idx) {
        landmarks_.at(static_cast<unsigned int>(idx)) = nullptr;
    }
}

void keyframe::replace_landmark(landmark* lm, const unsigned int idx) { landmarks_.at(idx) = lm; }

size_t keyframe::get_num_landmarks() const { return landmarks_.size(); }

std::vector<landmark*> keyframe::get_landmarks() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    return landmarks_;
}

std::set<landmark*> keyframe::get_valid_landmarks() const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    std::set<landmark*> valid_landmarks;

    for (const auto lm : landmarks_) {
        if (!lm) {
            continue;
        }
        if (lm->will_be_erased()) {
            continue;
        }

        valid_landmarks.insert(lm);
    }

    return valid_landmarks;
}

unsigned int keyframe::get_num_tracked_landmarks(const unsigned int min_num_obs_thr) const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    unsigned int num_tracked_lms = 0;

    if (0 < min_num_obs_thr) {
        for (const auto lm : landmarks_) {
            if (!lm) {
                continue;
            }
            if (lm->will_be_erased()) {
                continue;
            }

            // spdlog::debug("min_num_obs_thr: {}, lm observation num: {}", min_num_obs_thr, lm->num_observations());
            if (min_num_obs_thr <= lm->num_observations()) {
                ++num_tracked_lms;
            }
        }
    } else {
        for (const auto lm : landmarks_) {
            if (!lm) {
                continue;
            }
            if (lm->will_be_erased()) {
                continue;
            }

            ++num_tracked_lms;
        }
    }

    return num_tracked_lms;
}

landmark* keyframe::get_landmark(const unsigned int idx) const
{
    std::lock_guard<std::mutex> lock(mtx_observations_);
    assert(("no such landmark" + std::to_string(idx) + "in this keyframe " + std::to_string(id_),
            idx < landmarks_.size()));
    return landmarks_.at(idx);
}

std::vector<unsigned int> keyframe::get_keypoints_in_cell(const float ref_x, const float ref_y,
                                                          const float margin) const
{
    return data::get_keypoints_in_cell(camera_, undist_keypts_, keypt_indices_in_cells_, ref_x, ref_y, margin);
}

Vec3_t keyframe::triangulate_stereo(const unsigned int idx) const
{
    assert(camera_->setup_type_ != camera::setup_type_t::Monocular &&
           camera_->setup_type_ != camera::setup_type_t::Monocular_Inertial);

    switch (camera_->model_type_) {
        case camera::model_type_t::Perspective: {
            auto camera = static_cast<camera::perspective*>(camera_);

            const float depth = depths_.at(idx);
            if (0.0 < depth) {
                const float x = undist_keypts_.at(idx).pt.x;
                const float y = undist_keypts_.at(idx).pt.y;
                const float unproj_x = (x - camera->cx_) * depth * camera->fx_inv_;
                const float unproj_y = (y - camera->cy_) * depth * camera->fy_inv_;
                const Vec3_t pos_c{unproj_x, unproj_y, depth};

                std::lock_guard<std::mutex> lock(mtx_pose_);
                return cam_pose_wc_.block<3, 3>(0, 0) * pos_c + cam_pose_wc_.block<3, 1>(0, 3);
            } else {
                return Vec3_t::Zero();
            }
        }
        case camera::model_type_t::Fisheye: {
            auto camera = static_cast<camera::fisheye*>(camera_);

            const float depth = depths_.at(idx);
            if (0.0 < depth) {
                const float x = undist_keypts_.at(idx).pt.x;
                const float y = undist_keypts_.at(idx).pt.y;
                const float unproj_x = (x - camera->cx_) * depth * camera->fx_inv_;
                const float unproj_y = (y - camera->cy_) * depth * camera->fy_inv_;
                const Vec3_t pos_c{unproj_x, unproj_y, depth};

                std::lock_guard<std::mutex> lock(mtx_pose_);
                return cam_pose_wc_.block<3, 3>(0, 0) * pos_c + cam_pose_wc_.block<3, 1>(0, 3);
            } else {
                return Vec3_t::Zero();
            }
        }
        case camera::model_type_t::Equirectangular: {
            throw std::runtime_error("Not implemented: Stereo or RGBD of equirectangular camera model");
        }
    }

    return Vec3_t::Zero();
}

float keyframe::compute_median_depth(const bool abs) const
{
    std::vector<landmark*> landmarks;
    Mat44_t cam_pose_cw;
    {
        std::lock_guard<std::mutex> lock1(mtx_observations_);
        std::lock_guard<std::mutex> lock2(mtx_pose_);
        landmarks = landmarks_;
        cam_pose_cw = cam_pose_cw_;
    }

    std::vector<float> depths;
    depths.reserve(num_keypts_);
    const Vec3_t rot_cw_z_row = cam_pose_cw.block<1, 3>(2, 0);
    const float trans_cw_z = cam_pose_cw(2, 3);

    for (const auto lm : landmarks) {
        if (!lm) {
            continue;
        }
        const Vec3_t pos_w = lm->get_pos_in_world();
        const auto pos_c_z = rot_cw_z_row.dot(pos_w) + trans_cw_z;
        depths.push_back(abs ? std::abs(pos_c_z) : pos_c_z);
    }

    std::sort(depths.begin(), depths.end());

    return depths.at((depths.size() - 1) / 2);
}

bow_vocabulary* keyframe::get_bow_vocab() const
{
    std::lock_guard<std::mutex> lock(mtx_bow_);
    return bow_vocab_;
}

void keyframe::set_not_to_be_erased() { cannot_be_erased_ = true; }

void keyframe::set_to_be_erased()
{
    if (!graph_node_->has_loop_edge()) {
        cannot_be_erased_ = false;
    }
}

void keyframe::prepare_for_erasing(bool is_redundant, bool is_server)
{
    // for single slam, cannot erase the origin
    // for multi slam, the origin maybe can be erased
    if (!is_server) {
        if (map_db_->origin_keyfrm_ && *this == *(map_db_->origin_keyfrm_)) {
            return;
        }

        // cannot erase if the frag is raised
        if (cannot_be_erased_) {
            return;
        }
    }

    if (!will_be_erased_)
        update_imu_link();  // If will_be_erased_, it means this keyframe has been removed from local map and
                            // the imu link has already been updated

    // 1. raise the flag which indicates it has been erased

    will_be_erased_ = true;

    // 2. remove associations between keypoints and landmarks

    for (const auto lm : landmarks_) {
        if (!lm) {
            continue;
        }
        lm->erase_observation(this, is_server);
    }

    // 3. recover covisibility graph and spanning tree

    // remove covisibility information
    graph_node_->erase_all_connections();
    // recover spanning tree
    if (!map_db_->get_server_virtual_keyframe() || id_ != map_db_->get_server_virtual_keyframe()->id_) {
        graph_node_->recover_spanning_connections();
    }

    // 4. update frame statistics
    if (graph_node_->get_spanning_parent())
        map_db_->replace_reference_keyframe(this, graph_node_->get_spanning_parent());

    // 5. remove myself from the databased

    map_db_->erase_keyframe(this, is_redundant);
    bow_db_->erase_keyframe(this);
}


void keyframe::prepare_for_erasing()
{
    // cannot erase the origin
    if (is_origin_) {
        return;
    }

    // cannot erase if the flag is raised
    if (cannot_be_erased_) {
        return;
    }

    if (!graph_node_->get_spanning_parent()) return;

    // 1. raise the flag which indicates it has been erased

    will_be_erased_ = true;

    // 2. remove associations between keypoints and landmarks

    for (const auto lm : landmarks_) {
        if (!lm) {
            continue;
        }
        lm->erase_observation(this);
    }

    // 3. recover covisibility graph and spanning tree

    // remove covisibility information
    graph_node_->erase_all_connections();
    // recover spanning tree
    graph_node_->recover_spanning_connections();

    // 4. update frame statistics
    map_db_->replace_reference_keyframe(this, graph_node_->get_spanning_parent());

    // 5. remove myself from the databased

    map_db_->erase_keyframe(this);
    bow_db_->erase_keyframe(this);
}

void keyframe::prepare_for_erasing_remapping()
{
    if (!is_origin_ && !graph_node_->get_spanning_parent()) {
        spdlog::warn("Spanning parent of non-origin keyframe {} is nullptr!", id_);
        return;
    }
    spdlog::debug("Start to erase keyframe {}", id_);

    /*
        1. raise the flag which indicates it has been erased
    */

    will_be_erased_ = true;

    /*
        2. remove associations between keypoints and landmarks
    */

    for (const auto lm : landmarks_) {
        if (!lm) {
            continue;
        }
        lm->erase_observation(this);
    }

    /*
        3. recover covisibility graph and spanning tree
    */

    // remove covisibility information
    graph_node_->erase_all_connections();
    // replace current origin keyframe with another candidate in the same map
    // replace the spanning parent of all its spanning child with the candidate
    bool skip_recover_spanning_connections = false;
    if (is_origin_) {
        skip_recover_spanning_connections = true;
        replace_origin_with_other_candidate();
    }
    // remove loop edges information
    if (graph_node_->has_loop_edge()) graph_node_->erase_all_loop_edges();
    // recover spanning tree
    if (!skip_recover_spanning_connections) graph_node_->recover_spanning_connections();

    /*
        4. update frame statistics
    */
    map_db_->replace_reference_keyframe(this, graph_node_->get_spanning_parent());

    /*
        5. remove myself from the databased
    */

    map_db_->erase_keyframe(this);
    bow_db_->erase_keyframe(this);
}

void keyframe::replace_origin_with_other_candidate()
{
    /*
        try to find another candidate in map database to replace this
        keyframe, then set is_origin_ flag to false for this keyframe.
    */
    std::map<KeyframeID, keyframe*> all_keyframes_in_map;
    map_db_->get_all_keyframes_map(all_keyframes_in_map, map_id_);
    all_keyframes_in_map.erase(id_);

    if (all_keyframes_in_map.empty()) {
        spdlog::warn("Map database is empty except the origin keyframe, so just erase it from origin_keyfrms_ \
                unordered map in map database!");
        map_db_->erase_origin_keyframe(map_id_);

        is_origin_ = false;
        return;
    }

    /*
        available methods:
        1. first to choose the upper bound of current origin keyframe
        2. first to choose a spanning child of current origin keyframe
        In most of the cases, these two methods have the same result, but
        here we choose method 1 due to easier implementation.
    */
    auto candidate = all_keyframes_in_map.upper_bound(id_);
    if (candidate == all_keyframes_in_map.end()) {
        spdlog::warn("Failed to find a replacement for origin keyframe {} for map {} based on the keyframe ID!");
        spdlog::warn("Just try to choose the keyframe with the smallest keyframe ID {} in map database");
        candidate = all_keyframes_in_map.begin();
    }
    spdlog::info("Replace current origin keyframe {} for map {} with keyframe {}", id_, map_id_,
                 (*candidate).first);
    (*candidate).second->set_origin();
    map_db_->set_origin_keyframe(map_id_, (*candidate).second);
    (*candidate).second->graph_node_->set_spanning_parent(nullptr);

    /*
        set flag of the current origin keyframe to false.
    */
    is_origin_ = false;

    /*
        set the spanning parent of all the spanning child for the current
        origin keyframe to the candidate.
    */
    auto spanning_children = graph_node_->get_spanning_children();
    for (auto& spanning_child : spanning_children) {
        if (!spanning_child || spanning_child->will_be_erased()) continue;
        if (spanning_child == (*candidate).second) continue;
        spanning_child->graph_node_->change_spanning_parent((*candidate).second);
        spdlog::debug("Change the spanning parent of spanning child {} from current origin keyframe to {}",
                     spanning_child->id_, (*candidate).first);
    }

}

bool keyframe::will_be_erased() { return will_be_erased_; }

bool keyframe::is_origin() { return is_origin_; }

}  // namespace data
}  // namespace openvslam

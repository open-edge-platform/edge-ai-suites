/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#include "modules/inference_util/radar/libradar_helper.hpp"

namespace hce {

namespace ai {

namespace inference {

RadarTracker::RadarTracker(RadarParam radarParam):m_lib_radar_config_(radarParam){

    maxRadarPointCloudsLen	= radarParam.mp;
    maxCluster	= radarParam.mc;
}
RadarTracker::~RadarTracker(){
    free(m_radar_tracking_result_.td);
    m_radar_tracking_result_.td = nullptr;
}

void RadarTracker::Init(){

    m_radar_tracking_result_ = {
    .len	=   0,
    .maxLen	=   maxTrackerNum,
    .td	=   (TrackingDescription*)ALIGN_ALLOC(64, sizeof(TrackingDescription) * maxTrackerNum)
    };

}
RadarTracker *RadarTracker::CreateInstance(RadarParam m_lib_radar_config_){
    RadarTracker *tracker = nullptr;
    tracker = new RadarTracker(m_lib_radar_config_);
    // radarGetMemSize(&m_lib_radar_config_, &bufSize);
    // tracker->Init(buf, bufSize);
    tracker->Init();
    return tracker;
}
TrackingResult& RadarTracker::RunTracking(RadarHandle* handle, ClusterResult m_radar_cluster_result_){
    handle_ = handle;
    if(radarTracking(handle, &m_radar_cluster_result_, &m_radar_tracking_result_)!= R_SUCCESS){
        HVA_ERROR("radarTracking failed");
    }
    HVA_DEBUG("radarTracking result len %d", m_radar_tracking_result_.len);
    return m_radar_tracking_result_;
}

TrackingResult& RadarTracker::GetRadarTrackingResult(){
    return m_radar_tracking_result_;
}

void RadarTracker::Reset(void) {
  HVA_DEBUG("radarDestroyHandle: handle destroyed");
  m_radar_tracking_result_.len = 0;
  //free(m_radar_tracking_result_.td);

}  // namespace inference
}
}  // namespace ai

}  // namespace hce

/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2023 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and
 * your use of them is governed by the express license under which they were
 * provided to you (License). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or
 * the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express
 * or implied warranties, other than those that are expressly stated in the
 * License.
 */

#ifndef HCE_AI_INF_LIB_RADAR_HELPER_HPP
#define HCE_AI_INF_LIB_RADAR_HELPER_HPP

#include "inc/api/hvaLogger.hpp"
#include "../libradar/src/libradar.h"

namespace hce {

namespace ai {

namespace inference {

#ifdef ENABLE_SANITIZE
    #define ALIGN_ALLOC(align, size) malloc((size))
#else
    #define ALIGN_ALLOC(align, size) aligned_alloc((align), (size))
#endif

class RadarTracker {
 public:
  static RadarTracker* CreateInstance(RadarParam m_lib_radar_config_);
  ~RadarTracker();

  void Init();
  void Reset(void);
  TrackingResult& RunTracking(RadarHandle* handle,
                              ClusterResult m_radar_cluster_result_);

  TrackingResult& GetRadarTrackingResult();

 protected:
  explicit RadarTracker(RadarParam radarParam);
  RadarTracker() = delete;

 private:
  RadarParam m_lib_radar_config_;
  ClusterResult m_radar_cluster_result_;
  TrackingResult m_radar_tracking_result_;
  RadarHandle* handle_ = nullptr;
  int maxRadarPointCloudsLen;
  int maxCluster;
  const int maxTrackerNum = 64;
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_RADAR_CLUSTING_HELPER_HPP

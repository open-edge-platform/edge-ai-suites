/*
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#ifndef UNIVLOC_MAPPING_MODULE_H
#define UNIVLOC_MAPPING_MODULE_H

#include "LoopTimer.h"

namespace openvslam
{

namespace data
{
class keyframe;
class map_database;
class bow_database;
}  // namespace data

class univloc_mapping_module : public mapping_module
{
public:
  //! constructor
  univloc_mapping_module(
    data::map_database * map_db, data::bow_database * bow_db, const bool is_monocular,
    const bool use_odom, const bool clean_keyframe);

  //! destructor
  ~univloc_mapping_module();

  void run() override;

  void reset() override;

  //-----------------code related to IMU------------------------

  //! update the time duration after IMU initialization
  void update_imu_duration(double & time_after_initalizing);

  //! optimezation based on IMU
  unsigned int optimize_imu(double & time_after_initializing);

  //! initialize IMU
  void initialize_imu(double acc_weight, double gyro_weight);

  //! refine the scale based on IMU
  void scale_refinement();

  //! remove old map in database
  void remove_old_map();

  //! transformation matrix from IMU to camera coordinate
  Mat44_t Tci_;

  //! rotation matrix from IMU to world coordinate
  Mat33_t Rwi_;

  //! scale
  double scale_;

  //! bias vector of IMU accelerator
  Vec3_t bias_acc_;

  //! bias vector of IMU gyro
  Vec3_t bias_gyro_;

  //! mininum keyframes num for initializing IMU
  const unsigned int keyframes_num_for_initializing_imu_;

  //------------------- communication with server----------------------

  void populate_sent_landmarks(std::vector<data::landmark *> & landmarks_out);

  void populate_local_keyframes(std::vector<data::keyframe *> & keyframes_out);

  void send_to_server(unsigned int optimize_times = 0);

  void pause_tracker();

  void resume_tracker();

  data::keyframe * get_cur_keyframe();

protected:
  LoopTimer timer_;
};

}  // namespace openvslam

#endif  // UNIVLOC_MAPPING_MODULE_H

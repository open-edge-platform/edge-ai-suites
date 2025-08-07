// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef __ADBSCAN__
#define __ADBSCAN__

//#include <gflags/gflags.h> //jcao7
#include "dbscan_adaptiveK.h"
#include <string>
using namespace std;

/*=========================================
 * CONFIGURATION
 *========================================*/

/*=========================================
 * TYPE DEFINITIONS
 *========================================*/
typedef enum
{
	ADBSCAN_SUCCESS                          = 0,
	ADBSCAN_CONFIG_PARAMS_FILE_OPEN_FAILED   = -1,
	ADBSCAN_CONFIG_PARAM_MISSING             = -2,
	ADBSCAN_ADAPTIVE_PARAMS_FILE_OPEN_FAILED = -3,
	ADBSCAN_ADAPTIVE_PARAMS_LOAD_FAILED      = -4,
	ADBSCAN_IN_LiDAR_FILE_OPEN_FAILED        = -5,
	ADBSCAN_IN_LiDAR_FILE_READ_FAILED        = -6,
	ADBSCAN_IN_LiDAR_FILE_MEMALLOC_FAILED    = -7,
	ADBSCAN_K_ARRAY_MEMALLOC_FAILED          = -8,
	ADBSCAN_K_FLOOR_ARRAY_MEMALLOC_FAILED    = -9,
	ADBSCAN_ESP_ARRAY_MEMALLOC_FAILED        = -10,
	ADBSCAN_ESP_CONT_ARRAY_MEMALLOC_FAILED   = -11,
	ADBSCAN_TYPE_MEMALLOC_FAILED             = -12,
	ADBSCAN_CLASS_MEMALLOC_FAILED            = -13,
	ADBSCAN_3D_DATA_MEMALLOC_FAILED          = -14,
	ADBSCAN_TOUCHED_MEMALLOC_FAILED          = -15,
	ADBSCAN_DIST_MEMALLOC_FAILED             = -16,
	ADBSCAN_LIST_MEMALLOC_FAILED             = -17,
	ADBSCAN_LIST1_MEMALLOC_FAILED            = -18,
	ADBSCAN_MAX_NUM_OF_POINT_EXCEEDED        = -19
} ADBSCAN_Result_t;

typedef enum _filter_op
{
	FILTER_OP_GREATER_THAN = 0,
	FILTER_OP_LESS_THAN    = -1
} FILTER_op_t;

typedef enum _filter_index
{
	X_INDEX = 0,
	Y_INDEX = 1,
	Z_INDEX = 2
} FILTER_index_t;

#define SUBSAMPLE_RATIO_BIT	0x00000001
#define X_FILTER_BACK_BIT	0x00000002
#define Y_FILTER_LEFT_BIT	0x00000004
#define Y_FILTER_RIGHT_BIT	0x00000008
#define Z_FILTER_BIT		0x00000010
#define GROUND_REMOVAL_BIT	0x00000020

typedef struct _adbscan_params
{
	FP32_t subsample_ratio;
	FP32_t x_filter_back;
	FP32_t y_filter_left;
	FP32_t y_filter_right;
	FP32_t z_filter;
	UINT32_t Z_based_ground_removal;
} ADBSCAN_params_t;

typedef struct _adaptive_params
{
	FP32_t base;
	FP32_t coeff_1;
	FP32_t coeff_2;
} Adaptive_params_t;

typedef struct _config_params //to be moved into ADBScan.h and becomes global varaible
{ 
  float subsample_ratio;
  float x_filter_back;
  float y_filter_left;
  float y_filter_right;
  float z_filter;
  float Z_based_ground_removal;
  float base;
  float coeff_1;
  float coeff_2;
  bool verbose;
  string Lidar_type;
  float scale_factor;
  float init_tgt_loc;
  float max_dist;
  float min_dist;
  float max_linear;
  float max_angular;
  int max_frame_blocked;
  float tracking_radius;
} Config_params_t;

typedef struct _point
{
  float x;
  float y;
  float z;
} Point_xyz;  //Point type used for ADBSCAN input 


extern Config_params_t CONFIG_PARAMS;

/// @brief message for help argument
static const char help_message[] = "Print a usage message";
/// @brief message for LiDAR data file argument
static const char LiDAR_data_message[] = "Required. Path to input LiDAR data file";
/// @brief message for configuration file argument
static const char configuration_parameters_file_message[] = "Required. Path to configuration parameters file";
/// @brief message for assigning cnn calculation to device
static const char target_device_message[] = "Required. Target device for acceleration: (CPU or FPGA)";
/// @brief message for superimpose flag argument
static const char superimpose_message[] = "Required. Superimpose: (yes or no)";
/// @brief message for image file argument
static const char image_file_message[] = "Conditional parameter required when s flag is \"yes\". Path to image file.";
/// @brief message for camera calibratin argument
static const char camera_calibration_message[] = "Conditional parameter required when s flag is \"yes\". Path to camera calibration file. ";
/// @brief message for lidar calibratin argument
static const char lidar_calibration_message[] = "Conditional parameter required when s flag is \"yes\". Path to LiDAR calibration file. ";
/// @brief message for adaptive parameters file argument
static const char adaptive_parameters_file_message[] = "Optional. Path to adaptive parameters file";
/// @brief message for adaptive parameters file argument
static const char output_file_message[] = "Optional. Path to output file";
/// @brief message for number of iterations argument
static const char number_of_iterations_message[] = "Optional. Number of iterations";



#endif

// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef __ADBSCAN_ADAPTIVE_K
#define __ADBSCAN_ADAPTIVE_K

/*===================================
 * CONSTANT DEFINITIONS
 *==================================*/
#define ADBSCAN_PI 3.1416
#define ADBSCAN_GAMMA 1.3293
#define ADBSCAN_MAX_PAR_NAME_SIZE 128
#define NUM_ITERATIONS 10
#define MAX_POINTS	409600

/*===================================
 * CONFIGURATION
 *==================================*/
//#define USE_LINKED_LISTS
#define INLINE_FUNCTIONS
//#define ADD_FPGA_SUPPORT
//#define FPGA_DBSCAN

#ifdef ADD_FPGA_SUPPORT
#include <iostream>
#include <fstream>
#include "CL/cl.hpp"
#endif

/*===================================
 * TYPE DEFINITIONS
 *==================================*/
typedef signed int		INT32_t;
typedef unsigned int	UINT32_t;
typedef unsigned char	UINT8_t;
typedef float			FP32_t;
typedef double			FP64_t;
typedef double			FPDS_t;

#define LIDAR_DATA_SIZE_4D 4
typedef struct _lidar_data
{
	FP32_t val[LIDAR_DATA_SIZE_4D];
} LiDAR_data_4D_t;

#define LIDAR_DATA_SIZE_3D (LIDAR_DATA_SIZE_4D - 1)
typedef struct _lidar_data_3D
{
	FP32_t val[LIDAR_DATA_SIZE_3D];
} LiDAR_data_3D_t;

#ifdef USE_LINKED_LISTS
typedef struct list_item
{
	INT32_t active;
	INT32_t index;
	struct list_item *p_next;
	struct list_item *p_prev;
} ADBSCAN_list_item_t;

typedef struct
{
	ADBSCAN_list_item_t *items;	
	ADBSCAN_list_item_t *pFirst;
	ADBSCAN_list_item_t *pLast;
	INT32_t count;
	INT32_t max_size;
} ADBSCAN_list_t;
#endif /* #ifdef USE_LINKED_LISTS */

#ifdef FPGA_DBSCAN
#define MAX_KERNEL_NAME
typedef struct
{
	std::vector<cl::Platform> PlatformList;
	std::vector<cl::Device> DeviceList;
	cl::Context mycontext;
	cl::CommandQueue myqueue;
	cl::Buffer Buffer_InX;
	cl::Buffer Buffer_InY;
	cl::Buffer Buffer_InZ;
	cl::Buffer Buffer_InK;
	cl::Buffer Buffer_InE;
	cl::Buffer Buffer_Out1;
	cl::Buffer Buffer_Out2;
	const char kernel_name[MAX_KERNEL_NAME];
	std::ifstream aocx_stream;
	std::string prog;
	cl::Program::Binaries mybinaries;
	
} ADBScan_fpga_context_t;

#endif 

/*==================================
 * FUNCTION DEFINITIONS
 *=================================*/
void dbscan_adaptiveK(
	LiDAR_data_3D_t x[], 
	FPDS_t k_array[], 
	FPDS_t esp_array[], 
	INT32_t oclass[], 
	INT32_t type[], 
	INT32_t num_points);

#ifdef ADD_FPGA_SUPPORT
void dbscan_adaptiveK_fpga(
	LiDAR_data_3D_t x[], 
	FPDS_t k_array[], 
	FPDS_t esp_array[], 
	INT32_t oclass[], 
	INT32_t type[], 
	INT32_t num_points,
	INT32_t num_iter);
#endif
	
#endif /* #ifndef __ADBSCAN_ADAPTIVE_K */

/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/


#ifndef _GATHER_GPU_METRICS_FROM_ONE_API_H
#define _GATHER_GPU_METRICS_FROM_ONE_API_H

#if defined(__cplusplus)
#pragma once
#endif

#include "gmg_common_util.h"
#include <level_zero/zes_api.h>


#define SAMP "gpu_metrics"
#define MAX_METRIC_NAME_LENGTH 256
#define MAX_NUMBER_DEVICE_INDEX 255

#if defined(__cplusplus)
extern "C" {
#endif

#ifdef ENABLE_AUTO_SIMULATION
#define SIMULATION_CONTROL_FILE "/opt/ucs/RUN_GPU_METRICS_GATHERERS_IN_SIMULATION_MODE"
void autoSetSimulationMode();
#endif

size_t getMallocCount();

bool getSimulationMode();

void setSimulationMode(
        bool isInSimulationMode
);


ze_result_t initializeOneApi();

ze_driver_handle_t getDriver();

ze_device_handle_t *enumerateGpuDevices(
        ze_driver_handle_t hDriver,
        uint32_t *pCount
);

void freeZeDeviceHandle(
        ze_device_handle_t *phDevice
);

const char *getGpuDeviceName(
        ze_device_handle_t hDevice
);

const uint8_t *getGpuUuid(
        ze_device_handle_t hDevice
);

/**
 * When invoked in SAMPLING mode, this function returns the actual gpu utilization.  When invoked in SIMULATION mode,
 * this function returns fluctuating simulated gpu utilization.
 * @param hDevice handle to gpu device.
 * @return gpu utilization in percentage.
 */
double getGpuUtilization(
        ze_device_handle_t hDevice,
        zes_engine_group_t engineGroup
);

double getMemoryUtilization(
        ze_device_handle_t hDevice
);

uint64_t getMemVRAMUsed(
        ze_device_handle_t hDevice
);

int32_t getSysClockFreq(
        ze_device_handle_t hDevice
);

double getMemoryReadBandwidth(
        ze_device_handle_t hDevice
);

double getMemoryWriteBandwidth(
        ze_device_handle_t hDevice
);

double getPerfLevel(
        ze_device_handle_t hDevice
);

int32_t getPowerUsage(
        ze_device_handle_t hDevice
);

int32_t getPowerCap(
        ze_device_handle_t hDevice
);

double getGpuTemp(
        ze_device_handle_t hDevice
);

int64_t getPciMaxSpeed(
        zes_device_handle_t hDevice
);

const char *getGpuSerialNumber(
        zes_device_handle_t hDevice
);

#if defined(__cplusplus)
} // extern "C"
#endif // __cplusplus

#endif // _GATHER_GPU_METRICS_FROM_ONE_API_H

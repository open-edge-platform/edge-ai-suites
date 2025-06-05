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

#include <string.h>
#include <time.h>
#include <stdlib.h>
#include <stdio.h>

#include "gather_gpu_metrics_from_one_api.h"


static uint64_t mallocCount = 0;

size_t getMallocCount() {
    return mallocCount;
}

static void *GMG_MALLOC(size_t size) {
    // GMGLOG(LDMSD_LDEBUG, ">>GMG_MALLOC(size=%ld)\n", size);
    void *p = calloc(size, 1);
    if (!p) {
        // GMGLOG(LDMSD_LERROR, "!!!calloc(size=%ld, 1) => NULL\n", size);
        return NULL;
    }
    mallocCount++;
    // GMGLOG(LDMSD_LDEBUG, "<<GMG_MALLOC(size=%ld) => %p\n", size, p);
    return p;
}

static void gmgFree(void *p) {
    // GMGLOG(LDMSD_LDEBUG, ">>gmgFree(p=%p)\n", p);
    if (!p) {
        // GMGLOG(LDMSD_LERROR, "!!!Attempting to free a NULL pointer\n");
        return;
    }
    free(p);
    // GMGLOG(LDMSD_LDEBUG, "<<gmgFree()\n");
    --mallocCount;
}

#define GMG_FREE(p) { \
    gmgFree((p)); \
    (p) = NULL;   \
}

const long samplingIntervalInMs = 10;

/**
 * Simulation Data Definitions
 */
static const uint32_t cNumberOfSimulatedDrivers = 1;
static const uint32_t cNumberOfSimulatedDevices = 6;


bool g_bIsInSimulationMode = false;

bool getSimulationMode() {
    return g_bIsInSimulationMode;
}

void setSimulationMode(bool bIsInSimulationMode) {
    g_bIsInSimulationMode = bIsInSimulationMode;
    // GMGLOG(LDMSD_LDEBUG, "Setting g_bIsInSimulationMode=%d\n", bIsInSimulationMode);
}

#ifdef ENABLE_AUTO_SIMULATION
void autoSetSimulationMode() {
    if (isFileExists(SIMULATION_CONTROL_FILE)) {
        setSimulationMode(true);
    }
}
#endif

ze_result_t initializeOneApi() {
    // GMGLOG(LDMSD_LINFO, ">>initializeOneApi()\n");
    if (g_bIsInSimulationMode) {
//        msSleep(8 * 1000);    // simulated delay
        return ZE_RESULT_SUCCESS;
    }

    if (setenv("ZES_ENABLE_SYSMAN", "1", 1) == -1) {
        // GMGLOG(LDMSD_LERROR, "Cannot set environment variable ZES_ENABLE_SYSMAN=1\n");
        return ZE_RESULT_ERROR_UNINITIALIZED;
    }

    ze_result_t res = zeInit(ZE_INIT_FLAG_GPU_ONLY);
    // GMGLOG(LDMSD_LINFO, "<<initializeOneApi()\n");
    return res;
}

static ze_result_t gmgDriverGet(
        uint32_t *pCount,
        ze_driver_handle_t *phDrivers) {
    if (g_bIsInSimulationMode) {
        *pCount = cNumberOfSimulatedDrivers;
        if (phDrivers == NULL) return ZE_RESULT_SUCCESS;

        for (size_t i = 0; i < *pCount; i++) {
            phDrivers[i] = (ze_driver_handle_t)(i + 1);
        }
        return ZE_RESULT_SUCCESS;
    }

    return zeDriverGet(pCount, phDrivers);
}

static ze_result_t gmgDeviceGet(
        ze_driver_handle_t hDriver,
        uint32_t *pCount,
        ze_device_handle_t *phDevices) {
    if (g_bIsInSimulationMode) {
        *pCount = cNumberOfSimulatedDevices;
        if (phDevices == NULL) return ZE_RESULT_SUCCESS;

        for (size_t i = 0; i < *pCount; i++) {
            phDevices[i] = (ze_device_handle_t)(i + 1);
        }
        return ZE_RESULT_SUCCESS;
    }

    return zeDeviceGet(hDriver, pCount, phDevices);
}


static ze_result_t gmgDeviceGetProperties(
        ze_device_handle_t hDevice,
        ze_device_properties_t *pDeviceProperties) {
    if (g_bIsInSimulationMode) {
        strncpy(pDeviceProperties->name, "Intel(R) Graphics [0x0bd5]", ZE_MAX_DEVICE_NAME);
        for (uint32_t i = 0; i < ZE_MAX_DEVICE_UUID_SIZE; i++) {
            pDeviceProperties->uuid.id[i] = i;
        }
        return ZE_RESULT_SUCCESS;
    }

    return zeDeviceGetProperties(hDevice, pDeviceProperties);
}

ze_result_t gmgsEngineGetActivity(
        zes_engine_handle_t hEngine,
        zes_engine_stats_t *pStats) {

    if (g_bIsInSimulationMode) {
        const long BILLION = 1000000000L;
        struct timespec currentTime;

        clock_gettime(CLOCK_REALTIME, &currentTime);
        pStats->activeTime = (BILLION * currentTime.tv_sec + currentTime.tv_nsec) / 100;
        clock_gettime(CLOCK_REALTIME, &currentTime);
        pStats->timestamp = BILLION * currentTime.tv_sec + currentTime.tv_nsec;

        return ZE_RESULT_SUCCESS;
    }

    ze_result_t res = zesEngineGetActivity(hEngine, pStats);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesEngineGetActivity(hEngine=%p,pStats=%p) => 0x%x\n", hEngine, pStats, res);
    }
    return res;
}

ze_result_t gmgsDeviceEnumEngineGroups(
        zes_device_handle_t hDevice,
        uint32_t *pCount,
        zes_engine_handle_t *phEngine) {
    if (g_bIsInSimulationMode) {
        *pCount = 1;    // only need ZES_ENGINE_GROUP_ALL = 0
        if (phEngine == NULL) return ZE_RESULT_SUCCESS;

        phEngine[ZES_ENGINE_GROUP_ALL] = (zes_engine_handle_t) 1;
        return ZE_RESULT_SUCCESS;
    }

    ze_result_t res = zesDeviceEnumEngineGroups(hDevice, pCount, phEngine);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesDeviceEnumEngineGroups(hDevice=%p,pCount=%p,phEngine=%p) => 0x%x\n", hDevice, pCount, phEngine, res);
    }
    return res;
}

static
ze_driver_handle_t *enumerateDrivers(uint32_t *pCount) {
    ze_result_t res = gmgDriverGet(pCount, NULL);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgDriverGet(pCount=%p, NULL) => 0x%x\n", pCount, res);
        return NULL;
    }

    if (*pCount < 1) {
        // GMGLOG(LDMSD_LERROR, "!!!*pCount=%d < 1\n", *pCount);
        return NULL;
    }

    size_t memSizeDrivers = sizeof(ze_driver_handle_t) * *pCount;
    ze_driver_handle_t *phDrivers = GMG_MALLOC(memSizeDrivers);

    res = gmgDriverGet(pCount, phDrivers);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgDriverGet(pCount=%p,phDrivers=%p) => 0x%x\n", pCount, phDrivers, res);
        GMG_FREE(phDrivers);
        return NULL;
    }

    return phDrivers;
}

ze_driver_handle_t getDriver() {
    // GMGLOG(LDMSD_LINFO, ">>getDriver()\n");
    uint32_t numDrivers = 0;
    ze_driver_handle_t *phDrivers = enumerateDrivers(&numDrivers);
    if (phDrivers == NULL) {
        return NULL;
    }

    ze_driver_handle_t hDriver = phDrivers[0];
    GMG_FREE(phDrivers);
    // GMGLOG(LDMSD_LINFO, "<<getDriver()\n");
    return hDriver;
}

ze_device_handle_t *enumerateGpuDevices(ze_driver_handle_t hDriver, uint32_t *pCount) {
    // GMGLOG(LDMSD_LINFO, ">>enumerateGpuDevices()\n");

    ze_result_t res = gmgDeviceGet(hDriver, pCount, NULL);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgDeviceGet(hDriver=%p,pCount=%p,NULL) => 0x%x\n", hDriver, pCount, res);
        return NULL;
    }
    // GMGLOG(LDMSD_LDEBUG, "*pCount = %d\n", *pCount);
    if (*pCount < 1) {
        // GMGLOG(LDMSD_LERROR, "!!!*pCount=%d < 1\n", *pCount);
        return NULL;
    }

    ze_device_handle_t *phDevices = GMG_MALLOC(sizeof(ze_device_handle_t) * *pCount);
    res = gmgDeviceGet(hDriver, pCount, phDevices);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgDeviceGet(hDriver=%p,pCount=%p,phDevices=%p) => 0x%x\n", hDriver, pCount, phDevices, res);
        GMG_FREE(phDevices);
        return NULL;
    }

    // GMGLOG(LDMSD_LINFO, "<<enumerateGpuDevices()\n");
    return phDevices;
}

void freeZeDeviceHandle(
        ze_device_handle_t *
        phDevice) {
    GMG_FREE(phDevice);
}

const char *getGpuDeviceName(
        ze_device_handle_t hDevice) {
    static char szName[ZE_MAX_DEVICE_NAME+1];
    memset(szName, 0, sizeof(szName)/sizeof(szName[0]));

    ze_device_properties_t deviceProperties = {
            ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES};

    ze_result_t res = gmgDeviceGetProperties(hDevice, &deviceProperties);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgDeviceGetProperties(hDevice=%p, &deviceProperties=%p) => 0x%x", hDevice, &deviceProperties, res);
        return szName;
    }

    size_t nameLength = strnlen(deviceProperties.name, ZE_MAX_DEVICE_NAME);
    // GMGLOG(LDMSD_LDEBUG, "%s has length = %ld\n", deviceProperties.name, nameLength);

    strncpy(szName, deviceProperties.name, ZE_MAX_DEVICE_NAME);
    return szName;
}

const uint8_t *getGpuUuid(
        ze_device_handle_t hDevice) {
    static uint8_t uuid[ZE_MAX_DEVICE_UUID_SIZE];
    memset(uuid, 0, ZE_MAX_DEVICE_UUID_SIZE);

    ze_device_properties_t deviceProperties = {
            ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES};

    ze_result_t res = gmgDeviceGetProperties(hDevice, &deviceProperties);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgDeviceGetProperties(hDevice=%p, &deviceProperties=%p) => 0x%x", hDevice, &deviceProperties, res);
        return uuid;
    }

    for (size_t i = 0; i < ZE_MAX_DEVICE_UUID_SIZE; i++) {
        uuid[i] = deviceProperties.uuid.id[i];
    }

    return uuid;
}

static zes_engine_handle_t *getEngineDomains(ze_device_handle_t hDevice, uint32_t *pCount) {
    gmgsDeviceEnumEngineGroups(hDevice, pCount, NULL);
    if (*pCount == 0) {
        // GMGLOG(LDMSD_LERROR, "!!!count = 0\n");
        return NULL;
    }

    size_t memSize = sizeof(zes_engine_handle_t) * *pCount;
    zes_engine_handle_t *phEngine = GMG_MALLOC(memSize);
    ze_result_t res = gmgsDeviceEnumEngineGroups(hDevice, pCount, phEngine);

    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgsDeviceEnumEngineGroups(hDevice=%p,pCount=%p,phEngine=%p) => 0x%x\n", hDevice, pCount, phEngine, res);
        GMG_FREE(phEngine);
        return NULL;
    }

    return phEngine;
}

double getGpuUtilization(ze_device_handle_t hDevice, zes_engine_group_t engineGroup) {
    uint32_t count = 0;
    zes_engine_handle_t *phEngine = getEngineDomains(hDevice, &count);
    if (phEngine == NULL) {
        // GMGLOG(LDMSD_LERROR, "!!!getEngineDomains(hDevice=%p, &count=%p) => NULL, count=%d\n", hDevice, &count, count);
        return -99.9;
    }

    zes_engine_stats_t engineStats0 = {};
    zes_engine_stats_t engineStats1 = {};

    // //
    // // Accelerator engine groups: https://spec.oneapi.io/level-zero/latest/sysman/api.html#zes-engine-group-t
    // //
    // zes_engine_group_t engineGroup = ZES_ENGINE_GROUP_COMPUTE_SINGLE;

    /**
     * Percent utilization is calculated by taking two snapshots (s1, s2) and using the equation: 
     *  util = (s2.activeTime - s1.activeTime) / (s2.timestamp - s1.timestamp)
     */
    double gpuUtilization = -99.9;
    do {
        if (gmgsEngineGetActivity(phEngine[engineGroup], &engineStats0) != ZE_RESULT_SUCCESS) {
            break;
        }
        if (msSleep(samplingIntervalInMs) != 0) {
            break;
        }
        if (gmgsEngineGetActivity(phEngine[engineGroup], &engineStats1) != ZE_RESULT_SUCCESS) {
            break;
        }

        gpuUtilization = 100.0 * (engineStats1.activeTime - engineStats0.activeTime) /    // in percentage
                         (engineStats1.timestamp - engineStats0.timestamp);
    } while (false);
    GMG_FREE(phEngine);

    return gpuUtilization;
}

static
zes_mem_handle_t *getMemoryModules(ze_device_handle_t hDevice, uint32_t *pCount) {
    zesDeviceEnumMemoryModules(hDevice, pCount, NULL);
    if (*pCount == 0) {
        // GMGLOG(LDMSD_LERROR, "!!!Could not retrieve memory modules\n");
        return NULL;
    }
    size_t memSize = sizeof(zes_engine_handle_t) * *pCount;
    zes_mem_handle_t *phMemoryModules = GMG_MALLOC(memSize);
    ze_result_t res =zesDeviceEnumMemoryModules(hDevice, pCount, phMemoryModules);

    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesDeviceEnumMemoryModules(hDevice=%p,pCount=%p,phMemoryModules=%p) => 0x%x\n", hDevice, pCount, phMemoryModules, res);
        GMG_FREE(phMemoryModules);
        return NULL;
    }

    return phMemoryModules;
}

double getMemoryUtilization(
        ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 4.0;
    }

    uint32_t count = 0;
    zes_mem_handle_t *phMemoryModules = getMemoryModules(hDevice, &count);
    if (phMemoryModules == NULL) {
        // GMGLOG(LDMSD_LERROR, "!!!getMemoryModules(hDevice=%p, &count=%p) => NULL, count=%d\n", hDevice, &count, count);
        return -99.9;
    }

    int64_t allocatableMemory = 0;
    int64_t usedMemory = 0;

    for (size_t i = 0; i < count; i++) {
        zes_mem_state_t memoryState = {};
        zesMemoryGetState(phMemoryModules[i], &memoryState);
        allocatableMemory += memoryState.size;
        usedMemory += memoryState.size - memoryState.free;
    }
    if (allocatableMemory == 0) {
        return 0.0;
    }
    GMG_FREE(phMemoryModules);

    return (100.0 * usedMemory) / allocatableMemory; // in percentage
}


uint64_t getMemVRAMUsed(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 42424242;
    }

    uint32_t count = 0;
    zes_mem_handle_t *phMemoryModules = getMemoryModules(hDevice, &count);
    if (phMemoryModules == NULL) {
        // GMGLOG(LDMSD_LERROR, "!!!getMemoryModules(hDevice=%p, &count=%p) => NULL, count=%d\n", hDevice, &count, count);
        return 999999;
    }

    int64_t usedMemory = 0;
    for (size_t i = 0; i < count; i++) {
        zes_mem_state_t memoryState = {};
        zesMemoryGetState(phMemoryModules[i], &memoryState);
        usedMemory += memoryState.size - memoryState.free;
    }
    GMG_FREE(phMemoryModules);

    return usedMemory;
}


int32_t getSysClockFreq(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 4242;
    }

    ze_device_properties_t deviceProperties = {
            ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES};
    if (zeDeviceGetProperties(hDevice, &deviceProperties) != ZE_RESULT_SUCCESS) {
        return 9999;
    }
    return deviceProperties.coreClockRate;
}

int64_t getCumulativeReadCounter(zes_mem_handle_t *phMemoryModules, uint32_t count) {
    int64_t cumulativeReadCount = 0;
    for (uint32_t i = 0; i < count; i++) {
        zes_mem_bandwidth_t memoryBandwidth = {};
        if (zesMemoryGetBandwidth(phMemoryModules[i], &memoryBandwidth) != ZE_RESULT_SUCCESS) {
            return -9999;
        }
        // GMGLOG(LDMSD_LDEBUG, "memoryBandwidth.readCounter = %ld\n", memoryBandwidth.readCounter);
        cumulativeReadCount += memoryBandwidth.readCounter;
    }

    return cumulativeReadCount;
}

double getMemoryReadBandwidth(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 42.0;
    }

    uint32_t count = 0;
    zes_mem_handle_t *phMemoryModules = getMemoryModules(hDevice, &count);
    if (phMemoryModules == NULL) {
        // GMGLOG(LDMSD_LERROR, "!!!getMemoryModules(hDevice=%p, &count=%p) => NULL, count=%d\n", hDevice, &count, count);
        return 999999.0;
    }
    // GMGLOG(LDMSD_LDEBUG, "count = %d\n", count);

    double bandwidth = -99999.0;
    do {
        int64_t cumulativeReadCounter0 = getCumulativeReadCounter(phMemoryModules, count);
        if (cumulativeReadCounter0 < 0) {
            break;
        }
        if (msSleep(samplingIntervalInMs) != 0) {
            break;
        }
        int64_t cumulativeReadCounter1 = getCumulativeReadCounter(phMemoryModules, count);
        if (cumulativeReadCounter1 < 0) {
            break;
        }

        int64_t bytesRead = cumulativeReadCounter1 - cumulativeReadCounter0;
        bandwidth = (double) bytesRead / samplingIntervalInMs;
    } while (false);
    GMG_FREE(phMemoryModules);

    return bandwidth;
}

int64_t getCumulativeWriteCounter(zes_mem_handle_t *phMemoryModules, uint32_t count) {
    int64_t cumulativeWriteCount = 0;
    for (uint32_t i = 0; i < count; i++) {
        zes_mem_bandwidth_t memoryBandwidth = {};
        if (zesMemoryGetBandwidth(phMemoryModules[i], &memoryBandwidth) != ZE_RESULT_SUCCESS) {
            return -9999;
        }
        // GMGLOG(LDMSD_LDEBUG, "memoryBandwidth.writeCounter = %ld\n", memoryBandwidth.writeCounter);
        cumulativeWriteCount += memoryBandwidth.writeCounter;
    }

    return cumulativeWriteCount;
}

double getMemoryWriteBandwidth(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 24.0;
    }

    uint32_t count = 0;
    zes_mem_handle_t *phMemoryModules = getMemoryModules(hDevice, &count);
    if (phMemoryModules == NULL) {
        // GMGLOG(LDMSD_LERROR, "!!!getMemoryModules(hDevice=%p, &count=%p) => NULL, count=%d\n", hDevice, &count, count);
        return 999999.0;
    }
    // GMGLOG(LDMSD_LDEBUG, "count = %d\n", count);

    double bandwidth = -99999.0;
    do {
        int64_t cumulativeWriteCounter0 = getCumulativeWriteCounter(phMemoryModules, count);
        if (cumulativeWriteCounter0 < 0) {
            break;
        }
        if (msSleep(samplingIntervalInMs) != 0) {
            break;
        }
        int64_t cumulativeWriteCounter1 = getCumulativeWriteCounter(phMemoryModules, count);
        if (cumulativeWriteCounter1 < 0) {
            break;
        }

        int64_t bytesWritten = cumulativeWriteCounter1 - cumulativeWriteCounter0;
        bandwidth = (double) bytesWritten / samplingIntervalInMs;
    } while (false);
    GMG_FREE(phMemoryModules);

    return bandwidth;
}

zes_perf_handle_t *getPerformanceFactorDomains(ze_device_handle_t hDevice, uint32_t *pCount) {
    ze_result_t res = zesDeviceEnumPerformanceFactorDomains(hDevice, pCount, NULL);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesDeviceEnumPerformanceFactorDomains(hDevice=%p,&count=%p,NULL) => 0x%x\n", hDevice, pCount, res);
        return NULL;
    }
    if (*pCount == 0) {
        // GMGLOG(LDMSD_LERROR, "!!!Could not retrieve performance factor domains: *pCount = 0\n");
        return NULL;
    }

    size_t memSize = sizeof(zes_perf_handle_t) * *pCount;
    zes_perf_handle_t *phPerf = GMG_MALLOC(memSize);

    res = zesDeviceEnumPerformanceFactorDomains(hDevice, pCount, phPerf);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesDeviceEnumPerformanceFactorDomains(hDevice=%p,pCount=%p,phPerf=%p) => 0x%x\n", hDevice, pCount, phPerf, res);
        GMG_FREE(phPerf);
        return NULL;
    }
    return phPerf;
}

double getPerfLevel(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 4.0;
    }

    uint32_t count = 0;
    zes_perf_handle_t *pHandle = getPerformanceFactorDomains(hDevice, &count);
    if (pHandle == NULL) {
        return -9999.9;
    }
    // GMGLOG(LDMSD_LDEBUG, "count = %d\n", count);

    double originalFactor = -9999.9;
    ze_result_t res = zesPerformanceFactorGetConfig(pHandle[0], &originalFactor);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesPerformanceFactorGetConfig(pHandle[0]=%p,&originalFactor=%p) => 0x%x\n", pHandle[0], &originalFactor, res);
    }
    GMG_FREE(pHandle);

    return originalFactor;
}

zes_pwr_handle_t *getPowerDomains(ze_device_handle_t hDevice, uint32_t *pCount) {
    ze_result_t res = zesDeviceEnumPowerDomains(hDevice, pCount, NULL);
    if (res != ZE_RESULT_SUCCESS) {
        return NULL;
    }
    if (*pCount == 0) {
        // GMGLOG(LDMSD_LERROR, "!!!Could not retrieve power domains: *pCount == 0\n");
        return NULL;
    }

    size_t memSize = sizeof(zes_pwr_handle_t) * *pCount;
    zes_pwr_handle_t *phPower = GMG_MALLOC(memSize);

    res = zesDeviceEnumPowerDomains(hDevice, pCount, phPower);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesDeviceEnumPowerDomains(hDevice=%p,pCount=%p,phPower=%p) => 0x%x\n", hDevice, pCount, phPower, res);
        GMG_FREE(phPower);
        return NULL;
    }
    return phPower;
}

int32_t getPowerUsage(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 42;
    }

    uint32_t count = 0;
    zes_pwr_handle_t *pHandle = getPowerDomains(hDevice, &count);
    if (pHandle == NULL) {
        return -99;
    }
    // GMGLOG(LDMSD_LDEBUG, "count = %d\n", count);

    int32_t powerUsage = -999;
    do {
        zes_power_energy_counter_t energyCounter0, energyCounter1;
        if (zesPowerGetEnergyCounter(pHandle[0], &energyCounter0) != ZE_RESULT_SUCCESS) {
            break;
        }
        if (msSleep(samplingIntervalInMs) != 0) {
            break;
        }
        if (zesPowerGetEnergyCounter(pHandle[0], &energyCounter1) != ZE_RESULT_SUCCESS) {
            break;
        }
        powerUsage = (energyCounter1.energy - energyCounter0.energy) /
                     (energyCounter1.timestamp - energyCounter0.timestamp);
    } while (false);
    GMG_FREE(pHandle);

    return powerUsage;
}

int32_t getPowerCap(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 424242;
    }

    uint32_t count = 0;
    zes_pwr_handle_t *pHandle = getPowerDomains(hDevice, &count);
    if (pHandle == NULL) {
        return -99;
    }
    // GMGLOG(LDMSD_LDEBUG, "count = %d\n", count);

    zes_power_properties_t properties;
    ze_result_t res = zesPowerGetProperties(pHandle[0], &properties);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesPowerGetProperties(pHandle[0]=%p,&properties=%p) => 0x%x\n", pHandle[0], &properties, res);
        return -9999;
    }
    GMG_FREE(pHandle);

    return properties.maxLimit;
}

zes_temp_handle_t *getDeviceEnumTemperatureSensors(ze_device_handle_t hDevice, uint32_t *pCount) {
    ze_result_t res = zesDeviceEnumTemperatureSensors(hDevice, pCount, NULL);
    if (res != ZE_RESULT_SUCCESS) {
        return NULL;
    }
    if (*pCount == 0) {
        // GMGLOG(LDMSD_LERROR, "!!!Could not enum temperature sensors: *pCount == 0\n");
        return NULL;
    }

    size_t memSize = sizeof(zes_temp_handle_t) * *pCount;
    zes_temp_handle_t *pHandle = GMG_MALLOC(memSize);

    res = zesDeviceEnumTemperatureSensors(hDevice, pCount, pHandle);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesDeviceEnumTemperatureSensors(hDevice=%p,pCount=%p,pHandle=%p) => 0x%x\n", hDevice, pCount, pHandle, res);
        GMG_FREE(pHandle);
        return NULL;
    }

    return pHandle;
}

double getGpuTemp(ze_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 42.0;
    }

    uint32_t count = 0;
    zes_temp_handle_t *pHandle = getDeviceEnumTemperatureSensors(hDevice, &count);
    if (pHandle == NULL) {
        return -99.0;
    }
    // GMGLOG(LDMSD_LDEBUG, "count = %d\n", count);

    double gpuTemperature = -999.0;

    ze_result_t res = zesTemperatureGetState(pHandle[0], &gpuTemperature);
    if (res != ZE_RESULT_SUCCESS) {
        return -99.9;
    }
    GMG_FREE(pHandle);

    return gpuTemperature;
}

int64_t getPciMaxSpeed(
        zes_device_handle_t hDevice) {
    if (g_bIsInSimulationMode) {
        return 424242;
    }
    zes_pci_stats_t state = {};

    ze_result_t res = zesDevicePciGetStats(hDevice, &state);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!zesDevicePciGetStats(hDevice=%p,&state=%p) => 0x%x\n", hDevice, &state, res);
        return -99999;
    }
    return state.speed.maxBandwidth;
}

static ze_result_t gmgsDeviceGetProperties(
        zes_device_handle_t hDevice,
        zes_device_properties_t *pDeviceProperties) {
    if (g_bIsInSimulationMode) {
        strncpy(pDeviceProperties->serialNumber, "GPU Serial Number 999", ZES_STRING_PROPERTY_SIZE);
        return ZE_RESULT_SUCCESS;
    }

    return zesDeviceGetProperties(hDevice, pDeviceProperties);
}

const char *getGpuSerialNumber(
        zes_device_handle_t hDevice) {
    static char szSerialNumber[ZES_STRING_PROPERTY_SIZE+1];
    memset(szSerialNumber, 0, sizeof(szSerialNumber)/sizeof(szSerialNumber[0]));

    zes_device_properties_t deviceProperties = {
            ZES_STRUCTURE_TYPE_DEVICE_PROPERTIES};

    ze_result_t res = gmgsDeviceGetProperties(hDevice, &deviceProperties);
    if (res != ZE_RESULT_SUCCESS) {
        // GMGLOG(LDMSD_LERROR, "!!!gmgsDeviceGetProperties(hDevice=%p, &deviceProperties=%p) => 0x%x", hDevice, &deviceProperties, res);
        return szSerialNumber;
    }

    size_t serialNumberLength = strnlen(deviceProperties.serialNumber, ZES_STRING_PROPERTY_SIZE);
    // GMGLOG(LDMSD_LDEBUG, "%s has length = %ld\n", deviceProperties.serialNumber, serialNumberLength);

    strncpy(szSerialNumber, deviceProperties.serialNumber, ZES_STRING_PROPERTY_SIZE);
    return szSerialNumber;
}

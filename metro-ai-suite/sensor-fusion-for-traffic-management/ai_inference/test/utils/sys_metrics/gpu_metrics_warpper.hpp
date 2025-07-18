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

#ifndef GPU_METRICS_WRAPPER_HPP
#define GPU_METRICS_WRAPPER_HPP

#include <iostream>
#include <iomanip>
#include <chrono>
#include <assert.h>

#include "gather_gpu_metrics_from_one_api.h"
#include <level_zero/zes_api.h>

using namespace std::chrono;
using namespace std;

namespace hce{

namespace ai{

namespace inference{
     
class GPUMetrics {
public:
     GPUMetrics() : m_numDevices(0), m_phDevices(NULL) {}; 

     ~GPUMetrics() {
          freeZeDeviceHandle(m_phDevices);
          m_phDevices = NULL;
     };

     /**
      * @brief initialize device context
      */
     void init(){
          ze_result_t res = initializeOneApi();
          if (res != ZE_RESULT_SUCCESS) {
               cerr << "!!!initializeOneApi => 0x" << hex << res << endl;
               assert(false);
          }
          ze_driver_handle_t hDriver = getDriver();
          if (hDriver == NULL) {
               cerr << "!!!getDriver() => NULL" << endl;
               assert(false);
          }
          
          m_phDevices = enumerateGpuDevices(hDriver, &m_numDevices);
          if (m_phDevices == NULL) {
               cerr << "!!!enumerateGpuDevices() => NULL" << endl;
               assert(false);
          }
          std::cout << m_numDevices << " GPU device(s) discovered" << std::endl;
     };

     /**
      * @brief get device name by device_id
      * @param DeviceId
      * @return Device name, e.g: 
      *             Intel(R) Arc A770 Graphics
      *             Intel(R) UHD Graphics Adler Lake-S
      */
     std::string deviceName(uint32_t DeviceId) {
          std::string desc = getGpuDeviceName(m_phDevices[DeviceId]);
          int pos = desc.rfind("[");
          int len = desc.rfind("]") - pos;
          std::string pciId = desc.substr(pos + 1, len - 1);
          return pciId2deviceName(pciId);
     };

     /**
      * @brief get device uuid by device_id
      * @param DeviceId
      * @return Device name, e.g: 
      *             00000002-0000-0000-0000-000000000001
      *             00000300-0000-0000-0000-000000000001
      */
     std::string deviceUUid(uint32_t DeviceId) {
          return convertUuidToString(getGpuUuid(m_phDevices[DeviceId]));
     };

     /**
      * @brief get device serial number by device_id
      * @param DeviceId
      */
     std::string deviceSerialNumber(uint32_t DeviceId) {
          return getGpuSerialNumber(m_phDevices[DeviceId]);
     };

     /**
      * @brief gpu utilization on zes_engine_group_t: ZES_ENGINE_GROUP_ALL
      * @param DeviceId
      */
     double gpuAllUtilization(uint32_t DeviceId) {
          return getGpuUtilization(m_phDevices[DeviceId], ZES_ENGINE_GROUP_ALL);
     };

     /**
      * @brief gpu utilization on zes_engine_group_t: ZES_ENGINE_GROUP_COMPUTE_SINGLE
      * @param DeviceId
      */
     double gpuComputeUtilization(uint32_t DeviceId) {
          return getGpuUtilization(m_phDevices[DeviceId], ZES_ENGINE_GROUP_COMPUTE_SINGLE);
     };

     /**
      * @brief gpu utilization on zes_engine_group_t: ZES_ENGINE_GROUP_MEDIA_DECODE_SINGLE
      * @param DeviceId
      */
     double gpuDecodeUtilization(uint32_t DeviceId) {
          return getGpuUtilization(m_phDevices[DeviceId], ZES_ENGINE_GROUP_MEDIA_DECODE_SINGLE);
     };

     /**
      * @brief memory utilization
      * @param DeviceId
      */
     double memUtilization(uint32_t DeviceId) {
          return getMemoryUtilization(m_phDevices[DeviceId]);
     };

     /**
      * @brief power utilization
      * @param DeviceId
      */
     double powerUsage(uint32_t DeviceId) {
          return getPowerUsage(m_phDevices[DeviceId]);
     };

     /**
      * @brief gpu temperature
      * @param DeviceId
      */
     double gpuTemp(uint32_t DeviceId) {
          return getGpuTemp(m_phDevices[DeviceId]);
     };

     /**
      * @brief gpu device number
      */
     int deviceCount() {
          return m_numDevices;
     }

     /**
      * @brief report gpu utilization description
     */
     std::string report(uint32_t DeviceId) {

          double utilization = gpuAllUtilization(DeviceId);
          char gpuStr[1024];
          sprintf(gpuStr, "[GPU] %s: %0.2f%%", deviceName(DeviceId).c_str(), utilization);

          return std::string(gpuStr);
     }

private:
     uint32_t m_numDevices;
     ze_device_handle_t *m_phDevices;

     /**
      * @brief convter intel pci id to device name
      *        reference: https://dgpu-docs.intel.com/devices/hardware-table.html
      * @param pciId
      */
     std::string pciId2deviceName(std::string pciId) {
          if (pciId == "0x56a0") {
               return "Intel(R) Arc A770 Graphics";
          } else if (pciId == "0x56a1") {
               return "Intel(R) Arc A750 Graphics";
          } else if (pciId == "0x56a5") {
               return "Intel(R) Arc A380 Graphics";
          } else if (pciId == "0x4690") {
               return "Intel(R) UHD Graphics Adler Lake-S";
          } else {
               return pciId;
          }
     }
};


void printGpuMetrics(ze_device_handle_t device, uint32_t devNumber) {
    cout << " " << devNumber << "    -1 Format: Value          Descriptive text" << endl;

    uint32_t metricNumber = 0;
    cout << fixed << setprecision(2);
    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getGpuUtilization(device, ZES_ENGINE_GROUP_ALL) << "           [all] gpu_util (%)" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getGpuUtilization(device, ZES_ENGINE_GROUP_COMPUTE_SINGLE) << "           [compute] gpu_util (%)" << endl;
         
    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getGpuUtilization(device, ZES_ENGINE_GROUP_MEDIA_DECODE_SINGLE) << "           [decode] gpu_util (%)" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getMemoryUtilization(device) << "           mem_util (%)" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getMemVRAMUsed(device) << "       mem_vram_used" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getSysClockFreq(device) << "           sys_clock_freq (MHz)" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getMemoryReadBandwidth(device) << "          mem_read_bandwidth (kilobaud)" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getMemoryWriteBandwidth(device) << "          mem_write_bandwidth (kilobaud)" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getPerfLevel(device) << "           perf_level" << endl;


    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getPowerUsage(device) << "             power_usage (mW)" << endl;

    //  The following is no longer supported.
//    cout << " " << devNumber << "     " << metricNumber++ << "         "
//         << getPowerCap(device) << "         power_cap (mW)" << endl;

    cout << " " << devNumber << "     " << metricNumber++ << "         "
         << getGpuTemp(device) << "          gpu_temp (Celsius)" << endl;
}

int sampleGpuMetrics() {
    auto start = high_resolution_clock::now();

    ze_result_t res = initializeOneApi();
    if (res != ZE_RESULT_SUCCESS) {
        cerr << "!!!initializeOneApi => 0x" << hex << res << endl;
        return 1;
    }

    cout << "-1    -1         GPU Driver discovery ..." << endl;
    ze_driver_handle_t hDriver = getDriver();
    if (hDriver == NULL) {
        cerr << "!!!getDriver() => NULL" << endl;
        return 2;
    }

    auto stop = high_resolution_clock::now();
    auto duration = duration_cast<microseconds>(stop - start);
    cout << "-1    -1         GPU driver discovered in " << duration.count() / 1000 <<
         " ms" << endl;

    cout << "-1    -1         Enumerating devices managed by driver[0] ..." << endl;
    uint32_t numDevices = 0;
    ze_device_handle_t *phDevices = enumerateGpuDevices(hDriver, &numDevices);
    if (phDevices == NULL) {
        cerr << "!!!enumerateGpuDevices() => NULL" << endl;
        return 3;
    }
    cout << "-1    -1         " << numDevices << " GPU device(s) discovered" << endl;

    uint32_t devNumber = 0;
    for (uint32_t i = 0; i < numDevices; i++) {
        cout << " " << devNumber << "    -1         Device name = " << getGpuDeviceName(phDevices[devNumber]) << endl;
        cout << " " << devNumber << "    -1         Device uuid = " << convertUuidToString(getGpuUuid(phDevices[devNumber])) << endl;
        cout << " " << devNumber << "    -1         Serial number = " << getGpuSerialNumber(phDevices[devNumber])<< endl;
        printGpuMetrics(phDevices[i], devNumber++);
    }

    freeZeDeviceHandle(phDevices);
    phDevices = NULL;

    return 0;
}


}
}
}

#endif /* GPU_METRICS_WRAPPER_HPP */
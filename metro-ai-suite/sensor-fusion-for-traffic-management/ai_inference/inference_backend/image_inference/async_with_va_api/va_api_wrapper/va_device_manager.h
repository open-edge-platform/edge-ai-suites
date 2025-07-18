/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#pragma once

#include <mutex>
#include <memory>
#include <stdexcept>
#include <string>
#include <assert.h>
#include <fcntl.h>
#include <glob.h>
#include <unistd.h>
#include <unordered_map>

#include <vaapi_utils.h>
#include <scope_guard.h>

#include "modules/vaapi/context.h"

#ifdef ENABLE_VAAPI
    #include "va/va.h"
    #include "va/va_drm.h"
#endif

namespace hce{

namespace ai{

namespace inference{

// /**
//  * A singleton that holds a map of created VADisplay with device id info
//  * so that a device id only relates to a single VADisplay
//  */
class VADeviceManager {
  public:
    
    ~VADeviceManager();

    /**
     * @brief Get a reference to pipeline manager instance
     *
     * @param void
     * @return reference to the singleton
     *
     */
    static VADeviceManager& getInstance();

    // VADisplay getVADisplay(uint32_t deviceID = 0);
    hce::ai::inference::VAAPIContextPtr getVADisplay(uint32_t deviceID = 0);
    void addVADisplay(VADisplay display);

  private:
    VADeviceManager();

    hce::ai::inference::VAAPIContextPtr createVaDevice(uint32_t deviceID = 0);

    /**
     * Sets the internal VADisplay's error and info callbacks. Initializes the
     * internal VADisplay.
     *
     * @pre _display must be set.
     * @pre libva_handle must be set to initialize VADisplay.
     * @pre message_callback_error, message_callback_info functions must reside in
     * namespace to set callbacks.
     *
     * @throw std::runtime_error if the initialization failed.
     * @throw std::invalid_argument if display is null.
     */
    void initializeVaDisplay(VaDpyWrapper display);

    void destroyVaDevice(VADisplay display);

    // static int _dri_file_descriptor;
    std::unordered_map<uint32_t, hce::ai::inference::VAAPIContextPtr> m_vaDisplayDict;

    std::mutex mMutex;
};

// // /**
// //  * A singleton that holds a map of created VADisplay with device id info
// //  * so that a device id only relates to a single VADisplay
// //  */
// class VADeviceManager {
//   public:
    
//     ~VADeviceManager() {
//         int status = close(_dri_file_descriptor);
//         if (status != 0) {
//             GVA_WARNING("DRI file descriptor closing failed with code: %d", status);
//         }
//         for (auto &dsp : m_vaDisplayDict) {
//             destroyVaDevice(dsp.second);
//         }
//         m_vaDisplayDict.clear();
//     };

//     /**
//      * @brief Get a reference to pipeline manager instance
//      *
//      * @param void
//      * @return reference to the singleton
//      *
//      */
//     static VADeviceManager& getInstance() {
//         static VADeviceManager instance; // Guaranteed to be destroyed, Instantiated on first use.
//         return instance;
//     };

//     VADisplay getVADisplay(uint32_t deviceID = 0) {
//         std::lock_guard<std::mutex> lck(mMutex);
//         if (m_vaDisplayDict.count(deviceID) == 0) {
//             std::cout << "creating vadisplay for device" <<  deviceID << " as count= " << m_vaDisplayDict.count(deviceID) << std::endl;
//             createVaDevice(deviceID);
//         } else {
//             std::cout << "will reuse vadisplay" << std::endl;
//         }
//         VADisplay dsp = m_vaDisplayDict.at(deviceID);
//         std::cout << "VADisplay addr " << dsp << std::endl;
//         return dsp;
//     };

//   private:
//     VADeviceManager();

//     void createVaDevice(uint32_t deviceID = 0) {
//         static const char *DEV_DRI_RENDER_PATTERN = "/dev/dri/renderD*";

//         glob_t globbuf;
//         globbuf.gl_offs = 0;

//         int ret = glob(DEV_DRI_RENDER_PATTERN, GLOB_ERR, NULL, &globbuf);
//         auto globbuf_sg = makeScopeGuard([&] { globfree(&globbuf); });

//         if (ret != 0) {
//             throw std::runtime_error("Can't access render devices at /dev/dri. glob error " + std::to_string(ret));
//         }

//         if (deviceID >= globbuf.gl_pathc) {
//             throw std::runtime_error("There is no device with index " + std::to_string(deviceID));
//         }

//         _dri_file_descriptor = open(globbuf.gl_pathv[deviceID], O_RDWR);
//         if (_dri_file_descriptor < 0) {
//             int err = errno;
//             throw std::runtime_error("Error opening " + std::string(globbuf.gl_pathv[deviceID]) + ": " +
//                                     std::to_string(err));
//         }

//         VADisplay display = VaApiLibBinder::get().GetDisplayDRM(_dri_file_descriptor);
//         initializeVaDisplay(VaDpyWrapper::fromHandle(display));

//         std::cout << "inserting display for " <<  deviceID << std::endl;
//         m_vaDisplayDict.insert(std::make_pair(deviceID, display));
//         std::cout << "inserting display for " <<  deviceID << " done" << std::endl;
//         std::cout << " as count= " << m_vaDisplayDict.count(deviceID) << std::endl;
//     };

//     /**
//      * Sets the internal VADisplay's error and info callbacks. Initializes the
//      * internal VADisplay.
//      *
//      * @pre _display must be set.
//      * @pre libva_handle must be set to initialize VADisplay.
//      * @pre message_callback_error, message_callback_info functions must reside in
//      * namespace to set callbacks.
//      *
//      * @throw std::runtime_error if the initialization failed.
//      * @throw std::invalid_argument if display is null.
//      */
//     void initializeVaDisplay(VaDpyWrapper display) {
//         assert(display);

//         int major_version = 0, minor_version = 0;
//         VA_CALL(VaApiLibBinder::get().Initialize(display.raw(), &major_version, &minor_version));
//     }

//     void destroyVaDevice(VADisplay display) {
//         VAStatus va_status = VaApiLibBinder::get().Terminate(display);
//         if (va_status != VA_STATUS_SUCCESS) {
//             GVA_ERROR("VA Display termination failed with code: %d", va_status);
//         }
//     };

//     int _dri_file_descriptor;
//     std::unordered_map<uint32_t, VADisplay> m_vaDisplayDict;

//     std::mutex mMutex;
// };

} // namespace inference

} // namespace ai

} // namespace hce

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

#include "va_device_manager.h"


namespace hce{

namespace ai{

namespace inference{

VADeviceManager::VADeviceManager() {
}

VADeviceManager::~VADeviceManager(){
    // for (auto &dsp : m_vaDisplayDict) {
    //     destroyVaDevice(dsp.second);
    // }
    m_vaDisplayDict.clear();
    // if (_dri_file_descriptor >= 0) {
    //     int status = close(_dri_file_descriptor);
    //     // if (status != 0) {
    //     //     GVA_WARNING("DRI file descriptor closing failed with code: %d", status);
    //     // }
    // }
    
}

VADeviceManager& VADeviceManager::getInstance(){
    static VADeviceManager instance; // Guaranteed to be destroyed, Instantiated on first use.
    return instance;
}

// VADisplay VADeviceManager::getVADisplay(uint32_t deviceID) {
//     std::lock_guard<std::mutex> lck(mMutex);
//     if (m_vaDisplayDict.count(deviceID) == 0) {
//         GVA_INFO("Create new VA display");
//         createVaDevice(deviceID);
//     } 
//     VADisplay dsp = m_vaDisplayDict.at(deviceID);
//     return dsp;
// }

hce::ai::inference::VAAPIContextPtr VADeviceManager::getVADisplay(uint32_t deviceID) {
    std::lock_guard<std::mutex> lck(mMutex);
    if (m_vaDisplayDict.count(deviceID) == 0) {
        hce::ai::inference::VAAPIContextPtr context = createVaDevice(deviceID);
        m_vaDisplayDict.insert(std::make_pair(deviceID, context));
    } 
    return m_vaDisplayDict.at(deviceID);
    
}

hce::ai::inference::VAAPIContextPtr VADeviceManager::createVaDevice(uint32_t deviceID) {
    static const char *DEV_DRI_RENDER_PATTERN = "/dev/dri/renderD*";

    glob_t globbuf;
    globbuf.gl_offs = 0;

    int ret = glob(DEV_DRI_RENDER_PATTERN, GLOB_ERR, NULL, &globbuf);
    auto globbuf_sg = makeScopeGuard([&] { globfree(&globbuf); });

    if (ret != 0) {
        throw std::runtime_error("Can't access render devices at /dev/dri. glob error " + std::to_string(ret));
    }

    if (deviceID >= globbuf.gl_pathc) {
        throw std::runtime_error("There is no device with index " + std::to_string(deviceID));
    }

    int _dri_file_descriptor = open(globbuf.gl_pathv[deviceID], O_RDWR);
    if (_dri_file_descriptor < 0) {
        int err = errno;
        throw std::runtime_error("Error opening " + std::string(globbuf.gl_pathv[deviceID]) + ": " +
                                 std::to_string(err));
    }

    VADisplay display = VaApiLibBinder::get().GetDisplayDRM(_dri_file_descriptor);
    initializeVaDisplay(VaDpyWrapper::fromHandle(display));

    auto deleter = [_dri_file_descriptor](hce::ai::inference::VAAPIContext *context) {
        VADisplay display = context->va_display();
        VAStatus va_status = VaApiLibBinder::get().Terminate(display);
        if (va_status != VA_STATUS_SUCCESS) {
            GVA_ERROR("VA Display termination failed with code: %d", va_status);
        }
        int status = close(_dri_file_descriptor);
        if (status != 0) {
            GVA_WARNING("DRI file descriptor closing failed with code: %d", status);
        }
        delete context;
    };

    return {new hce::ai::inference::VAAPIContext(display), deleter};
}

void VADeviceManager::destroyVaDevice(VADisplay display) {
    VAStatus va_status = VaApiLibBinder::get().Terminate(display);
    // if (va_status != VA_STATUS_SUCCESS) {
    //     GVA_ERROR("VA Display termination failed with code: %d", va_status);
    // }
}

/**
 * Sets the internal VADisplay's error and info callbacks. Initializes the internal VADisplay.
 *
 * @pre _display must be set.
 * @pre libva_handle must be set to initialize VADisplay.
 *
 * @throw std::runtime_error if the initialization failed.
 * @throw std::invalid_argument if display is null.
 */
void VADeviceManager::initializeVaDisplay(VaDpyWrapper display) {
    assert(display);

    int major_version = 0, minor_version = 0;
    VA_CALL(VaApiLibBinder::get().Initialize(display.raw(), &major_version, &minor_version));
}


} // namespace inference

} // namespace ai

} // namespace hce
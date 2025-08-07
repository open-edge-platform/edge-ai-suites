/*

 * INTEL CONFIDENTIAL

 *

 * Copyright (C) 2023-2024 Intel Corporation

 *

 * This software and the related documents are Intel copyrighted materials, and your use of them is governed by the

 * express license under which they were provided to you ("License"). Unless the License provides otherwise, you may not

 * use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without Intel's

 * prior written permission.

 *

 * This software and the related documents are provided as is, with no express or implied warranties, other than those

 * that are expressly stated in the License.

 */

#pragma once
#include <string>
#include <memory>
#include <memory>
#include <map>
#include "svet_util.h"


namespace SVET_APP {
    struct DisplayAttr {
        int resolutionH; //Max Horizontal resolution
        int resolutionV; //Max Vertical resolution
        int refreshR; //Refresh rate of supported max resolution
        std::string name;
        int deviceId;
    };


    enum class VideoLayerState : unsigned int {
        Uninitialized,
        Initialized,
        Play,
        Stop,
        Destroy
    };

    struct VideoLayerInfo {
        Rect rect;
        unsigned int bufferSize;
        unsigned int pixelFormat;
        unsigned int refreshRate; //The refresh rate of display mode
        unsigned int fps;   //The fps of videolayer showing on display
        unsigned int tilenum;   // Number of tiles for tile composition
        VideoLayerState state;
    };

    class DisplayDevice {
    public:
        using Ptr = std::shared_ptr<DisplayDevice>;
        //Print the connected display devices, like device name, maximum resolution and frame rate.
        //Return the number of display device
        static int ShowDisplayDevices();
        //id ranges from 0 to (max display device - 1). It maps to the Nth device ID
        //e.g.  3 displays with device id 110, 134, 150. Then id 0 indicates display with device id 110,
        //id 1 indicates display with device id 134. Not support hot-plug.
        DisplayDevice() : mState(NodeState::Uninitialized), mId(-1)  {}

        virtual ~DisplayDevice();;

        //Work flow: init -> CreateVideoLayers -> start -> stop
        //If success, return 0, otherwise return -1.
        int Init(int id);

        int Start();

        int Stop();

        int Start(int videoLayer);
        int Stop(int videoLayerId);

        NodeState getDispState() {return mState; };

        int StartDisp();

        //Return the id of current display device. Return -1 if the display device hasn't been initialized.
        int GetDisplayId() {return (mState > NodeState::Uninitialized) ? mId : -1; };

        //Return the device id of current display device. Return -1 if the display device hasn't been initialized.
        int GetDeviceId() {return (mState > NodeState::Uninitialized) ? mDispInfo.deviceId : -1; };

        bool IsInited() {return (mState > NodeState::Uninitialized); };

        int SetDisplayAttributes(int resW, int resH, int refreshR);

        int CreateVideoLayer(VideoLayerInfo &attr, int id);

        bool hasVideoLayer(int id) {return (mVideoLayers.find(id) != mVideoLayers.end()); }

        std::map<int, std::shared_ptr<VideoLayerInfo>> mVideoLayers;

        int Destroy();

    private:
        //If no display device found, the returned deviceId will be -1.
        int GetDisplayInfo(int id, DisplayAttr &info);  

        DisplayAttr mDispInfo;
        NodeState mState;
        int mId;

    };
}
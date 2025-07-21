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
//
// Created by dell on 2022/9/29.
//

#pragma once

#include <vector>
#include <string>
#include <memory>
#include <stdint.h>

namespace SVET_APP {
/*
 * 1. All commands must be grouped. There are two types of command groups: a) Pipeline set up b) Pipeline control
 * 2. Pipeline set up commands group can contain commands NewVideoLayer, NewDec, NewVpp. It's to initialize the pipeline
 * 3. Pipeline control commands include DecCtrl and OsdCtrl. The pipeline must be initialized before it's sent to pipeline
 *    manager.
 * 4. The decode channel, vpp task and video output id must be unique.
 * 5. The group of commands must end with Ctrl command. It indicates if svet app need to pause for a while before parsing
 *    next commands group.
 * 6. All decode nodes must link to pp or display sink. All pp nodes must link to display sink. Dangling nodes aren't
 *    allowed
 * 7. Make sure on extra space at the end of each line in configuration file. Otherwise you will see error "The following
 *    argument was not expected"
 * 8. One commands group only targets one video output. If there is no newvl command in the group, user shall specify
 *    video layer id in the command 'ctrl'
 *
 * */


enum class VideoFrameType : int {
       FOURCC_NV12,
       FOURCC_YUY2,
       FOURCC_RGB4
};

inline const char *FormatToString(int videoFrameFormat) {
    VideoFrameType format = static_cast<VideoFrameType>(videoFrameFormat);
    switch (format) {
        case VideoFrameType::FOURCC_NV12:
            return "NV12";
        case VideoFrameType::FOURCC_RGB4:
            return "RGB4";
        case VideoFrameType::FOURCC_YUY2:
            return "YUY2";
        default:
            return "Unknown";
    }
}
//operate type
    enum class OpType : int {
        Ctrl,
        NewVideoLayer,
        DispCH,
        NewDec,
        NewVpp,
        DecCtrl,
        OsdCtrl,
        DispChCtrl
    };

//control command
    enum class CtrlCMD : int {
        Run, //Send the set up commands group to pipeline manager and process next command
        Noop, //Sleep for specified time and process next command
        Stop, //stop the pipeline
        Update, //Send the commands to pipeline manager and process next command
        ShowDisplay //show the information of connected display device, like id, max resolution and refresh rate
    };

//control operate parameter
    struct CtrlPara {
        CtrlPara() : cmd(CtrlCMD::Run), time(0), videoLayerId(-1) {}

        CtrlCMD cmd;
        uint32_t time;
        int32_t videoLayerId; //If there is no newvl command in current command group, user shall specify the video layer id
    };

//new video layer parameter
    struct NewVideoLayerPara {
        NewVideoLayerPara() : id(0), resW(0), resH(0), refresh(30), format(0), dispid(0), fps(30), tilenum(0) {}

        uint32_t id; //This id should be unqiue for all video layers.
        uint16_t resW;
        uint16_t resH;
        uint32_t refresh; //display referesh rate
        uint32_t format;
        uint32_t dispid;
        uint32_t fps; //video layer display fps
        uint32_t tilenum;  // number of tiles if tile composition is needed
        //uint32_t layer;
    };

//display stream parameter
    struct DispStreamPara {
        DispStreamPara() : id(0), w(0), h(0), x(0), y(0), videoLayer(0), tileid(-1) {}

        uint32_t id; //This id should be unqiue for one video layer.
        uint16_t w;
        uint16_t h;
        uint16_t x;
        uint16_t y;
        uint32_t videoLayer;
        int32_t tileid;
    };

//decode mode
    enum class DecMode : int {
        Playback,
        Preview
    };

//new decode node parameter
    struct NewDecPara {
        //SFC is on by default.But if the decW and decH aren't set and sink input isn't set, like pp,
        //SFC will be disabled because app can't decide the output size.
        NewDecPara() : id(0), decW(0), decH(0), decFormat(0), rotate(0),
        mode(DecMode::Playback), sfcEnable(false), loopInput(false) {}

        uint32_t id;
        std::string input;
        std::string dump;
        std::string codec;
        uint32_t decW;
        uint32_t decH;
        uint32_t decFormat;
        uint32_t rotate;
        std::string sink;
        DecMode mode;
        bool sfcEnable;
        bool loopInput;
    };

//decode control command
    enum class DecCtrlCMD : int {
        Remove,
        AddPic,
        RemovePic
    };

//decode control parameter
    struct DecCtrlPara {
        DecCtrlPara() : decid(-1), w(0), h(0), cmd(DecCtrlCMD::RemovePic),
        instant(true) {}
        int32_t decid;
        uint32_t w;
        uint32_t h;
        DecCtrlCMD cmd;
        std::string picFilename;
        bool instant; //If the enable user picture command take effect immediately or add user picture to decode queue
    };

//post process output parameter
    struct PostProcessOutputPara {
        PostProcessOutputPara() : w(0), h(0), format(0), rotation(0), framerate(0), cropW(0), cropH(0),
                                  cropX(), cropY(0), denoise(0), depth(0) {}

        std::string sink;
        uint32_t w;
        uint32_t h;
        uint32_t format;
        uint32_t rotation;
        uint32_t framerate;
        uint32_t cropW;
        uint32_t cropH;
        uint32_t cropX;
        uint32_t cropY;
        uint32_t denoise;
        uint8_t depth;
    };

//post process parameter
    struct PostProcessPara {
        PostProcessPara() : id(0) {}

        uint32_t id;
        std::vector<std::shared_ptr<PostProcessOutputPara>> OutputParas;
    };

    enum class DispChCtrlCMD : int {
        Pause,
        Resume,
        Hide,
        Show,
        ZoomIn,
        ZoomOut,
        AddOsd,
        DelOsd
    };

//Display channel control parameter
    struct DispChCtrlPara {
        DispChCtrlPara() : id(0), videoLayer(0), cmd(DispChCtrlCMD::Pause), osdid(0), w(0), h(0), x(0), y(0) {}

        uint32_t id;
        uint32_t videoLayer; //The video layer that this display stream belongs to.
        DispChCtrlCMD cmd;
        std::string picFilename;
        uint32_t osdid;
        uint16_t w; //For Zoomin command, specify the Zoomin area.
        uint16_t h;
        uint16_t x;
        uint16_t y;
    };

//OSD control command
    enum class OSDCtrlCMD : int {
        Add,
        Remove,
        SetAttrs,
    };

//OSD control command parameter
    struct OSDCtrlPara {
        OSDCtrlPara() : id(0), cmd(OSDCtrlCMD::Add), dispch(-1), videoLayer(-1), ppstream(-1), width(0), height(0), gridSize(0), x(0), y(0) {}

        uint32_t id;
        OSDCtrlCMD cmd;
        int32_t dispch;
        int32_t videoLayer;
        int32_t ppstream;
        uint16_t width;
        uint16_t height;
        uint32_t gridSize;
        uint16_t x;
        uint16_t y;
    };

//parsed command and it's data
    struct OperateCmd {
        OpType type;
        std::shared_ptr<void> para;
    };

    using OperateCmds = std::vector<std::shared_ptr<OperateCmd>>;

    enum class CmdsError : int {
        None = 0,
        UnknownCmd = -1,
        Uninitialized = -2,
        DuplicatedId = -3,
        InvalidId = -4,
        MixedSetupAndCtrl = -5,
        DanglingNodes = -6,
        UnknownError = -7,
        InvalidParameter = -8,
        VPPSDK_FAIL = -9
    };
class PipelineException: public std::exception {
private:
    CmdsError mCmdError;
public:
    PipelineException(CmdsError cmdError) : mCmdError(cmdError) {

    }
    CmdsError getErrorCode() {return mCmdError;}
    const char *what() const noexcept override{
        switch (mCmdError) {
            case CmdsError::None:
                return "None";
            case CmdsError::UnknownCmd:
                return "UnknownCmd";
            case CmdsError::Uninitialized:
                return "Uninitialized";
            case CmdsError::DuplicatedId:
                return "DuplicatedId";
            case CmdsError::InvalidId:
                return "InvalidId";
            case CmdsError::MixedSetupAndCtrl:
                return "MixedSetupAndCtrl";
            case CmdsError::DanglingNodes:
                return "DanglingNodes";
            case CmdsError::InvalidParameter:
                return "InvalidParameter";
            case CmdsError::VPPSDK_FAIL:
                return "VPPSDK_FAIL";
            case CmdsError::UnknownError:
                default:
                    return "UnknownError";
        }
    }
};
}

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

#include <tuple>
#include <iostream>
#include <memory>
//#define VPPSDK
#ifdef VPPSDK
#include <vpp_common.h>
#include <vpp_system.h>
#else
#ifdef VPPSDK_DEC
#include <vpp_common.h>
#include <vpp_system.h>
#endif
#endif
#include "pipeline_manager.h"
#include "svet_util.h"
#include "display_device.h"
#include "decode.h"
#include "spdlog/spdlog.h"
#include "postprocess.h"
#include "osd.h"

using std::tuple;
using std::string;
using std::cout;
using std::endl;
using spdlog::debug;
using spdlog::info;
using spdlog::error;
using spdlog::warn;

using namespace SVET_APP;

PipelineManager::PipelineManager() : mState(PipelineState::Uninitialize), mVppSDKInit(false) {

}

PipelineManager::~PipelineManager() {
#ifdef VPPSDK_DEC
    if (mVppSDKInit) {
        int res = VPP_DeInit();
        if (res != VPP_STATUS_SUCCESS ) {
                std::cout<<"SVET app: "<<__func__<< " VPP_DeInit return error: "<< res <<std::endl;
        }
    }
#endif
}

void PipelineManager::printCmdErrors(const char *errorMsg) {
    error("SVET app: command error {} ", errorMsg);
}

int PipelineManager::processCmds(OperateCmds &cmds, CtrlPara &ctrlCmd) {
    CmdsValidateResults res = {false};

    try {
        validateCmds(cmds, res);

#ifdef VPPSDK_DEC
        int vppres = 0;
        if (!mVppSDKInit) {
            vppres = VPP_Init();
            if (vppres != VPP_STATUS_SUCCESS ) {
                error("SVET app: {} VPP_Init return error {}", __func__, vppres);
                throw(PipelineException(CmdsError::VPPSDK_FAIL));
            }
            mVppSDKInit = true;
        }
#endif
        if (res.isSetupCmd) {
            processSetupCmds(cmds, ctrlCmd.videoLayerId);
        } else {
            changeState(cmds, ctrlCmd);
        }
    }
    catch (PipelineException &e) {
        printCmdErrors(e.what());
        return (int)e.getErrorCode();
    }
    return 0;
}

int PipelineManager::changeState(OperateCmds &cmds, CtrlPara &ctrlCmd) {
    for (auto &opcmd : cmds) {
        OpType type = opcmd->type;
        switch (type) {

            case OpType::DecCtrl: {
                DecCtrlPara *para = reinterpret_cast<DecCtrlPara *>(opcmd->para.get());
                if (ctrlCmd.videoLayerId < 0) {
                    error("SVET app: {}: invalid video layer id {}", __func__, ctrlCmd.videoLayerId);
                    error("SVET app: Please specify which video layer will be used as display");
                    break;
                }
                processDecodeCtrlCmds(para);
                break;
            }
            case OpType::NewDec: {
                if (ctrlCmd.videoLayerId < 0) {
                    error("SVET app: {}: invalid video layer id {}", __func__, ctrlCmd.videoLayerId);
                    error("SVET app: Please specify which video layer will be used as display");
                    break;
                }
            }
                break;
            case OpType::DispChCtrl: {
                DispChCtrlPara *para = reinterpret_cast<DispChCtrlPara *>(opcmd->para.get());
                processDispChCtrlCmds(para);
            }
                break;
            case OpType::OsdCtrl: {
                OSDCtrlPara *para = reinterpret_cast<OSDCtrlPara *>(opcmd->para.get());
                processOsdCtrlCmds(para);
            }
                break;
            default:
                throw(PipelineException(CmdsError::UnknownCmd));
                break;
        }
    }
    return 0;
}


int PipelineManager::validateCmds(OperateCmds &cmds, CmdsValidateResults &res) {
    bool hasNewVo = false;
    bool hasNewDec = false;
    bool hasCtrlCmd = false;
    bool hasDispCh = false;
    res.isSetupCmd = false;

    for (auto &opcmd : cmds) {
        OpType type = opcmd->type;
        switch (type) {
            case OpType::NewVideoLayer:
            {
                //NewVideoLayerPara *para = reinterpret_cast<NewVideoLayerPara *>(opcmd->para.get());
                hasNewVo = true;
            }
            break;
            case OpType::DispCH:
            {
                //DispStreamPara *para = reinterpret_cast<DispStreamPara *>(opcmd->para.get());
                hasDispCh = true;

            }
            break;
            case OpType::NewDec:
            {
                //NewDecPara *para = reinterpret_cast<NewDecPara *>(opcmd->para.get());
                hasNewDec = true;

            }
            break;
            case OpType::DecCtrl:
                hasCtrlCmd = true;
                break;
            case OpType::OsdCtrl:
                hasCtrlCmd = true;
                break;
            case OpType::DispChCtrl:
                hasCtrlCmd = true;
                break;
            case OpType::NewVpp:
                break;
            default:
                throw(PipelineException(CmdsError::UnknownCmd));
                break;
        }
    }


    if (hasNewDec || hasNewVo) {
        res.isSetupCmd = true;
        if (hasCtrlCmd)
            throw(PipelineException(CmdsError::MixedSetupAndCtrl));
    }

    if (hasCtrlCmd && (mState == PipelineState::Uninitialize)) {
        throw(PipelineException(CmdsError::Uninitialized));
    }

    if ((hasNewVo && !hasDispCh))
        throw(PipelineException(CmdsError::DanglingNodes));

    //1st Set up commands must specify video output and display channel
    if ((mState == PipelineState::Uninitialize) && !hasDispCh && !hasNewVo)
        throw(PipelineException(CmdsError::DanglingNodes));

    return 0;
}


int PipelineManager::processSetupCmds(OperateCmds &cmds, int targetVideoLayerId) {
    //Store the state changes commands and process them after all the newxx commands are processed.
    //vector<Cmd> stateChanges;

    //create the map of decode, pp and display
    vector<NodeId> newDecNodes;
    vector<NodeId> newPPNodes;
    vector<NodeId> newDispNodes;
    vector<NodeId> newDispStreamNodes;

    std::shared_ptr<NodeInfo> node;
    vector<tuple<NodeId, NodeId>> PPToDisp;

    //One command group only targets one video layer
    //If there is no newvl in the command group, it means the set up commands target
    //existing videolayer whose id was specified in the ctrl command
    int videolayerId = targetVideoLayerId;
    bool targetExistingVL = false;
    int displayid = -1;
    int videoLayerFPS = 30; 

    if (videolayerId >= 0) {
        targetExistingVL = true;
        info("SVET app: {} current commands target exisitng video layer {}", __func__, targetVideoLayerId);
    }
    else {
        info("SVET app: {} process a group of commands", __func__);
    }

    for (auto &opcmd : cmds) {
        node.reset(new NodeInfo);
        OpType type = opcmd->type;
        switch (type) {
            case OpType::NewVideoLayer:
            {
                NewVideoLayerPara *para = reinterpret_cast<NewVideoLayerPara *>(opcmd->para.get());
                node->id.id = para->id;
                node->id.devId = 0;
                node->id.type = VPPNodeType::VideOutput;
                node->info = opcmd->para;

                if (mPipeline.getNodeInfo(node->id) != nullptr) {
                    throw(PipelineException(CmdsError::DuplicatedId));
                    break;
                }
                mPipeline.addNodeInfo(node);
                newDispNodes.push_back(node->id);
                videolayerId = node->id.id;
                displayid = para->dispid;
                debug("SVET app: {} Set taraget video layer id to {} with display id {}",
                      __func__, videolayerId, displayid);
               
            }
            break;
            case OpType::DispCH:
            {
                DispStreamPara *para = reinterpret_cast<DispStreamPara *>(opcmd->para.get());
                node->id.id = para->id;
                node->id.devId = para->videoLayer; //TBD: validate the videoLayer
                node->id.type = VPPNodeType::DispCh;
                node->info = opcmd->para;

                mPipeline.addNodeInfo(node);
                newDispStreamNodes.push_back(node->id);
                if (videolayerId < 0) {
                    videolayerId = para->videoLayer;
                    debug("SVET app: {} Set taraget video layer id to {}", __func__, videolayerId);
                }
                // set ContextId
#ifdef VPPSDK_DEC
               int sts = VPP_SYS_SetContextId(para->videoLayer);
               debug("SVET app: {} set SetContextId id is {}",__func__, para->videoLayer);
#endif
            }
            break;
            case OpType::NewDec:
            {
                NewDecPara *para = reinterpret_cast<NewDecPara *>(opcmd->para.get());
                node->id.id = para->id;
                node->id.devId = 0;
                node->id.type = VPPNodeType::Decode;

                if (mPipeline.getNodeInfo(node->id) != nullptr) {
                    throw(PipelineException(CmdsError::DuplicatedId));
                    break;
                }

                node->info = opcmd->para;
                debug("decode input {}", para->input);
                NodeId sinkid;
                string sinkname = para->sink;
                if (sinkname.rfind(VideoPipelineInfo::SINK_NAME_DISP) == 0) {
                    sinkid.type = VPPNodeType::DispCh;
                    string sinkidstr = sinkname.substr(VideoPipelineInfo::SINK_NAME_DISP.size());
                    sinkid.id = std::stoi(sinkidstr);
                    sinkid.devId = videolayerId;
                    //when SFC is enabled and decW/decH aren't set, use the display channel output size instead
                    if (para->sfcEnable && (para->decW < 1 || para->decH < 1)) {
                        auto dispchInfo = mPipeline.getNodeInfo(sinkid);
                        if (dispchInfo) {
                            DispStreamPara *dispchpara = reinterpret_cast<DispStreamPara *>(dispchInfo->info.get());
                            if (dispchpara->w < 1 || dispchpara->h < 1) {
                                error("SVET app: {} decode {}: sfc is enabled, W/H not set. Invalid display channel ({}, {}) size {}x{}",
                                      __func__, para->id, sinkid.devId, sinkid.id, dispchpara->w, dispchpara->h);
                                throw(PipelineException(CmdsError::InvalidParameter));
                            }
                            info("SVET app: {} decode {}: sfc is enabled and W/H not set. will use display channel ({}, {}) output size {}x{}",
                                 __func__, para->id, sinkid.devId, sinkid.id, dispchpara->w, dispchpara->h);
                            para->decW = dispchpara->w;
                            para->decH = dispchpara->h;
                        } else {
                            error("SVET app: {} decode {}: sfc is enabled, W/H not set. Invalid display channel id: ({}, {})",
                                  __func__, para->id, sinkid.devId, sinkid.id);
                            throw(PipelineException(CmdsError::InvalidParameter));
                        }
                    }
                } else if (sinkname.rfind(VideoPipelineInfo::SINK_NAME_PP) == 0) {
                    sinkid.type = VPPNodeType::PP;
                    string sinkidstr = sinkname.substr(VideoPipelineInfo::SINK_NAME_PP.size());
                    sinkid.devId = -1;
                    sinkid.id = std::stoi(sinkidstr);
                } else {
                    error("SVET app: {} sink name {} is not supported", __func__, sinkname);
                    throw(PipelineException(CmdsError::DanglingNodes));
                    break;
                }

                node->sink.push_back(sinkid);
                mPipeline.addNodeInfo(node);
                newDecNodes.push_back(node->id);
            }
            break;
            case OpType::NewVpp:
            {
                PostProcessPara *para = reinterpret_cast<PostProcessPara *>(opcmd->para.get());
                node->id.id = para->id;
                node->id.devId = -1;
                node->id.type = VPPNodeType::PP;

                if (mPipeline.getNodeInfo(node->id) != nullptr) {
                    throw(PipelineException(CmdsError::DuplicatedId));
                    break;
                }

                node->info = opcmd->para;

                for (int i = 0; i < para->OutputParas.size(); i++) {
                    NodeId sinkid;
                    auto sinkname = para->OutputParas[i]->sink;
                    //For alpha, PP can only connect to display
                    if (sinkname.rfind(VideoPipelineInfo::SINK_NAME_DISP) == 0) {
                        sinkid.type = VPPNodeType::DispCh;
                        string sinkidstr = sinkname.substr(VideoPipelineInfo::SINK_NAME_DISP.size());
                        sinkid.id = std::stoi(sinkidstr);
                        sinkid.devId = 0;
                        node->sink.push_back(sinkid);
                        NodeId streamid = node->id;
                        if (videolayerId >= 0) {
                            sinkid.devId = videolayerId;
                        } else {
                            warn("SVET app: {} Target video layer not set, use 0", __func__);
                            sinkid.devId = 0;
                        }

                        PPToDisp.push_back({streamid, sinkid});
                    } else {
                        //TBD
                        error("SVET app: {} unsupported sink name {}", __func__, sinkname);
                        throw(PipelineException(CmdsError::DanglingNodes));
                        break;
                    }
                }
                mPipeline.addNodeInfo(node);
                newPPNodes.push_back(node->id);
                break;
            }
            default:
                cout<<"Command type "<<(int)type<<" is not supported"<<endl;
                break;
        }
    }

    if (newDispNodes.size() > 1) {
        warn("SVET app: {} newvl command. only one newvl command allowed in one commands group!", newDispNodes.size());
    }

    //create video output node
    for ( auto &dispOut : newDispNodes ) {
        NodeInfo::Ptr info = mPipeline.getNodeInfo(dispOut);
        if (!info) {
            error("SVET app: can't find display with video layer id {}", dispOut.id);
            continue;
        }
        NewVideoLayerPara *para = reinterpret_cast<NewVideoLayerPara *>(info->info.get());
        int res = createDisplayOutNode(para);
        if (res < 0) {
            mPipeline.deleteNodeInfo(dispOut);
            break;
        }
        videoLayerFPS = para->fps; //use video layer composition fps for display stream frame rate.
    }

    //Stop video layer before adding new display stream
    if (targetExistingVL) {
        // setVideoLayerState(videolayerId, PipelineState::Stop);
        NodeId id;
        id.type = VPPNodeType::VideOutput;
        id.devId = 0;
        id.id = videolayerId;

        NodeInfo::Ptr info = mPipeline.getNodeInfo(id);
        if (info){
             NewVideoLayerPara *para = reinterpret_cast<NewVideoLayerPara *>(info->info.get());
             if (para) {
                videoLayerFPS = para->fps;
                debug("SVET app: {} Target videolayer fps:{}", __func__, videoLayerFPS);
             }
             else {
                warn("SVET app: {} can't find videolayer({}) fps information", __func__, videolayerId);
             }
        }
        else {
            error("SVET app: can't find display with video layer id {}", id.id);            ;
        }
    }

    //create display streams/channels
    for (auto &dispStream : newDispStreamNodes) {
        NodeInfo::Ptr info = mPipeline.getNodeInfo(dispStream);
        int res = createDisplayChannelNode(info, videoLayerFPS);
        if (res < 0 ) {
            mPipeline.deleteNodeInfo(dispStream);
            break;
        }
    }

    //create decode source and record if it's bind to pp or display
    NodesTupleVector  decToDisp;
    NodesTupleVector  decToPP;

    auto decIt = newDecNodes.begin();
    while (decIt != newDecNodes.end()) {
        auto decId = *decIt;
        NodeInfo::Ptr decNode = mPipeline.getNodeInfo(decId);
        if (!decNode) {
            cout<<"Dec node with id "<<decId.id<<" not found!"<<endl;
            decIt = newDecNodes.erase(decIt);
            continue;
        }
        int r = createDecodeNode(decNode);
        if (r < 0) {
            error("SVET app: create decode {} failed. Remove it from pipeline", decId.id);
            mPipeline.deleteNodeInfo(decId);
            decIt = newDecNodes.erase(decIt);
            continue;
        }

        if (decNode->sink.size() > 0) {
            NodeId id = decNode->sink[0];
            if (id.type == VPPNodeType::PP) {
                decToPP.push_back( {decNode->id, id});
            } else if (id.type == VPPNodeType::DispCh)  {
                decToDisp.push_back( {decNode->id, id});
            } else {
                //TBD Handle errors
            }
        }
        decIt++;
    }

    //Create PP streams
    for ( auto &nodeid : newPPNodes) {
        NodeInfo::Ptr info = mPipeline.getNodeInfo(nodeid);
        if (!info) {
            error("SVET app: can't find PP node with id {}:{}", nodeid.devId,nodeid.id);
            continue;
        }
        PostProcessPara *para = reinterpret_cast< PostProcessPara *>(info->info.get());
        int r = Postprocess::validatePPStream(para);
        if (r != 0) {
            mPipeline.deleteNodeInfo(nodeid);
            continue;
        }
        r = Postprocess::createPPStream(para);
        if (r != 0 ) {
            mPipeline.deleteNodeInfo(nodeid);
            continue;
        }
    }

    //Bind dec to pp
    processNodesBinding(decToPP);

    //Bind dec to disp
    processNodesBinding(decToDisp);

    //Bind PP to disp
    processNodesBinding(PPToDisp);

    //start new decode source
    if (mState == PipelineState::Uninitialize)
        mState = PipelineState::Ready;

        //start videolayer
    if (!targetExistingVL) {
        setVideoLayerState(videolayerId, PipelineState::Play);
    }
    
    if (newPPNodes.size() > 0) {
        std::set<VPPNodeType> nodeTypes;
        nodeTypes.insert(VPPNodeType::PP);
        NodesSetPtr ptr;
        ptr = std::make_shared<NodesSet>(newPPNodes.begin(), newPPNodes.end());        
        changeNodesState(nodeTypes, PipelineState::Play, ptr);

    }

    int res = 0;
    for (auto &decId : newDecNodes) {
        debug("SVET app: {} new dec id {}", __func__, decId.id);
        res = startDecoding(decId);
        if (res != 0) {
            error("SVET app: {} decoder {} fails. Remove it from pipeline", __func__, int(decId.id));
            mPipeline.deleteNodeInfo(decId);
        }
    }

    //If the message thread hasn't been created, create it.
    startLoop();
    return 0;
}

int PipelineManager::createDecodeNode(NodeInfo::Ptr decInfo) {
    NewDecPara *decPara = reinterpret_cast<NewDecPara *>(decInfo->info.get());
    //If it's local video clip, check if file exists.
    if ((decPara->input.rfind(Decode::RTSP_URL_PREFIX) != 0)
        && (!isFileGood(decPara->input.c_str()))) {
        error("SVET app: {} decode input file {} doesn't exist", __func__,decPara->input);
        return SVET_ERR_FILE_NOT_EXIST;
    }
    //create decode source thread to read video stream from RTSP or local file
    Decode::Ptr decoder = std::make_shared<Decode>();
    int res = decoder->init(decPara);
    if (res < 0)
        return res;
    if (mDecoders.find(decPara->id) != mDecoders.end()) {
        warn("SVET app: {} duplicated decoder id {}!", __func__, decPara->id);
        return SVET_ERR_DUPLICATED_ID;
    }

    mDecoders[decPara->id] = decoder;
    return 0;
}


int PipelineManager::startDecoding(NodeId decId) {
    auto dec = mDecoders.find(decId.id);
    if (dec != mDecoders.end()) {
        debug("SVET app: {} will start decode {}", __func__ , decId.id);
        int res = dec->second->start();
        return res;
    } else {
        warn("SVET app: {} decode({}) instance not found!!",__func__, decId.id);
        return SVET_ERR_DUPLICATED_ID;
    }
}


int PipelineManager::bindNodes(NodeId source, NodeId sink) {
    //Call VPP SDK API to bind nodes

#ifdef VPPSDK_DISP
    VPP_StreamIdentifier idl, idr;
    idl.NodeType = VideoPipelineInfo::toVPPNodeType(source.type);
    idr.NodeType = VideoPipelineInfo::toVPPNodeType(sink.type);
    idl.StreamId = source.id;
    idr.StreamId = sink.id;

    if ((source.type == VPPNodeType::Decode ) || (source.type == VPPNodeType::PP )) {
        idl.DeviceId = VPP_ID_NOT_APPLICABLE; //igore decode node device id
    }
    else {
        idl.DeviceId = source.devId;
    }

    if ((sink.type == VPPNodeType::Decode ) || (sink.type == VPPNodeType::PP )) {
        idr.DeviceId = VPP_ID_NOT_APPLICABLE; //igore decode node device id
    }
    else {
        idr.DeviceId = sink.devId;
    }

    debug("SVET app: call VPP_SYS_Bind(({}, {}, {}), ({}, {}, {})) in {}",
        idl.NodeType, idl.DeviceId, idl.StreamId, 
        idr.NodeType, idr.DeviceId, idr.StreamId, __func__);
#else
    debug("SVET app: call VPP_SYS_Bind(({}, {}, {}), ({}, {}, {})) in ()",
          VideoPipelineInfo::getTypeString(source.type), source.devId, source.id,
          VideoPipelineInfo::getTypeString(sink.type), sink.devId,sink.id, __func__);

 #endif

#ifdef VPPSDK_DISP
    VPP_STATUS sts = VPP_SYS_Bind(idl, idr);
    if (sts != VPP_STATUS_SUCCESS) {
        throw(PipelineException(CmdsError::VPPSDK_FAIL));
    }

#endif
    return 0;
}


int PipelineManager::processDecodeCtrlCmds(DecCtrlPara *para) {
    NodeId decId;
    decId.id = para->decid;
    decId.type = VPPNodeType::Decode;
    decId.devId = 0;

    if (mPipeline.getNodeInfo(decId) == nullptr) {
        throw(PipelineException(CmdsError::InvalidId));
        return 0;
    }

    switch (para->cmd) {
        case DecCtrlCMD::Remove: {
            removeDecode(decId);
        }
        break;
        case DecCtrlCMD::AddPic: {
            addUserPicToDecode(decId, para);
        }
            break;
        case DecCtrlCMD::RemovePic: {
            removeUserPicFromDecode(decId);
        }
            break;
        default:
            break;

    }
    return 0;
}

int PipelineManager::processPPCtrlCmds(OperateCmds &cmd) {
    return 0;
}

int PipelineManager::processOsdCtrlCmds(OSDCtrlPara *para) {
   
    switch (para->cmd) {
        case OSDCtrlCMD::Add: {
#ifdef VPPSDK_DEC
            int sts = OSD::createOSDArea(para);
            if (sts==VPP_STATUS_SUCCESS)
            {
                mOSD.push_back(para->id);
                debug("SVET app: CreateOSDArea id {} successfully.", para->id);
            }
            else {
                error("SVET app: CreateOSDArea id {} fail.", para->id);
            }
            OSD::attachOSDToStream(para);
#endif
        }
        break;
        case OSDCtrlCMD::SetAttrs: {
            OSD::setOSDAreaAttrs(para);
            OSD::setOSDAreaAttachAttrs(para);
        }
            break;
        case OSDCtrlCMD::Remove: {
            OSD::detachOSDFromStream(para);
        }
            break;
        default:
            break;

    }
    return 0;
}

void PipelineManager::startLoop() {
    if (!mThread) {
        if (mState != PipelineState::Ready) {
            error("SVET app: {} expect state({}), but current state is {}", __func__, int(PipelineState::Ready),
                int(mState));
            return;
        }
        mThread = std::make_shared<std::thread>(&PipelineManager::loop, this);
        mState = PipelineState::Play;
    }
}

void PipelineManager::stopLoop() {
    PipelineMessage msg;
    msg.type = MessageType::MsgThreadStop;
    mMsgQueue.push_back(msg);
    if (mThread)
        mThread->join();
}

int PipelineManager::processDispChCtrlCmds(DispChCtrlPara *para) {
    int res = DisplayStream::processControlCmd(para, mPipeline);
    return res;
}


int PipelineManager::stopSinkonChain(NodeId id, NodeId &displaySink) {
#ifdef VPPSDK_DEC
    VPP_StreamIdentifier srcId = VideoPipelineInfo::nodeTypeToStreamId(id);
    //display node doesn't have sink
    if (srcId.NodeType == VPP_NODE_TYPE::NODE_TYPE_DISPLAY || (srcId.DeviceId < 0 && srcId.StreamId < 0)) 
        return 0;

    VPP_Bind_Sink sink;

    debug("SVET app: call VPP_SYS_GetBindingSink( (, {})) ", int(srcId.NodeType),
          int(srcId.DeviceId), int(srcId.StreamId));
    VPP_STATUS sts = VPP_SYS_GetBindingSink(srcId, &sink);
    CHK_VPPSDK_RET(sts, "VPP_SYS_GetBindingSink");
    if (sink.Num < 1) {
        warn("SVET app: {} no sink bind to node ({}, {}, {})", __func__, int(srcId.NodeType),
          int(srcId.DeviceId), int(srcId.StreamId));
        return 0;
    }

    //Stop all the sinks
    std::set<VPPNodeType> nodeTypes;
    NodesSetPtr ptr = std::make_shared<NodesSet>();
    int res = 0;

    for (int i = 0; i < sink.Num; i++) {
        switch( sink.StreamIdArr[i].NodeType) {
            case VPP_NODE_TYPE::NODE_TYPE_DISPLAY:
            {
                NodeId nodeId = VideoPipelineInfo::streamIdToNodeId(sink.StreamIdArr[i]);
                if (nodeId.type == VPPNodeType::Max) {
                    warn("SVET app: {} line {} : unknown node type", __func__, __LINE__);
                    break;
                }
                nodeTypes.clear();
                nodeTypes.insert(VPPNodeType::VideOutput);

                NodeId nodeVideoLayer;
                nodeVideoLayer.type = VPPNodeType::VideOutput;
                nodeVideoLayer.devId = 0;
                nodeVideoLayer.id = nodeId.devId;
                ptr->clear();
                ptr->insert(nodeVideoLayer);
                //Ignore the return value
                changeNodesState(nodeTypes, PipelineState::Stop, ptr);
                displaySink = nodeVideoLayer;         
            }
            break;
            case VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM:
            {
                NodeId ppId = VideoPipelineInfo::streamIdToNodeId(sink.StreamIdArr[i]);

                nodeTypes.clear();
                nodeTypes.insert(VPPNodeType::PP);

                ptr->clear();
                ptr->insert(ppId);
                //Ignore the return value
                changeNodesState(nodeTypes, PipelineState::Stop, ptr); 
                NodeId videoLayerId;
                stopSinkonChain(ppId, videoLayerId);
                break;
            }
            default:
                warn("SVET app: {} line {}: unexpected VPP_NODE_TYPE {}", __func__, __LINE__,
                int(sink.StreamIdArr[i].NodeType));
            break;
                
        }
    }
#endif
    return 0;
}


int PipelineManager::removeDecode(NodeId nodeId) {
    auto decode = mDecoders.find(nodeId.id);

    if (decode == mDecoders.end()) {
        error("SVET app: {} decoder id {} is invalide", __func__, nodeId.id);
        return SVET_ERR_INVALID_ID;
    }
    debug("SVET app: {} will stop and destroy decode with id {}", __func__, nodeId.id);
    decode->second->stop();

    NodeId videoLayer; 
    // stopSinkonChain(nodeId, videoLayer);

    std::set<VPPNodeType> nodeTypes;
    NodesSetPtr ptr = std::make_shared<NodesSet>();

    NodeId sinkId;
    decode->second->unbindFromSink(sinkId);

    //Remove sink node
    nodeTypes.insert(sinkId.type);
    ptr->insert(sinkId);
    changeNodesState(nodeTypes, PipelineState::Destroy, ptr);  
    
    //Set videolayer to play state
    nodeTypes.clear();
    ptr->clear();
    nodeTypes.insert(VPPNodeType::VideOutput);
    ptr->insert(videoLayer); 
    // changeNodesState(nodeTypes, PipelineState::Play, ptr);   

    decode->second->destroy();

    mDecoders.erase(nodeId.id);
    mPipeline.deleteNodeInfo(nodeId);
    mPipeline.deleteNodeInfo(sinkId);
    return 0;
}

int PipelineManager::addUserPicToDecode(NodeId nodeId, DecCtrlPara *para) {
    auto decode = mDecoders.find(nodeId.id);

    if (decode == mDecoders.end()) {
        error("SVET app: {} decoder id {} is invalide", __func__, nodeId.id);
        return SVET_ERR_INVALID_ID;
    }

    FILE *file = fopen(para->picFilename.c_str(), "r");
    if (!file) {
        error("SVET app: {} open file {} failed!", __func__, para->picFilename);
        return SVET_ERR_FILE_NOT_EXIST;
    }

    size_t expectedSize = para->w * para->h * 3 / 2;
    void *data = malloc(expectedSize);
    if (!data) {
        error("SVET app: {} malloc with size {} failed", __func__, expectedSize);
        fclose(file);
        return SVET_ERR_MEMORY_ALLOC_FAIL;
    }
    auto datasize = fread(data, 1, expectedSize, file);

    if (datasize != expectedSize) {
        error("SVET app: {} exptected user picture file size {}, read size {} ", __func__, expectedSize, datasize);
        free(data);
        fclose(file);
        return SVET_ERR_INVALID_PARA;
    }
    bool flagInstant = para->instant;
    //Stop decoder before enabling user picture
    decode->second->stop();
    int res =  decode->second->enableUserPic(para->w, para->h, true, data);
    decode->second->start();
    free(data);
    fclose(file);
    return res;
}

int PipelineManager::removeUserPicFromDecode(NodeId nodeId) {
    auto decode = mDecoders.find(nodeId.id);

    if (decode == mDecoders.end()) {
        error("SVET app: {} decoder id {} is invalide", __func__, nodeId.id);
        return SVET_ERR_INVALID_ID;
    }

    return decode->second->disableUserPic();
}

int PipelineManager::createDisplayOutNode(NewVideoLayerPara *para) {
    //Call VPP SDK API to create display out
    DisplayDevice::Ptr dispDev;

    if (mDisplayDevices.find(para->dispid) == mDisplayDevices.end()) {
        dispDev = std::make_shared<DisplayDevice>();
        int res = dispDev->Init(para->dispid);
        if (res < 0) {
            return res;
        }
        mDisplayDevices[para->id] = dispDev;
    }
    else {
        debug("SVET app: Display device ({}) already created", para->dispid);
        dispDev = mDisplayDevices[para->dispid];
    }

    //If SetDisplayAttributes fails, the display mode will be set with the highest resolution
    dispDev->SetDisplayAttributes(para->resW, para->resH, para->refresh);
    unsigned int pbsize;
    switch (static_cast<VideoFrameType>(para->format)) {
        case VideoFrameType::FOURCC_NV12:
            pbsize = para->resW * para->resH * 3 / 2;
            break;
        case VideoFrameType::FOURCC_RGB4:
            pbsize = para->resW * para->resH * 4;
            break;
        default:
            error("SVET app: {0} not support pixel format {1:x}", __func__, para->format);
            return SVET_ERR_PIXELFORMMAT_UNSUPPORT;
            break;
    }

    VideoLayerInfo attr = {{0, 0, (para->resW), (para->resH)},
                           pbsize, para->format, para->refresh, para->fps, para->tilenum };
    int sts = dispDev->CreateVideoLayer(attr, para->id);
    return sts;
}

int PipelineManager::startVideoLayer(int dispid) {
    //Call VPP SDK API to create display out
    DisplayDevice::Ptr dispDev;

    if (mDisplayDevices.find(dispid) == mDisplayDevices.end()) {
        error("SVET app: {}: display id {} not found", __func__, dispid);
        throw(PipelineException(CmdsError::InvalidId));
    } else {
        debug("SVET app: {}: start display device ({})",
              __func__, dispid);
        dispDev = mDisplayDevices[dispid];
        dispDev->Start();
    }
    return 0;
}

bool PipelineManager::isIncludedinSet(NodeId id, NodesSetPtr ptr) {
    //If ptr is null, no limitation on NodeId
    if (!ptr) {
        return true;
    }

    return (ptr->find(id) != ptr->end());

}
int PipelineManager::changeNodesState(std::set<VPPNodeType> &nodeTypes, PipelineState state, NodesSetPtr ptr) {

    if (nodeTypes.find(VPPNodeType::Decode) != nodeTypes.end()) {
         
        for (auto &dec : mDecoders) {
            NodeId id;
            id.type = VPPNodeType::Decode;
            id.devId = 0;
            id.id = dec.second->getId();

            if (!isIncludedinSet(id, ptr)) {
                continue;
            }

            switch (state) {
                case PipelineState::Stop:
                    dec.second->stop();
                    break;
                case PipelineState::Destroy:
                    dec.second->destroy();
                    break;
                case PipelineState::Unbind:
                {
                    NodeId sinkId;
                    dec.second->unbindFromSink(sinkId);
                }
                    break;
                default:
                    error("SVET app: {} decode unimplemented state: {}", __func__, (int)state);
                    break;
            }

        }
    }

    if (nodeTypes.find(VPPNodeType::PP) != nodeTypes.end()) {
        
        auto & nodes = mPipeline.getNodeMap(VPPNodeType::PP);
        for (auto &ppnode : nodes) {            
            NodeId id = ppnode.first;

            if (!isIncludedinSet(id, ptr)) {
                continue;
            }
            
            NodeInfo::Ptr info = mPipeline.getNodeInfo(ppnode.first);
            if (!info) {
                error("SVET app: {} can't find PP node with id {}:{}", __func__, ppnode.first.devId, ppnode.first.id);
                continue;
            }
            PostProcessPara *para = reinterpret_cast< PostProcessPara *>(info->info.get());
            switch (state) {
                    case PipelineState::Play:
                        Postprocess::startPPStream(para);
                        break;  
                    case PipelineState::Stop:
                        Postprocess::stopPPStream(para);
                        break;    
                    case PipelineState::Destroy:
                        Postprocess::destroyPPStream(para);
                        break;
                    case PipelineState::Unbind:
                        Postprocess::unbindPPStream(para);
                        break;
                    default:
                        error("SVET app: {} PP unimplemented state: {}", __func__, (int)state);
                        break;
            }
        }
    }

    if (nodeTypes.find(VPPNodeType::DispCh) != nodeTypes.end()) {
         auto & nodes = mPipeline.getNodeMap(VPPNodeType::DispCh);
        for (auto &node : nodes) {

            if (!isIncludedinSet(node.first, ptr)) {
                continue;
            }
            NodeInfo::Ptr info = mPipeline.getNodeInfo(node.first);
            if (!info) {
                error("SVET app: {} can't find PP node with id {}:{}", __func__, node.first.devId, node.first.id);
                continue;
            }

            switch (state) { 
                    case PipelineState::Destroy:
                        DisplayStream::destroy(info->id.id, info->id.devId);
                        break;
                    default:
                        error("SVET app: {} display channel unimplemented state: {}", __func__, (int)state);
                        break;
            }
        }
        
    }

    if (nodeTypes.find(VPPNodeType::VideOutput ) != nodeTypes.end()) {

        if (!ptr) {
            for (auto &displayDev : mDisplayDevices) {
                switch (state) {
                        case PipelineState::Stop:
                            displayDev.second->Stop();
                            break;
                        case PipelineState::Destroy:
                            displayDev.second->Destroy();
                            break;
                        default:
                            error("SVET app: {} display device unimplemented state: {}", __func__, (int)state);
                            break;
                }
            }
        } else {
            
            bool match = false;
            int videoLayer;
            for (auto &displayDev : mDisplayDevices) {
                for (auto &videolayer : displayDev.second->mVideoLayers) {
                    NodeId id;
                    id.type = VPPNodeType::VideOutput;
                    id.devId = 0;
                    id.id = videolayer.first;
                        
                    if (!isIncludedinSet(id, ptr)) {
                        match = false;
                    }
                    else {
                        videoLayer = id.id;
                        match = true;
                    }
                }

                if (!match) {
                    continue;
                }
            switch (state) { 
                case PipelineState::Stop:
                    displayDev.second->Stop(videoLayer);
                    break; 
                case PipelineState::Play:
                    displayDev.second->Start(videoLayer);
                    if (displayDev.second->getDispState() != NodeState::Play) {
                        displayDev.second->StartDisp();
                    }
                    break;
                default:
                    warn("SVET app: {} line {} unexpected video layer target state {}",
                    __func__, __LINE__, int(state));
                    break;
                } 
            }
        }
    }


    return 0;
}

int PipelineManager::destroyAllOSDArea(){
    for (int i = 0; i < mOSD.size(); i++) {
        debug("SVET app: {} call VPP_OSD_DestroyArea id is {}", __func__, mOSD[i]);
		OSD::destroyOSDArea(mOSD[i]);
	}
    return 0;
}


int PipelineManager::createDisplayChannelNode(NodeInfo::Ptr nodeInfo, int fps) {
    DispStreamPara * para = reinterpret_cast<DispStreamPara *>(nodeInfo->info.get());
    int res = DisplayStream::create(para, fps);
    return res;
}

void PipelineManager::loop() {
    while (true) {
        PipelineMessage msg = mMsgQueue.front();
        switch (msg.type) {
            case MessageType::DecodeStop: {


            }
            break;
            case MessageType::MsgThreadStop: {
                info("SVET app: message thread stops");
                std::set<VPPNodeType> nodeTypes;
                nodeTypes.insert(VPPNodeType::Decode);
                nodeTypes.insert(VPPNodeType::PP);                
                nodeTypes.insert(VPPNodeType::VideOutput);
                //display stream doens't have stop API
                changeNodesState(nodeTypes, PipelineState::Stop);

                std::set<VPPNodeType> nodesToUnbind;
                nodesToUnbind.insert(VPPNodeType::Decode);
                nodesToUnbind.insert(VPPNodeType::PP);
                changeNodesState(nodesToUnbind, PipelineState::Unbind);
                
                nodeTypes.insert(VPPNodeType::DispCh);
                // destroy osd
                destroyAllOSDArea();
                changeNodesState(nodeTypes, PipelineState::Destroy);
                return;
            }
                break;
            case MessageType::Unknown:
            default: {
                warn("SVET app: {} Receive unknown message, ignore");
            }
                break;
        }
        
    }
    return;
}

int PipelineManager::processNodesBinding(NodesTupleVector &nodesTupleVector) {
    for (auto &nodes : nodesTupleVector) {
        auto &nodel =  std::get<0>(nodes);
        auto &noder = std::get<1>(nodes);
        info("SVET app: {} bind {} node {}:{} to {} node {}:{}", __func__,
             VideoPipelineInfo::getTypeString(nodel.type), nodel.devId, nodel.id,
             VideoPipelineInfo::getTypeString(noder.type), noder.devId, noder.id);
        int res = bindNodes(nodel, noder);
        if (res != 0)
            return res;
    }
    return 0;
}

int PipelineManager::setVideoLayerState(int videoLayerId, PipelineState state) {
    std::set<VPPNodeType> nodeTypes;
    NodesSetPtr ptr = std::make_shared<NodesSet>();
    int res = 0;

    NodeId nodeVideoLayer;
    nodeVideoLayer.type = VPPNodeType::VideOutput;
    nodeVideoLayer.devId = 0;
    nodeVideoLayer.id = videoLayerId;
    
    nodeTypes.insert(VPPNodeType::VideOutput);
    ptr->insert(nodeVideoLayer);
    
    return changeNodesState(nodeTypes, state, ptr);
}


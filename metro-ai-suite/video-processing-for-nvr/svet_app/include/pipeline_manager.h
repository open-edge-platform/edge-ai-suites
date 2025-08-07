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

#include <vector>
#include <thread>
#include <set>
#include <tuple>
#include "video_pipeline.h"
#include "svet_cmd.h"
#include "display_stream.h"
#include "display_device.h"
#include "sample_queue.h"
#include "decode.h"
using std::vector;


#define PIPELINE_ERROR_NONE 0
#define PIPELINE_ERROR_INVAlID_PARAMETER -1
#define PIPELINE_ERROR_UNLINKED -2

namespace SVET_APP {

    enum class PipelineState : uint {
        Uninitialize,
        Ready,
        Play,
        Stop,
        Unbind,
        Destroy
    };

    struct CmdsValidateResults {
        bool isSetupCmd;
    };

    using NodesTupleVector =  vector<std::tuple<NodeId, NodeId>>;
    using NodesSet= std::set<NodeId>;
    using NodesSetPtr = shared_ptr<NodesSet>;
    class PipelineManager {

    public:
        PipelineManager();

        virtual ~PipelineManager();

        void startLoop();

        void stopLoop();

        int processCmds(OperateCmds &cmds, CtrlPara &ctrlCmd);

    private:
        int validateCmds(OperateCmds &cmds, CmdsValidateResults &res);

        void printCmdErrors(const char *errorMsg);

        //If the videoLayerId is not -1, it means the new decode or pp will connect to existing video layer
        int processSetupCmds(OperateCmds &cmds, int videoLayerId = -1);

        int changeState(OperateCmds &cmds, CtrlPara &ctrlCmd);

        int createDecodeNode(NodeInfo::Ptr);

        int startDecoding(NodeId decId);

        int createDisplayOutNode(NewVideoLayerPara *para);

        int startVideoLayer(int dispid);

        bool isIncludedinSet(NodeId id, NodesSetPtr ptr);
        //Change the nodes with specified types to a given state. If ptr isn't null, ptr will contains the node Ids
        int changeNodesState(std::set<VPPNodeType> &nodeTypes, PipelineState state, NodesSetPtr ptr = nullptr);

        int createDisplayChannelNode(NodeInfo::Ptr nodeInfo, int fps);

        int bindNodes(NodeId source, NodeId sink);

        int processNodesBinding(NodesTupleVector &nodesTupleVector);

        int processDecodeCtrlCmds(DecCtrlPara *para);

        int processDispChCtrlCmds(DispChCtrlPara *para);

        int processPPCtrlCmds(OperateCmds &cmd);

        int processOsdCtrlCmds(OSDCtrlPara *para);

        int stopSinkonChain(NodeId srcId, NodeId &displaySink);

        int startSinkonChain(NodeId srcId);

        int removeDecode(NodeId nodeId);

        int addUserPicToDecode(NodeId nodeId, DecCtrlPara *para);

        int removeUserPicFromDecode(NodeId nodeId);

        void loop();

        int destroyAllOSDArea();

        int setVideoLayerState(int videoLayerId, PipelineState state);

        VideoPipelineInfo mPipeline;
        std::map<int, DisplayDevice::Ptr> mDisplayDevices;
        std::map<int, Decode::Ptr> mDecoders;
        std::vector<int> mOSD;
        PipelineState mState;
        DisplayStream mDispCh;
        SampleQueue<PipelineMessage> mMsgQueue;
        std::shared_ptr<std::thread> mThread;

        bool mVppSDKInit;
    };
}




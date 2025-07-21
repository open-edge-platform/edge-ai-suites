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
// Created by dell on 2022/9/27.
//
#include <iostream>
#include "video_pipeline.h"
#include "spdlog/spdlog.h"
#include "svet_util.h"

using std::cout;
using std::endl;
using spdlog::error;
using spdlog::debug;
using spdlog::warn;
using namespace SVET_APP;

const string VideoPipelineInfo::SINK_NAME_DISP = "disp";
const string VideoPipelineInfo::SINK_NAME_PP = "pp";
VideoPipelineInfo::VideoPipelineInfo() {
    for (int i = 0; i < (uint)VPPNodeType::Max; i++) {
        mNodes.push_back(NodeMap());
    }
}

VideoPipelineInfo::~VideoPipelineInfo() {

}

#define NODE_TYPE_TO_STR(name) #name
const char *gNodeTypeStr[] {
        NODE_TYPE_TO_STR( Decode ),
        NODE_TYPE_TO_STR( PP ),
        NODE_TYPE_TO_STR( VideoOutput ),
        NODE_TYPE_TO_STR( DisCh ),
        NODE_TYPE_TO_STR( Max ),
};

const char * VideoPipelineInfo::getTypeString(VPPNodeType type) {
    if (type < VPPNodeType::Max) {
        return gNodeTypeStr[uint(type)];
    }
    else
    {
        return gNodeTypeStr[uint(VPPNodeType::Max)];
    }
}
int VideoPipelineInfo::deleteNodeInfo(NodeId id) {
    VPPNodeType type = id.type;
    if (type < VPPNodeType::Max) {
        auto &nodes = mNodes[(uint)type];
        nodes.erase(id);
    }
    return 0;
}

int VideoPipelineInfo::addNodeInfo(NodeInfo::Ptr nodeInfo) {
    VPPNodeType type = nodeInfo->id.type;
    if (getNodeInfo(nodeInfo->id) != nullptr) {
        error("The node id is already used by existing node ");
        return -1;
    }
    debug("SVET app: {} node map: insert ({}, {}, {}), sink size {} ",
          __func__, (uint)type, nodeInfo->id.devId, nodeInfo->id.id, nodeInfo->sink.size());

    if (type < VPPNodeType::Max) {
        auto &nodes = mNodes[(uint)type];
        nodes.insert({nodeInfo->id, nodeInfo});
    }
    return 0;
}

shared_ptr<NodeInfo> VideoPipelineInfo::getNodeInfo(const NodeId id) {
    VPPNodeType type = id.type;
    NodeInfo::Ptr nodePtr = nullptr;
    if (type < VPPNodeType::Max) {
        auto &nodes = mNodes[(uint)type];
        auto r = nodes.find(id);
        if (r != nodes.end()) {
            return r->second;
        }
    }
    return nullptr;
}

VideoPipelineInfo::NodeMap & VideoPipelineInfo::getNodeMap(VPPNodeType type) {
    auto &nodes = mNodes[(uint)type];
    return nodes;
}

#if defined(VPPSDK_DISP) || defined(VPPSDK_PP) || defined(VPPSDK_DEC)
VPP_NODE_TYPE VideoPipelineInfo::toVPPNodeType(VPPNodeType type) {
    switch (type) {
        case VPPNodeType::Decode:
            return NODE_TYPE_DECODE;
        case VPPNodeType::PP:
            return NODE_TYPE_POSTPROC_STREAM;
        case VPPNodeType::DispCh:
            return NODE_TYPE_DISPLAY;
        case VPPNodeType::VideOutput:
            return NODE_TYPE_DISPLAY;
        default:
            return NODE_TYPE_UNKNOWN;
    }
}

int VideoPipelineInfo::unbindFromSink(VPP_StreamIdentifier srcId, VPP_StreamIdentifier &sinkId) {
    VPP_Bind_Sink sink;
    debug("SVET app: call VPP_SYS_GetBindingSink( ({}, {}, {})) ", int(srcId.NodeType),
          int(srcId.DeviceId), int(srcId.StreamId));
    VPP_STATUS sts = VPP_SYS_GetBindingSink(srcId, &sink);
    CHK_VPPSDK_RET(sts, "VPP_SYS_GetBindingSink");

    if (sink.Num < 1) {
        warn("SVET app: {} no sink bind to node ({}, {}, {})", __func__, int(srcId.NodeType),
          int(srcId.DeviceId), int(srcId.StreamId));
        return 0;
    }
    sinkId = sink.StreamIdArr[0];
    
    debug("SVET app: call VPP_SYS_Unbind(({}, {}, {}), ({}, {}, {})", int(srcId.NodeType),
          int(srcId.DeviceId), int(srcId.StreamId), sink.StreamIdArr[0].NodeType,
        sink.StreamIdArr[0].DeviceId, sink.StreamIdArr[0].StreamId);
    sts = VPP_SYS_Unbind(srcId, sink.StreamIdArr[0]);
    CHK_VPPSDK_RET(sts, "VPP_SYS_Unbind");
    return 0;
}


VPP_StreamIdentifier VideoPipelineInfo::nodeTypeToStreamId(NodeId id) {
    VPP_StreamIdentifier vppId = {VPP_NODE_TYPE::NODE_TYPE_UNKNOWN, -1, -1};
    switch(id.type) {
        case VPPNodeType::Decode:
            vppId.NodeType = VPP_NODE_TYPE::NODE_TYPE_DECODE;
            vppId.DeviceId = VPP_ID_NOT_APPLICABLE;
            vppId.StreamId = id.id;
            break;
        case VPPNodeType::PP:
            vppId.NodeType = VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM;
            vppId.DeviceId = VPP_ID_NOT_APPLICABLE;
            vppId.StreamId = id.id;
            break;
        case VPPNodeType::DispCh:
            vppId.NodeType = VPP_NODE_TYPE::NODE_TYPE_DISPLAY;
            vppId.DeviceId = id.devId;
            vppId.StreamId = id.id;
            break;
        default:
            warn("SVET app: {} unknown Node type {}", __func__, int(id.type));
            break;

    }
    return vppId;
}



NodeId VideoPipelineInfo::streamIdToNodeId(VPP_StreamIdentifier vppId ) {
    NodeId id;
    id.type = VPPNodeType::Max;
    id.devId = 0;
    id.id = 0;
    switch(vppId.NodeType) {
        case VPP_NODE_TYPE::NODE_TYPE_DECODE:
            id.type = VPPNodeType::Decode;
            id.id = vppId.StreamId;
            break;
        case VPP_NODE_TYPE::NODE_TYPE_POSTPROC_STREAM:
            id.type = VPPNodeType::PP;
            id.id = vppId.StreamId;
            break;
        case VPP_NODE_TYPE::NODE_TYPE_DISPLAY:
            id.type = VPPNodeType::DispCh;
            id.devId = vppId.DeviceId;
            id.id = vppId.StreamId;
            break;
        default:
            warn("SVET app: {} unknown VPP type {}", __func__, int(vppId.NodeType));
            break;

    }
    return id;
}
#endif

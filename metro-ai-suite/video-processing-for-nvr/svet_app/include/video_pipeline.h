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

#pragma once

#include <map>
#include <vector>
#include <memory>
#include <string>

#if defined(VPPSDK_DISP) || defined(VPPSDK_PP) || defined(VPPSDK_DEC)
#include <vpp_common.h>
#include <vpp_system.h>
#endif
#include "svet_cmd.h"
using  std::vector;
using  std::map;
using  std::shared_ptr;
using  std::string;

namespace SVET_APP {
    enum class VPPNodeType : uint {
        Decode = 0,
        PP = 1,
        VideOutput = 2,
        DispCh = 3,
        Max = 4,
    };
    struct NodeId {
        NodeId() : type(VPPNodeType::Max), devId(-1), id(-1) {};
        VPPNodeType type;
        int devId; // 0~(2^8 - 1)
        int id;    // 0~(2^20 -1)
        friend bool operator< (const  NodeId &left, const  NodeId &right) {
            return ((((static_cast<uint>(left.type))<<28)  + (left.devId << 20) + (left.id)) < 
            (((static_cast<uint>(right.type))<<28)  + (right.devId << 20) + (right.id)));
        }
    };

    struct NodeInfo {
        using Ptr = shared_ptr<NodeInfo>;
        NodeId id;
        vector<NodeId> source;
        vector<NodeId> sink;
        std::shared_ptr<void> info;
    };

    enum class MessageType {
        Unknown,
        DecodeStop,
        MsgThreadStop
    };
    struct PipelineMessage {
        MessageType type;
        NodeId nodeId;
    };

    class VideoPipelineInfo {
    public:
        VideoPipelineInfo();

        virtual ~VideoPipelineInfo();

        static const char * getTypeString(VPPNodeType type);
#if defined(VPPSDK_DISP) || defined(VPPSDK_PP) || defined(VPPSDK_DEC)
        static VPP_NODE_TYPE toVPPNodeType(VPPNodeType type);
        static int unbindFromSink(VPP_StreamIdentifier srcId, VPP_StreamIdentifier &sinkId);
        static VPP_StreamIdentifier nodeTypeToStreamId(NodeId id);
        static NodeId streamIdToNodeId(VPP_StreamIdentifier vppId );
#endif

        shared_ptr<NodeInfo> getNodeInfo(const NodeId id);

        int addNodeInfo(shared_ptr<NodeInfo>);

        int deleteNodeInfo(NodeId id);

        //TBD: just for debug, will remove this function before release.
        /* void printMap(VPPNodeType type) {
            int t = int(type);
            auto &m = mNodes[t];
            cout<<__func__<<endl;
            for (auto &item : m ) {
                cout<<int(item.first.type)<<":"<<int(item.first.id)<<",";
            }
            cout<<endl;
        }; */

        struct NodeIdCompare {
            bool operator()(const NodeId &lid, const NodeId &rid) const {
                auto ha = [](const NodeId &id) {
                    return ((uint) (id.type) << 28) | ((uint) (id.devId) << 21) | (uint) (id.id);
                };
                return ha(lid) < ha(rid);
            };
        };

        using NodeMap = map<NodeId, shared_ptr<NodeInfo>, NodeIdCompare>;

        NodeMap & getNodeMap(VPPNodeType type);


        static const string SINK_NAME_DISP;
        static const string SINK_NAME_PP;

        vector<NodeMap> mNodes;
    private:

    };
}




// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
// Helper header to include messages defined by univloc_msgs in a ROS1/ROS2 compatible way

#pragma once

// ROS2
#include "univloc_msgs/msg/cv_keypoint.hpp"
#include "univloc_msgs/msg/descriptor.hpp"
#include "univloc_msgs/msg/imu_status.hpp"
#include "univloc_msgs/msg/lidar_status.hpp"
#include "univloc_msgs/msg/keyframe.hpp"
#include "univloc_msgs/msg/keyframe_update.hpp"
#include "univloc_msgs/msg/landmark.hpp"
#include "univloc_msgs/msg/camera_info.hpp"
#include "univloc_msgs/msg/map.hpp"
#include "univloc_msgs/msg/node.hpp"
#include "univloc_msgs/msg/octree.hpp"
#include "univloc_msgs/msg/ofusion.hpp"
#include "univloc_msgs/msg/voxel_block.hpp"
#include "univloc_msgs/msg/octree_param.hpp"
#include "univloc_msgs/srv/map_based_comm.hpp"

#define DECLARE_MSG_TYPES(Name) typedef msg::Name Name; \
                            typedef msg::Name::ConstSharedPtr Name##ConstPtr; \
                            typedef msg::Name::SharedPtr Name##Ptr;

#define DECLARE_SRV_TYPES(Name) typedef srv::Name Name; \
                            typedef srv::Name::Request Name##Request; \
                            typedef srv::Name::Response Name##Response;

namespace univloc_msgs{
DECLARE_MSG_TYPES(CvKeypoint)
DECLARE_MSG_TYPES(Descriptor)
DECLARE_MSG_TYPES(ImuStatus)
DECLARE_MSG_TYPES(LidarStatus)
DECLARE_MSG_TYPES(Keyframe)
DECLARE_MSG_TYPES(KeyframeUpdate)
DECLARE_MSG_TYPES(Landmark)
DECLARE_MSG_TYPES(CameraInfo)
DECLARE_MSG_TYPES(Map)
DECLARE_MSG_TYPES(Node)
DECLARE_MSG_TYPES(Octree)
DECLARE_MSG_TYPES(Ofusion)
DECLARE_MSG_TYPES(VoxelBlock)
DECLARE_MSG_TYPES(OctreeParam)
DECLARE_SRV_TYPES(MapBasedComm)
}

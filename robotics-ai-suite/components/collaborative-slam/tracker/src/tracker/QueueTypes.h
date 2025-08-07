// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include "DataQueue.h"
#include "data/frame.h"
#include "univloc_tracker/ImageFrame.h"
#include "univloc_tracker/LidarFrame.h"

namespace openvslam {

using univloc_tracker::ImageFrame;
using univloc_tracker::LidarFrame;

using RequestQueue = DataQueue<std::shared_ptr<ImageFrame>>;

using RequestLidarQueue = DataQueue<std::shared_ptr<LidarFrame>>;

using FeatureQueue = DataQueue<std::pair<std::shared_ptr<ImageFrame>, std::shared_ptr<data::frame>>>;

using VisualizationFrameQueue = DataQueue<std::shared_ptr<data::frame>>;

}

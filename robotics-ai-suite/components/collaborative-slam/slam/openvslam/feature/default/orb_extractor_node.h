// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#ifndef OPENVSLAM_FEATURE_ORB_EXTRACTOR_NODE_H
#define OPENVSLAM_FEATURE_ORB_EXTRACTOR_NODE_H

#include <array>
#include <list>

#include <opencv2/core/types.hpp>

template <typename T>
class orb_extractor_node {
public:
    //! Constructor
    orb_extractor_node() = default;

    //! Divide node to four child nodes
    typename std::array<orb_extractor_node, 4> divide_node()
    {
        // Half width/height of the allocated patch area
        const unsigned int half_x = cvCeil((pt_end_.x - pt_begin_.x) / 2.0);
        const unsigned int half_y = cvCeil((pt_end_.y - pt_begin_.y) / 2.0);

        // Four new child nodes
        std::array<orb_extractor_node, 4> child_nodes;

        // A position of center top, left center, center, right center, and center bottom
        // These positions are used to determine new split areas
        const auto pt_top = cv::Point2i(pt_begin_.x + half_x, pt_begin_.y);
        const auto pt_left = cv::Point2i(pt_begin_.x, pt_begin_.y + half_y);
        const auto pt_center = cv::Point2i(pt_begin_.x + half_x, pt_begin_.y + half_y);
        const auto pt_right = cv::Point2i(pt_end_.x, pt_begin_.y + half_y);
        const auto pt_bottom = cv::Point2i(pt_begin_.x + half_x, pt_end_.y);

        // Assign new patch border for each child nodes
        child_nodes.at(0).pt_begin_ = pt_begin_;
        child_nodes.at(0).pt_end_ = pt_center;
        child_nodes.at(1).pt_begin_ = pt_top;
        child_nodes.at(1).pt_end_ = pt_right;
        child_nodes.at(2).pt_begin_ = pt_left;
        child_nodes.at(2).pt_end_ = pt_bottom;
        child_nodes.at(3).pt_begin_ = pt_center;
        child_nodes.at(3).pt_end_ = pt_end_;

        // Memory reservation for child nodes
        for (auto& node : child_nodes) {
            node.keypts_.reserve(keypts_.size());
        }

        // Distribute keypoints to child nodes
        for (const auto& keypt : keypts_) {
            unsigned int idx = 0;
            if (pt_begin_.x + half_x <= keypt.pt.x) {
                idx += 1;
            }
            if (pt_begin_.y + half_y <= keypt.pt.y) {
                idx += 2;
            }
            child_nodes.at(idx).keypts_.push_back(keypt);
        }

        return child_nodes;
    }

    //! Keypoints which distributed into this node
    std::vector<T> keypts_;

    //! Begin and end of the allocated area on the image
    cv::Point2i pt_begin_, pt_end_;

    //! A iterator pointing to self, used for removal on list
    typename std::list<orb_extractor_node>::iterator iter_;

    //! A flag designating if this node is a leaf node
    bool is_leaf_node_ = false;
};

#endif // OPENVSLAM_FEATURE_ORB_EXTRACTOR_NODE_H

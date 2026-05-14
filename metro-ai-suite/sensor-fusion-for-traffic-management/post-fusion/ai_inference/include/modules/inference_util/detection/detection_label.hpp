/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#ifndef HCE_AI_INF_DETECTION_LABEL_HPP
#define HCE_AI_INF_DETECTION_LABEL_HPP

#include <vector>
#include <string>
#include <unordered_map>

namespace hce{

namespace ai{

namespace inference{

class DetectionLabel {
public:
    using Ptr = std::shared_ptr<DetectionLabel>;
    DetectionLabel() {};

    /**
     * @brief init with custom labels definition
     */
    bool init(const std::vector<std::string>& labels) {
        for (int index = 0; index < labels.size(); index ++) {
            m_label_map.emplace(index, labels[index]);
        }
        return true;
    };

    /**
     * @brief Get label name string by label index
     * @param i Label id
     * @return Label string
     */
    std::string label_name(int index) {
        if (m_label_map.count(index) > 0)
        {
            return m_label_map[index];
        }
        else
        {
            return "unknown";
        }
    };

    /**
     * @brief Get label index by label name
     * @param label Label name
     * @return Label index
     */
    int label_index(std::string& label) {
        for (auto it = m_label_map.begin(); it != m_label_map.end(); ++it) {
            if (it->second == label) 
                return it->first;
        }
        return -1;
    }

    /**
     * @brief Get category string by label id
     * @param i Label id
     * @return num classes
     */
    size_t num_classes() {
    return m_label_map.size();
}

private:
    std::unordered_map<int, std::string> m_label_map;
};

/**
 * Class used to store pascal voc label
 */
class Pascal_voc_label {
public:
    Pascal_voc_label() 
    {
        _labels = std::vector<std::string> {
            "aeroplane",
            "bicycle",
            "bird",
            "boat",
            "bottle",
            "bus",
            "car",
            "cat",
            "chair",
            "cow",
            "diningtable",
            "dog",
            "horse",
            "motorbike",
            "person",
            "pottedplant",
            "sheep",
            "sofa",
            "train",
            "tvmonitor"
        };
    }
    
    /**
     * @brief Get labels
     * @return labels
     */
    std::vector<std::string> labels() {
        return _labels;
    }

private:
    std::vector<std::string> _labels;
};

/**
 * Class used to store ms coco label
 */
class Ms_coco_label {
public:
    Ms_coco_label()
    {
        _labels = std::vector<std::string> {
            "person",
            "bicycle",
            "car",
            "motorbike",
            "aeroplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light",
            "fire hydrant",
            "stop sign",
            "parking meter",
            "bench",
            "bird",
            "cat",
            "dog",
            "horse",
            "sheep",
            "cow",
            "elephant",
            "bear",
            "zebra",
            "giraffe",
            "backpack",
            "umbrella",
            "handbag",
            "tie",
            "suitcase",
            "frisbee",
            "skis",
            "snowboard",
            "sports ball",
            "kite",
            "baseball bat",
            "baseball glove",
            "skateboard",
            "surfboard",
            "tennis racket",
            "bottle",
            "wine glass",
            "cup",
            "fork",
            "knife",
            "spoon",
            "bowl",
            "banana",
            "apple",
            "sandwich",
            "orange",
            "broccoli",
            "carrot",
            "hot dog",
            "pizza",
            "donut",
            "cake",
            "chair",
            "sofa",
            "pottedplant",
            "bed",
            "diningtable",
            "toilet",
            "tvmonitor",
            "laptop",
            "mouse",
            "remote",
            "keyboard",
            "cell phone",
            "microwave",
            "oven",
            "toaster",
            "sink",
            "refrigerator",
            "book",
            "clock",
            "vase",
            "scissors",
            "teddy bear",
            "hair drier",
            "toothbrush"
        };
    }
    
    /**
     * @brief Get labels
     * @return labels
     */
    std::vector<std::string> labels() {
        return _labels;
    }

private:
    std::vector<std::string> _labels;
};


}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_DETECTION_LABEL_HPP
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
#ifndef HCE_AI_INF_CLASSIFICATION_LABEL_HPP
#define HCE_AI_INF_CLASSIFICATION_LABEL_HPP

#include <algorithm>
#include <cmath>

namespace hce{

namespace ai{

namespace inference{

class ClassificationLabel_t {
public:
    ClassificationLabel_t () {};

    bool init(const std::string& name, const std::vector<std::string>& labels) {
        m_name = name;
        m_labels = labels;
        return true;
    };

    /**
     * @brief Get label name string by label index
     * @param index Label index
     * @return Label string
     */
    std::string label_name(int index) {
        if (0 <= index < m_labels.size())
            return m_labels[index];
        return "unkown";
    };

    /**
     * @brief Get label index by label name
     * @param label Label name
     * @return Label index
     */
    int label_index(std::string& label) {
        for (int i = 0; i < m_labels.size(); i ++) {
            if (m_labels[i] == label) {
                return i;
            }
        }
        // unkown label
        return -1;
    }

    /**
     * @brief Get number of classes
     * @return num classes
     */
    size_t num_classes() {
        return m_labels.size();
    }

    /**
     * @brief Get attribute name
     */
    std::string attibute_name() {
        return m_name;
    }

private:
    std::string m_name;     // attribute name
    std::vector<std::string> m_labels;
};

}   // namespace inference

}   // namespace ai

}   // namespace hce

#endif //#ifndef HCE_AI_INF_CLASSIFICATION_LABEL_HPP
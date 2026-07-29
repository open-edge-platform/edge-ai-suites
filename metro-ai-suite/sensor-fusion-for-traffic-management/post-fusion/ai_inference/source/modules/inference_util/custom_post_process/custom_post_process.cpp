/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2023 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/

#include <map>
#include <boost/property_tree/json_parser.hpp>

namespace hce{

namespace ai{

namespace inference{

extern "C" {
std::string SSDPostProc(std::map<std::string, float*> blob_data,
                        std::map<std::string, size_t> blob_length,
                        float class_conf_thresh, size_t target_batch_id);
}

/**
 * @brief configures for output layer, each field is assined with an index
 * 
 */
struct OutputLayerShapeConfig {
    const size_t classes_number = 2;
    size_t top_proposals = 200;
    const size_t one_bbox_blob_size = 7;
    enum Index : size_t {
      BATCH_IDX = 0,
      CLASS_ID = 1,
      CONFIDENCE = 2,
      X_MIN = 3,
      Y_MIN = 4,
      X_MAX = 5,
      Y_MAX = 6
    };
};

OutputLayerShapeConfig output_shape_info;

size_t getIndex(size_t index, size_t offset) {
    return index * output_shape_info.one_bbox_blob_size + offset;
}

/**
 * @brief custom post-process function: SSDPostProc
 * @param blob_data <layer_name, inference_blob_data>
 * @param blob_length <layer_name, blob_length>
 * @return std::string, results with json format
 */
std::string SSDPostProc(std::map<std::string, float*> blob_data,
                        std::map<std::string, size_t> blob_length,
                        float class_conf_thresh, size_t target_batch_id) {
    namespace pt = boost::property_tree;
    pt::ptree res_ptree;
    pt::ptree all_rois;
    for (const auto &blob_iter : blob_data) {

        std::string layer_name = blob_iter.first;

        // fetch blob data from output layer
        const float *buffer = (const float *)blob_iter.second;
        output_shape_info.top_proposals = blob_length[layer_name] / output_shape_info.one_bbox_blob_size;
        
        using Index = OutputLayerShapeConfig::Index;
        // traverse each candidate roi and remove those boxes with smaller confidence score
        for (size_t bbox_idx = 0; bbox_idx < output_shape_info.top_proposals; bbox_idx ++) {

            // support openvino OP: DetectionOutput
            // https://docs.openvino.ai/2022.3/openvino_docs_ops_detection_DetectionOutput_1.html#doxid-openvino-docs-ops-detection-detection-output-1
            // The output tensor contains information about filtered detections described with 7 element tuples: [batch_id, class_id, confidence, x_1, y_1, x_2, y_2]. 
            // The first tuple with batch_id equal to -1 means end of output.
            auto cur_batch_id = data[Index::BATCH_IDX];
            if (cur_batch_id == -1) {
                break;
            }
            if (cur_batch_id != target_batch_id) {
                continue;
            }

            const float x_min = buffer[getIndex(bbox_idx, Index::X_MIN)];
            const float y_min = buffer[getIndex(bbox_idx, Index::Y_MIN)];
            const float x_max = buffer[getIndex(bbox_idx, Index::X_MAX)];
            const float y_max = buffer[getIndex(bbox_idx, Index::Y_MAX)];
            const float bbox_w = x_max - x_min;
            const float bbox_h = y_max - y_min;
            size_t bbox_class_id = (size_t)buffer[getIndex(bbox_idx, Index::CLASS_ID)];  // class_id starts from 1 in blobs
            if (bbox_class_id > output_shape_info.classes_number) {
                continue;
            }
            // HVA_ASSERT(bbox_class_id < output_shape_info.classes_number);
            float bbox_confidence = buffer[getIndex(bbox_idx, Index::CONFIDENCE)];

            // note that the coordinates x, y etc. are normalized to 0 ~ 1.
            if (bbox_confidence >= class_conf_thresh) {
                pt::ptree bbox_ptree;
                pt::ptree bbox_element;
                pt::ptree x_coordinate_element;
                pt::ptree y_coordinate_element;
                pt::ptree bbox_w_element;
                pt::ptree bbox_h_element;
                x_coordinate_element.put("", x_min);
                y_coordinate_element.put("", y_min);
                bbox_w_element.put("", bbox_w);
                bbox_h_element.put("", bbox_h);
                bbox_element.push_back(std::make_pair("", x_coordinate_element));
                bbox_element.push_back(std::make_pair("", y_coordinate_element));
                bbox_element.push_back(std::make_pair("", bbox_w_element));
                bbox_element.push_back(std::make_pair("", bbox_h_element));

                bbox_ptree.add_child("bbox", bbox_element);

                pt::ptree confidence_element;
                confidence_element.put("", bbox_confidence);
                bbox_ptree.add_child("confidence", confidence_element);

                pt::ptree class_id_element;
                class_id_element.put("", bbox_class_id);
                bbox_ptree.add_child("label_id", class_id_element);

                all_rois.push_back(std::make_pair("", bbox_ptree));
            }
            else {
                // ignore the proposals with confidence less than pre-defined threshold
            }
        }
    }
    res_ptree.add_child("format", all_rois);
    std::stringstream json_results;
    pt::json_parser::write_json(json_results, res_ptree);

    /**
     * @brief Format json_results
     *
     * json_results.str() schema:
       {
            "format": [
                {
                    "bbox": [
                        float,
                        float,
                        float,
                        float
                    ],
                    "confidence": float,
                    "label_id": int
                },
                ...
            ]
        }
    */
    return json_results.str();
}

}

}

}

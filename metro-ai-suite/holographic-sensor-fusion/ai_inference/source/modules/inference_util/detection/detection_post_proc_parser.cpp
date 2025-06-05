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

#include "modules/inference_util/detection/detection_model_proc_parser.hpp"


namespace hce{

namespace ai{

namespace inference{

// ============================================================================
//                      Detection Model Output Formatter
// ============================================================================

DetectionOutputFormatter::DetectionOutputFormatter() {

}

DetectionOutputFormatter::~DetectionOutputFormatter() {
    
}

/**
 * @brief init output formmater with json items
 * Can be scalable with optional field
 */
void DetectionOutputFormatter::init(const nlohmann::json& format_items) {

    std::vector<std::string> required_fields = {"bbox", "label_id", "confidence"};
    JsonReader::check_required_item(format_items, required_fields);

    for (nlohmann::json::const_iterator it = format_items.begin(); it != format_items.end(); ++it) {
        std::string key = it.key();
        std::string type = it.value();
        // TODO standardize `type`
        m_register_key.emplace(key, type);
    }
}

/**
 * @brief set value to registered keys
 * @param key registered key
 * @param val runtime value
 */
void DetectionOutputFormatter::setVal(std::string key, const std::vector<float>& val) {
    std::string type = m_register_key[key];

    // TODO type
    if (type == "FLOAT_ARRAY") {
        boost::property_tree::ptree ptree_val;
        for (auto v : val) {
            boost::property_tree::ptree coord;
            coord.put("", v);
            ptree_val.push_back(std::make_pair("", coord));
        }
        m_output.add_child(key, ptree_val);

    }
    else if (type == "FLOAT") {
        if (val.size() != 1) {
            char log[512];
            sprintf(log, "Invalid input size: %d, value type is expected to be FLOAT!", (int)val.size());
            throw std::invalid_argument(log);
        }
        m_output.put(key, val[0]);
    }
    else if (type == "INT") {
        if (val.size() != 1) {
            char log[512];
            sprintf(log, "Invalid input size: %d, value type is expected to be INT!", (int)val.size());
            throw std::invalid_argument(log);
        }
        float x = val[0];

        if ((int)x * 1.0 != x) {
            char log[512];
            sprintf(log, "Invalid input value: %f, value type is expected to be INT!", x);
            throw std::invalid_argument(log);
        }
        m_output.put(key, (int)x);
    }
    else {
        throw std::invalid_argument(
            "Required type: " + type + " for output key: " + key +
            ", but got invalid value here!");
    }
}

/**
 * @brief reset each ptree det result
*/
void DetectionOutputFormatter::resetOutput() {
    for (const auto& item : m_register_key) {
        m_output.erase(item.first);
    }
}


// ============================================================================
//                      Detection Model Processing Parser
// ============================================================================

DetectionModelProcParser::DetectionModelProcParser(std::string& confPath) : m_conf_path(confPath) {

}

DetectionModelProcParser::~DetectionModelProcParser() {

}

/**
 * @brief read and parse model_proc file
 * @return boolean 
*/
bool DetectionModelProcParser::parse() {
    try {
        // read json file contents
        readJsonFile();

        // "labels_table"
        parseLabelsTable();

        // "model_output", depends on the field "labels_table"
        parseModelOutput();

        // "post_proc_output"
        parsePostprocOutput();
    }
    catch (std::exception &e) {
        HVA_ERROR("Parsing model_proc json content failed, error: %s!", e.what());
        return false;
    }
    catch (...) {
        HVA_ERROR("Parsing model_proc json content failed!");
        return false;
    }
    
    return true;
}

/**
 * @brief read json content into m_json_reader, check reuqired fields
 *        and parse basic fields: json_schema_version, model_type
 * @return void
*/
void DetectionModelProcParser::readJsonFile() {
    HVA_DEBUG("Parsing model_proc json from file: %s", m_conf_path.c_str());

    m_json_reader.read(m_conf_path);

    const nlohmann::json &model_proc_content = m_json_reader.content();

    std::vector<std::string> required_fields = {
        "json_schema_version", "model_type",       "model_input",
        "model_output",        "post_proc_output", "labels_table"};
    JsonReader::check_required_item(model_proc_content, required_fields);

    // json_schema_version
    m_json_schema_version = model_proc_content["json_schema_version"].get<std::string>();

    // model_type
    m_model_type = model_proc_content["model_type"].get<std::string>();
};

/**
 * @brief parse `model_output` field in model_proc file
 */
void DetectionModelProcParser::parseModelOutput() {
    /**
    "model_output": {
        "format": {
            "layout": "BCxCy",
            "detection_output": {
                "size": 85,
                "bbox_format": "CENTER_SIZE",
                "location_index": [0, 1, 2, 3],
                "confidence_index": 4,
                "first_class_prob_index": 5
            }
        },
        "class_label_table": "coco"
    },
        */
    const nlohmann::json &model_proc_content = m_json_reader.content();
    auto proc_items = model_proc_content.at("model_output");

    //
    // model_output
    //
    std::vector<std::string> required_fields = {"class_label_table"};
    JsonReader::check_required_item(proc_items, required_fields);

    // model_output.class_label_table
    std::string class_label_table = proc_items["class_label_table"].get<std::string>();
    if (m_labels_table.count(class_label_table) == 0) {
        throw std::invalid_argument(
            "Unknown class_label_table is defined: " +
            class_label_table +
            ", please make sure it exists in 'labels_table' field!");
    }
    // get DetectionLabel
    m_proc_params.model_output.labels = m_labels_table[class_label_table];

    // get num_classes from the length of defined labels
    m_proc_params.model_output.num_classes = m_proc_params.model_output.labels->num_classes();
    
    //
    // Optional: model_output.format
    //
    if (JsonReader::check_item(proc_items, "format")) {
        auto format_items = proc_items.at("format");
        required_fields = {"layout"};
        JsonReader::check_required_item(format_items, required_fields);

        // model_output.format.layout
        std::string layout_str = format_items["layout"].get<std::string>();
        if (layout_str == "BCxCy") {
            m_proc_params.model_output.layout = DetOutputDimsLayout_t::BCxCy;
        }
        else if (layout_str == "CxCyB") {
            m_proc_params.model_output.layout = DetOutputDimsLayout_t::CxCyB;
        }
        else if (layout_str == "B") {
            m_proc_params.model_output.layout = DetOutputDimsLayout_t::B;
        }
        else {
            throw std::invalid_argument(
                "Unknown model output layout is specified in model_proc: " + layout_str + " supported: BCxCy, CxCyB, B");
        }

        //
        // model_output.format.detection_output
        //
        // m_proc_params.model_output.detection_output values will be assigned
        m_proc_params.model_output.detection_output.enabled = true;

        auto detection_output_items = format_items.at("detection_output");
        required_fields = {"size", "bbox_format", "location_index"};
        JsonReader::check_required_item(detection_output_items, required_fields);

        // model_output.format.detection_output.size
        auto iter = detection_output_items.find("size");
        iter.value().get_to(m_proc_params.model_output.detection_output.size);

        // model_output.format.detection_output.bbox_format
        std::string bbox_format_str =
            detection_output_items["bbox_format"].get<std::string>();
        if (bbox_format_str == "CENTER_SIZE") {
            m_proc_params.model_output.detection_output.bbox_format = DetBBoxFormat_t::CENTER_SIZE;
        }
        else if (bbox_format_str == "CORNER_SIZE") {
            m_proc_params.model_output.detection_output.bbox_format = DetBBoxFormat_t::CORNER_SIZE;
        }
        else if (bbox_format_str == "CORNER") {
            m_proc_params.model_output.detection_output.bbox_format = DetBBoxFormat_t::CORNER;
        }
        else {
            throw std::invalid_argument(
                "Unknown bbox_format: " + bbox_format_str +
                " supported layout: CENTER_SIZE, CORNER_SIZE, CORNER");
        }

        // model_output.format.detection_output.location_index
        m_proc_params.model_output.detection_output.location_index =
            detection_output_items["location_index"].get<std::vector<int>>();

        //
        // Either existence check:
        // > (confidence_index || first_class_prob_index)
        // > (first_class_prob_index || predict_label_index)
        //
        if (!JsonReader::check_item(detection_output_items, "confidence_index") &&
            !JsonReader::check_item(detection_output_items, "first_class_prob_index")) {

            throw std::invalid_argument(
                "At least : confidence_index or first_class_prob_index should be specified!");
        }
        if (!JsonReader::check_item(detection_output_items, "first_class_prob_index") &&
            !JsonReader::check_item(detection_output_items, "predict_label_index")) {

            throw std::invalid_argument(
                "At least : first_class_prob_index or predict_label_index should be specified!");
        }

        // optional: model_output.format.detection_output.confidence_index
        if (JsonReader::check_item(detection_output_items, "confidence_index")) {
            int index = detection_output_items["confidence_index"].get<int>();
            if (index < 0) {
                throw std::invalid_argument("Invalid confidence_index is specified, should be >= 0");
            }
            m_proc_params.model_output.detection_output.confidence_index = index;
        }

        // optional: model_output.format.detection_output.first_class_prob_index
        if (JsonReader::check_item(detection_output_items, "first_class_prob_index")) {
            int index = detection_output_items["first_class_prob_index"].get<int>();
            if (index < 0) {
                throw std::invalid_argument("Invalid first_class_prob_index is specified, should be >= 0");
            }
            m_proc_params.model_output.detection_output.first_class_prob_index = index;
        }

        // optional: model_output.format.detection_output.predict_label_index
        if (JsonReader::check_item(detection_output_items, "predict_label_index")) {
            int index = detection_output_items["predict_label_index"].get<int>();
            if (index < 0) {
                throw std::invalid_argument("Invalid predict_label_index is specified, should be >= 0");
            }
            m_proc_params.model_output.detection_output.predict_label_index = index;
        }

        // optional: model_output.format.detection_output.batchid_index
        if (JsonReader::check_item(detection_output_items, "batchid_index")) {
            int index = detection_output_items["batchid_index"].get<int>();
            if (index < 0) {
                throw std::invalid_argument("Invalid batchid_index is specified, should be >= 0");
            }
            m_proc_params.model_output.detection_output.batchid_index = index;
        }
    } else {
        // m_proc_params.model_output.detection_output all values are not assigned
        m_proc_params.model_output.detection_output.enabled = false;
    }
}

/**
 * @brief parse `post_proc_output` field in model_proc file
 */
void DetectionModelProcParser::parsePostprocOutput() {
    
    const nlohmann::json &model_proc_content = m_json_reader.content();
    parsePPOutputItems(model_proc_content.at("post_proc_output"), m_proc_params.pp_output);

}

/**
 * @brief parse `labels_table` field in model_proc file
*/
void DetectionModelProcParser::parseLabelsTable() {
    /**
    "labels_table": [
        {
            "name": "coco",
            "labels": [
                "person",
                "bicycle",
                "car"
            ]
        },
        {...}
    ]
    */
    const nlohmann::json &model_proc_content = m_json_reader.content();
    auto labels_table_items = model_proc_content.at("labels_table");
    
    for (auto &items : labels_table_items) {
        std::vector<std::string> required_fields = {"name", "labels"};
        JsonReader::check_required_item(items, required_fields);
        
        // labels_table[i].name
        std::string name = items["name"].get<std::string>();

        // labels_table[i].labels
        std::vector<std::string> vlabels = items["labels"].get<std::vector<std::string>>();

        DetectionLabel::Ptr _label = DetectionLabel::Ptr(new DetectionLabel());
        _label->init(vlabels);
        m_labels_table.emplace(name, _label);
    }
}

/**
 * @brief parse model proc item: "post_proc_output"
 */
void DetectionModelProcParser::parsePPOutputItems(const nlohmann::basic_json<> &proc_items, _post_proc_output_t &params) {
    /**
    "post_proc_output": {
        "function_name": "HVA_det_postproc",
        "format": {
            "bbox": "FLOAT_ARRAY",
            "label_id": "INT",
            "confidence": "FLOAT"
        },
        "process": [
            {}, {}, ...
        ],
        "mapping": {
            "bbox": {},
            "label_id": {},
            "confidence": {}
        }
    }
    */

    //
    // post_proc_output
    //
    std::vector<std::string> required_fields = {"function_name", "format"};
    JsonReader::check_required_item(proc_items, required_fields);

    // post_proc_output.function_name
    auto iter = proc_items.find("function_name");
    iter.value().get_to(params.function_name);

    //
    // post_proc_output.format
    //
    auto format_items = proc_items.at("format");
    params.output_formatter = DetectionOutputFormatter::Ptr(new DetectionOutputFormatter());
    params.output_formatter->init(format_items);

    //
    // post_proc_output.process
    //
    if (JsonReader::check_item(proc_items, "process")) {
        auto process_items = proc_items.at("process");
        parseProcessorList(process_items, params.processor_factory);
    }

    //
    // post_proc_output.mapping
    //
    if (JsonReader::check_item(proc_items, "mapping")) {
        auto mapping_items = proc_items.at("mapping");
        parseMappingItems(mapping_items, params.output_formatter, params.mapping_factory);
    }
}

/**
 * @brief parse processor list from field: "post_proc_output.process"
 */
void DetectionModelProcParser::parseProcessorList(
    const nlohmann::basic_json<>& proc_items,
    std::vector<ModelPostProcessor::Ptr>& processor_factory) {
    /**
    "process": [
        {
            "name": "bbox_transform",
            "params": {
                "target_type": "CORNER_SIZE"
            }
        },
        {
            "name":
            "params":
        },

    ]
        */
    for (auto &processor_items : proc_items) {
        std::vector<std::string> required_fields = {"name", "params"};
        JsonReader::check_required_item(processor_items, required_fields);
        
        std::string name = processor_items["name"].get<std::string>();

        ModelPostProcessor::Ptr processor = ModelPostProcessor::CreateInstance(
            m_proc_params.model_output, name, processor_items.at("params"));

        processor_factory.push_back(processor);
    }

}

/**
 * @brief parse mapping items from field: "post_proc_output.mapping"
*/
void DetectionModelProcParser::parseMappingItems(
    const nlohmann::basic_json<>& mapping_items,
    const DetectionOutputFormatter::Ptr& output_formatter,
    std::unordered_map<std::string, _output_mapping_t>& mapping_factory) {

    for (const auto& output_key : output_formatter->getRegisterKeys()) {
        std::string key_name = output_key.first;

        // each key registred in post_proc_output.format should be described
        // here
        JsonReader::check_required_item(mapping_items, key_name);
        _output_mapping_t output_mapping;

        //
        // parse each mapping item: post_proc_output.mapping.{key_name}
        //
        auto each_mapping_item = mapping_items.at(key_name);
        std::vector<std::string> required_fields = { "input", "op" };
        JsonReader::check_required_item(each_mapping_item, required_fields);

        // 
        // post_proc_output.mapping.{key_name}.input
        // 
        auto input_items = each_mapping_item.at("input");
        required_fields = { "index" };
        JsonReader::check_required_item(input_items, required_fields);

        // post_proc_output.mapping.{key_name}.input.index
        auto iter = input_items.find("index");
        iter.value().get_to(output_mapping.index);

        // post_proc_output.mapping.{key_name}.op
        std::vector<ModelOutputOperator::Ptr> ops;
        for (auto& op_items : each_mapping_item.at("op")) {
            required_fields = { "name", "params" };
            JsonReader::check_required_item(op_items, required_fields);

            std::string name = op_items["name"].get<std::string>();
            ModelOutputOperator::Ptr op = ModelOutputOperator::CreateInstance(
                m_proc_params.model_output, name,
                op_items.at("params"));
            ops.push_back(op);
        }
        output_mapping.ops = ops;
        mapping_factory.emplace(key_name, output_mapping);
    }
}


}   // namespace inference

}   // namespace ai

}   // namespace hce
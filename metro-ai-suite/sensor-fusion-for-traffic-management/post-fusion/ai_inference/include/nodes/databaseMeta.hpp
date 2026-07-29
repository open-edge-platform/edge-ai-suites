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

#ifndef HCE_AI_INF_DATABASE_META_HPP
#define HCE_AI_INF_DATABASE_META_HPP

#include <unordered_map>
#include "common/common.hpp"
#include "nodes/radarDatabaseMeta.hpp"

#include <mutex>
#include <condition_variable>
#include <atomic>

namespace hce {

namespace ai {

namespace inference {

/**
 * @struct describe classification results
 *
 */
struct ClassificationObject_t
{
    std::string label; /** Attribute label */
    int class_id;      /** Attribute label id */
    float confidence;  /** Attribute confidence */

    ClassificationObject_t() = default;
    ClassificationObject_t(int class_id, float confidence)
    {
        this->class_id = class_id;
        this->confidence = confidence;
    }
};

struct AttributeContainer_t
{
    std::unordered_map<std::string, ClassificationObject_t> attr;
    AttributeContainer_t() = default;
};

struct TimeStamp_t
{
    std::chrono::time_point<std::chrono::high_resolution_clock> timeStamp;
    TimeStamp_t() = default;
};

struct InferenceTimeStamp_t
{
    std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
    std::chrono::time_point<std::chrono::high_resolution_clock> endTime;
    InferenceTimeStamp_t() = default;
};

struct LidarTimeStamp_t
{
    std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
    std::chrono::time_point<std::chrono::high_resolution_clock> endTime;
    LidarTimeStamp_t() = default;
};

struct VideoTimeStamp_t
{
    std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
    std::chrono::time_point<std::chrono::high_resolution_clock> endTime;
    VideoTimeStamp_t() = default;
};

struct TimeStampAll_t
{
    std::chrono::time_point<std::chrono::high_resolution_clock> timeStamp[6];
    TimeStampAll_t() = default;
};

struct InferenceTimeAll_t
{
    double inferenceLatencies[6];
    InferenceTimeAll_t() = default;
};

struct VideoTimeAll_t
{
    double videoLatencies[6];
    VideoTimeAll_t() = default;
};

// mapping: ("roi_id", "attributes")
typedef std::unordered_map<size_t, AttributeContainer_t> AttributeResultMeta;

// mapping: ("roi_id", "license-plate")
typedef std::unordered_map<size_t, std::string> LPRResultMeta;

// mapping: ("roi_id", "quality-score")
typedef std::unordered_map<size_t, float> QualityResultMeta;

// mapping: ("roi_id", "is_ignored")
typedef std::unordered_map<size_t, bool> SelectResultMeta;

/**
 * @struct describe associate relation for rois, using roi index to track
 *
 */
struct ObjectAssociate_t
{
    int32_t associated_to = -1;
};

// mapping: ("roi_id", "assocated-to")
typedef std::unordered_map<size_t, ObjectAssociate_t> ObjectAssociateResultMeta;
enum HceDataMetaBufType {
    BUFTYPE_UNKNOWN,
    BUFTYPE_STRING,
    BUFTYPE_UINT8,
    BUFTYPE_MFX_FRAME,
};


class HCE_AI_DECLSPEC HceDatabaseMeta {
  public:
    using Ptr = std::shared_ptr<HceDatabaseMeta>;

    HceDatabaseMeta() : timeStamp(0u), captureSourceId("100"){};

    ~HceDatabaseMeta(){};

    std::string mediaUri;         // schema: Hash(media_type,4) + Hash(data_source,4) + content(32)
    uint64_t timeStamp;           // the unix timestamp in ms
    std::string captureSourceId;  // camera identification, default as `100`
    std::string localFilePath;    // optional. record local path for input, support image or video
    // std::string radarConfigPath;
    HceDataMetaBufType bufType = HceDataMetaBufType::BUFTYPE_UNKNOWN;

    // Represents Color formats
    hce::ai::inference::ColorFormat colorFormat = hce::ai::inference::ColorFormat::BGR;
    // Image scale ratio
    // scaleHeight = oriHeight / height
    // scaleWidth = oriWidth / width
    float scaleHeight = 1.0f;
    float scaleWidth = 1.0f;

    /// @brief results meta
    AttributeResultMeta attributeResult;     // attribute results, {key, value} => {roi_id, result}
    LPRResultMeta lprResult;                 // license plate recognition results, {key, value} => {roi_id, result}
    ObjectAssociateResultMeta objAssResult;  // object associate results, {key, value} => {roi_id, result}
    QualityResultMeta qualityResult;         // quality assessment results, {key, value} => {roi_id, quality-score}
    SelectResultMeta ignoreFlags;            // If one roi is dropped in selection node, mask would be set as true,
                                             // so that the downstreaming nodes will ignore this roi.
    RadarConfigParam radarParams;            // Radar config params  //need to delete

    /**
     * @brief reset all results in meta
     *
     */
    void resetAllResults()
    {
        attributeResult.clear();
        lprResult.clear();
        objAssResult.clear();
        qualityResult.clear();
        ignoreFlags.clear();
    }
};

class SendController {
  public:
    using Ptr = std::shared_ptr<SendController>;

    SendController() : capacity(1u), stride(1u), count(0u), controlType("Video"){};

    SendController(size_t c) : capacity(c), stride(1u), count(0u), controlType("Video"){};

    SendController(size_t c, std::string type) : capacity(c), stride(1u), count(0u), controlType(type){};

    SendController(size_t c, size_t s, std::string type) : capacity(c), stride(s), count(0u), controlType(type){};

    ~SendController(){};

    void setCapacity(size_t c)
    {
        capacity = c;
    }

    void setControlType(std::string type)
    {
        controlType = type;
    }

    void setStride(size_t s)
    {
        stride = s;
    }

  public:
    size_t capacity;          // The capacity bound
    size_t stride;            // The stride for count
    size_t count;             // Current number of elements
    std::string controlType;  // decide to control radar pipeline or video pipeline
    std::mutex mtx;
    std::condition_variable notFull;
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_DATABASE_META_HPP

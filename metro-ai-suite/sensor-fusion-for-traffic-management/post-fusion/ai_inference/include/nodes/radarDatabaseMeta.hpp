/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2025 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
 */

#ifndef HCE_AI_INF_RADAR_DATABASE_META_HPP
#define HCE_AI_INF_RADAR_DATABASE_META_HPP

#include <vector>
#include <complex>
#include "common/common.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"

namespace hce {

namespace ai {

namespace inference {

typedef std::complex<float> ComplexFloat_t;
typedef std::vector<ComplexFloat_t> radarVec_t;

/**
 * @brief
 * This file defines all related radar/fusion data struture.
 * Developers can use these data structure through hva meta data design, both roi-level and frame-level are supported by hvaframework now.
 *
 * > use header:
 * #include <inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp>
 *
 * > define buffer
 * hva::hvaVideoFrameWithMetaROIBuf::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf::make_buffer<ThreeDimArray<ComplexFloat>>(*test_matrix, radar_frame_size);
 *
 * > frame-level
 * //
 * // A better way to set meta data (frame-level)
 * //
 * hvabuf->setMeta(m_radar_config);
 * // how to get this meta data in downstream node?
 * if (hvabuf->containMeta<RadarConfigParam>()) {
 *     // success
 *     RadarConfigParam _get_radar_config;
 *     hvabuf->getMeta(_get_radar_config)
 *     // now you get the exact values passing from previous node: _get_radar_config
 * }
 * else {
 *     // previous node not ever put this type of meta into hvabuf
 * }
 *
 *
 * > roi-level
 * //
 * // A better way to set meta data (roi-level)
 * //
 * hva::hvaMetaROI_t roi;
 * roi.setMeta(m_tracker_output);
 * hvabuf->rois.push_back(roi);
 * for(unsigned i_roi = 0; i_roi < hvabuf->rois.size(); ++i_roi){
 *     hva::hvaMetaROI_t _get_roi = hvabuf->rois[i_roi];
 *     if(_get_roi.containMeta<trackerOutput>()) {
 *         // success
 *         trackerOutput _get_tracker_output;
 *         _get_roi.getMeta(_get_tracker_output)
 *         // now you get the exact values passing from previous node: _get_tracker_output
 *     }
 *     else {
 *         // previous node not ever put this type of meta into this roi
 *     }
 * }
 *
 *
 */

/*************************************************************************************************
 * @brief Radar processing related meta data: RadarConfigParam
 * produced by `RadarPreProcessingNode`, may be consumed by downstream nodes
 *************************************************************************************************/
enum WinType { Hanning = 1, Hamming = 2, Cheyshev = 3 };
enum AoaEstimationType { FFT = 1, MUSIC = 2, DBF = 3, CAPON = 4 };

enum CfarMethod { CA_CFAR = 1, SO_CFAR = 2, GO_CFAR = 3, OS_CFAR = 4 };

struct RadarBasicConfig
{
    int numRx;               // number of TRx
    int numTx;               // number of Tx
    double Start_frequency;  // start freqency
    double idle;             // idle time
    double adcStartTime;     // start time
    double rampEndTime;      // ramp end time
    double freqSlopeConst;   // slope
    double adcSampleRate;    // adc sample rate
    int adcSamples;          // number of samples
    int numChirps;           // sampling rate
    float fps;               // radar frame rate
};

struct RadarDetectionConfig
{
    WinType m_range_win_type_;                 // windowing type for range fft
    WinType m_doppler_win_type_;               // windowing type for doppler fft
    AoaEstimationType m_aoa_estimation_type_;  // enum, aoa method
    CfarMethod m_doppler_cfar_method_;         // enum, doppler cfar method
    float DopplerPfa;                          // desired false alarm rate
    int DopplerWinGuardLen;                    // number of doppler cfar guard cells
    int DopplerWinTrainLen;                    // number of doppler cfar training cells
    CfarMethod m_range_cfar_method_;           // enum, range cfar method
    float RangePfa;                            // desired false alarm rate.
    int RangeWinGuardLen;                      // number of range cfar guard cells
    int RangeWinTrainLen;                      // number of range cfar training cells
};

struct RadarClusteringConfig
{
    float eps;               // distance threshold for cluster check
    float weight;            // the weight between the distance and speed
    int minPointsInCluster;  // minimum number of points in a cluster
    int maxClusters;         // maximum number of clusters
    int maxPoints;           // maximum number of points that can be services per dbscanRun call
};
struct RadarTrackingConfig
{
    float trackerAssociationThreshold;  // tracker association threshold
    float measurementNoiseVariance;     // measurement noise variance
    float timePerFrame;                 // time period per frame
    float iirForgetFactor;              // IIR filter forgettting factor
    int trackerActiveThreshold;         // counter threshold for tracker  to turn from detect to active.
    int trackerForgetThreshold;         // counter threshold for tracker to turn from active to expire.
};

struct RadarConfigParam
{
    RadarBasicConfig m_radar_basic_config_;
    RadarDetectionConfig m_radar_detection_config_;
    RadarClusteringConfig m_radar_clusterging_config_;
    RadarTrackingConfig m_radar_tracking_config_;
    std::string CSVFilePath;
    int csvRepeatNum;
};


/*************************************************************************************************
 * @brief Radar processing related meta data: pointClouds
 * produced by `RadarDetectionNode`, may be consumed by downstream nodes
//  *************************************************************************************************/

struct pointClouds
{
    int num;
    std::vector<int> rangeIdxArray;
    std::vector<float> rangeFloat;
    std::vector<int> speedIdxArray;
    std::vector<float> speedFloat;

    std::vector<float> SNRArray;
    std::vector<float> aoaVar;
};


/*************************************************************************************************
 * @brief Radar processing related meta data: clusteringDBscanOutput
 * produced by `RadarClusteringNode`, may be consumed by downstream nodes
 *************************************************************************************************/

// Structure for each cluster information report
struct clusteringDBscanReport
{
    int numPoints;           // number of points in this cluster
    float xCenter;           // the clustering center on x direction
    float yCenter;           // the clustering center on y direction
    float xSize;             // the clustering size on x direction
    float ySize;             // the clustering size on y direction
    float avgVel;            // the average velocity within this cluster
    float centerRangeVar;    // variance of the range estimation
    float centerAngleVar;    // variance of the angle estimation
    float centerDopplerVar;  // variance of the doppler estimation
};

// Structure of clusrering output
struct clusteringDBscanOutput
{
    // int *InputArray;                                         // clustering result index array
    std::vector<int> InputArray;  // clustering result index array
    int numCluster;               // number of cluster detected
    // clusteringDBscanReport *report;                          // information report for each cluster
    std::vector<clusteringDBscanReport> report;  // information report for each cluster
};


/*************************************************************************************************
 * @brief Radar processing related meta data: trackerOutput
 * produced by `RadarTrackingNode`, may be consumed by downstream nodes
 *************************************************************************************************/

struct trackerOutputDataType
{
    int trackerID;   // tracker ID
    int state;       // tracker state
    float S_hat[4];  // state vector is [x,y, vx, vy]
    float xSize;     //  size in x direction
    float ySize;     // size in y direction

    trackerOutputDataType() : trackerID(0), state(0), S_hat{0.0f, 0.0f, 0.0f, 0.0f}, xSize(0.0f), ySize(0.0f) {}
};

class trackerOutput {
  public:
    // int totalNumOfOutput;
    // trackerOutputDataType* outputInfo;
    std::vector<trackerOutputDataType> outputInfo;
};


struct BBox
{
    float x;
    float y;
    float width;
    float height;

    BBox(float x_ = 0.0f, float y_ = 0.0f, float width_ = 0.0f, float height_ = 0.0f) : x(x_), y(y_), width(width_), height(height_) {}
};

/*************************************************************************************************
 * @brief Radar-Media fusion processing related meta data: coordinateTransformationOutput
 *************************************************************************************************/
class coordinateTransformationOutput {
  public:
    std::vector<hva::hvaROI_t> m_cameraRois;
    std::vector<trackerOutputDataType> m_radarOutput;

    std::vector<BBox> m_cameraRadarCoords;
    std::vector<std::vector<uint8_t>> m_isAssociated;
    std::vector<int32_t> m_radarAssociatedCameraIndex;

  public:
    using Ptr = std::shared_ptr<coordinateTransformationOutput>;

    coordinateTransformationOutput() {}

    coordinateTransformationOutput(size_t cameraSize, size_t radarSize, std::vector<hva::hvaROI_t> &rois, std::vector<trackerOutputDataType> &radarOutput)
        : m_cameraRois(rois), m_radarOutput(radarOutput)
    {
        if (0 != cameraSize && 0 != radarSize) {
            std::vector<uint8_t> temp(cameraSize, 0);
            m_isAssociated.resize(radarSize, temp);
            m_radarAssociatedCameraIndex.resize(radarSize, -1);
        }
    }

    ~coordinateTransformationOutput() {}

    void setValue(float x, float y, float width, float height)
    {
        BBox box(x, y, width, height);
        // for camera radar coordinates
        m_cameraRadarCoords.push_back(std::move(box));
    }
};
struct DetectedObject
{
    BBox bbox;  // can be camera pixel roi or bev roi
    float confidence = 0.0f;
    std::string label = "";

    DetectedObject() : bbox(), confidence(0.0f), label("dummy") {}

    DetectedObject(const BBox &bbox_, float confidence_ = 0.0f, const std::string &label_ = "dummy") : bbox(bbox_), confidence(confidence_), label(label_) {}
};

struct FusionBBox
{
    trackerOutputDataType radarOutput;  // radar output
    DetectedObject det;                 // corresponding camera detections after fusion, no value if no corresponding camera detections
    FusionBBox() : radarOutput(), det() {}
};

class FusionOutput {
  public:
    int32_t m_numOfCams;
    std::vector<std::vector<hva::hvaROI_t>> m_cameraRois;  // original camera roi
    std::vector<std::vector<BBox>> m_cameraRadarCoords;    // the radar roi of corresponding camera detections
    std::vector<trackerOutputDataType> m_radarOutput;      // original radar output

    std::vector<DetectedObject> m_cameraFusionRadarCoords;      // the radar coordinates of fusion camera detections
    std::vector<int8_t> m_cameraFusionRadarCoordsIsAssociated;  // whether the radar coordinates of fusion camera detections is associated with radar
    std::vector<FusionBBox> m_fusionBBox;                       // final radar&camera fusion results

  public:
    using Ptr = std::shared_ptr<FusionOutput>;

    FusionOutput(int32_t numOfCams) : m_numOfCams(numOfCams)
    {
        m_cameraRois.resize(m_numOfCams);
        m_cameraRadarCoords.resize(m_numOfCams);
    }

    FusionOutput() : m_numOfCams(1)
    {
        m_cameraRois.resize(m_numOfCams);
        m_cameraRadarCoords.resize(m_numOfCams);
    }

    void addCameraROI(int32_t cameraID, std::vector<hva::hvaROI_t> &rois, std::vector<BBox> &bbox)
    {
        m_cameraRois[cameraID] = rois;
        m_cameraRadarCoords[cameraID] = bbox;
    }

    void setCameraFusionRadarCoords(std::vector<DetectedObject> &cameraFusionRadarCoords)
    {
        m_cameraFusionRadarCoords = cameraFusionRadarCoords;
        m_cameraFusionRadarCoordsIsAssociated.resize(cameraFusionRadarCoords.size());
        for (int32_t i = 0; i < cameraFusionRadarCoords.size(); ++i) {
            m_cameraFusionRadarCoordsIsAssociated[i] = 0;
        }
    }

    void setRadarOutput(std::vector<trackerOutputDataType> &radarOutput)
    {
        m_radarOutput = radarOutput;
    }

    void addRadarFusionBBox(FusionBBox &fusionBBox)
    {
        m_fusionBBox.push_back(fusionBBox);
    }

    ~FusionOutput() {}
};


}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_RADAR_DATABASE_META_HPP

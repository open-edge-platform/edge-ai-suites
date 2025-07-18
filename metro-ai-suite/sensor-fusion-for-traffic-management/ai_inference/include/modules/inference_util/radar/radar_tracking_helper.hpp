/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2021-2023 Intel Corporation.
 *
 * This software and the related documents are Intel copyrighted materials, and
 * your use of them is governed by the express license under which they were
 * provided to you (License). Unless the License provides otherwise, you may not
 * use, modify, copy, publish, distribute, disclose or transmit this software or
 * the related documents without Intel's prior written permission.
 *
 * This software and the related documents are provided as is, with no express
 * or implied warranties, other than those that are expressly stated in the
 * License.
 */

#ifndef HCE_AI_INF_RADAR_TRACKING_HELPER_HPP
#define HCE_AI_INF_RADAR_TRACKING_HELPER_HPP

#include <algorithm>
#include "inc/api/hvaLogger.hpp"
// #include "modules/inference_util/radar/radar_detection_helper.hpp"
#include "modules/inference_util/radar/radar_clustering_helper.hpp"
#include "nodes/radarDatabaseMeta.hpp"

#define CT_MAX_NUM_TRACKER       (64)  // be multiple of 8
#define CT_MAX_NUM_CLUSTER       (24)  // be multiple of 8

#define CT_MAX_NUM_ASSOC         (6)
#define CT_MAX_NUM_EXPIRE        (16)
// #define CT_MAX_DIST              (10000000000.f)
#define CT_MAX_DIST              MAXFLOAT

#define CLUSTERTRACKER_PIOVER180 (3.141592653589793 / 180.0)  //!< define the pi/180
#define CLUSTERTRACKER_PI        (3.141592653589793f)         //!< define pi

namespace hce {

namespace ai {

namespace inference {

using trackerInput = clusteringDBscanOutput;

using trackerInputDataType = clusteringDBscanReport;

// struct trackerOutput
// {
//     int totalNumOfOutput;
//     trackerOutputDataType *outputInfo;
// };

// struct trackerOutputDataType
// {
//     int trackerID;   // tracker ID
//     int state;       // tracker state
//     float S_hat[4];  // state vector is [x,y, vx, vy]
//     float xSize;     //  size in x direction
//     float ySize;     // size in y direction
// };

/*************************************************************************************************
 * @brief  Error code for tracking module.
 *************************************************************************************************/
typedef enum {
    CLUSTERTRACKER_NO_ERROR = 0,               /**< no error */
    CLUSTERTRACKER_FAIL_ALLOCATE_HANDLE,       /**< clusterTracker_create failed to allocate handle */
    CLUSTERTRACKER_FAIL_ALLOCATE_LOCALINSTMEM, /**< clusterTracker_create failed to allocate memory for buffers in local instance */
    CLUSTERTRACKER_FAIL_ALLOCATE_TRACKER,      /**< clusterTracker_run failed to allocate new trackers  */
    CLUSTERTRACKER_INOUTPTR_NOTCORRECT,        /**< input and/or output buffer for clusterTracker_run are either NULL, or not aligned properly  */
    CLUSTERTRACKER_NUM_TRACKER_EXCEED_MAX,     /**< the number of tracker exceed the max value */
    CLUSTERTRACKER_NUM_ASSOC_EXCEED_MAX,       /**< the number of measure association exceed the max value */
    CLUSTERTRACKER_INPUT_EXCEED_MAX            /**< the number of input exceed the max value */
} clusterTrackerErrorCode;


typedef enum { TRACKER_STATE_EXPIRE, TRACKER_STATE_DETECTION, TRACKER_STATE_ACTIVE } clusterTrackerState;

typedef struct trackerInputInternalDataType_
{
    int numPoints;    /**< Number of samples in this cluster */
    float range;      /**< cluster center location in range direction.*/
    float azimuth;    /**< cluster center location in angle .*/
    float doppler;    /**< averge doppler of the cluster.*/
    float xSize;      /**< max distance of point from cluster center in x direction.*/
    float ySize;      /**< max distance of point from cluster center in y direction.*/
    float rangeVar;   /**< variance of the range estimation */
    float angleVar;   /**< variance of the angle estimation */
    float dopplerVar; /**< variance of the doppler estimation */
} trackerInputInternalDataType;

/*************************************************************************************************
 * @brief  Internal structure for each tracker
 *************************************************************************************************/
typedef struct trackerInternalDataType_
{
    clusterTrackerState state; /**< tracker state.*/
    int detect2activeCount;
    int detect2freeCount;
    int active2freeCount;
    int activeThreshold;
    int forgetThreshold;
    float S_hat[4]; /**< state vector is [x, y, vx, vy].*/
    float P[16];
    float C[9];
    float P_apriori[16];
    float S_apriori_hat[4];
    float H_s_apriori_hat[3];
    float speed2;    /**< speed in amplitude square: vx^2 + vy^2  */
    float doppler;   /**< average doppler for all the associated points/clusters */
    float xSize;     /**< xSize after IIR filtering */
    float ySize;     /**< ySize after IIR filtering */
    float diagonal2; /**< diagnonal square for this tracker */
} trackerInternalDataType;


typedef struct trackerListElement_
{
    int tid;
    // trackerListElement *next;
    void *next;
} trackerListElement;


typedef struct trackerList_
{
    int size;
    trackerListElement *first;
    trackerListElement *last;
} trackerList;


/*************************************************************************************************
 * @brief  Structure element of the list of descriptors for UL allocations.
 *************************************************************************************************/
struct clusterTrackerHandle
{
    float trackerAssociationThreshold;
    int trackerActiveThreshold;
    int trackerForgetThreshold;
    // int fxInputScalar;
    float measurementNoiseVariance;
    float iirForgetFactor;
    float Q[16];                              // 4x4
    float F[16];                              // 4x4
    trackerListElement *trackerElementArray;  //[CT_MAX_NUM_TRACKER];
    // std::vector<trackerListElement> trackerElementArray;  //[CT_MAX_NUM_TRACKER];
    trackerList idleTrackerList;
    trackerList activeTrackerList;
    // std::vector<int> associatedList;               //[CT_MAX_NUM_TRACKER * CT_MAX_NUM_ASSOC];
    // std::vector<int> pendingIndication;            //[CT_MAX_NUM_TRACKER];
    // std::vector<trackerInternalDataType> tracker;  //[CT_MAX_NUM_TRACKER];
    int *associatedList;               //[CT_MAX_NUM_TRACKER * CT_MAX_NUM_ASSOC];
    int *pendingIndication;            //[CT_MAX_NUM_TRACKER];
    trackerInternalDataType *tracker;  //[CT_MAX_NUM_TRACKER];
    char *scratchPad;
    // float scratchPad[96];
    int numOfInputMeasure;
    // std::vector<trackerInputInternalDataType> inputInfo;
    // std::vector<int> numAssoc;
    // std::vector<float> dist;  // pointer to the distance matrix
    trackerInputInternalDataType *inputInfo;
    int *numAssoc;
    float *dist;  // pointer to the distance matrix
};

void tracker_matrixMultiply(int m1, int m2, int m3, float *A, float *B, float *C);

void tracker_matrixConjugateMultiply(int m1, int m2, int m3, float *A, float *B, float *C);

void tracker_matrixAdd(int dim, float *A, float *B, float *C);

void tracker_matrixSub(int dim, float *A, float *B, float *C);

void tracker_computeH(float *S, float *H);

void clusterTracker_distCalc(trackerInputInternalDataType *measureInfo, trackerInternalDataType *tracker, float *dist);

float clusterTracker_associateThresholdCalc(float presetTH, trackerInternalDataType *tracker);

void clusterTracker_combineMeasure(trackerInputInternalDataType *inputInfo,
                                   //  std::vector<trackerInputInternalDataType> &inputInfo,
                                   int *associatedList,
                                   int numAssoc,
                                   trackerInputInternalDataType *combinedInput);

float clusterTracker_IIRFilter(float yn, float xn, float forgetFactor);

void clusterTracker_computeCartesian(float *H, float *S);

void clusterTracker_computeJacobian(float *S, float *J);

void tracker_cholesky3(float *A, float *G);

void cluster_matInv3(float *A, float *Ainv);

void clusterTracker_kalmanUpdate(trackerInternalDataType *tracker,
                                 trackerInputInternalDataType *combinedInput,
                                 float *F,
                                 float *Q,
                                 float *R,
                                 float *scratchPad);

void clusterTracker_kalmanUpdateWithNoMeasure(trackerInternalDataType *tracker, float *F, float *Q);


class ClusterTracker {
  public:
    ClusterTracker();

    ~ClusterTracker();

  public:
    clusterTrackerHandle *m_handle;

    /**
     * @brief Create and initialize ClusterTracker module.
     * @param param RadarTrackingConfig
     * @return Error Code
     */
    clusterTrackerErrorCode clusterTrackerCreate(RadarTrackingConfig *param);

    /**
     * @brief associate the input points/cluster with tracker and allocate new tracker / merge trackers/delete trackers if neccessary.
     * @param input Pointer to the points/cluster input info.
     * @param output Pointer to the tracker output info.
     * @return Error Code
     */
    clusterTrackerErrorCode clusterTrackerRun(trackerInput *input, float dt, trackerOutput *output);

  private:
    /**
     * @brief Delete ClusterTracker module.
     */
    void clusterTrackerDelete();

    /**
     * @brief
     * @param dt Update the state transition matrix F according to the new elapsed time, Time is measured in seconds.
     */
    void clusterTracker_updateFQ(float dt);

    void clusterTrackerList_init();

    int clusterTrackerList_addToList();

    void clusterTrackerList_removeFromList(int listId);

    void clusterTracker_timeUpdateTrackers();

    clusterTrackerErrorCode clusterTracker_associateTrackers();
    clusterTrackerErrorCode clusterTracker_associateTrackersKM();

    clusterTrackerErrorCode clusterTracker_allocateNewTrackers();

    void clusterTracker_updateTrackerStateMachine(trackerInternalDataType *tracker, bool hitFlag);

    void clusterTracker_updateTrackers(float *scratchPad);

    void clusterTracker_reportTrackers(trackerOutput *output);

    void clusterTracker_inputDataTransfer(int numCluster,
                                          // int scale,
                                          std::vector<trackerInputDataType> &inputInfo,
                                          // std::vector<trackerInputInternalDataType> &internalInputInfo
                                          trackerInputInternalDataType *internalInputInfo);
};

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_RADAR_TRACKING_HELPER_HPP

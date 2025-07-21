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

#include "modules/inference_util/radar/radar_tracking_helper.hpp"

#include "modules/inference_util/radar/hungarian_optimizer.hpp"
#include <cmath>

namespace hce {

namespace ai {

namespace inference {

ClusterTracker::ClusterTracker()
{
    // clusterTrackerErrorCode errorCode = clusterTrackerCreate(param);
    // if (errorCode != CLUSTERTRACKER_NO_ERROR) {
    //     HVA_ERROR("Create ClusterTracker Instance Failed!");
    // }
}

ClusterTracker::~ClusterTracker()
{
    clusterTrackerDelete();
}

clusterTrackerErrorCode ClusterTracker::clusterTrackerCreate(RadarTrackingConfig *param)
{
    // clusterTrackerHandle *m_handle;
    int index;

    clusterTrackerErrorCode errorCode = CLUSTERTRACKER_NO_ERROR;

    // m_handle = (clusterTrackerHandle *)radarOsal_memAlloc((uint8_t)RADARMEMOSAL_HEAPTYPE_LL2, 0, sizeof(clusterTrackerHandle), 1);
    m_handle = (clusterTrackerHandle *)aligned_alloc(8, sizeof(clusterTrackerHandle));
    if (m_handle == nullptr) {
        errorCode = CLUSTERTRACKER_FAIL_ALLOCATE_HANDLE;
        return errorCode;
    }
    // initialized with configuration structure
    m_handle->trackerAssociationThreshold = param->trackerAssociationThreshold;
    m_handle->trackerActiveThreshold = param->trackerActiveThreshold;
    m_handle->trackerForgetThreshold = param->trackerForgetThreshold;
    m_handle->measurementNoiseVariance = param->measurementNoiseVariance;
    m_handle->iirForgetFactor = param->iirForgetFactor;
    // m_handle->fxInputScalar = param->fxInputScalar;

    // memory allocation
    // m_handle->trackerElementArray.resize(CT_MAX_NUM_TRACKER);
    m_handle->trackerElementArray = (trackerListElement *)aligned_alloc(8, CT_MAX_NUM_TRACKER * sizeof(trackerListElement));
    if (m_handle->trackerElementArray == nullptr) {
        errorCode = CLUSTERTRACKER_FAIL_ALLOCATE_LOCALINSTMEM;
        return errorCode;
    }

    // m_handle->tracker.resize(CT_MAX_NUM_TRACKER);
    m_handle->tracker = (trackerInternalDataType *)aligned_alloc(8, CT_MAX_NUM_TRACKER * sizeof(trackerInternalDataType));
    if (m_handle->tracker == nullptr) {
        errorCode = CLUSTERTRACKER_FAIL_ALLOCATE_LOCALINSTMEM;
        return errorCode;
    }

    // m_handle->pendingIndication.resize(CT_MAX_NUM_TRACKER, 1);
    // m_handle->associatedList.resize(CT_MAX_NUM_TRACKER * CT_MAX_NUM_ASSOC, -1);
    // m_handle->numAssoc.resize(CT_MAX_NUM_TRACKER, 0);
    // m_handle->dist.resize(CT_MAX_NUM_TRACKER * CT_MAX_NUM_CLUSTER, CT_MAX_DIST);
    // m_handle->inputInfo.resize(CT_MAX_NUM_CLUSTER);

    // scratchPad allocation for memory reuse cross different modules
    index = CT_MAX_NUM_TRACKER * sizeof(int);                            // PENDING indication
    index += CT_MAX_NUM_TRACKER * CT_MAX_NUM_ASSOC * sizeof(int);        // associateList
    index += CT_MAX_NUM_TRACKER * sizeof(int);                           // numAssoc
    index += CT_MAX_NUM_TRACKER * CT_MAX_NUM_CLUSTER * sizeof(float);    // distance
    index += CT_MAX_NUM_CLUSTER * sizeof(trackerInputInternalDataType);  // inputInfo
    index += 96 * sizeof(float);                                         // for 6 internal temp matrix operation
    m_handle->scratchPad = (char *)aligned_alloc(8, index);
    if (m_handle->scratchPad == nullptr) {
        errorCode = CLUSTERTRACKER_FAIL_ALLOCATE_LOCALINSTMEM;
        return errorCode;
    }

    // initialized the trackerList
    clusterTrackerList_init();

    return errorCode;
}

void ClusterTracker::clusterTrackerDelete()
{
    free(m_handle->trackerElementArray);
    free(m_handle->tracker);
    free(m_handle->scratchPad);
    free(m_handle);
    // radarOsal_memFree(m_handle->trackerElementArray, CT_MAX_NUM_TRACKER * sizeof(trackerListElement));
    // radarOsal_memFree(m_handle->tracker, CT_MAX_NUM_TRACKER * sizeof(trackerInternalDataType));
    // radarOsal_memFree(m_handle->scratchPad, 2 * CT_MAX_NUM_ASSOC * CT_MAX_NUM_TRACKER * sizeof(int));
    // radarOsal_memFree(m_handle, sizeof(clusterTrackerHandle));
}

clusterTrackerErrorCode ClusterTracker::clusterTrackerRun(trackerInput *input, float dt, trackerOutput *output)
{
    // int index;
    int nTrack, i;
    clusterTrackerErrorCode errorCode = CLUSTERTRACKER_NO_ERROR;

    m_handle->numOfInputMeasure = input->numCluster;

    if (input->numCluster > CT_MAX_NUM_CLUSTER)
        return CLUSTERTRACKER_INPUT_EXCEED_MAX;

    if ((input->report.size() == 0) && (input->numCluster > 0))
        errorCode = CLUSTERTRACKER_INOUTPTR_NOTCORRECT;
    if (output == nullptr)
        errorCode = CLUSTERTRACKER_INOUTPTR_NOTCORRECT;
    if (m_handle->scratchPad == nullptr)
        errorCode = CLUSTERTRACKER_INOUTPTR_NOTCORRECT;
    if (errorCode > CLUSTERTRACKER_NO_ERROR)
        return errorCode;

    // Create measurements initialize pendingIndication, associationList, numAssoc and distance matrix
    // for (i = 0; i < CT_MAX_NUM_TRACKER; i++)
    //     m_handle->pendingIndication[i] = 1;
    // for (i = 0; i < CT_MAX_NUM_TRACKER * CT_MAX_NUM_ASSOC; i++)
    //     m_handle->associatedList[i] = -1;
    // for (i = 0; i < CT_MAX_NUM_TRACKER; i++)
    //     m_handle->numAssoc[i] = 0;
    // nTrack = m_handle->activeTrackerList.size;
    // for (i = 0; i < input->numCluster * nTrack; i++)
    //     m_handle->dist[i] = CT_MAX_DIST;

    int index = 0;
    m_handle->pendingIndication = (int *)&m_handle->scratchPad[index];
    for (i = 0; i < CT_MAX_NUM_TRACKER; i++)
        m_handle->pendingIndication[i] = 1;
    index += CT_MAX_NUM_TRACKER * sizeof(int);

    m_handle->associatedList = (int *)&m_handle->scratchPad[index];
    for (i = 0; i < CT_MAX_NUM_TRACKER * CT_MAX_NUM_ASSOC; i++)
        m_handle->associatedList[i] = -1;
    index += CT_MAX_NUM_TRACKER * CT_MAX_NUM_ASSOC * sizeof(int);

    m_handle->numAssoc = (int *)&m_handle->scratchPad[index];
    for (i = 0; i < CT_MAX_NUM_TRACKER; i++)
        m_handle->numAssoc[i] = 0;
    index += CT_MAX_NUM_TRACKER * sizeof(int);

    m_handle->dist = (float *)&m_handle->scratchPad[index];
    nTrack = m_handle->activeTrackerList.size;
    for (i = 0; i < input->numCluster * nTrack; i++)
        m_handle->dist[i] = CT_MAX_DIST;
    index += CT_MAX_NUM_TRACKER * CT_MAX_NUM_CLUSTER * sizeof(float);

    m_handle->inputInfo = (trackerInputInternalDataType *)&m_handle->scratchPad[index];
    index += CT_MAX_NUM_CLUSTER * sizeof(trackerInputInternalDataType);

    clusterTracker_inputDataTransfer(input->numCluster,
                                     //  m_handle->fxInputScalar,
                                     input->report, m_handle->inputInfo);
    clusterTracker_updateFQ(dt);
    clusterTracker_timeUpdateTrackers();  // compute S_apriori_hat and H_s_apriori_hat in activeTrackerList
    if (input->numCluster > 0) {
        errorCode = clusterTracker_associateTrackers();
        if (errorCode > CLUSTERTRACKER_NO_ERROR)
            return errorCode;

        errorCode = clusterTracker_allocateNewTrackers();
        if (errorCode > CLUSTERTRACKER_NO_ERROR)
            return errorCode;
    }

    clusterTracker_updateTrackers((float *)&m_handle->scratchPad[index]);
    clusterTracker_reportTrackers(output);
    return errorCode;
}


void ClusterTracker::clusterTracker_updateFQ(float dt)
{
    int i;
    // initialize F and Q
    // float F[16] = {
    //	1, 0, dt, 0,
    //	0, 1, 0, dt,
    //	0, 0, 1, 0 ,
    //	0, 0, 0, 1};

    // float d = 1.0;
    float c = (float)(dt * dt * 4.0);  // (dt*2)^2 *d
    float b = (float)(c * dt * 2);     // (dt*2)^3 *d
    float a = (float)(c * c);          // (dt*2)^4 *d

    //! TODO: which way to update Q matrix, above or below
    //! see reference: https://github.com/Hyagoro/Extended_Kalman_Filter/blob/master/src/FusionEKF.cpp#L120
    //! see reference: https://github.com/mdemirst/Extended-Kalman-Filter/blob/master/src/ekf_radar.cpp#L28
    // float c = dt * dt;     // dt^2
    // float b = c * dt / 2;  // (dt^3) / 2
    // float a = c * c / 4;   // (dt^4) / 4

    // float Q[16] = {
    //	a, 0, b, 0,
    //	0, a, 0, b,
    //	b, 0, c, 0,
    //	0, b, 0, c};
    for (i = 0; i < 16; i++) {
        m_handle->F[i] = 0;
        m_handle->Q[i] = 0;
    }
    m_handle->F[0] = 1;
    m_handle->F[2] = dt;
    m_handle->F[5] = 1;
    m_handle->F[7] = dt;
    m_handle->F[10] = 1;
    m_handle->F[15] = 1;

    m_handle->Q[0] = a;
    m_handle->Q[2] = b;
    m_handle->Q[5] = a;
    m_handle->Q[7] = b;
    m_handle->Q[8] = b;
    m_handle->Q[10] = c;
    m_handle->Q[13] = b;
    m_handle->Q[15] = c;
}

void ClusterTracker::clusterTrackerList_init()
{
    int i;

    // initialize the idle and active tracker list
    m_handle->activeTrackerList.size = 0;
    m_handle->activeTrackerList.first = nullptr;
    m_handle->activeTrackerList.last = nullptr;
    m_handle->idleTrackerList.size = CT_MAX_NUM_TRACKER;
    m_handle->idleTrackerList.first = &m_handle->trackerElementArray[0];
    m_handle->idleTrackerList.last = &m_handle->trackerElementArray[CT_MAX_NUM_TRACKER - 1];
    for (i = 1; i < CT_MAX_NUM_TRACKER; i++)
        m_handle->trackerElementArray[i - 1].next = &m_handle->trackerElementArray[i];
    for (i = 0; i < CT_MAX_NUM_TRACKER; i++)
        m_handle->trackerElementArray[i].tid = i;
}

int ClusterTracker::clusterTrackerList_addToList()
{
    int tid;
    trackerListElement *firstPointer, *nextPointer;
    m_handle->activeTrackerList.size++;
    firstPointer = m_handle->idleTrackerList.first;
    nextPointer = (trackerListElement *)(firstPointer->next);
    tid = firstPointer->tid;
    firstPointer->next = m_handle->activeTrackerList.first;
    m_handle->activeTrackerList.first = firstPointer;
    // m_handle->activeTrackerList.last->next = firstPointer;
    // m_handle->activeTrackerList.last = firstPointer;
    // m_handle->activeTrackerList.last->next = nullptr;
    m_handle->idleTrackerList.size--;
    m_handle->idleTrackerList.first = nextPointer;
    // debug zg:
    // printf("Tracker %d allocated", tid);
    return (tid);
}

void ClusterTracker::clusterTrackerList_removeFromList(int listId)
{
    int i;
    trackerListElement *cand, *oldLast, *newLast;
    if (listId == 0) {
        newLast = m_handle->activeTrackerList.first;
        m_handle->activeTrackerList.first = (trackerListElement *)(newLast->next);
    }
    else {
        cand = m_handle->activeTrackerList.first;
        for (i = 0; i < (listId - 1); i++)
            cand = (trackerListElement *)(cand->next);
        newLast = (trackerListElement *)(cand->next);
        cand->next = newLast->next;
    }
    m_handle->activeTrackerList.size--;

    m_handle->idleTrackerList.size++;
    oldLast = m_handle->idleTrackerList.last;
    oldLast->next = newLast;
    newLast->next = NULL;
    m_handle->idleTrackerList.last = newLast;
    // debug zg:
    // printf("Tracker %d released", newLast->tid);
}

void ClusterTracker::clusterTracker_timeUpdateTrackers()
{
    int i, tid;
    int numTracker = m_handle->activeTrackerList.size;
    trackerListElement *tElem;
    trackerInternalDataType *tracker;
    tElem = m_handle->activeTrackerList.first;
    for (i = 0; i < numTracker; i++) {
        tid = tElem->tid;
        tracker = &m_handle->tracker[tid];
        // Prediction based on state equation
        tracker_matrixMultiply(4, 4, 1, m_handle->F, tracker->S_hat, tracker->S_apriori_hat);  // x'=fx+u, Sapr(n) =Fs(n-1) compute S_apriori_hat

        // convert from spherical to Cartesian coordinates
        tracker_computeH(tracker->S_apriori_hat, tracker->H_s_apriori_hat);
        tElem = (trackerListElement *)(tElem->next);
    }
}

clusterTrackerErrorCode ClusterTracker::clusterTracker_associateTrackers()
{
    uint32_t nTrack = m_handle->activeTrackerList.size;
    uint32_t nMeas = m_handle->numOfInputMeasure;
    uint32_t mid, n, j, tid, index, minTid, len, assocIndex, minMid;
    float minDist, distTH, dist;
    float *distPtr;
    trackerListElement *tElem;
    trackerInternalDataType *tracker;
    clusterTrackerErrorCode errorCode;
    bool hitFlag;

    errorCode = CLUSTERTRACKER_NO_ERROR;
    // Apply association only if both trackerList and number of measurement are nonZero
    if ((nMeas > 0) && (nTrack > 0)) {
        index = 0;
        for (mid = 0; mid < nMeas; mid++) {
            tElem = m_handle->activeTrackerList.first;
            // calculate the distance from one measure to all the trackers
            // record the min dist, and associate index
            minDist = CT_MAX_DIST;
            for (j = 0; j < nTrack; j++) {
                tid = tElem->tid;
                // HVA_DEBUG("tid: %d, minTid: %d", tid, minTid);
                tracker = &m_handle->tracker[tid];
                distPtr = &m_handle->dist[index + j];
                clusterTracker_distCalc(&m_handle->inputInfo[mid], tracker, distPtr);
                if ((*distPtr) < minDist) {
                    minDist = (*distPtr);
                    // minTrackListIndex = j;
                    minTid = tid;
                    // HVA_DEBUG("tid: %d, minTid: %d", tid, minTid);
                }
                tElem = (trackerListElement *)(tElem->next);
            }
            // compare minDist with threshold
            // HVA_DEBUG("tid: %d, minTid: %d", tid, minTid);
            // HVA_DEBUG("xSize,ySize:(%f,%f)", m_handle->tracker[minTid].xSize, m_handle->tracker[minTid].ySize);
            // HVA_DEBUG("minDist is %f", minDist);
            distTH = clusterTracker_associateThresholdCalc(m_handle->trackerAssociationThreshold, &m_handle->tracker[minTid]);
            // distTH =0;
            if (minDist < distTH) {
                len = m_handle->numAssoc[minTid];
                assocIndex = minTid * CT_MAX_NUM_ASSOC + len;
                // add to the association list
                m_handle->associatedList[assocIndex] = mid;
                m_handle->numAssoc[minTid]++;
                // remove from pending Indication list
                m_handle->pendingIndication[mid] = 0;
                // error protection
                if (m_handle->numAssoc[minTid] >= CT_MAX_NUM_ASSOC) {
                    errorCode = CLUSTERTRACKER_NUM_ASSOC_EXCEED_MAX;
                    return (errorCode);
                }
            }
            index = index + nTrack;
        }  // for nMeas



    }  // if
    return errorCode;
}

// KM algorithm for multiple objects detection
clusterTrackerErrorCode ClusterTracker::clusterTracker_associateTrackersKM()
{
    size_t nTrack = m_handle->activeTrackerList.size;
    size_t nMeas = m_handle->numOfInputMeasure;
    size_t mid, n, j, tid, index, minTid, len, assocIndex, minMid;
    float minDist, distTH, dist;
    float *distPtr;
    trackerListElement *tElem;
    trackerInternalDataType *tracker;
    clusterTrackerErrorCode errorCode;
    bool hitFlag;

    errorCode = CLUSTERTRACKER_NO_ERROR;

   if ((nMeas > 0) && (nTrack > 0)) {
    std::vector<std::vector<float>> costMatrix(nMeas, std::vector<float>(nTrack, 0));

    for (size_t mid = 0; mid < nMeas; mid++) {
        tElem = m_handle->activeTrackerList.first;
        for (size_t j = 0; j < nTrack; j++) {
            tracker = &m_handle->tracker[tElem->tid];
            float dist;
            clusterTracker_distCalc(&m_handle->inputInfo[mid], tracker, &dist);
            costMatrix[mid][j] = dist;
            tElem = (trackerListElement *)(tElem->next);
        }
    }
    HungarianOptimizer<float> optimizer;
    std::vector<std::pair<size_t, size_t>> assignments;
    // std::vector<int> assignments;
    UpdateCosts(costMatrix, optimizer.costs());
    optimizer.Minimize(&assignments);

    for(size_t mid=0;mid < nMeas; mid++){

        for(auto &item:assignments){
            if(item.first == mid){
                minTid = item.second;
                len = m_handle->numAssoc[item.second];
                assocIndex = item.second * CT_MAX_NUM_ASSOC + len;
                // add to the association list
                m_handle->associatedList[assocIndex] = mid;
                m_handle->numAssoc[item.second]++;
                // remove from pending Indication list
                m_handle->pendingIndication[mid] = 0;
                // error protection
                if (m_handle->numAssoc[item.second] >= CT_MAX_NUM_ASSOC) {
                    errorCode = CLUSTERTRACKER_NUM_ASSOC_EXCEED_MAX;
                    return (errorCode);
                }
            }
        }
    }

   }
    return errorCode;
}

clusterTrackerErrorCode ClusterTracker::clusterTracker_allocateNewTrackers()
{
    // int nTrack = m_handle->activeTrackerList.size;
    int nMeas = m_handle->numOfInputMeasure;
    int i, j, mid, tid;
    clusterTrackerErrorCode errorCode;
    trackerInternalDataType *tracker;
    trackerInputInternalDataType *inputPoint;
    float H[3];

    errorCode = CLUSTERTRACKER_NO_ERROR;
    for (mid = 0; mid < nMeas; mid++) {
        if (m_handle->pendingIndication[mid] == 1) {
            if (m_handle->idleTrackerList.size > 0) {
                tid = clusterTrackerList_addToList();
                tracker = &m_handle->tracker[tid];
                inputPoint = &m_handle->inputInfo[mid];
                tracker->state = TRACKER_STATE_DETECTION;
                tracker->detect2activeCount = 0;
                tracker->detect2freeCount = 0;
                tracker->active2freeCount = 0;
                tracker->activeThreshold = m_handle->trackerActiveThreshold;
                tracker->forgetThreshold = m_handle->trackerForgetThreshold;
                tracker->xSize = inputPoint->xSize;
                tracker->ySize = inputPoint->ySize;
                tracker->diagonal2 = inputPoint->xSize * inputPoint->xSize + inputPoint->ySize * inputPoint->ySize;
                tracker->speed2 = inputPoint->doppler * inputPoint->doppler;
                tracker->doppler = inputPoint->doppler;

                // may add the debug print out for new tracker allocation
                m_handle->pendingIndication[mid] = 0;
                // m_handle->associatedList[tid * CT_MAX_NUM_ASSOC] = mid;
                // m_handle->numAssoc[tid] = 1;

                // Initialization S_hat, P
                H[0] = inputPoint->range;
                H[1] = inputPoint->azimuth;
                H[2] = inputPoint->doppler;
                clusterTracker_computeCartesian(H, tracker->S_hat);
                // obj.P(:,:,id) = diag(ones(1,obj.pStateVectorLength));
                for (i = 0; i < 4; i++) {
                    for (j = 0; j < 4; j++)
                        tracker->P[i * 4 + j] = 0;
                    tracker->P[i * 4 + i] = 1;
                }

                for (i = 0; i < 3; i++) {
                    for (j = 0; j < 3; j++)
                        tracker->C[i * 3 + j] = 0;
                    tracker->C[i * 3 + i] = 1;
                }
                tracker_matrixMultiply(4, 4, 1, m_handle->F, tracker->S_hat, tracker->S_apriori_hat);  // compute S_apriori_hat
                tracker_computeH(tracker->S_apriori_hat, tracker->H_s_apriori_hat);
            }
            else
                errorCode = CLUSTERTRACKER_FAIL_ALLOCATE_TRACKER;
        }
    }

    return errorCode;
}

void ClusterTracker::clusterTracker_updateTrackerStateMachine(trackerInternalDataType *tracker, bool hitFlag)
{
    switch (tracker->state) {
        case TRACKER_STATE_DETECTION:
            if (hitFlag) {
                tracker->detect2freeCount = 0;
                if (tracker->detect2activeCount > tracker->activeThreshold)
                    tracker->state = TRACKER_STATE_ACTIVE;
                else
                    tracker->detect2activeCount++;
            }
            else {
                if (tracker->detect2freeCount > tracker->forgetThreshold)
                    tracker->state = TRACKER_STATE_EXPIRE;
                else
                    tracker->detect2freeCount++;
                if (tracker->detect2activeCount > 0)
                    tracker->detect2activeCount--;
            }
            break;

        case TRACKER_STATE_ACTIVE:
            if (hitFlag) {
                if (tracker->active2freeCount > 0)
                    tracker->active2freeCount--;
            }
            else {
                if (tracker->active2freeCount > tracker->forgetThreshold)
                    tracker->state = TRACKER_STATE_EXPIRE;
                else
                    tracker->active2freeCount++;
            }
            break;
    }
}

void ClusterTracker::clusterTracker_updateTrackers(float *scratchPad)
{
    float R[9] = {0, 0, 0, 0, 0, 0, 0, 0, 0};
    int nTrack = m_handle->activeTrackerList.size;
    int numExpireTracker = 0;
    int expireList[CT_MAX_NUM_EXPIRE];
    trackerListElement *tElem;
    trackerInternalDataType *tracker;
    trackerInputInternalDataType combinedInput;
    trackerInputInternalDataType *combinedInputPtr;
    int i, tid, mid, index;
    int j;
    float diag2;
    bool hitFlag;

    tElem = m_handle->activeTrackerList.first;
    // debug zg:
    // printf("\n");
    for (i = 0; i < nTrack; i++) {
        tid = tElem->tid;
        index = tid * CT_MAX_NUM_ASSOC;
        tracker = &m_handle->tracker[tid];
        // debug zg:
        // printf("associatedList[%d] = %d   ", index, m_handle->associatedList[index] + 1);

        if (m_handle->associatedList[index] > -1) {
            // there is some measurement associate with this tracker
            hitFlag = 1;
            clusterTracker_updateTrackerStateMachine(tracker, hitFlag);

            // calculate the new measure based on all the assocated measures, xSize and ySize will be set to the maximum xSize and ySize
            mid = m_handle->associatedList[index];
            combinedInputPtr = &m_handle->inputInfo[mid];
            if (m_handle->numAssoc[tid] > 0) {
                clusterTracker_combineMeasure(m_handle->inputInfo, &m_handle->associatedList[index], m_handle->numAssoc[tid], &combinedInput);
                combinedInputPtr = &combinedInput;
            }

            // construct R matrix
            R[0] = combinedInputPtr->rangeVar * m_handle->measurementNoiseVariance;
            R[4] = combinedInputPtr->angleVar * m_handle->measurementNoiseVariance;
            R[8] = combinedInputPtr->dopplerVar * m_handle->measurementNoiseVariance;

            // R[0] = combinedInputPtr->rangeVar * m_handle->measurementNoiseVariance*0.001;
            // R[4] = combinedInputPtr->angleVar * m_handle->measurementNoiseVariance*0.001;
            // R[8] = combinedInputPtr->dopplerVar * m_handle->measurementNoiseVariance*0.001;

            // update tracker->S_hat
            clusterTracker_kalmanUpdate(tracker, combinedInputPtr, m_handle->F, m_handle->Q, R, scratchPad);

            // update speed2 and doppler
            tracker->speed2 = tracker->S_hat[2] * tracker->S_hat[2] + tracker->S_hat[3] * tracker->S_hat[3];
            tracker->doppler = combinedInputPtr->doppler;

            // update xSize and ySize
            tracker->xSize = clusterTracker_IIRFilter(tracker->xSize, combinedInputPtr->xSize, m_handle->iirForgetFactor);
            tracker->ySize = clusterTracker_IIRFilter(tracker->ySize, combinedInputPtr->ySize, m_handle->iirForgetFactor);
            diag2 = tracker->xSize * tracker->xSize + tracker->ySize * tracker->ySize;
            if (diag2 > tracker->diagonal2)
                tracker->diagonal2 = diag2;
        }
        else {
            hitFlag = 0;
            clusterTracker_updateTrackerStateMachine(tracker, hitFlag);

            // consider free the tracker or do time update, if too much tracker needs to be released then wait for next time.
            if ((tracker->state == TRACKER_STATE_EXPIRE) && (numExpireTracker < (CT_MAX_NUM_EXPIRE - 1))) {
                // collect the free list and free at the end of the function;
                expireList[numExpireTracker] = i;
                numExpireTracker++;
            }
            else
                clusterTracker_kalmanUpdateWithNoMeasure(tracker, m_handle->F, m_handle->Q);
        }
        tElem = (trackerListElement *)(tElem->next);
    }
    // free the expired tracker
    for (j = numExpireTracker - 1; j >= 0; j--)
        clusterTrackerList_removeFromList(expireList[j]);
}

// bool ClusterTracker::IsConfirmed(trackerInternalDataType *tracker) const { return tracker->detect2activeCount > tracker->trackerActiveThreshold; }

void ClusterTracker::clusterTracker_reportTrackers(trackerOutput *output)
{
    int n, nTracker, tid;
    trackerListElement *tElem, *firstPointer, *tempHead;
    trackerInternalDataType *tracker, *othertracker;

    // merge tracker int activeTrackerList if they are too close

    // if (m_handle->activeTrackerList.size > 1)
    // {
    //     int main_tid, other_tid;
    //     firstPointer = m_handle->activeTrackerList.first;
    //     // for (auto iter = ++m_handle->activeTrackerList.first; iter != m_handle->activeTrackerList.last; )
       
    //     while (firstPointer!=nullptr && firstPointer->next != m_handle->activeTrackerList.last&&m_handle->activeTrackerList.size>1)
    //     {
    //         auto iter = firstPointer->next;
    //         main_tid = firstPointer->tid;
    //         tracker = &m_handle->tracker[main_tid];
    //         int next_listId = 1;

    //         while (iter!=nullptr&& iter != m_handle->activeTrackerList.last && firstPointer != m_handle->activeTrackerList.last&&m_handle->activeTrackerList.size>1)
    //         {
    //             trackerListElement *nextPointer, *newLast, *oldLast, *cand;
    //             nextPointer = (trackerListElement *)(iter);
    //             next_listId++;
    //             other_tid = nextPointer->tid;
    //             othertracker = &m_handle->tracker[other_tid];
    //             // calculate threshold
    //             if ((pow((tracker->S_hat[0] - othertracker->S_hat[0]), 2) + pow((tracker->S_hat[1] - othertracker->S_hat[1]), 2)) > 0 && (pow((tracker->S_hat[0] - othertracker->S_hat[0]), 2) + pow((tracker->S_hat[1] - othertracker->S_hat[1]), 2)) < 10)
    //             {
    //                 // merge tracker
    //                 // erase tracker in activeTrackerList
 
    //                 cand = m_handle->activeTrackerList.first;
    //                 // tElem =(trackerListElement*)cand->next;
    //                 for(auto i=0; i!=next_listId-2;i++){
    //                     cand =(trackerListElement*)cand->next;
    //                 }
    //                 newLast = (trackerListElement*)(cand->next);
    //                 cand->next = newLast->next;

    //                 m_handle->activeTrackerList.size--;

    //                 m_handle->idleTrackerList.size++;
    //                 oldLast =m_handle->idleTrackerList.last;
    //                 oldLast->next =newLast;
    //                 newLast->next =nullptr;
    //                 m_handle->idleTrackerList.last = newLast;
    //                 iter = nextPointer->next;

    //             }
    //             else{
    //                 iter = nextPointer->next;
    //             }
    //         }
    //         firstPointer = (trackerListElement *)(firstPointer->next);
    //     }
     
    // }

    nTracker = m_handle->activeTrackerList.size;
    if (nTracker > CT_MAX_NUM_TRACKER)
        nTracker = CT_MAX_NUM_TRACKER;

    output->outputInfo.resize(nTracker);

    tElem = m_handle->activeTrackerList.first;

    for (n = 0; n < nTracker; n++) {
        tid = tElem->tid;
        tracker = &m_handle->tracker[tid];
        // lack of tracker state check (TRACKER_STATE_ACTIVE)
        if (tracker->state == TRACKER_STATE_ACTIVE) {
          output->outputInfo[n].trackerID = tid;
          output->outputInfo[n].S_hat[0] = tracker->S_hat[0];
          output->outputInfo[n].S_hat[1] = tracker->S_hat[1];
          output->outputInfo[n].S_hat[2] = tracker->S_hat[2];
          output->outputInfo[n].S_hat[3] = tracker->S_hat[3];
          output->outputInfo[n].xSize = tracker->xSize;
          output->outputInfo[n].ySize = tracker->ySize;
          output->outputInfo[n].state = tracker->state;
          tElem = (trackerListElement*)(tElem->next);
        }
        else{
            tElem = (trackerListElement*)(tElem->next);
        }
    }
}

void ClusterTracker::clusterTracker_inputDataTransfer(int numCluster,
                                                      //   int scale,
                                                      std::vector<trackerInputDataType> &inputInfo,
                                                      //   std::vector<trackerInputInternalDataType> &internalInputInfo
                                                      trackerInputInternalDataType *internalInputInfo)
{
    int i;
    float posx, posy;
    // float scaleInv = 1.0 / (float)(scale);
    float scaleInv = 1.0;
    for (i = 0; i < numCluster; i++) {
        internalInputInfo[i].xSize = (float)(inputInfo[i].xSize) * scaleInv;
        internalInputInfo[i].ySize = (float)(inputInfo[i].ySize) * scaleInv;
        internalInputInfo[i].doppler = -(float)(inputInfo[i].avgVel) * scaleInv;
        internalInputInfo[i].numPoints = inputInfo[i].numPoints;
        internalInputInfo[i].rangeVar = inputInfo[i].centerRangeVar * scaleInv * scaleInv;
        internalInputInfo[i].angleVar = inputInfo[i].centerAngleVar;
        internalInputInfo[i].dopplerVar = inputInfo[i].centerDopplerVar * scaleInv * scaleInv;
        posx = (float)(inputInfo[i].xCenter) * scaleInv;
        posy = (float)(inputInfo[i].yCenter) * scaleInv;
        internalInputInfo[i].range = (float)(sqrt(posx * posx + posy * posy));

        // calc azimuth
        // if (posx < 0)
        //     internalInputInfo[i].azimuth = (float)(atan(posy / posx)) + CLUSTERTRACKER_PI;
        // else if (posx == 0 && posy > 0)
        //     internalInputInfo[i].azimuth = CLUSTERTRACKER_PI / 2;
        // else if (posx == 0 && posy < 0)
        //     internalInputInfo[i].azimuth = CLUSTERTRACKER_PI / 2 + CLUSTERTRACKER_PI;
        // else if (posx > 0 && posy > 0)
        //     internalInputInfo[i].azimuth = (float)(atan(posy / posx));
        // else if (posx > 0 && posy < 0)
        //     internalInputInfo[i].azimuth = (float)(atan(posy / posx)) + 2 * CLUSTERTRACKER_PI;

        if (posx == 0)
            internalInputInfo[i].azimuth = CLUSTERTRACKER_PI / 2;
        else if (posx > 0)
            internalInputInfo[i].azimuth = (float)(atan(posy / posx));
        else
            internalInputInfo[i].azimuth = (float)(atan(posy / posx)) + CLUSTERTRACKER_PI;
        
    }
}

void tracker_matrixMultiply(int m1, int m2, int m3, float *A, float *B, float *C)
{
    // C(m1*m3) = A(m1*m2)*B(m2*m3)
    int i, j, k;
    for (i = 0; i < m1; i++) {
        for (j = 0; j < m3; j++) {
            C[i * m3 + j] = 0;
            for (k = 0; k < m2; k++)
                C[i * m3 + j] += A[i * m2 + k] * B[k * m3 + j];
        }
    }
}

void tracker_matrixConjugateMultiply(int m1, int m2, int m3, float *A, float *B, float *C)
{
    // C(m1*m3) = A(m1*m2)*B(m2*m3)
    int i, j, k;
    for (i = 0; i < m1; i++) {
        for (j = 0; j < m3; j++) {
            C[i * m3 + j] = 0;
            for (k = 0; k < m2; k++)
                C[i * m3 + j] += A[i * m2 + k] * B[k + j * m2];
        }
    }
}

void tracker_matrixAdd(int dim, float *A, float *B, float *C)
{
    // C = A + B
    int i, j;
    for (i = 0; i < dim; i++) {
        for (j = 0; j < dim; j++) {
            C[i * dim + j] = A[i * dim + j] + B[i * dim + j];
        }
    }
}

void tracker_matrixSub(int dim, float *A, float *B, float *C)
{
    // C = A + B
    int i, j;
    for (i = 0; i < dim; i++) {
        for (j = 0; j < dim; j++) {
            C[i * dim + j] = A[i * dim + j] - B[i * dim + j];
        }
    }
}

void tracker_computeH(float *S, float *H)
{
    // S = [posx posy velx vely]
    // H = [range azimuth doppler]
    float posx = S[0];
    float posy = S[1];
    float velx = S[2];
    float vely = S[3];
    // calc range
    H[0] = (float)(sqrt(posx * posx + posy * posy));

    // calc azimuth
    if (posx == 0)
        H[1] = CLUSTERTRACKER_PI / 2;
    else if (posx > 0)
        H[1] = (float)(atan(posy / posx));
    else
        H[1] = (float)(atan(posy / posx)) + CLUSTERTRACKER_PI;

    // calc doppler;
    H[2] = (posx * velx + posy * vely) / H[0];
}

void clusterTracker_distCalc(trackerInputInternalDataType *measureInfo, trackerInternalDataType *tracker, float *dist)
{
    dist[0] = measureInfo->range * measureInfo->range + tracker->H_s_apriori_hat[0] * tracker->H_s_apriori_hat[0] -
              2 * measureInfo->range * tracker->H_s_apriori_hat[0] * (float)(cos(tracker->H_s_apriori_hat[1] - measureInfo->azimuth));
    // // float temp = 0;

    // // dist[0] = pow((measureInfo->range - tracker->H_s_apriori_hat[0]), 2) + pow((measureInfo->azimuth - tracker->H_s_apriori_hat[1]), 2) +
    // //           pow((measureInfo->doppler - tracker->H_s_apriori_hat[2]), 2);

    // float u_tilda[3], temp[3];
    // u_tilda[0] = measureInfo->range - tracker->H_s_apriori_hat[0];
    // u_tilda[1] = measureInfo->azimuth - tracker->H_s_apriori_hat[1];
    // u_tilda[2] = measureInfo->doppler - tracker->H_s_apriori_hat[2];
    // tracker_matrixMultiply(1,3,3, u_tilda, tracker->C, temp);

    // dist[0] = temp[0]*u_tilda[0]+temp[1]*u_tilda[1]+temp[2]*u_tilda[2];

}

float clusterTracker_associateThresholdCalc(float presetTH, trackerInternalDataType *tracker)
{
    float threshold =0;
    // HVA_DEBUG("presetTH: %f", presetTH);
    // HVA_DEBUG("diagonal2: %f", tracker->diagonal2);
    // threshold = presetTH + 6 * tracker->diagonal2;
    float r_Th = std::max(presetTH, (float)sqrt(tracker->diagonal2) / 2);
    // float x_Th = presetTH * 10;
    float x_Th = presetTH;
    float ang_ref = 2 * atan(x_Th / tracker->H_s_apriori_hat[0]);
    float v_Th = presetTH;
    threshold = pow(r_Th, 2) + pow(ang_ref, 2) + pow(v_Th, 2);
    return threshold;
    
    // Mahalanobis Distance
    // float um[3];
    // um[0] = r_Th;
    // um[1] = ang_ref;
    // um[2] = v_Th;
    // float temp[3];
    // tracker_matrixMultiply(1,3,3, um, tracker->C, temp);
    // for(int i=0;i<3;i++){
    //     threshold += temp[i]*um[i];
    // }

    // return threshold;
}

// float clusterTracker_associateThresholdCalc(float presetTH,
//                                             trackerInternalDataType* tracker) {
//   float threshold;
//   threshold = presetTH + 5 * tracker->diagonal2;
//   return (threshold);
// }

void clusterTracker_combineMeasure(trackerInputInternalDataType *inputInfo,
                                   // std::vector<trackerInputInternalDataType> &inputInfo,
                                   int *associatedList,
                                   int numAssoc,
                                   trackerInputInternalDataType *combinedInput)
{
    float range = 0;
    float azimuth = 0;    /**< cluster center location in angle .*/
    float doppler = 0;    /**< averge doppler of the cluster.*/
    float xSize = 0;      /**< max distance of point from cluster center in x direction.*/
    float ySize = 0;      /**< max distance of point from cluster center in y direction.*/
    float rangeVar = 0;   /**< variance of the range estimation */
    float angleVar = 0;   /**< variance of the angle estimation */
    float dopplerVar = 0; /**< variance of the doppler estimation */
    int i, size, totSize, mid;
    float totSizeInv;
    totSize = 0;
    for (i = 0; i < numAssoc; i++) {
        mid = associatedList[i];
        size = inputInfo[mid].numPoints;
        totSize += size;
        range += inputInfo[mid].range * size;
        azimuth += inputInfo[mid].azimuth * size;
        doppler += inputInfo[mid].doppler * size;
        rangeVar += inputInfo[mid].rangeVar * size;
        angleVar += inputInfo[mid].angleVar * size;
        dopplerVar += inputInfo[mid].dopplerVar * size;
        if (xSize < inputInfo[mid].xSize)
            xSize = inputInfo[mid].xSize;
        if (ySize < inputInfo[mid].ySize)
            ySize = inputInfo[mid].ySize;
    }
    totSizeInv = (float)(1.0 / (float)(totSize));
    combinedInput->range = range * totSizeInv;
    combinedInput->azimuth = azimuth * totSizeInv;
    combinedInput->doppler = doppler * totSizeInv;
    combinedInput->rangeVar = rangeVar * totSizeInv;
    combinedInput->angleVar = angleVar * totSizeInv;
    combinedInput->dopplerVar = dopplerVar * totSizeInv;
    combinedInput->xSize = xSize;
    combinedInput->ySize = ySize;
    combinedInput->numPoints = totSize;
}

float clusterTracker_IIRFilter(float yn, float xn, float forgetFactor)
{
    float ynext;
    ynext = (float)(yn * (1.0 - forgetFactor) + xn * forgetFactor);
    return ynext;
}

void clusterTracker_computeCartesian(float *H, float *S)
{
    // H = [range azimuth doppler]
    // S = [posx posy velx vely]

    S[0] = H[0] * (float)(cos(H[1]));
    S[1] = H[0] * (float)(sin(H[1]));
    S[2] = H[2] * (float)(cos(H[1]));
    S[3] = H[2] * (float)(sin(H[1]));
}

void clusterTracker_computeJacobian(float *S, float *J)
{
    // S = [posx posy velx vely]
    // J is with size [3x4]

    float r2 = (S[0] * S[0] + S[1] * S[1]);
    float r = (float)(sqrt(r2));
    J[0] = S[0] / r;  // J[0][0]
    J[1] = S[1] / r;  // J[0][1]
    J[2] = 0;
    J[3] = 0;

    J[4] = -S[1] / r2;  // J[1][0]
    J[5] = S[0] / r2;   // J[1][1]
    J[6] = 0;
    J[7] = 0;

    J[8] = (float)((S[1] * (S[2] * S[1] - S[0] * S[3])) / r / r2);  // J[2][0]
    J[9] = (float)((S[0] * (S[3] * S[0] - S[2] * S[1])) / r / r2);  // J[2][1]
    J[10] = (float)(S[0] / r);                                      // J[2][2]
    J[11] = (float)(S[1] / r);                                      // J[2][3]
}

void tracker_cholesky3(float *A, float *G)
{
    float v[3] = {0, 0, 0};
    float temp;
    int i, j, k;
    int dim = 3;

    for (j = 0; j < dim; j++) {
        // v(j:n,1) = A(j:n,j);
        for (i = j; i < dim; i++)
            v[i] = A[i * dim + j];

        for (k = 0; k < j; k++) {
            // v(j:n,1) = v(j:n,1) - G(j,k)*G(j:n,k);
            for (i = j; i < dim; i++)
                v[i] = v[i] - G[j * dim + k] * G[i * dim + k];
        }

        // G(j:n,j) = v(j:n,1)/sqrt(v(j));
        temp = 1.0 / sqrt(v[j]);
        for (i = j; i < dim; i++)
            G[i * dim + j] = v[i] * temp;
    }
}

void cluster_matInv3(float *A, float *Ainv)
{
    int i, j, k, dim;
    // Ac and Ainv are both 3 by 3 Matrix
    float Ac[9] = {0, 0, 0, 0, 0, 0, 0, 0, 0};
    float Acinv[9] = {0, 0, 0, 0, 0, 0, 0, 0, 0};

    tracker_cholesky3(A, Ac);

    // Acinv(1,1) = 1/Ac(1, 1);
    // Acinv(2,2) = 1/Ac(2, 2);
    // Acinv(3,3) = 1/Ac(3, 3);
    dim = 3;
    for (i = 0; i < dim; i++)
        Acinv[i * dim + i] = (float)(1.0 / Ac[i * dim + i]);

    // Acinv(2,1) = -Ac(2,1)*Acinv(1,1)*Acinv(2,2);
    Acinv[3] = -Ac[3] * Acinv[0] * Acinv[4];

    // Acinv(3,2) = -Ac(3,2)*Acinv(2,2)*Acinv(3,3);
    Acinv[7] = -Ac[7] * Acinv[4] * Acinv[8];

    // Acinv(3,1) = (Ac(2,1)*Ac(3,2)-Ac(2,2)*Ac(3,1))*Acinv(1,1)*Acinv(2,2)*Acinv(3,3);
    Acinv[6] = (Ac[3] * Ac[7] - Ac[4] * Ac[6]) * Acinv[0] * Acinv[4] * Acinv[8];

    // Ainv = Acinv' * Acinv;
    for (i = 0; i < dim; i++) {
        for (j = 0; j < dim; j++) {
            Ainv[i * dim + j] = 0;
            for (k = 0; k < dim; k++)
                Ainv[i * dim + j] += Acinv[k * dim + i] * Acinv[k * dim + j];
        }
    }
}

void clusterTracker_kalmanUpdate(trackerInternalDataType *tracker, trackerInputInternalDataType *combinedInput, float *F, float *Q, float *R, float *scratchPad)
{
    int i, j;
    // float J[12];
    float H[3];
    float *J, *temp1, *temp2, *temp3, *invMatrix, *K;
    // float temp1[16], temp2[16], temp3[9], invMatrix[9], K[12];
    float avg;

    temp1 = &scratchPad[0];
    temp2 = &scratchPad[16];
    temp3 = &scratchPad[32];
    invMatrix = &scratchPad[48];
    K = &scratchPad[64];
    J = &scratchPad[80];


    // obj.P_apriori(:,:,tid) = obj.F * obj.P(:,:,tid) * obj.F' + obj.Q;
    // P_aprior =F*P*F'+Q
    tracker_matrixMultiply(4, 4, 4, F, tracker->P, temp1);                   // temp1 = F*P
    tracker_matrixConjugateMultiply(4, 4, 4, temp1, F, tracker->P_apriori);  // P_apriori =temp1* F
    tracker_matrixAdd(4, tracker->P_apriori, Q, tracker->P_apriori);

    //%Enforce symmetry constraint on P_apriori
    // obj.P_apriori(:,:,tid) = 1/2 * (obj.P_apriori(:,:,tid)+obj.P_apriori(:,:,tid)');
    for (i = 0; i < 4; i++) {
        for (j = i; j < 4; j++) {
            avg = tracker->P_apriori[i * 4 + j] + tracker->P_apriori[j * 4 + i];
            avg = (float)(avg * 0.5);
            tracker->P_apriori[i * 4 + j] = avg;
            tracker->P_apriori[j * 4 + i] = avg;
        }
    }

    //%Compute the Jacobian (can be over-written)
    // J = computeJacobian(obj.S_apriori_hat(:,tid));
    clusterTracker_computeJacobian(tracker->S_apriori_hat, J);

    //% Measurement update
    //% Kalman gain using matrix inverse via Cholesky decomposition
    // K = obj.P_apriori(:,:,tid) * J' * matinv(J * obj.P_apriori(:,:,tid) * J' + R);
    tracker_matrixMultiply(3, 4, 4, J, tracker->P_apriori, temp2);           // 3*4: J * P_apriori
    tracker_matrixConjugateMultiply(3, 4, 3, temp2, J, temp3);               // 3*3: J * P_apriori * J'
    tracker_matrixAdd(3, temp3, R, temp3);                                   // 3*3:J * P_apriori * J' + R

    //Update C
    //tracker->C = J *tracker->P_apriori*J' +R +Rm
    float Rm[9], H_temp[3];
    Rm[0] =4;
    
    for(int i=0;i<3;i++){
        H_temp[i] = (float)(tracker->H_s_apriori_hat[i]*0.5);
    }
    Rm[4] = pow(2*atan(H_temp[0]), 2);
    // Rm[4] = pow(2*atan(float(1/2)*tracker->H_s_apriori_hat[0]), 2);
    
    Rm[8] = 1;
    tracker_matrixSub(3, temp3, Rm, tracker->C);

    cluster_matInv3(temp3, invMatrix);                                       // inv(J * P_apriori * J' + R)
    tracker_matrixConjugateMultiply(4, 4, 3, tracker->P_apriori, J, temp2);  // 4*3: P_apriori * J'
    tracker_matrixMultiply(4, 3, 3, temp2, invMatrix, K);                    // 4*3: K = P_apriori * J' * invMat

    // obj.P(:,:,tid) = obj.P_apriori(:,:,tid) - K * J * obj.P_apriori(:,:,tid);
    tracker_matrixMultiply(4, 3, 4, K, J, temp1);                       // 4*4: K*J
    tracker_matrixMultiply(4, 4, 4, temp1, tracker->P_apriori, temp2);  // 4*4: K*J*P_priori
    tracker_matrixSub(4, tracker->P_apriori, temp2, tracker->P);        // 4*4: P_priori - K*J*P_priori


    // obj.S_hat(:,tid) = obj.S_apriori_hat(:,tid) + K * (um - obj.H_s_apriori_hat(:,tid));
    H[0] = combinedInput->range - tracker->H_s_apriori_hat[0];
    H[1] = combinedInput->azimuth - tracker->H_s_apriori_hat[1];
    H[2] = combinedInput->doppler - tracker->H_s_apriori_hat[2];
    tracker_matrixMultiply(4, 3, 1, K, H, temp1);  // 4*1: K*(um - H_s_apriori_hat);
    for (i = 0; i < 4; i++)
        tracker->S_hat[i] = tracker->S_apriori_hat[i] + temp1[i];  // 4*1: S_hat = S_priori + K*(um - H_s_apriori_hat);
}

void clusterTracker_kalmanUpdateWithNoMeasure(trackerInternalDataType *tracker, float *F, float *Q)
{
    int i, j, index;
    int dim = 4;
    float temp1[16];

    // obj.P_apriori(:,:,tid) = obj.F * obj.P(:,:,tid) * obj.F' + obj.Q;
    tracker_matrixMultiply(4, 4, 4, F, tracker->P, temp1);
    tracker_matrixConjugateMultiply(4, 4, 4, temp1, F, tracker->P_apriori);
    tracker_matrixAdd(4, tracker->P_apriori, Q, tracker->P_apriori);

    // obj.P(:,:,tid) = obj.P_apriori(:,:,tid);
    // obj.S_hat(:,tid) = obj.S_apriori_hat(:,tid);
    for (i = 0; i < dim; i++) {
        tracker->S_hat[i] = tracker->S_apriori_hat[i];
        for (j = 0; j < dim; j++) {
            index = i * dim + j;
            tracker->P[index] = tracker->P_apriori[index];
        }
    }
}


}  // namespace inference

}  // namespace ai

}  // namespace hce
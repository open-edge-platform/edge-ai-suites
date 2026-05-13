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

#ifndef HCE_AI_INF_RADAR_CLUSTING_HELPER_HPP
#define HCE_AI_INF_RADAR_CLUSTING_HELPER_HPP

#include "inc/api/hvaLogger.hpp"
#include "nodes/radarDatabaseMeta.hpp"

namespace hce {

namespace ai {

namespace inference {

#define DBSCAN_FIXEDWEIGHTSHIFT  (3)                          // ASSUMPTION: weight is smaller than 8!!!!
#define DBSCAN_PIOVER180         (3.141592653589793 / 180.0)  //!< define the pi/180

#define RESTRICT                 __restrict

#define DBSCAN_ERROR_CODE_OFFSET 100

using clusteringDBscanInput = pointClouds;

// typedef enum {
//     DBSCAN_INPUT_FLOATINGPT = 0,      // Input format SP floating-point
//     DBSCAN_INPUT_16BITFIXEDPT,        // Input format 16-bit fixed-point
//     DBSCAN_INPUTFORMAT_NOT_SUPPORTED  // To be added
// } clusteringDBscanInputFormat;

//   Structure element of the list of descriptors for clusteringDBscan
//   configuration.
// typedef struct
// {
//     float epsilon;  // distance threhold for cluster check
//     float weight;   // the weight between the distance and speed
//     //   float vFactor;  // additional velocity factor for speed delta

//     uint16_t minPointsInCluster;  // minimum number of points in a cluster
//     uint16_t maxClusters;         // maximum number of clusters

//     uint16_t maxPoints;           // Maximum number of points that can be services per
//                                   // dbscanRun call
//                                   //   clusteringDBscanInputFormat
//                                   //       inputPntPrecision;  // Precision of the input point: 0 --
//                                   //       single-preision
//                                   //                           // floating point; 1 -- 16-bit fixed-point
//                                   //   uint16_t fixedPointScale;  // Block scale value to convert x-y from
//                                   //                              // floating-point to fixed-point. Should be
//                                   //                              the
//                                   //                              // same the one used in converting r-theta to
//                                   //                              x-y,
//                                   //                              // not used for floating-point input
// } clusteringDBscanConfig;

typedef enum {
    DBSCAN_OK = 0,                                               /**< To be added */
    DBSCAN_ERROR_MEMORY_ALLOC_FAILED = DBSCAN_ERROR_CODE_OFFSET, /**< To be added */
    DBSCAN_ERROR_NOT_SUPPORTED,                                  /**< To be added */
    DBSCAN_ERROR_CLUSTER_LIMIT_REACHED                           /**< To be added */
} clusteringDBscanErrorCodes;

// // clustering input, get from RadarDetectionNode
// struct clusteringDBscanInput
// {
//     int numPoints;  // number of point for clustering
//     union
//     {
//         int *pointArrayInt;      // range index
//         float *pointArrayFloat;  // range value
//     } pointArray;
//     union
//     {
//         int *speedInt;      // speed index
//         float *speedFloat;  // speed value
//     } speed;
//     float *aoaVar;
//     float *SNRArray;
// };

// output

// // Structure for each cluster information report
// struct clusteringDBscanReport
// {
//     int numPoints;           // number of points in this cluster
//     int xCenter;             // the clustering center on x direction
//     int yCenter;             // the clustering center on y direction
//     int xSize;               // the clustering size on x direction
//     int ySize;               // the clustering size on y direction
//     int avgVel;              // the average velocity within this cluster
//     float centerRangeVar;    // variance of the range estimation
//     float centerAngleVar;    // variance of the angle estimation
//     float centerDopplerVar;  // variance of the doppler estimation
// };

// // Structure of clusrering output
// struct clusteringDBscanOutput
// {
//     int *indexArray;                 // clustering result index array
//     int numCluster;                  // number of cluster detected
//     clusteringDBscanReport *report;  // information report for each cluster
// };

typedef struct
{
    float x;
    float y;
} clusteringDBscanPoint2d;

// typedef struct
// {
//     int numPoints[10];
// } clusteringDBscanClusterInfo;

// typedef struct
// {
//     clusteringDBscanClusterInfo *clusterInfo;
//     unsigned int memoryUsed;
//     uint64_t benchPoint[10];
// } clusteringDBscanDebugInfo;

typedef struct
{
    float epsilon;  // distance threhold for cluster check
    float weight;   // the weight between the distance and speed
    // float vFactor;                // additional velocity factor for speed delta

    int minPointsInCluster;  // minimum number of points in a cluster
    int maxClusters;         // maximum number of clusters
    int pointIndex;

    int maxPoints;  // Maximum number of points that can be services per
                    // dbscanRun call

    char *scratchPad;
    char *visited;
    char *scope;
    int *neighbors;
    // float *distances;
    // clusteringDBscanDebugInfo *debugInfo;

    // uint8_t inputPntPrecision; /**< Precision of the input point: 0 -- single-preision
    //                               floating point; 1 -- 16-bit fixed-point */
    // uint16_t fixedPointScale;  /**< Block scale value to convert x-y from
    //                               floating-point to fixed-point. Should be the same
    //                               the one used in converting r-theta to x-y, not
    //                               used for floating-point input */
} clusteringDBscanInstance;

typedef enum { POINT_UNKNOWN = 0, POINT_VISITED } clusteringDBscanPointState;

}  // namespace inference

}  // namespace ai

}  // namespace hce

#endif  // #ifndef HCE_AI_INF_RADAR_CLUSTING_HELPER_HPP

/*
 * INTEL CONFIDENTIAL
 *
 * Copyright (C) 2023 Intel Corporation.
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

#include "nodes/CPU-backend/RadarClusteringNode.hpp"
#include "inc/buffer/hvaVideoFrameWithROIBuf.hpp"
#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "nodes/databaseMeta.hpp"

#include <sys/stat.h>

#include <cmath>
#include <opencv2/opencv.hpp>
#include <unordered_map>

#include <cmath>
#include <algorithm>

#include <immintrin.h>
#include <xmmintrin.h>

#include <vector>

namespace hce {

namespace ai {

namespace inference {

void printPointClouds(pointClouds *pcl)
{
    std::stringstream log;
    if (0 == pcl->num) {
        log << "pointClouds{}" <<std::endl;
    }
    else {
        log << "pointClouds{" << pcl->num << ",\t" <<"[";

        for (int i = 0; i < pcl->num - 1; ++i) {
            log << pcl->rangeFloat[i] << ", ";
        }

        log << pcl->rangeFloat[pcl->num -1] << "], \t";

        float *pointArray = new float[pcl->num * 2];
        for (int i = 0; i < pcl->num; ++i) {
            pointArray[i * 2] = pcl->rangeFloat[i] * cos(pcl->aoaVar[i] * M_PI / 180);
            pointArray[i * 2 + 1] = pcl->rangeFloat[i] * sin(pcl->aoaVar[i] * M_PI / 180);
        }

        log << "[";
        for (int i = 0; i < pcl->num * 2 - 1; ++i) {
            log << pointArray[i] << ", ";
        }

        log << pointArray[pcl->num *2 -1] <<"],\t";
        // free(pointArray);
        delete[] pointArray;

        log <<"[";
        for (int i = 0; i < pcl->num - 1; ++i) {
            log << pcl->speedFloat[i] << ", ";
        }

        log << pcl->speedFloat[pcl->num -1] << "],\t" << "[";

        for (int i = 0; i < pcl->num - 1; ++i) {
            log << pcl->aoaVar[i] << ", ";
        }

        log << pcl->aoaVar[pcl->num -1] << "],\t" << "[";
        for (int i = 0; i < pcl->num - 1; ++i) {
            log << pcl->SNRArray[i] << ", ";
        }

        log << pcl->SNRArray[pcl->num -1] << "],\t" <<"}"<<std::endl;
    }
    HVA_DEBUG("%s", log.str().c_str());
}

void printClusteringDBscanOutput(clusteringDBscanOutput *output)
{
    std::stringstream log;
    if (0 == output->numCluster) {
        log << "clusteringDBscanOutput{}" << std::endl;
    }
    else {

        log <<"clusteringDBscanOutput{" << "[";

        for (int i = 0; i < output->InputArray.size() - 1; ++i) {
            log << output->InputArray[i];
        }

        log << output->InputArray[output->InputArray.size() - 1] << "],\t";

        for (int i = 0; i < output->numCluster; ++i) {

            log << "[" << output->report[i].numPoints <<",\t"<< output->report[i].xCenter << ",\t" << output->report[i].yCenter << ",\t"<< output->report[i].xSize <<",\t"<<output->report[i].ySize<< ",\t";
            log << output->report[i].avgVel <<",\t"<< output->report[i].centerRangeVar << ",\t" << output->report[i].centerAngleVar << ",\t"<< output->report[i].centerDopplerVar << "];";
        
        }
        log << std::string("}") << std::endl;
    }
    HVA_DEBUG("%s", log.str().c_str());
}

class RadarClusteringNode::Impl {
  public:
    Impl(RadarClusteringNode &ctx);

    ~Impl();

    /**
     * @brief Parse params, called by hva framework right after node instantiate.
     * @param config Configure string required by this node.
     * @return hva status
     */
    virtual hva::hvaStatus_t configureByString(const std::string &config);

    /**
     * @brief To validate ModelPath in configure is not none.
     * @return hva status
     */
    virtual hva::hvaStatus_t validateConfiguration() const;

    /**
     * @brief Constructs and returns a node worker instance:
     * RadarClusteringNodeWorker.
     * @return shared_ptr of hvaNodeWorker
     */
    std::shared_ptr<hva::hvaNodeWorker_t> createNodeWorker(RadarClusteringNode *parent) const;

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();

    hva::hvaStatus_t prepare();

  private:
    RadarClusteringNode &m_ctx;

    // hva::hvaConfigStringParser_t m_configParser;
    // RadarClusteringConfig m_param;
};

RadarClusteringNode::Impl::Impl(RadarClusteringNode &ctx) : m_ctx(ctx)
{
    // m_configParser.reset();
}

RadarClusteringNode::Impl::~Impl() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t RadarClusteringNode::Impl::configureByString(const std::string &config)
{
    //! TODO:
    m_ctx.transitStateTo(hva::hvaState_t::configured);
    return hva::hvaSuccess;
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t RadarClusteringNode::Impl::validateConfiguration() const
{
    //! TODO:
    return hva::hvaSuccess;
}

/**
 * @brief Constructs and returns a node worker instance:
 * RadarClusteringNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> RadarClusteringNode::Impl::createNodeWorker(RadarClusteringNode *parent) const
{
    return std::shared_ptr<hva::hvaNodeWorker_t>(new RadarClusteringNodeWorker(parent));
}

hva::hvaStatus_t RadarClusteringNode::Impl::prepare()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarClusteringNode::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarClusteringNode::Impl::reset()
{
    return hva::hvaSuccess;
}

RadarClusteringNode::RadarClusteringNode(std::size_t totalThreadNum) : hva::hvaNode_t(1, 1, totalThreadNum), m_impl(new Impl(*this)) {}

RadarClusteringNode::~RadarClusteringNode() {}

/**
 * @brief Parse params, called by hva framework right after node instantiate.
 * @param config Configure string required by this node.
 * @return hva status
 */
hva::hvaStatus_t RadarClusteringNode::configureByString(const std::string &config)
{
    return m_impl->configureByString(config);
}

/**
 * @brief To validate ModelPath in configure is not none.
 * @return hva status
 */
hva::hvaStatus_t RadarClusteringNode::validateConfiguration() const
{
    return m_impl->validateConfiguration();
}

/**
 * @brief Constructs and returns a node worker instance:
 * RadarTrackingNodeWorker.
 * @return shared_ptr of hvaNodeWorker
 */
std::shared_ptr<hva::hvaNodeWorker_t> RadarClusteringNode::createNodeWorker() const
{
    return m_impl->createNodeWorker(const_cast<RadarClusteringNode *>(this));
}

hva::hvaStatus_t RadarClusteringNode::rearm()
{
    return m_impl->rearm();
}

hva::hvaStatus_t RadarClusteringNode::reset()
{
    return m_impl->reset();
}

hva::hvaStatus_t RadarClusteringNode::prepare()
{
    return m_impl->prepare();
}

class RadarClusteringNodeWorker::Impl {
  public:
    Impl(RadarClusteringNodeWorker &ctx);

    ~Impl();

    /**
     * @brief Called by hva framework for each frame, Run radar clustering and pass output to following node
     * @param batchIdx Internal parameter handled by hvaframework
     */
    void process(std::size_t batchIdx);

    void init();

    hva::hvaStatus_t rearm();

    hva::hvaStatus_t reset();


  private:
    RadarClusteringNodeWorker &m_ctx;

    clusteringDBscanInstance *m_inst=nullptr;  // Pointer to input handle for clusteringDBscan module.

    bool m_configured;

    /**
     * @brief Create and initialize clusteringDBscan.
     * @param param RadarClusteringConfig
     * @return Error code.
     */
    clusteringDBscanErrorCodes clusteringDBscanCreate(RadarClusteringConfig *param);

    /**
     * @brief Run clusteringDBscan module.
     * @param input Pointer to input data to clusteringDBscan module.
     * @param output Pointer to output data from clusteringDBscan module
     * @return Error code.
     */
    clusteringDBscanErrorCodes clusteringDBscanRun(clusteringDBscanInput *input, clusteringDBscanOutput *output);

    /**
     * @brief Delete fucntion for clusteringDBscan module.
     * @return Error code.
     */
    clusteringDBscanErrorCodes clusteringDBscanDelete();

    int clusteringDBscan_findNeighbors2(clusteringDBscanPoint2d *pointArray,
                                        float *speedArray,
                                        int point,
                                        int *neigh,
                                        int numPoints,
                                        float epsilon2,
                                        float weight,
                                        //    int32_t vFactor,
                                        char *visited,
                                        int *newCount);
    void clusteringDBscan_calcInfo(
        // uint16_t scale,
        clusteringDBscanPoint2d *pointArray,
        float *speedArray,
        float *SNRArray,
        float *aoaVar,
        int *neighStart,
        int *neighLast,
        clusteringDBscanReport *report);
};

RadarClusteringNodeWorker::Impl::Impl(RadarClusteringNodeWorker &ctx) : m_ctx(ctx), m_configured(false) {}

RadarClusteringNodeWorker::Impl::~Impl()
{
    clusteringDBscanDelete();
}

void RadarClusteringNodeWorker::Impl::init()
{
    return;
}

/**
 * @brief Called by hva framework for each frame, Run radar clustering
 * and pass output to following node
 * @param batchIdx Internal parameter handled by hvaframework
 */
void RadarClusteringNodeWorker::Impl::process(std::size_t batchIdx)
{
    // get input blob from port 0
    auto vecBlobInput = m_ctx.getParentPtr()->getBatchedInput(batchIdx, std::vector<size_t>{0});
    HVA_DEBUG("Get the ret size is %d", vecBlobInput.size());

    if (vecBlobInput.size() != 0) {
        hva::hvaBlob_t::Ptr blob = vecBlobInput[0];
        HVA_ASSERT(blob);
        HVA_DEBUG("RadarClustering node %d on frameId %d", batchIdx, blob->frameId);
        std::shared_ptr<hva::timeStampInfo> RadarClusteringIn =
        std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarClusteringIn");
        m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarClusteringIn);
        hva::hvaVideoFrameWithMetaROIBuf_t::Ptr ptrFrameBuf = std::dynamic_pointer_cast<hva::hvaVideoFrameWithMetaROIBuf_t>(blob->get(0));
        HVA_ASSERT(ptrFrameBuf);

        if (!ptrFrameBuf->drop) {
            // inherit meta data from previous input field
            RadarConfigParam radarParams;
            if (ptrFrameBuf->containMeta<RadarConfigParam>()) {
                // success
                ptrFrameBuf->getMeta(radarParams);
            }
            else {
                // previous node not ever put this type of meta into hvabuf
                HVA_ERROR("Previous node not ever put this type of RadarConfigParam into hvabuf!");
            }

            if (!m_configured) {
                clusteringDBscanErrorCodes errorCode = clusteringDBscanCreate(&radarParams.m_radar_clusterging_config_);
                if (errorCode != DBSCAN_OK) {
                    HVA_ERROR("Create clusteringDBscan Instance Failed!");
                }
                HVA_DEBUG("Create clusteringDBscan Instance Success!");
                m_configured = true;
            }

            clusteringDBscanInput clusterInput = ptrFrameBuf->get<pointClouds>();
            // printPointClouds(&clusterInput);
            clusteringDBscanOutput clusterOutput;
            clusterOutput.InputArray.resize(clusterInput.num);
            clusterOutput.report.resize(m_inst->maxClusters);

            if (clusteringDBscanRun(&clusterInput, &clusterOutput) != DBSCAN_OK) {
                HVA_ERROR("clusteringDBscanRun Failed!");
            }

            // printPointClouds(&clusterInput);
            // printClusteringDBscanOutput(&clusterOutput);
            ptrFrameBuf->setMeta<clusteringDBscanOutput>(clusterOutput);

            HVA_DEBUG("RadarCluster node sending blob with frameid %u and streamid %u, tag %d", blob->frameId, blob->streamId, ptrFrameBuf->getTag());
            m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarClusteringOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarClusteringOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarClusteringOut);
            HVA_DEBUG("RadarCluster node sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
        }
        else {
            clusteringDBscanOutput clusterOutput;
            ptrFrameBuf->setMeta<clusteringDBscanOutput>(clusterOutput);

            HVA_DEBUG("RadarCluster node sending blob with frameid %u and streamid %u, tag %d, drop is true", blob->frameId, blob->streamId,
                      ptrFrameBuf->getTag());
            m_ctx.sendOutput(blob, 0, std::chrono::milliseconds(0));
            std::shared_ptr<hva::timeStampInfo> RadarClusteringOut =
            std::make_shared<hva::timeStampInfo>(blob->frameId, "RadarClusteringOut");
            m_ctx.getParentPtr()->emitEvent(hvaEvent_PipelineTimeStampRecord, &RadarClusteringOut);
            HVA_DEBUG("RadarCluster node sent blob with frameid %u and streamid %u", blob->frameId, blob->streamId);
        }
    }
}

hva::hvaStatus_t RadarClusteringNodeWorker::Impl::rearm()
{
    return hva::hvaSuccess;
}

hva::hvaStatus_t RadarClusteringNodeWorker::Impl::reset()
{
    return hva::hvaSuccess;
}

clusteringDBscanErrorCodes RadarClusteringNodeWorker::Impl::clusteringDBscanCreate(RadarClusteringConfig *param)
{
    // clusteringDBscanInstance *m_inst;
    unsigned int memoryUsed = 0;

    clusteringDBscanErrorCodes errorCode = DBSCAN_OK;

    memoryUsed += sizeof(clusteringDBscanInstance);
    // m_inst = (clusteringDBscanInstance *)radarOsal_memAlloc(RADARMEMOSAL_HEAPTYPE_LL2, 0, sizeof(clusteringDBscanInstance), 8);
    m_inst = (clusteringDBscanInstance *)aligned_alloc(8, sizeof(clusteringDBscanInstance));
    if (m_inst == nullptr) {
        errorCode = DBSCAN_ERROR_MEMORY_ALLOC_FAILED;
        return errorCode;
    }

    m_inst->epsilon = param->eps;
    // m_inst->vFactor = param->vFactor;
    m_inst->weight = param->weight * param->weight * param->eps;  // m_inst->weight * m_inst->weight * epsilon;
    m_inst->weight = param->weight;
    m_inst->maxClusters = param->maxClusters;
    m_inst->minPointsInCluster = param->minPointsInCluster;
    m_inst->maxPoints = param->maxPoints;
    // m_inst->inputPntPrecision = param->inputPntPrecision;
    // m_inst->fixedPointScale = param->fixedPointScale;

    memoryUsed += m_inst->maxPoints * (sizeof(char) * 2 + sizeof(int));

    //! TODO
    // m_inst->scratchPad =
    //     (char *)radarOsal_memAlloc(RADARMEMOSAL_HEAPTYPE_LL1, 1, m_inst->maxPoints * (sizeof(char) * 2 + sizeof(uint16_t)), 8); /* 1 is the flag for
    //     scratch*/
    m_inst->scratchPad = (char *)aligned_alloc(8, m_inst->maxPoints * (sizeof(char) * 2 + sizeof(int))); /* 1 is the flag for scratch*/
    if (m_inst->scratchPad == nullptr) {
        errorCode = DBSCAN_ERROR_MEMORY_ALLOC_FAILED;
        return errorCode;
    }
    m_inst->visited = (char *)&m_inst->scratchPad[0];
    m_inst->scope = (char *)&m_inst->scratchPad[m_inst->maxPoints];
    m_inst->neighbors = (int *)&m_inst->scratchPad[2 * m_inst->maxPoints];

    return errorCode;
}

clusteringDBscanErrorCodes RadarClusteringNodeWorker::Impl::clusteringDBscanRun(clusteringDBscanInput *input, clusteringDBscanOutput *output)
{
    int *neighLast;
    int *neighCurrent;
    int neighCount;
    int newCount;
    int point, member;
    int numPoints;
    int clusterId;
    int ind;
    float epsilon, epsilon2, weight;

    numPoints = input->num;
    clusterId = 0;
    epsilon = m_inst->epsilon;
    epsilon2 = epsilon * epsilon;
    weight = m_inst->weight;

    float *pointArray = new float[numPoints * 2];
    for (int i = 0; i < numPoints; ++i) {
        pointArray[i * 2] = input->rangeFloat[i] * cos(input->aoaVar[i] * M_PI / 180);
        pointArray[i * 2 + 1] = input->rangeFloat[i] * sin(input->aoaVar[i] * M_PI / 180);
    }

    memset(m_inst->visited, POINT_UNKNOWN, numPoints * sizeof(char));

    // scan through all the points to find its neighbors
    for (point = 0; point < numPoints; point++) {
        if (m_inst->visited[point] != POINT_VISITED) {
            // m_inst->visited[point] = POINT_VISITED;
            // if (input->SNRArray[point] > 20.0) {
            //     m_inst->visited[point] = POINT_VISITED;
            //     output->InputArray[point] = 0;
            // }

            neighCurrent = neighLast = m_inst->neighbors;
            // scope is the local copy of visit
            memcpy(m_inst->scope, m_inst->visited, numPoints * sizeof(char));

            neighCount = clusteringDBscan_findNeighbors2((clusteringDBscanPoint2d *)pointArray, &input->speedFloat[0], point, neighLast, numPoints, epsilon2,
                                                         weight, m_inst->scope, &newCount);
            m_inst->visited[point] = POINT_VISITED;
            if (neighCount < m_inst->minPointsInCluster) {
                // This point is Noise
                output->InputArray[point] = 0;
            }
            else {
                // This point belongs to a New Cluster
                clusterId++;                            // New cluster ID
                output->InputArray[point] = clusterId;  // This point belong to this cluster

                // tag all the neighbors as visited in scope so that it will not be found again when searching neighbor's neighbor.
                for (ind = 0; ind < newCount; ind++) {
                    member = neighLast[ind];
                    m_inst->scope[member] = POINT_VISITED;
                }
                neighLast += newCount;

                while (neighCurrent != neighLast)  // neigh shall be at least minPoints in front of neighborhood pointer
                {
                    // Explore the neighborhood
                    member = *neighCurrent++;                // Take point from the neighborhood
                    output->InputArray[member] = clusterId;  // All points from the neighborhood also belong to this cluster
                    m_inst->visited[member] = POINT_VISITED;
                    neighCount = clusteringDBscan_findNeighbors2((clusteringDBscanPoint2d *)pointArray, &input->speedFloat[0], member, neighLast, numPoints,
                                                                 epsilon2, weight, m_inst->scope, &newCount);


                    if (neighCount >= m_inst->minPointsInCluster) {
                        for (ind = 0; ind < newCount; ind++) {
                            member = neighLast[ind];
                            m_inst->scope[member] = POINT_VISITED;
                        }
                        neighLast += newCount;  // Member is a core point, and its neighborhood is added to the cluster
                    }
                }
                if (clusterId >= m_inst->maxClusters)
                    return DBSCAN_ERROR_CLUSTER_LIMIT_REACHED;

                // calculate the clustering center and edge information
                clusteringDBscan_calcInfo((clusteringDBscanPoint2d *)pointArray, &input->speedFloat[0], &input->SNRArray[0], &input->aoaVar[0],
                                          m_inst->neighbors, neighLast, (clusteringDBscanReport *)&output->report[clusterId - 1]);
            }
        }
    }  // for
    output->numCluster = clusterId;

    // HVA_DEBUG("numPoints: %d", numPoints);
    // for (int i = 0; i < numPoints * 2; ++i) {
    //     HVA_DEBUG("%f", pointArray[i]);
    // }

    delete[] pointArray;

    return DBSCAN_OK;
}

clusteringDBscanErrorCodes RadarClusteringNodeWorker::Impl::clusteringDBscanDelete()
{
    free(m_inst->scratchPad);
    free(m_inst);
    return DBSCAN_OK;
}

int RadarClusteringNodeWorker::Impl::clusteringDBscan_findNeighbors2(clusteringDBscanPoint2d *pointArray,
                                                                     float *RESTRICT speedArray,
                                                                     int point,
                                                                     int *RESTRICT neigh,
                                                                     int numPoints,
                                                                     float epsilon2,
                                                                     float weight,
                                                                     //    int32_t vFactor,
                                                                     char *RESTRICT visited,
                                                                     int *newCount)
{
// #if defined(__AVX512F__)
#if 0
    int i = 0, idx = 0;
    size_t cnt = numPoints;
    int newcount = 0;
    float *xArr = (float *)aligned_alloc(64, sizeof(float) * numPoints > 64 ? sizeof(float) * numPoints : 64);
    float *yArr = (float *)aligned_alloc(64, sizeof(float) * numPoints > 64 ? sizeof(float) * numPoints : 64);
    float *speedArr = (float *)aligned_alloc(64, sizeof(float) * numPoints > 64 ? sizeof(float) * numPoints : 64);
    for (i = 0; i < numPoints; ++i) {
        xArr[i] = pointArray[i].x;
        yArr[i] = pointArray[i].y;
        speedArr[i] = speedArray[i];
    }

    float *xBuf = (float *)aligned_alloc(64, 64);
    float *yBuf = (float *)aligned_alloc(64, 64);
    float *speedBuf = (float *)aligned_alloc(64, 64);
    float *weightBuf = (float *)aligned_alloc(64, 64);
    for (i = 0; i < 16; ++i) {
        xBuf[i] = pointArray[point].x;
        yBuf[i] = pointArray[point].y;
        speedBuf[i] = speedArray[point];
        weightBuf[i] = speedArray[point];
    }

    __m512 x_m512 = _mm512_load_ps(xBuf);
    __m512 y_m512 = _mm512_load_ps(yBuf);
    __m512 speed_m512 = _mm512_load_ps(speedBuf);
    __m512 weight_m512 = _mm512_load_ps(weightBuf);
    __m512 mx512, my512, mspped512, msum512;
    while (cnt >= 16) {
        mx512 = _mm512_sub_ps(_mm512_load_ps(xArr), x_m512);
        my512 = _mm512_sub_ps(_mm512_load_ps(yArr), y_m512);
        mspped512 = _mm512_sub_ps(_mm512_load_ps(speedArr), speed_m512);
        msum512 = _mm512_mul_ps(mx512, mx512) + _mm512_mul_ps(my512, my512) + _mm512_mul_ps(weight_m512, _mm512_mul_ps(mspped512, mspped512));

        for (int32_t j = 0; j < 16; ++j) {
            if ((visited[idx + j] == POINT_UNKNOWN) && ((float)msum512[i] < epsilon2)) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
        xArr += 16;
        yArr += 16;
        speedArr += 16;
        cnt -= 16;
        idx += 16;
    }

    while (cnt >= 8) {
        __m256 mx256 = _mm256_sub_ps(_mm256_load_ps(xArr), _mm256_load_ps(xBuf));
        __m256 my256 = _mm256_sub_ps(_mm256_load_ps(yArr), _mm256_load_ps(yBuf));
        __m256 mspeed256 = _mm256_sub_ps(_mm256_load_ps(speedArr), _mm256_load_ps(speedBuf));
        __m256 msum256 =
            _mm256_mul_ps(mx256, mx256) + _mm256_mul_ps(my256, my256) + _mm256_mul_ps(_mm256_load_ps(weightBuf), _mm256_mul_ps(mspeed256, mspeed256));

        for (int32_t j = 0; j < 8; ++j) {
            if ((visited[idx + j] == POINT_UNKNOWN) && ((float)msum256[i] < epsilon2)) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
        xArr += 8;
        yArr += 8;
        speedArr += 8;
        cnt -= 8;
        idx += 8;
    }

    while (cnt >= 4) {
        __m128 mx128 = _mm_sub_ps(_mm_load_ps(xArr), _mm_load_ps(xBuf));
        __m128 my128 = _mm_sub_ps(_mm_load_ps(yArr), _mm_load_ps(yBuf));
        __m128 mspeed128 = _mm_sub_ps(_mm_load_ps(speedArr), _mm_load_ps(speedBuf));
        __m128 msum128 = _mm_mul_ps(mx128, mx128) + _mm_mul_ps(my128, my128) + _mm_mul_ps(_mm_load_ps(weightBuf), _mm_mul_ps(mspeed128, mspeed128));

        for (int32_t j = 0; j < 4; ++j) {
            if ((visited[idx + j] == POINT_UNKNOWN) && ((float)msum128[i] < epsilon2)) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
        xArr += 4;
        yArr += 4;
        speedArr += 4;
        cnt -= 4;
        idx += 4;
    }

    // 0 < cnt < 4
    for (int32_t j = 0; j < cnt; ++j) {
        if (visited[idx + j] == POINT_UNKNOWN) {
            float a = pointArray[idx + j].x - pointArray[point].x;
            float b = pointArray[idx + j].y - pointArray[point].y;
            float c = speedArray[idx + j] - speedArray[point];
            float sum = a * a + b * b + weight * c * c;

            if (sum < epsilon2) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
    }

    free(xArr);
    free(yArr);
    free(speedArr);
    free(xBuf);
    free(yBuf);
    free(speedBuf);
    *newCount = newcount;
    return newcount;

// #elif defined(__AVX__)
#elif 0
    int i = 0, idx = 0;
    size_t cnt = numPoints;
    int newcount = 0;
    float *xArr = (float *)aligned_alloc(32, sizeof(float) * numPoints > 32 ? sizeof(float) * numPoints : 32);
    float *yArr = (float *)aligned_alloc(32, sizeof(float) * numPoints > 32 ? sizeof(float) * numPoints : 32);
    float *speedArr = (float *)aligned_alloc(32, sizeof(float) * numPoints > 32 ? sizeof(float) * numPoints : 32);
    for (i = 0; i < numPoints; ++i) {
        xArr[i] = pointArray[i].x;
        yArr[i] = pointArray[i].y;
        speedArr[i] = speedArray[i];
    }

    float *xBuf = (float *)aligned_alloc(32, 32);
    float *yBuf = (float *)aligned_alloc(32, 32);
    float *speedBuf = (float *)aligned_alloc(32, 32);
    float *weightBuf = (float *)aligned_alloc(32, 32);
    for (i = 0; i < 8; ++i) {
        xBuf[i] = pointArray[point].x;
        yBuf[i] = pointArray[point].y;
        speedBuf[i] = speedArray[point];
        weightBuf[i] = speedArray[point];
    }

    __m256 x_m256 = _mm256_load_ps(xBuf);
    __m256 y_m256 = _mm256_load_ps(yBuf);
    __m256 speed_m256 = _mm256_load_ps(speedBuf);
    __m256 weight_m256 = _mm256_load_ps(weightBuf);
    __m256 mx256, my256, mspeed256, msum256;
    while (cnt >= 8) {
        mx256 = _mm256_sub_ps(_mm256_load_ps(xArr), x_m256);
        my256 = _mm256_sub_ps(_mm256_load_ps(yArr), y_m256);
        mspeed256 = _mm256_sub_ps(_mm256_load_ps(speedArr), speed_m256);
        msum256 = _mm256_mul_ps(mx256, mx256) + _mm256_mul_ps(my256, my256) + _mm256_mul_ps(weight_m256, _mm256_mul_ps(mspeed256, mspeed256));

        for (int32_t j = 0; j < 8; ++j) {
            if ((visited[idx + j] == POINT_UNKNOWN) && ((float)msum256[i] < epsilon2)) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
        xArr += 8;
        yArr += 8;
        speedArr += 8;
        cnt -= 8;
        idx += 8;
    }

    while (cnt >= 4) {
        __m128 mx128 = _mm_sub_ps(_mm_load_ps(xArr), _mm_load_ps(xBuf));
        __m128 my128 = _mm_sub_ps(_mm_load_ps(yArr), _mm_load_ps(yBuf));
        __m128 mspeed128 = _mm_sub_ps(_mm_load_ps(speedArr), _mm_load_ps(speedBuf));
        __m128 msum128 = _mm_mul_ps(mx128, mx128) + _mm_mul_ps(my128, my128) + _mm_mul_ps(_mm_load_ps(weightBuf), _mm_mul_ps(mspeed128, mspeed128));

        for (int32_t j = 0; j < 4; ++j) {
            if ((visited[idx + j] == POINT_UNKNOWN) && ((float)msum128[i] < epsilon2)) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
        xArr += 4;
        yArr += 4;
        speedArr += 4;
        cnt -= 4;
        idx += 4;
    }

    // 0 < cnt < 4
    for (int32_t j = 0; j < cnt; ++j) {
        if (visited[idx + j] == POINT_UNKNOWN) {
            float a = pointArray[idx + j].x - pointArray[point].x;
            float b = pointArray[idx + j].y - pointArray[point].y;
            float c = speedArray[idx + j] - speedArray[point];
            float sum = a * a + b * b + weight * c * c;

            if (sum < epsilon2) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
    }

    free(xArr);
    free(yArr);
    free(speedArr);
    free(xBuf);
    free(yBuf);
    free(speedBuf);
    *newCount = newcount;
    return newcount;

// #elif defined(__SSE3__)
#elif 0
    int i = 0, idx = 0;
    size_t cnt = numPoints;
    int newcount = 0;
    float *xArr = (float *)aligned_alloc(16, sizeof(float) * numPoints > 16 ? sizeof(float) * numPoints : 16);
    float *yArr = (float *)aligned_alloc(16, sizeof(float) * numPoints > 16 ? sizeof(float) * numPoints : 16);
    float *speedArr = (float *)aligned_alloc(16, sizeof(float) * numPoints > 16 ? sizeof(float) * numPoints : 16);
    for (i = 0; i < numPoints; ++i) {
        xArr[i] = pointArray[i].x;
        yArr[i] = pointArray[i].y;
        speedArr[i] = speedArray[i];
    }

    float *xBuf = (float *)aligned_alloc(16, 16);
    float *yBuf = (float *)aligned_alloc(16, 16);
    float *speedBuf = (float *)aligned_alloc(16, 16);
    float *weightBuf = (float *)aligned_alloc(16, 16);
    for (i = 0; i < 4; ++i) {
        xBuf[i] = pointArray[point].x;
        yBuf[i] = pointArray[point].y;
        speedBuf[i] = speedArray[point];
        weightBuf[i] = speedArray[point];
    }

    __m128 x_m128 = _mm_load_ps(xBuf);
    __m128 y_m128 = _mm_load_ps(yBuf);
    __m128 speed_m128 = _mm_load_ps(speedBuf);
    __m128 weight_m128 = _mm_load_ps(weightBuf);
    __m128 mx128, my128, mspeed128, msum128;

    while (cnt >= 4) {
        mx128 = _mm_sub_ps(_mm_load_ps(xArr), x_m128);
        my128 = _mm_sub_ps(_mm_load_ps(yArr), y_m128);
        mspeed128 = _mm_sub_ps(_mm_load_ps(speedArr), speed_m128);
        msum128 = _mm_mul_ps(mx128, mx128) + _mm_mul_ps(my128, my128) + _mm_mul_ps(weight_m128, _mm_mul_ps(mspeed128, mspeed128));

        for (int32_t j = 0; j < 4; ++j) {
            if ((visited[idx + j] == POINT_UNKNOWN) && ((float)msum128[i] < epsilon2)) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
        xArr += 4;
        yArr += 4;
        speedArr += 4;
        cnt -= 4;
        idx += 4;
    }

    // 0 < cnt < 4
    for (int32_t j = 0; j < cnt; ++j) {
        if (visited[idx + j] == POINT_UNKNOWN) {
            float a = pointArray[idx + j].x - pointArray[point].x;
            float b = pointArray[idx + j].y - pointArray[point].y;
            float c = speedArray[idx + j] - speedArray[point];
            float sum = a * a + b * b + weight * c * c;

            if (sum < epsilon2) {
                *neigh++ = idx + j;
                newcount++;
            }
        }
    }

    free(xArr);
    free(yArr);
    free(speedArr);
    free(xBuf);
    free(yBuf);
    free(speedBuf);
    *newCount = newcount;
    return newcount;
#else
    float a, b, c, sum;
    int i;

    int newcount = 0;
    float x = pointArray[point].x;
    float y = pointArray[point].y;
    float speed = speedArray[point];
    // float epsilon2_;
    // float ftemp = vFactor;
    // if (std::abs(speed) < vFactor)
    //     ftemp = speed;
    // epsilon2_ = ftemp * ftemp * weight + epsilon2;

    for (i = 0; i < numPoints; i++) {
        if (visited[i] == POINT_UNKNOWN) {
            a = pointArray[i].x - x;
            b = pointArray[i].y - y;
            c = speedArray[i] - speed;
            // HVA_DEBUG("point is (%f, %f), %f", pointArray[i].x, pointArray[i].y, speedArray[i]);
            sum = a * a + b * b + weight * c * c;

            // HVA_DEBUG("sum is %f", sum);

            if (sum < epsilon2) {
                *neigh++ = i;
                newcount++;
            }
        }
    }
    *newCount = newcount;
    return newcount;
#endif
}


void RadarClusteringNodeWorker::Impl::clusteringDBscan_calcInfo(
    // uint16_t scale,
    clusteringDBscanPoint2d *pointArray,
    float *speedArray,
    float *SNRArray,
    float *aoaVar,
    int *neighStart,
    int *neighLast,
    clusteringDBscanReport *report)
{
    // float *inputSpeedArray;
    // int16_t *inputFxSpeedArray;
    int ind, length, member;
    float sumx, sumy, sumVel, xCenter, yCenter, xSize, ySize, avgVel, temp;
    float range2, lengthInv, rangeVar, angleVar, velVar;

    length = (neighLast - neighStart);
    // HVA_DEBUG("length is: %d", length);
    sumx = 0;
    sumy = 0;
    sumVel = 0;
    rangeVar = 0;
    if (length > 1) {
        for (ind = 0; ind < length; ind++) {
            member = neighStart[ind];
            sumx += (pointArray[member].x);
            sumy += (pointArray[member].y);
            sumVel += (speedArray[member]);
        }
        lengthInv = 1.0 / (float)(length);
        xCenter = sumx * lengthInv;
        yCenter = sumy * lengthInv;
        avgVel = sumVel * lengthInv;
        xSize = 0;
        ySize = 0;
        velVar = 0;
        rangeVar = 0;
        angleVar = 0;
        // HVA_DEBUG("xCenter:%f, yCenter:%f", xCenter, yCenter);
        for (ind = 0; ind < length; ind++) {
            member = neighStart[ind];
            temp = (pointArray[member].x - xCenter);
            // HVA_DEBUG("pointArray[member].x: %f", pointArray[member].x);
            // HVA_DEBUG("temp:%f", temp);
            temp = ((temp > 0) ? (temp) : (-temp));     // abs
            xSize = (xSize > temp) ? (xSize) : (temp);  // max
            temp = (pointArray[member].y - yCenter);
            temp = ((temp > 0) ? (temp) : (-temp));       // abs
            ySize = ((ySize > temp) ? (ySize) : (temp));  // max
            temp = (speedArray[member] - avgVel);
            velVar += temp * temp;

            range2 = (pointArray[member].x) * (pointArray[member].x) + (pointArray[member].y) * (pointArray[member].y);
            temp = range2 * SNRArray[member];
            rangeVar += temp;

            angleVar += aoaVar[member] * aoaVar[member];
        }
        report->numPoints = length;

        float scale = 1.0;
        report->xCenter = xCenter * scale;  // convert to centermeter in integer
        report->yCenter = yCenter * scale;  // convert to centermeter in integer
        report->xSize = xSize * scale;      // convert to centermeter in integer
        report->ySize = ySize * scale;      // convert to centermeter in integer
        report->avgVel = avgVel * scale;
        report->centerRangeVar = rangeVar * scale * scale * lengthInv;                        // rangeResolution * rangeResolution * 0.25;
        report->centerAngleVar = angleVar * DBSCAN_PIOVER180 * DBSCAN_PIOVER180 * lengthInv;  // (2 * DBSCAN_PIOVER180)^2
        report->centerDopplerVar = velVar * scale * scale * lengthInv;                        // dopplerResolution * dopplerResolution * 0.25;
    }
}

RadarClusteringNodeWorker::RadarClusteringNodeWorker(hva::hvaNode_t *parentNode) : hva::hvaNodeWorker_t(parentNode), m_impl(new Impl(*this)) {}

RadarClusteringNodeWorker::~RadarClusteringNodeWorker() {}

void RadarClusteringNodeWorker::init()
{
    return m_impl->init();
}

void RadarClusteringNodeWorker::process(std::size_t batchIdx)
{
    return m_impl->process(batchIdx);
}

#ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY
HVA_ENABLE_DYNAMIC_LOADING(RadarClusteringNode, RadarClusteringNode(threadNum))
#endif  // #ifdef HVA_NODE_COMPILE_TO_DYNAMIC_LIBRARY

}  // namespace inference

}  // namespace ai

}  // namespace hce

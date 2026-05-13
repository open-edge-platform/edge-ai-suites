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

#include "utils/testUtils.hpp"
#include "nodes/databaseMeta.hpp"
#include <nlohmann/json.hpp>
#include "inc/buffer/hvaVideoFrameWithMetaROIBuf.hpp"
#include "nodes/radarDatabaseMeta.hpp"
// #include "modules/inference_util/radar/radar_detection_helper.hpp"
#include "modules/inference_util/radar/radar_clustering_helper.hpp"
#include "modules/inference_util/radar/radar_tracking_helper.hpp"

#include <sys/types.h>
#include <sys/stat.h>
#include <sys/fcntl.h>
#include <sys/mman.h>

#define DIE_IF(cond)                                                                                                                                           \
    if (cond) {                                                                                                                                                \
        fprintf(stdout, "\033[31merror: %s. %s:%d\033[0m\n", #cond, __FILE__, __LINE__);                                                                       \
        return -__LINE__;                                                                                                                                      \
    }

using namespace hce::ai::inference;

class JsonReader {
  private:
    nlohmann::json m_contents;

  public:
    void read(const std::string &file_path);
    const nlohmann::json &content() const;

    static bool check_item(const nlohmann::json &content, std::string key);
    static void check_required_item(const nlohmann::json &content, std::string key);
    static void check_required_item(const nlohmann::json &content, std::vector<std::string> key_list);
};

void JsonReader::read(const std::string &file_path)
{
    std::ifstream input_file(file_path);
    if (not input_file)
        throw std::runtime_error("Radar Config file '" + file_path + "' was not found");

    input_file >> m_contents;
    input_file.close();
}

const nlohmann::json &JsonReader::content() const
{
    return m_contents;
}

bool JsonReader::check_item(const nlohmann::json &content, std::string key)
{
    auto iter = content.find(key);
    if (iter == content.end()) {
        return false;
    }
    if (iter.value() == "") {
        return false;
    }
    return true;
}

void JsonReader::check_required_item(const nlohmann::json &content, std::string key)
{
    if (!check_item(content, key)) {
        throw std::invalid_argument("Required property " + key + " not found in field!");
    }
}

void JsonReader::check_required_item(const nlohmann::json &content, std::vector<std::string> key_list)
{
    for (auto key : key_list) {
        if (!check_item(content, key)) {
            throw std::invalid_argument("Required property " + key + " not found in field!");
        }
    }
}

void readRadarConfigParam(RadarConfigParam &m_radar_config, std::string radarConfigPath)
{
    JsonReader m_json_reader;
    m_json_reader.read(radarConfigPath);
    const nlohmann::json &radar_config_content = m_json_reader.content();
    std::vector<std::string> required_fields = {"RadarBasicConfig", "RadarDetectionConfig", "RadarClusteringConfig", "RadarTrackingConfig"};
    JsonReader::check_required_item(radar_config_content, required_fields);
    // read RadarBasicConfig
    auto radar_basic_config_items = radar_config_content.at("RadarBasicConfig");
    for (auto &items : radar_basic_config_items) {
        m_radar_config.m_radar_basic_config_.numRx = items["numRx"].get<int>();
        m_radar_config.m_radar_basic_config_.numTx = items["numTx"].get<int>();
        m_radar_config.m_radar_basic_config_.Start_frequency = items["Start_frequency"].get<double>();
        m_radar_config.m_radar_basic_config_.idle = items["idle"].get<double>();
        m_radar_config.m_radar_basic_config_.adcStartTime = items["adcStartTime"].get<double>();
        m_radar_config.m_radar_basic_config_.rampEndTime = items["rampEndTime"].get<double>();
        m_radar_config.m_radar_basic_config_.freqSlopeConst = items["freqSlopeConst"].get<double>();
        m_radar_config.m_radar_basic_config_.adcSamples = items["adcSamples"].get<int>();
        m_radar_config.m_radar_basic_config_.numChirps = items["numChirps"].get<int>();
        m_radar_config.m_radar_basic_config_.fps = items["fps"].get<float>();
    }

    // read RadarDetectionConfig
    auto radar_detection_config_items = radar_config_content.at("RadarDetectionConfig");
    for (auto &items : radar_detection_config_items) {
        m_radar_config.m_radar_detection_config_.m_range_win_type_ = items["RangeWinType"].get<WinType>();
        m_radar_config.m_radar_detection_config_.m_doppler_win_type_ = items["DopplerWinType"].get<WinType>();
        m_radar_config.m_radar_detection_config_.m_aoa_estimation_type_ = items["AoaEstimationType"].get<AoaEstimationType>();
        m_radar_config.m_radar_detection_config_.m_doppler_cfar_method_ = items["DopplerCfarMethod"].get<CfarMethod>();
        m_radar_config.m_radar_detection_config_.DopplerPfa = items["DopplerPfa"].get<float>();
        m_radar_config.m_radar_detection_config_.DopplerWinGuardLen = items["DopplerWinGuardLen"].get<int>();
        m_radar_config.m_radar_detection_config_.DopplerWinTrainLen = items["DopplerWinTrainLen"].get<int>();
        m_radar_config.m_radar_detection_config_.m_range_cfar_method_ = items["RangeCfarMethod"].get<CfarMethod>();
        m_radar_config.m_radar_detection_config_.RangePfa = items["RangePfa"].get<float>();
        m_radar_config.m_radar_detection_config_.RangeWinGuardLen = items["RangeWinGuardLen"].get<int>();
        m_radar_config.m_radar_detection_config_.RangeWinTrainLen = items["RangeWinTrainLen"].get<int>();
    }

    // read RadarClusteringConfig
    auto radar_clustering_config_items = radar_config_content.at("RadarClusteringConfig");
    for (auto &items : radar_clustering_config_items) {
        m_radar_config.m_radar_clusterging_config_.eps = items["eps"].get<float>();
        m_radar_config.m_radar_clusterging_config_.weight = items["weight"].get<float>();
        m_radar_config.m_radar_clusterging_config_.minPointsInCluster = items["minPointsInCluster"].get<int>();
        m_radar_config.m_radar_clusterging_config_.maxClusters = items["maxClusters"].get<int>();
        m_radar_config.m_radar_clusterging_config_.maxPoints = items["maxPoints"].get<int>();
    }

    // read RadarTrackingConfig
    auto radar_tracking_config_items = radar_config_content.at("RadarTrackingConfig");
    for (auto &items : radar_tracking_config_items) {
        m_radar_config.m_radar_tracking_config_.trackerAssociationThreshold = items["trackerAssociationThreshold"].get<float>();
        m_radar_config.m_radar_tracking_config_.measurementNoiseVariance = items["measurementNoiseVariance"].get<float>();
        m_radar_config.m_radar_tracking_config_.timePerFrame = items["timePerFrame"].get<float>();
        m_radar_config.m_radar_tracking_config_.iirForgetFactor = items["iirForgetFactor"].get<float>();
        m_radar_config.m_radar_tracking_config_.trackerActiveThreshold = items["trackerActiveThreshold"].get<int>();
        m_radar_config.m_radar_tracking_config_.trackerForgetThreshold = items["trackerForgetThreshold"].get<int>();
    }
}

typedef struct MMS
{
    size_t sz;
    char *ptr;
} MMS;

size_t doMap(const char *path, MMS *mms)
{
    DIE_IF(nullptr == path || nullptr == mms);
    int fd = open(path, O_RDONLY);
    DIE_IF(fd < 0);
    struct stat bf;
    int err = fstat(fd, &bf);
    DIE_IF(err < 0);
    mms->sz = bf.st_size;
    mms->ptr = (char *)mmap(nullptr, mms->sz, PROT_READ, MAP_SHARED, fd, 0);
    DIE_IF(MAP_FAILED == mms->ptr);
    close(fd);
    return 0;
}

size_t undoMap(MMS *mms)
{
    DIE_IF(nullptr == mms);
    munmap(mms->ptr, mms->sz);
    return 0;
}

template <typename T> void readArray(char *ptr, std::vector<T> &arr, size_t &cur, const size_t len, bool last)
{
    size_t cCur = 0;
    size_t fCur = 0;
    char buf[64];
    for (; cur < len; ++cur) {
        if ('-' == ptr[cur] || '.' == ptr[cur] || ('0' <= ptr[cur] && '9' >= ptr[cur])) {
            buf[cCur++] = ptr[cur];
        }
        else if (',' == ptr[cur]) {
            buf[cCur] = 0;
            cCur = 0;
            arr[fCur] = (T)atof(buf);
            // printf("%f\n", arr[fCur]);
            fCur++;
        }
        else if (']' == ptr[cur]) {
            buf[cCur] = 0;
            arr[fCur] = (T)atof(buf);
            // printf("%f\n", arr[fCur]);
            cCur = 0;
            fCur++;
            break;
        }
    }
    if (last) {
        ++cur;
    }
    else {
        cur += 3;
    }
}

size_t readPointCloud(pointClouds *&pclArray, const char *filePath)
{
    DIE_IF(nullptr == filePath);
    MMS mms;
    DIE_IF(0 != doMap(filePath, &mms));
    char *ptr = mms.ptr;
    const size_t len = mms.sz;
    size_t rn = 0;
    for (size_t cur = 0; cur < len; ++cur) {
        if ('\n' == ptr[cur]) {
            rn++;
        }
    }
    DIE_IF(rn < 2);  // skip the header

    int cnt = rn - 1;

    pclArray = new pointClouds[cnt];
    DIE_IF(nullptr == pclArray);

    ptr = mms.ptr;
    size_t cur = 0;
    for (; cur < len; ++cur) {  // skip the header
        if ('\n' == ptr[cur]) {
            ++cur;
            break;
        }
    }

    char buf[64];
    size_t idx = 0;
    for (; cur < len; ++cur) {
        size_t cCur = 0;
        // the frameIndex
        for (; cur < len; ++cur) {
            if (',' == ptr[cur]) {
                ++cur;
                break;
            }
            if (' ' == ptr[cur])
                continue;
            buf[cCur++] = ptr[cur];
        }
        buf[cCur] = 0;

        // the numPoints
        cCur = 0;
        for (; cur < len; ++cur) {
            if (',' == ptr[cur]) {
                ++cur;
                break;
            }
            if (' ' == ptr[cur])
                continue;
            buf[cCur++] = ptr[cur];
        }
        buf[cCur] = 0;
        pclArray[idx].num = atoi(buf);


        if (0 != pclArray[idx].num) {
            pclArray[idx].rangeIdxArray.resize(pclArray[idx].num);
            pclArray[idx].rangeFloat.resize(pclArray[idx].num);
            pclArray[idx].speedIdxArray.resize(pclArray[idx].num);
            pclArray[idx].speedFloat.resize(pclArray[idx].num);
            pclArray[idx].SNRArray.resize(pclArray[idx].num);
            pclArray[idx].aoaVar.resize(pclArray[idx].num);

            readArray(ptr, pclArray[idx].rangeIdxArray, cur, len, false);  // the rangeIdxArray
            readArray(ptr, pclArray[idx].rangeFloat, cur, len, false);     // the rangeFloat
            readArray(ptr, pclArray[idx].speedIdxArray, cur, len, false);  // the speedIdxArray
            readArray(ptr, pclArray[idx].speedFloat, cur, len, false);     // the speedFloat
            readArray(ptr, pclArray[idx].aoaVar, cur, len, false);         // the aoaVar
            readArray(ptr, pclArray[idx].SNRArray, cur, len, true);        // the SNRArray
        }

        for (; cur < len; ++cur) {
            if ('\n' == ptr[cur]) {
                ++idx;
                break;
            }
        }
    }
    undoMap(&mms);
    return cnt;
}


void printPointClouds(pointClouds *pcl)
{
    if (0 == pcl->num) {
        printf("pointClouds{}\n");
    }
    else {
        printf("pointClouds{");
        printf("%d,\t", pcl->num);
        printf("[");
        for (int i = 0; i < pcl->num - 1; ++i) {
            printf("%f,", pcl->rangeFloat[i]);
        }
        printf("%f", pcl->rangeFloat[pcl->num - 1]);
        printf("],\t");

        // float *pointArray = (float *)malloc(sizeof(float) * pcl->num * 2);
        float *pointArray = new float[pcl->num * 2];
        for (int i = 0; i < pcl->num; ++i) {
            pointArray[i * 2] = pcl->rangeFloat[i] * cos(pcl->aoaVar[i] * M_PI / 180);
            pointArray[i * 2 + 1] = pcl->rangeFloat[i] * sin(pcl->aoaVar[i] * M_PI / 180);
        }

        printf("[");
        for (int i = 0; i < pcl->num * 2 - 1; ++i) {
            printf("%f,", pointArray[i]);
        }
        printf("%f", pointArray[pcl->num * 2 - 1]);
        printf("],\t");
        delete[] pointArray;

        printf("[");
        for (int i = 0; i < pcl->num - 1; ++i) {
            printf("%f,", pcl->speedFloat[i]);
        }
        printf("%f", pcl->speedFloat[pcl->num - 1]);
        printf("],\t");


        printf("[");
        for (int i = 0; i < pcl->num - 1; ++i) {
            printf("%f,", pcl->aoaVar[i]);
        }
        printf("%f", pcl->aoaVar[pcl->num - 1]);
        printf("],\t");

        printf("[");
        for (int i = 0; i < pcl->num - 1; ++i) {
            printf("%f,", pcl->SNRArray[i]);
        }
        printf("%f", pcl->SNRArray[pcl->num - 1]);
        printf("],\t");

        printf("}\n");
    }
}

int main(int argc, char **argv)
{
    try {
        // Check command line arguments.
        if (5 != argc) {
            std::cerr << "Usage: testRadarClusteringTrackingNode <repeats> <configure_file> "
                         "<image_folder> <hdf5_folder>\n"
                      << "Example:\n"
                      << "    testRadarClusteringTrackingNode 1 "
                         "../../ai_inference/test/configs/unit_tests/"
                         "UTradarClusteringTracking.json /path/to/radar_config /path/to/point_clouds_csv_file\n"
                      << "-----------------------------------------------------------"
                         "--------------------- \n"
                      << "Environment requirement:\n"
                      << "   export "
                         "HVA_NODE_DIR=/opt/hce-core/middleware/ai/build/lib \n"
                      << "   source /opt/intel/openvino*/setupvars.sh \n";
            return EXIT_FAILURE;
        }

        unsigned repeats(atoi(argv[1]));
        std::string config_file(argv[2]);
        std::string radarConfigPath(argv[3]);
        // std::string radarConfigPath = "/home/chaofan/workspaces/holographic-sensor-fusion/ai_inference/deployment/datasets/RadarConfig.json";
        std::string csvFile(argv[4]);

        RadarConfigParam m_radar_config;

        readRadarConfigParam(m_radar_config, radarConfigPath);

        hvaLogger.setLogLevel(hva::hvaLogger_t::LogLevel::DEBUG);
        hvaLogger.enableProfiling();

        hva::hvaNodeRegistry::getInstance().init(HVA_NODE_REGISTRY_NO_DLCLOSE | HVA_NODE_REGISTRY_RTLD_GLOBAL);

        std::string contents;

        std::ifstream in(config_file, std::ios::in);
        if (in) {
            in.seekg(0, std::ios::end);
            contents.resize(in.tellg());
            in.seekg(0, std::ios::beg);
            in.read(&contents[0], contents.size());
            in.close();
        }
        else {
            HVA_ERROR("invalid config file!");
            HVA_ASSERT(false);
        }
        std::cout << contents << std::endl;

        hva::hvaPipelineParser_t parser;
        std::shared_ptr<hva::hvaPipeline_t> pl(new hva::hvaPipeline_t());

        parser.parseFromString(contents, *pl);

        pl->prepare();

        HVA_INFO("Pipeline Start: ");
        pl->start();

        pointClouds *pclArray = nullptr;
        int samplesCnt = readPointCloud(pclArray, csvFile.c_str());
        std::cout << "Total read " << samplesCnt << " records." << std::endl;
        // std::shared_ptr<pointClouds> pclShared = std::shared_ptr<pointClouds>(pclArray);
        // pointClouds *test = pclShared[0];

        // printPointClouds(&pclArray[2199]);

        unsigned frameIdx = 0;
        for (size_t cnt = 0; cnt < repeats; cnt++) {
            HVA_DEBUG("Send pointClouds %d", cnt);
            hva::hvaVideoFrameWithMetaROIBuf_t::Ptr hvabuf = hva::hvaVideoFrameWithMetaROIBuf_t::make_buffer<pointClouds>(pclArray[cnt], sizeof(pointClouds));

            hvabuf->frameId = frameIdx;
            ++frameIdx;
            hvabuf->drop = false;
            if (cnt == repeats - 1) {
                hvabuf->tagAs(1);
            }
            else {
                hvabuf->tagAs(0);
            }

            // HceDatabaseMeta meta;
            // meta.radarConfigPath = radarConfigPath;
            // meta.radarParams = m_radar_config;
            // hvabuf->setMeta(meta);
            hvabuf->setMeta(m_radar_config);

            auto pclBlob = hva::hvaBlob_t::make_blob();
            pclBlob->frameId = frameIdx;
            pclBlob->push(hvabuf);

            pl->sendToPort(pclBlob, "Clustering", 0, std::chrono::milliseconds(0));
        }

        // wait till pipeline consuming all input frames
        // this is the maximum processing time as estimated, not stand for the real
        // duration.
        int estimate_latency = repeats * 30;  // 100ms for each image
        HVA_INFO("going to sleep for %d s", estimate_latency);
        std::this_thread::sleep_for(std::chrono::seconds(estimate_latency));

        HVA_INFO("going to stop");
        pl->stop();
        HVA_INFO("hva pipeline stopped.");

        // for (int idx = 0; idx < samplesCnt; ++idx) {
        //     if (0 != pclArray[idx].num) {
        //         delete[] pclArray[idx].rangeArray.rangeFloat;
        //         delete[] pclArray[idx].speed.speedFloat;
        //         delete[] pclArray[idx].SNRArray;
        //         delete[] pclArray[idx].aoaVar;
        //     }
        // }
        delete[] pclArray;

        return EXIT_SUCCESS;
    }
    catch (std::exception const &e) {
        std::cerr << "Error: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }
    return EXIT_SUCCESS;
}
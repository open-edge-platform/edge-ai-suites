#ifndef HVA_PERFORMANCE_MONITOR_HPP
#define HVA_PERFORMANCE_MONITOR_HPP

#include <mutex>
#include <vector>
#include <memory>
#include <unordered_map>
#include <inc/api/hvaEvent.hpp>
#include <inc/util/hvaUtil.hpp>

namespace hva {
    
    struct timeStampInfo {
        timeStampInfo () : frameId(0), name(""), timeStamp(0) {}

        timeStampInfo (unsigned frameId, std::string name)
            : frameId(frameId), name(name), timeStamp(0) {}

        unsigned frameId;
        std::string name;
        int64_t timeStamp;
    };

    struct LatencyInfo
    {
        LatencyInfo (): name(""), avgLatency(0.0), avgThroughput(0.0), processCnt(0) {}

        std::string name;
        std::chrono::time_point<std::chrono::high_resolution_clock> startTime;
        float avgLatency;
        float avgThroughput;
        size_t processCnt;
    };

    class HVA_DECLSPEC hvaNodeLatencyMonitor_t {
        public:
            hvaNodeLatencyMonitor_t();

            ~hvaNodeLatencyMonitor_t();

            void startRecording(size_t frameId, std::string name);

            void stopRecording(size_t frameId, std::string name);

            std::unordered_map<std::string, LatencyInfo>& getLatencyInfo();

            void reset();

        private:
            std::unordered_map<std::string, LatencyInfo> m_latencyMap;
            std::unordered_map<std::string, std::chrono::time_point<std::chrono::high_resolution_clock>> m_startTimeMap;
            std::mutex m_mutex;
    };

    class HVA_DECLSPEC hvaPipelinePerformanceMonitor_t {
        public:
            hvaPipelinePerformanceMonitor_t();

            ~hvaPipelinePerformanceMonitor_t();

            void recordLatencty(unsigned frameId);

            void recordTimeStamp(std::shared_ptr<timeStampInfo> info);

            float getAvgLatency();

            size_t getProcessCnt();

            std::unordered_map<unsigned, std::vector<std::shared_ptr<timeStampInfo>>>& getTimeStamps();

            void reset();

        private:
            std::unordered_map<unsigned, std::chrono::time_point<std::chrono::high_resolution_clock>> m_latencyMap;
            std::unordered_map<unsigned, std::vector<std::shared_ptr<timeStampInfo>>> m_timeStampMap;
            float m_avgLatency;
            size_t m_processCnt;
            std::mutex m_latencyMutex;
            std::mutex m_timestampMutex;
    };

    class _PipelineLatencyCaptureListener : public hvaEventListener_t {
        public:
            _PipelineLatencyCaptureListener(hvaPipelinePerformanceMonitor_t& LatencyMonitor);

            virtual bool onEvent(void* data) override;

        private:
            hvaPipelinePerformanceMonitor_t& m_PlLatencyMonitor;        
    };

    class _TimeStampRecordListener : public hvaEventListener_t {
        public:
            _TimeStampRecordListener(hvaPipelinePerformanceMonitor_t& LatencyMonitor);

            virtual bool onEvent(void* data) override;

        private:
            hvaPipelinePerformanceMonitor_t& m_PlLatencyMonitor;
    };

}

#endif

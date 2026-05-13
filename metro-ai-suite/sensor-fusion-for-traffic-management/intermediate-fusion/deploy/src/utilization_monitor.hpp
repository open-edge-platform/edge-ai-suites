#pragma once

#include <atomic>
#include <cstddef>
#include <mutex>
#include <string>
#include <thread>

class UtilizationMonitor {
  public:
    struct Options
    {
        bool enable;
        /// CPU sampling interval (ms).  /proc/stat is cheap, so this can be low.
        int interval_ms;
        /// GPU sampling interval (ms).  xpu-smi spawns a subprocess, so keep this
        /// higher to avoid excessive process creation overhead.
        int gpu_interval_ms;
        // Override with env var XPU_SMI_CMD if needed.
        std::string gpu_command;

        Options() : enable(true), interval_ms(50), gpu_interval_ms(100), gpu_command("sudo timeout 1 xpu-smi stats -d 0 -j") {}
    };

    explicit UtilizationMonitor(const Options &opts = Options());
    ~UtilizationMonitor();

    // Non-copyable, non-movable (owns running threads).
    UtilizationMonitor(const UtilizationMonitor &) = delete;
    UtilizationMonitor &operator=(const UtilizationMonitor &) = delete;

    bool start();
    void stop();

    /// Reset all accumulated statistics.  Call after warmup to exclude
    /// initialization data from reported averages.
    void reset();

    double avgCpuUtil() const;
    double avgGpuUtil() const;
    double latestCpuUtil() const;
    double latestGpuUtil() const;
    std::size_t cpuSamples() const;
    std::size_t gpuSamples() const;

  private:
    struct CpuTimes
    {
        unsigned long long user = 0;
        unsigned long long nice = 0;
        unsigned long long system = 0;
        unsigned long long idle = 0;
        unsigned long long iowait = 0;
        unsigned long long irq = 0;
        unsigned long long softirq = 0;
        unsigned long long steal = 0;
    };

    void cpuLoop_();
    void gpuLoop_();
    bool readCpuUtil_(double &out);
    bool readGpuUtil_(double &out);
    bool readProcStat_(CpuTimes &out);

    Options opts_;
    std::string gpu_cmd_cached_;  // resolved once at start()
    std::thread cpu_worker_;
    std::thread gpu_worker_;
    std::atomic<bool> running_{false};

    // CPU accumulators (guarded by cpu_mutex_)
    mutable std::mutex cpu_mutex_;
    double cpu_sum_ = 0.0;
    std::size_t cpu_count_ = 0;
    double cpu_latest_ = 0.0;

    // GPU accumulators (guarded by gpu_mutex_)
    mutable std::mutex gpu_mutex_;
    double gpu_sum_ = 0.0;
    std::size_t gpu_count_ = 0;
    double gpu_latest_ = 0.0;

    // CPU-only state (only accessed from cpu_worker_ thread)
    bool has_prev_cpu_ = false;
    CpuTimes prev_cpu_;
};

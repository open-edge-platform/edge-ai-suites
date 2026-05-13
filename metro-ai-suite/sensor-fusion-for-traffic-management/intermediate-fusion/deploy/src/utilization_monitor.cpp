#include "utilization_monitor.hpp"

#include <array>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <thread>

#include <boost/property_tree/json_parser.hpp>
#include <boost/property_tree/ptree.hpp>

UtilizationMonitor::UtilizationMonitor(const Options &opts) : opts_(opts) {}

UtilizationMonitor::~UtilizationMonitor()
{
    stop();
}

bool UtilizationMonitor::start()
{
    if (!opts_.enable)
        return true;
    if (running_.load())
        return true;

    // Resolve GPU command once: env var takes priority, then Options.
    const char *env_cmd = std::getenv("XPU_SMI_CMD");
    gpu_cmd_cached_ = (env_cmd && *env_cmd) ? std::string(env_cmd) : opts_.gpu_command;

    running_.store(true);
    cpu_worker_ = std::thread(&UtilizationMonitor::cpuLoop_, this);
    if (!gpu_cmd_cached_.empty()) {
        gpu_worker_ = std::thread(&UtilizationMonitor::gpuLoop_, this);
    }
    return true;
}

void UtilizationMonitor::stop()
{
    if (!running_.load())
        return;
    running_.store(false);
    if (cpu_worker_.joinable()) {
        cpu_worker_.join();
    }
    if (gpu_worker_.joinable()) {
        gpu_worker_.join();
    }
}

void UtilizationMonitor::reset()
{
    {
        std::lock_guard<std::mutex> lock(cpu_mutex_);
        cpu_sum_ = 0.0;
        cpu_count_ = 0;
        cpu_latest_ = 0.0;
    }
    {
        std::lock_guard<std::mutex> lock(gpu_mutex_);
        gpu_sum_ = 0.0;
        gpu_count_ = 0;
        gpu_latest_ = 0.0;
    }
}

double UtilizationMonitor::avgCpuUtil() const
{
    std::lock_guard<std::mutex> lock(cpu_mutex_);
    return cpu_count_ > 0 ? (cpu_sum_ / static_cast<double>(cpu_count_)) : 0.0;
}

double UtilizationMonitor::avgGpuUtil() const
{
    std::lock_guard<std::mutex> lock(gpu_mutex_);
    return gpu_count_ > 0 ? (gpu_sum_ / static_cast<double>(gpu_count_)) : 0.0;
}

double UtilizationMonitor::latestCpuUtil() const
{
    std::lock_guard<std::mutex> lock(cpu_mutex_);
    return cpu_latest_;
}

double UtilizationMonitor::latestGpuUtil() const
{
    std::lock_guard<std::mutex> lock(gpu_mutex_);
    return gpu_latest_;
}

std::size_t UtilizationMonitor::cpuSamples() const
{
    std::lock_guard<std::mutex> lock(cpu_mutex_);
    return cpu_count_;
}

std::size_t UtilizationMonitor::gpuSamples() const
{
    std::lock_guard<std::mutex> lock(gpu_mutex_);
    return gpu_count_;
}

void UtilizationMonitor::cpuLoop_()
{
    using namespace std::chrono;
    const auto sleep_dur = milliseconds(std::max(10, opts_.interval_ms));

    while (running_.load()) {
        double cpu = 0.0;
        const bool cpu_ok = readCpuUtil_(cpu);

        if (cpu_ok) {
            std::lock_guard<std::mutex> lock(cpu_mutex_);
            cpu_sum_ += cpu;
            cpu_count_ += 1;
            cpu_latest_ = cpu;
        }

        std::this_thread::sleep_for(sleep_dur);
    }
}

void UtilizationMonitor::gpuLoop_()
{
    using namespace std::chrono;
    const auto sleep_dur = milliseconds(std::max(100, opts_.gpu_interval_ms));

    while (running_.load()) {
        double gpu = 0.0;
        const bool gpu_ok = readGpuUtil_(gpu);

        if (gpu_ok) {
            std::lock_guard<std::mutex> lock(gpu_mutex_);
            gpu_sum_ += gpu;
            gpu_count_ += 1;
            gpu_latest_ = gpu;
        }

        std::this_thread::sleep_for(sleep_dur);
    }
}

bool UtilizationMonitor::readProcStat_(CpuTimes &out)
{
    std::ifstream fin("/proc/stat");
    if (!fin)
        return false;

    std::string label;
    fin >> label;
    if (label != "cpu")
        return false;

    fin >> out.user >> out.nice >> out.system >> out.idle >> out.iowait >> out.irq >> out.softirq >> out.steal;
    return true;
}

bool UtilizationMonitor::readCpuUtil_(double &out)
{
    CpuTimes cur;
    if (!readProcStat_(cur))
        return false;

    if (!has_prev_cpu_) {
        prev_cpu_ = cur;
        has_prev_cpu_ = true;
        return false;
    }

    const unsigned long long prev_idle = prev_cpu_.idle + prev_cpu_.iowait;
    const unsigned long long cur_idle = cur.idle + cur.iowait;

    const unsigned long long prev_total =
        prev_cpu_.user + prev_cpu_.nice + prev_cpu_.system + prev_cpu_.idle + prev_cpu_.iowait + prev_cpu_.irq + prev_cpu_.softirq + prev_cpu_.steal;
    const unsigned long long cur_total = cur.user + cur.nice + cur.system + cur.idle + cur.iowait + cur.irq + cur.softirq + cur.steal;

    const unsigned long long total_delta = cur_total - prev_total;
    const unsigned long long idle_delta = cur_idle - prev_idle;

    prev_cpu_ = cur;

    if (total_delta == 0)
        return false;

    const double util = 100.0 * (1.0 - (static_cast<double>(idle_delta) / static_cast<double>(total_delta)));
    out = util < 0.0 ? 0.0 : (util > 100.0 ? 100.0 : util);
    return true;
}

bool UtilizationMonitor::readGpuUtil_(double &out)
{
    if (gpu_cmd_cached_.empty())
        return false;

    std::array<char, 256> buffer;
    std::string result;
    FILE *pipe = popen(gpu_cmd_cached_.c_str(), "r");
    if (!pipe)
        return false;
    while (fgets(buffer.data(), buffer.size(), pipe) != nullptr) {
        result += buffer.data();
    }
    const int status = pclose(pipe);
    if (status != 0) {
        // Subprocess failed (non-zero exit or signal).
        return false;
    }

    if (result.empty())
        return false;

    // Parse JSON output from xpu-smi -j.
    try {
        std::istringstream jsonStream(result);
        boost::property_tree::ptree pt;
        boost::property_tree::read_json(jsonStream, pt);

        // xpu-smi stats -j: use engine_util.compute max value
        if (auto compute = pt.get_child_optional("engine_util.compute")) {
            double max_val = -1.0;
            for (const auto &item : *compute) {
                const double v = item.second.get<double>("value", -1.0);
                if (v > max_val) {
                    max_val = v;
                }
            }
            if (max_val >= 0.0) {
                out = max_val;
                return true;
            }
        }
    }
    catch (const std::exception &e) {
        // JSON parse error — command output may not be JSON.
        std::cerr << "[UtilizationMonitor] GPU JSON parse error: " << e.what() << std::endl;
    }

    return false;
}

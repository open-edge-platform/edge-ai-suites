// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
// 
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
// 
// http://www.apache.org/licenses/LICENSE-2.0
// 
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#pragma once

#include <spdlog/spdlog.h>

#include <boost/format.hpp>
#include <sstream>
#include <string>
#include <vector>

class ProcInfo {
protected:
    friend class LoopTimer;

    ProcInfo(const std::string &name, bool verbose) : name(name), count(0), totalTimeNs(0), verbose_(verbose)
    {
        this->startTime_.tv_sec = 0;
        this->startTime_.tv_nsec = 0;
    }

    inline void start(const timespec &time)
    {
        startTime_ = time;
        if (verbose_) spdlog::debug("[LoopTimer] {} starts\n", name);
    }

    inline void end(const timespec &time)
    {
        long long timeNs = (time.tv_sec - startTime_.tv_sec) * 1000000000ULL + time.tv_nsec - startTime_.tv_nsec;
        totalTimeNs += timeNs;
        count++;
        if (verbose_) spdlog::debug("[LoopTimer] {0} spent {1:.2f} ms\n", name, (double)timeNs * 1e-6);
    }

    std::string name;
    unsigned int count;
    long long totalTimeNs;

private:
    timespec startTime_;
    bool verbose_;
};

class LoopTimer {
public:
    LoopTimer(bool verbose = false)
        : loop_("Total", verbose), current_(procs_.begin()), verbose_(verbose), started_(false)
    {
        this->totalTimeMs_ = 0;
        this->startTime_.tv_sec = 0;
        this->startTime_.tv_nsec = 0;
        this->now_.tv_sec = 0;
        this->now_.tv_nsec = 0;
    }

    ~LoopTimer() {}

    inline void setName(std::string name) { name_ = name; }

    inline void reset()
    {
        procs_.clear();
        current_ = procs_.begin();
        loop_.totalTimeNs = 0;
        loop_.count = 0;
    }

    inline void start()
    {
        started_ = true;
        clock_gettime(CLOCK_MONOTONIC, &startTime_);
    }

#ifndef DISABLE_TIMER
    inline void startFirstProc(const std::string name)
    {
        clock_gettime(CLOCK_MONOTONIC, &now_);
        startFirstProc(name, now_);
    }

    inline void startFirstProc(const std::string name, const timespec &time)
    {
        findProc(name);
        current_->start(time);
        loop_.start(time);
    }

    inline void startNextProc(const std::string name)
    {
        clock_gettime(CLOCK_MONOTONIC, &now_);
        startNextProc(name, now_);
    }

    inline void startNextProc(const std::string name, const timespec &time)
    {
        current_->end(time);
        findProc(name);
        current_->start(time);
    }

    inline void endCycle()
    {
        clock_gettime(CLOCK_MONOTONIC, &now_);
        endCycle(now_);
    }

    inline void endCycle(const timespec time)
    {
        current_->end(time);
        loop_.end(time);
    }

    inline void finish()
    {
        if (!started_) return;
        started_ = false;
        clock_gettime(CLOCK_MONOTONIC, &now_);
        totalTimeMs_ = (now_.tv_sec - startTime_.tv_sec) * 1000 + (now_.tv_nsec - startTime_.tv_nsec) / (double)1000000;

        // Format result here so it only runs once even if user calls result() for multiple times
        formatResult();
    }

#else  /* DISABLE_TIMER */
    inline void startFirstProc(...) {}

    inline void startNextProc(...) {}

    inline void endCycle(...) { count_++; }

    inline void finish()
    {
        if (!started_) return;
        started_ = false;
        clock_gettime(CLOCK_MONOTONIC, &now_);
        double totalTimeMs =
            (now_.tv_sec - startTime_.tv_sec) * 1000 + (now_.tv_nsec - startTime_.tv_nsec) / (double)1000000;

        // Format result here
        result_ = (boost::format("Totel elapsed time: %1$.2lf s  Frequency: %2$.1f Hz\n") % (totalTimeMs / 1000) %
                   (count_ * 1000 / totalTimeMs))
                      .str();
    }
#endif /* DISABLE_TIMER */

    inline std::string &result() { return result_; }

private:
    // Find the proc in procs_ that fits the given name. Make a new one if not found.
    inline void findProc(const std::string &name)
    {
        auto begin = current_;
        for (; current_ != procs_.end(); current_++)
            if (current_->name == name) return;
        for (current_ = procs_.begin(); current_ != begin; current_++)
            if (current_->name == name) return;
        procs_.push_back(ProcInfo(name, verbose_));
        current_ = procs_.end() - 1;
    }

    inline void formatResult()
    {
        std::stringstream ss;
        if (!name_.empty()) ss << name_ << " Performance:\n";
        // Do not print the table if there is no procedure
        if (!procs_.empty()) {
            std::string title("Procedure");
            auto nameLen = title.size();
            procs_.push_back(loop_);
            for (current_ = procs_.begin(); current_ != procs_.end(); current_++)
                if (current_->name.size() > nameLen) nameLen = current_->name.size();
            std::string segment(nameLen + 36, '-');
            segment += "\n";
            title.resize(nameLen, ' ');
            ss << segment << title << "  Average Time   Total Time%   Count\n" << segment;
            for (current_ = procs_.begin(); current_ != procs_.end(); current_++) {
                if (current_ + 1 == procs_.end()) ss << segment;
                current_->name.resize(nameLen, ' ');
                double timeMs = (double)current_->totalTimeNs / 1000000;
                double ratio = timeMs / totalTimeMs_ * 100;
                timeMs = timeMs / current_->count;
                ss << current_->name;
                if (timeMs > 10000)
                    ss << boost::format(" %1$9.3lf s  %2$10.2lf %3$10d\n") % (timeMs / 1000) % ratio % current_->count;
                else if (timeMs > 0.01)
                    ss << boost::format(" %1$9.2lf ms %2$10.2lf %3$10d\n") % timeMs % ratio % current_->count;
                else if (timeMs > 0.01 * 1e-3)
                    ss << boost::format(" %1$9.1lf us %2$10.2lf %3$10d\n") % (timeMs * 1000) % ratio % current_->count;
                else
                    ss << boost::format(" %1$9.0lf ns %2$10.2lf %3$10d\n") % (timeMs * 1e6) % ratio % current_->count;
            }
            ss << segment;
        }
        ss << boost::format("Total elapsed time: %1$.2lf %2$3s    Frequency: %3$.1f Hz\n") %
                  ((totalTimeMs_ > 1000) ? totalTimeMs_ / 1000 : totalTimeMs_) % ((totalTimeMs_ > 1000) ? "s" : "ms") %
                  (loop_.count * 1000 / totalTimeMs_);
        result_ = ss.str();
    }

    std::string name_;
    ProcInfo loop_;
    std::vector<ProcInfo> procs_;
    std::vector<ProcInfo>::iterator current_;
    timespec startTime_, now_;
    double totalTimeMs_;
    std::string result_;
    bool verbose_;
    bool started_;
};

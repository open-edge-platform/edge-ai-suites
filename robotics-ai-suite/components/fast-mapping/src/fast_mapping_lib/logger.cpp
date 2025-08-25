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

#include <array>
#include <functional>
#include <iostream>
#include <iomanip>
#include <memory>
#include <mutex>
#include <sstream>

#include "logger.h"

FastMappingLogger logger;

LockedLogger::LockedLogger(FastMappingLogger& fmLogger) :
    logger(fmLogger),
    mlock(logger.iomutex, std::defer_lock)
{
  mlock.lock();
}

LockedLogger::~LockedLogger()
{ 
}

void FastMappingLogger::flushToOutput()
{
    if (verbosity <= verbosityLevel)
    {
        *out << outStrStrm.str() << std::flush;
    }
    outStrStrm.str("");
}

FastMappingLogger& FastMappingLogger::setMsgVerbosity(const Verbosity msgVerbosity)
{
    this->verbosity = msgVerbosity;

    if (msgVerbosity == Verbosity::error)
    {
        out = &std::cerr;
    }
    else
    {
        out = &std::cout;
    }
    return *this;
}

void FastMappingLogger::setFMVerbosity(Verbosity verbosity)
{
    verbosityLevel = verbosity;
}

FastMappingLogger::~FastMappingLogger()
{
    flushToOutput();
}

FastMappingLogger& FastMappingLogger::operator<<(std::ios_base &(*func)(std::ios_base &))
{
    outStrStrm << func;
    return *this;
}

FastMappingLogger& FastMappingLogger::operator<<(std::ostream &(*func)(std::ostream &))
{
    outStrStrm << func;
    if ((func == static_cast<std::ostream &(*)
        (std::ostream &)>(&std::endl<char, std::char_traits<char>>))
        ||
        (func == static_cast<std::ostream &(*)
        (std::ostream &)>(&std::flush<char, std::char_traits<char>>)))
    {
        flushToOutput();
    }
    return *this;
}

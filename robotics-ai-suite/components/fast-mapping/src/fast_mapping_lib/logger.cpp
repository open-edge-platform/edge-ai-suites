// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include "logger.h"

#include <array>
#include <functional>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>

FastMappingLogger logger;

LockedLogger::LockedLogger(FastMappingLogger & fmLogger)
: logger(fmLogger), mlock(logger.iomutex, std::defer_lock)
{
  mlock.lock();
}

LockedLogger::~LockedLogger() {}

void FastMappingLogger::flushToOutput()
{
  if (verbosity <= verbosityLevel) {
    *out << outStrStrm.str() << std::flush;
  }
  outStrStrm.str("");
}

FastMappingLogger & FastMappingLogger::setMsgVerbosity(const Verbosity msgVerbosity)
{
  this->verbosity = msgVerbosity;

  if (msgVerbosity == Verbosity::error) {
    out = &std::cerr;
  } else {
    out = &std::cout;
  }

  return *this;
}

void FastMappingLogger::setFMVerbosity(Verbosity verbosity) { verbosityLevel = verbosity; }

FastMappingLogger::~FastMappingLogger() { flushToOutput(); }

FastMappingLogger & FastMappingLogger::operator<<(std::ios_base & (*func)(std::ios_base &))
{
  outStrStrm << func;
  return *this;
}

FastMappingLogger & FastMappingLogger::operator<<(std::ostream & (*func)(std::ostream &))
{
  outStrStrm << func;
  if (
    (func ==
     static_cast<std::ostream & (*)(std::ostream &)>(&std::endl<char, std::char_traits<char>>)) ||
    (func ==
     static_cast<std::ostream & (*)(std::ostream &)>(&std::flush<char, std::char_traits<char>>))) {
    flushToOutput();
  }

  return *this;
}

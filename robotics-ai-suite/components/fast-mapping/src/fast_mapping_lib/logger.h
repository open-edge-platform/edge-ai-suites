// Copyright (C) 2025 Intel Corporation
//
// SPDX-License-Identifier: Apache-2.0

#include <array>
#include <functional>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>

#define FM_LOG(level) LockedLogger(logger)->setMsgVerbosity(FastMappingLogger::Verbosity::level)

class FastMappingLogger;

class LockedLogger
{
public:
  LockedLogger(FastMappingLogger & logger);

  ~LockedLogger();

  inline FastMappingLogger * operator->() { return &logger; }

private:
  FastMappingLogger & logger;
  std::unique_lock<std::mutex> mlock;
};

class FastMappingLogger
{
public:
  enum class Verbosity { error = 0, warning = 1, info = 2, debug = 3 };

  ~FastMappingLogger();

  void setFMVerbosity(Verbosity level);

  FastMappingLogger & operator<<(std::ostream & (*func)(std::ostream &));

  FastMappingLogger & setMsgVerbosity(const Verbosity verbosity);

  FastMappingLogger & operator<<(std::ios_base & (*func)(std::ios_base &));

  template <class CharT, class Traits = std::char_traits<CharT>>
  FastMappingLogger & operator<<(
    std::basic_ostream<CharT, Traits> & (*func)(std::basic_ostream<CharT, Traits> &))
  {
    outStrStrm << func;

    return *this;
  }

  template <class CharT, class Traits = std::char_traits<CharT>>
  FastMappingLogger & operator<<(std::basic_streambuf<CharT, Traits> * sb)
  {
    outStrStrm << sb;

    return *this;
  }

  template <class T>
  FastMappingLogger & operator<<(T && arg)
  {
    if (outStrStrm.str().empty()) {
      if (prefix.empty()) {
        switch (verbosity) {
          case Verbosity::error:
            prefix = "[error]: ";
            break;
          case Verbosity::warning:
            prefix = "[warn]: ";
            break;
          case Verbosity::info:
            prefix = "[info]: ";
            break;
          case Verbosity::debug:
            prefix = "[debug]: ";
            break;
        }
      }
      outStrStrm << prefix;
      prefix = "";
    }
    outStrStrm << std::forward<T>(arg);

    return *this;
  }

private:
  friend class LockedLogger;

  void flushToOutput();

  Verbosity verbosity = Verbosity::info;
  Verbosity verbosityLevel = Verbosity::info;
  std::ostream * out = &std::cout;
  std::mutex iomutex;
  std::string prefix;
  std::stringstream outStrStrm;
};

extern FastMappingLogger logger;

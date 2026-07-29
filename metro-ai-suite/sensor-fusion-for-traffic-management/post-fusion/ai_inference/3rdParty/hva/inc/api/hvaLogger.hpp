#ifndef HVA_LOGGER_HPP
#define HVA_LOGGER_HPP

#define ENABLE_LOG

#include <iostream>
#include <mutex>
#include <fstream>
#include <sstream>
#include <chrono>
#include <iomanip>
#include <inc/util/hvaUtil.hpp>
#if defined(__linux__)
#include <unistd.h>
#include <sys/syscall.h>
#endif //#if defined(__linux__)

namespace hva{

using ms = std::chrono::milliseconds;

/**
* @brief a singleton logger which dumps the logs to terminal or/and file
* 
*/
class HVA_DECLSPEC hvaLogger_t{
public:
    enum LogLevel : unsigned {
        ERROR = 0x01,
        WARNING = 0x02,
        INFO = 0x04,
        DEBUG = 0x08,
        DISABLED = 0x00
    };

    hvaLogger_t(const hvaLogger_t&) = delete;
    hvaLogger_t& operator=(const hvaLogger_t&) = delete;

    ~hvaLogger_t();

    static hvaLogger_t& getInstance();

    /**
    * @brief main entry for log
    * 
    * @param level current log level
    * @param file the source file triggered
    * @param line the line of code triggered
    * @param msg the formatted string of log message
    * @param args variadic arugment on formatted string
    * @return void
    * 
    */
    template<typename... Args>
    void log(LogLevel level,const char* file, const char* func, long line, const char* msg, Args... args);

    /**
    * @brief set the log ignorance level. Only those log with levels above the level set will be printed
    * 
    * @param logLevel the log level that this application will print out
    * @return void
    * 
    */
    void setLogLevel(unsigned logLevel);

    /**
    * @brief get current log level
    * 
    * @param void
    * @return the log level currently configured
    * 
    */
    unsigned getLogLevel() const;

    /**
    * @brief set the logger to dump to file
    * 
    * @param filename the file that logs will be saved
    * @param dumpToFileOnly if this sets to true, logger will only dump to file with no output on terminal
    * @return void
    * 
    */
    void dumpToFile(const std::string& filename, bool dumpToFileOnly);

    /**
    * @brief tell logger to add more profiling information on logs printed out. This includes the time stamp
    *           as well as the actual thread id that logs are generated
    * 
    * @param void
    * @return void
    * 
    */
    void enableProfiling();

    /**
    * @brief disable profiling
    * 
    * @param void
    * @return void
    * 
    * @sa hvaLogger_t::enableProfiling()
    */
    void disableProfiling();

private:
    hvaLogger_t();

    unsigned m_logLevel;
    std::mutex m_mutex;
    std::ofstream m_oStream;
    bool m_enablePrintToConsole;
    bool m_enablePrintToLog;
    std::string m_filename;
    volatile bool m_enableProfiling;
};

template<typename... Args>
void hvaLogger_t::log(LogLevel level,const char* file, const char* func, long line, const char* msg, Args... args){
#ifdef ENABLE_LOG
    if(!(static_cast<unsigned>(level) & m_logLevel)){
        return;
    }
    std::stringstream stream;
    switch(level){
        case LogLevel::DEBUG:
            stream<< std::setw(9) << "[DEBUG]";
            break;
        case LogLevel::INFO:
            stream<< std::setw(9) << "[INFO]";
            break;
        case LogLevel::WARNING:
            stream<< std::setw(9) <<"[WARNING]";
            break;
        case LogLevel::ERROR:
            stream<< std::setw(9) <<"[ERROR]";
            break;
        default:
            stream<< std::setw(9) <<"[UNKOWN]";
            break;
    }
    if(m_enableProfiling){
#if defined(__linux__)
        stream<<" ["<< syscall(SYS_gettid)<<"]";
#endif //#if defined(__linux__)
        stream<<" ["<< (std::chrono::duration_cast<ms>(std::chrono::high_resolution_clock::now().time_since_epoch())).count()<<"]";
    }
    stream<<": "<<file<<":"<<line<<" "<<func<<" "<<string_format(msg, args...);
        
    std::lock_guard<std::mutex> lg(m_mutex);

    if(m_enablePrintToConsole){
        std::cout<<stream.str()<<std::endl;
    }

    if(m_enablePrintToLog){
        m_oStream << stream.str()<<std::endl;
    }

#endif //#ifdef ENABLE_LOG
}

#define hvaLogger ::hva::hvaLogger_t::getInstance()

#define hva_setLogLevel(LEVEL) hvaLogger.setLogLevel(LEVEL)
#define hva_getLogLevel() hvaLogger.getLogLevel()

#ifdef ENABLE_LOG

#if defined(__linux__)
#define __FILENAME__ (__builtin_strrchr(__FILE__, '/') ? __builtin_strrchr(__FILE__, '/') + 1 : __FILE__)
#elif defined(WIN32)
#define __FILENAME__ (strrchr(__FILE__, '\\') ? strrchr(__FILE__, '\\') + 1 : __FILE__)
#endif //#if defined(__linux__)

#define LogPrint(logLevel, ...) \
    hvaLogger.log(logLevel,  __FILENAME__, __func__, __LINE__, __VA_ARGS__)

#define HVA_DEBUG(...) LogPrint(::hva::hvaLogger_t::LogLevel::DEBUG, __VA_ARGS__)
#define HVA_INFO(...) LogPrint(::hva::hvaLogger_t::LogLevel::INFO, __VA_ARGS__)
#define HVA_WARNING(...) LogPrint(::hva::hvaLogger_t::LogLevel::WARNING, __VA_ARGS__)
#define HVA_ERROR(...) LogPrint( ::hva::hvaLogger_t::LogLevel::ERROR, __VA_ARGS__)

#else //#ifdef ENABLE_LOG

#define LogPrint(logLevel, ...) 

#define HVA_DEBUG(...) 
#define HVA_INFO(...) 
#define HVA_WARNING(...) 
#define HVA_ERROR(...) 

#endif //#ifdef ENABLE_LOG

}

#endif //#ifndef HVA_LOGGER_HPP
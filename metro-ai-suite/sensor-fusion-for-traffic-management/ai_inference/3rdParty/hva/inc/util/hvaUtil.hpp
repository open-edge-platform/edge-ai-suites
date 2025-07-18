#ifndef HVA_HVAUTIL_HPP
#define HVA_HVAUTIL_HPP

#include <chrono>
#include <stdexcept>
#include <memory>
#include <string>

#if defined(__linux__)
#define HVA_DECLSPEC 
#elif defined(WIN32)
#ifdef HVA_DLL_EXPORT
#define HVA_DECLSPEC __declspec(dllexport) 
#else
#define HVA_DECLSPEC __declspec(dllimport) 
#endif
#endif

namespace hva{

HVA_DECLSPEC void hvaAssertFail(const char* cond, int line, const char* file,
                      const char* func);

// #define HVA_ASSERT(cond) if(!cond){ std::cout<<"Assert Failed!"<<std::endl;}
#define HVA_ASSERT(cond) do{if(!(cond)){::hva::hvaAssertFail(#cond, __LINE__, __FILE__, \
    __func__);}} while(false);

enum HVA_DECLSPEC hvaStatus_t{
    hvaSuccess = 0,
    hvaFailure,
    hvaPortFullDiscarded,
    hvaPortFullTimeout,
    hvaPortNullPtr,
    hvaEventRegisterFailed,
    hvaEventNotFound,
    hvaCallbackFail,
    hvaNotSupported,
    hvaNoCompatibleProtocol,
    hvaIllegalStateTransition,
    hvaNodeNotFound
};

using ms = std::chrono::milliseconds;

template<typename ... Args>
HVA_DECLSPEC std::string string_format( const std::string& format, Args ... args )
{
    size_t size = snprintf( nullptr, 0, format.c_str(), args ... ) + 1; // Extra space for '\0'
    if( size <= 0 ){ throw std::runtime_error( "Error during formatting." ); }
    std::unique_ptr<char[]> buf( new char[ size ] ); 
    snprintf( buf.get(), size, format.c_str(), args ... );
    return std::string( buf.get(), buf.get() + size - 1 ); // We don't want the '\0' inside
};

HVA_DECLSPEC std::string string_format( const std::string& format);

}

#define _HVA_PP_CONCAT(A, B) A##B
#define HVA_PP_CONCAT(A, B) _HVA_PP_CONCAT(A, B)

#endif //HVA_HVAUTIL_HPP
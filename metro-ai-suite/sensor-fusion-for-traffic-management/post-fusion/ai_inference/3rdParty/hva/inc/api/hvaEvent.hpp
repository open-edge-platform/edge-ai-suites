#ifndef HVA_HVAEVENT_HPP
#define HVA_HVAEVENT_HPP

#include <cstdint>
#include <functional>
#include <inc/util/hvaUtil.hpp>

namespace hva{

typedef uint64_t hvaEvent_t;

#define hvaEvent_Null                   0x0ull
#define hvaEvent_EOS                    0x1ull
#define hvaEvent_PipelineConfig         0x2ull
#define hvaEvent_PipelinePrepare        0x3ull
#define hvaEvent_PipelineStart          0x4ull
#define hvaEvent_PipelinePause          0x5ull
#define hvaEvent_PipelineStop           0x6ull
#define hvaEvent_PipelineReConfig       0x7ull
#define hvaEvent_UserDefined1           0x8ull
#define hvaEvent_UserDefined2           0x9ull
#define hvaEvent_UserDefined3           0xAull
#define hvaEvent_PipelineLatencyCapture 0xBull
#define hvaEvent_PipelineTimeStampRecord 0xCull

/**
* @brief the event listener prototype for to handle any event triggers this handler
* @sa hvaPipeline_t::registerCallback() hvaNode_t::registerCallback()
* @sa hvaPipeline_t::emitEvent() hvaNode_t::emitEvent()
*
* Note that the callback function executes within the exact thread where emitEvent()
* is called, so users expect not to have much workload in a single callback function
*/
class HVA_DECLSPEC hvaEventListener_t{
public:

    hvaEventListener_t() = default;

    virtual ~hvaEventListener_t() = default;

    /**
    * @brief callback function upon event handling
    * 
    * @param data data transitted to callback function 
    * @return a bool indicating the callback function execution status
    * 
    */
    virtual bool onEvent(void* data) = 0;

};

}

#endif //#ifndef HVA_HVAEVENT_HPP

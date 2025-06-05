#ifndef HVA_HVASTATE_HPP
#define HVA_HVASTATE_HPP

#include <inc/util/hvaUtil.hpp>

namespace hva{

// hva state transistion workflow:
//
//
//  idle     --> configured     --> prepared      
//                                  /\   |
//    -------------------------------|   |
//    |                                  \/
//  stop     <-- depleting        <-- running
//    /\             /\                 /\            
//    |              |                  |
//    |              |                  \/
//    |--------------|--------------- paused

class HVA_DECLSPEC hvaState_t final{
public:
    enum HVA_DECLSPEC State{
        idle = 0,
        configured,
        prepared,
        running,
        paused,
        depleting,
        stop
    };

    hvaState_t();

    hvaState_t(const State& state);

    hvaState_t(const hvaState_t& state);

    hvaState_t(hvaState_t&& state);

    ~hvaState_t();

    hvaState_t& operator=(const hvaState_t& state);

    hvaState_t& operator=(hvaState_t&& state);

    hvaStatus_t transitTo(const hvaState_t& state);

    void transitToForced(const hvaState_t& state);

    bool operator==(const hvaState_t& state) const;

    bool operator!=(const hvaState_t& state) const;

    bool operator==(const State& state) const;

    bool operator!=(const State& state) const;

    operator State() const;

    std::string str() const;

private:
    /// @private
    class Impl;
    std::unique_ptr<Impl> m_impl;
};

}

#endif //#ifndef HVA_HVASTATE_HPP
#ifndef HVA_HVAPROTOCOL_HPP
#define HVA_HVAPROTOCOL_HPP

#include <inc/util/hvaUtil.hpp>
#include <memory>
#include <type_traits>
#include <string>
#include <unordered_set>

namespace hva{

/// @private
class HVA_DECLSPEC hvaProtocol_t{
public:
    hvaProtocol_t();

    hvaProtocol_t(std::string keystring);

    template <typename T, typename... Args, typename std::enable_if<std::is_same<T, std::string>::value>::type* = nullptr>
    hvaProtocol_t(T keystring1, T keystring2, Args... others);

    template <typename T, typename... Args, typename std::enable_if<std::is_same<T, const char*>::value>::type* = nullptr>
    hvaProtocol_t(T keystring1, T keystring2, Args... others);

    hvaProtocol_t(const hvaProtocol_t& proto) = default;

    hvaProtocol_t(hvaProtocol_t&& proto);

    hvaProtocol_t& operator=(const hvaProtocol_t& proto) = default;

    hvaProtocol_t& operator=(hvaProtocol_t&& proto);

    template <typename T, typename... Args, typename std::enable_if<std::is_same<T, std::string>::value>::type* = nullptr>
    void accept(T keystring, Args... others);

    template <typename T, typename std::enable_if<std::is_same<T, std::string>::value>::type* = nullptr>
    void accept(T keystring, T other);

    bool contain(const std::string& keystring) const;

    std::unordered_set<std::string> overlap(const hvaProtocol_t& proto) const;

    bool select(const std::string& keystring);

    std::string getSelected() const;

    bool haveSelected() const;

    bool clearSelected();

private:
    std::unordered_set<std::string> m_set;
    std::string m_selected;
};

template <typename T, typename... Args, typename std::enable_if<std::is_same<T, std::string>::value>::type*>
hvaProtocol_t::hvaProtocol_t(T keystring1, T keystring2, Args... others):m_selected(""){
    m_set.insert(keystring1);
    std::string keystrings[] = {keystring2, others...};
    for(const auto& item: keystrings){
        m_set.insert(item);
    }
};

template <typename T, typename... Args, typename std::enable_if<std::is_same<T, const char*>::value>::type*>
hvaProtocol_t::hvaProtocol_t(T keystring1, T keystring2, Args... others){
    m_set.insert(std::string(keystring1));
    std::string keystrings[] = {keystring2, others...};
    for(const auto& item: keystrings){
        m_set.insert(item);
    }
}

template <typename T, typename... Args, typename std::enable_if<std::is_same<T, std::string>::value>::type*>
void hvaProtocol_t::accept(T keystring, Args... others){
    m_set.insert(keystring);
    accept(others...);
};

template <typename T, typename std::enable_if<std::is_same<T, std::string>::value>::type*>
void hvaProtocol_t::accept(T keystring, T other){
    m_set.insert(keystring);
    m_set.insert(other);
};

}

#endif //#ifndef HVA_HVAPROTOCOL_HPP
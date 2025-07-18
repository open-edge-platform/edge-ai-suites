#ifndef HVA_HVACONFIGSTRINGPARSER_HPP
#define HVA_HVACONFIGSTRINGPARSER_HPP

#include <inc/util/hvaUtil.hpp>
#include <vector>
#include <type_traits>
#include <unordered_map>

namespace hva{

/// @private
template<typename T>
struct _hva_is_valid_val_type: std::false_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<int> : std::true_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<float> : std::true_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<bool> : std::true_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<std::string> : std::true_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<std::vector<int>> : std::true_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<std::vector<float>> : std::true_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<std::vector<bool>> : std::true_type{ };
/// @private
template<>
struct _hva_is_valid_val_type<std::vector<std::string>> : std::true_type{ };

/**
* @brief This config string parser parses string in form of "key1=(TYPE)VALUE1;key2=(TYPE)VALUE2", where
*       TYPE could be one of the following: INT, FLOAT, BOOL, STRING, INT_ARRAY, FLOAT_ARRAY, BOOL_ARRAY, STRING_ARRAY,
*       where in case of an array, value should be wrapped within []. e.g. "threshold=(FLOAT_ARRARY)[0.2, 0.584];mode=(STRING)detection"
* 
*/
class HVA_DECLSPEC hvaConfigStringParser_t{
public:
    enum HVA_DECLSPEC ValType{
        hvaInvalid,
        hvaInteger,
        hvaFloat,
        hvaBool,
        hvaString,
        hvaIntegerArray,
        hvaFloatArray,
        hvaBoolArray,
        hvaStringArray
    };

    /// @private
    class _hvaValTypeContainerBase_t{
    public:
        using Ptr = std::unique_ptr<_hvaValTypeContainerBase_t>;

        _hvaValTypeContainerBase_t():type(hvaInvalid){ };

        virtual ~_hvaValTypeContainerBase_t(){ };

        _hvaValTypeContainerBase_t(const _hvaValTypeContainerBase_t& ) = delete;

        _hvaValTypeContainerBase_t(_hvaValTypeContainerBase_t&& ) = delete;

        _hvaValTypeContainerBase_t& operator=(const _hvaValTypeContainerBase_t& ) = delete;

        _hvaValTypeContainerBase_t& operator=(_hvaValTypeContainerBase_t&& ) = delete;

        virtual _hvaValTypeContainerBase_t* clone() = 0;

        ValType type;

    };

    /// @private
    template<typename T, typename std::enable_if<_hva_is_valid_val_type<T>::value>::type* = nullptr>
    class _hvaValTypeContainer_t: public _hvaValTypeContainerBase_t{
    public:
        using Ptr = std::unique_ptr<_hvaValTypeContainer_t>;

        _hvaValTypeContainer_t(const T& v){
            val = v;
            if(std::is_same<T, int>::value){
                type = hvaInteger;
            }
            else if(std::is_same<T, float>::value){
                type = hvaFloat;
            }
            else if(std::is_same<T, bool>::value){
                type = hvaBool;
            }
            else if(std::is_same<T, std::string>::value){
                type = hvaString;
            }
            else if(std::is_same<T, std::vector<int>>::value){
                type = hvaIntegerArray;
            }
            else if(std::is_same<T, std::vector<float>>::value){
                type = hvaFloatArray;
            }
            else if(std::is_same<T, std::vector<bool>>::value){
                type = hvaBoolArray;
            }
            else if(std::is_same<T, std::vector<std::string>>::value){
                type = hvaStringArray;
            }
            else{
                HVA_ASSERT(false);
            }
        };

        _hvaValTypeContainer_t(T&& v){
            std::swap(val, v);
            if(std::is_same<T, int>::value){
                type = hvaInteger;
            }
            else if(std::is_same<T, float>::value){
                type = hvaFloat;
            }
            else if(std::is_same<T, bool>::value){
                type = hvaBool;
            }
            else if(std::is_same<T, std::string>::value){
                type = hvaString;
            }
            else if(std::is_same<T, std::vector<int>>::value){
                type = hvaIntegerArray;
            }
            else if(std::is_same<T, std::vector<float>>::value){
                type = hvaFloatArray;
            }
            else if(std::is_same<T, std::vector<bool>>::value){
                type = hvaBoolArray;
            }
            else if(std::is_same<T, std::vector<std::string>>::value){
                type = hvaStringArray;
            }
            else{
                HVA_ASSERT(false);
            }
        };

        _hvaValTypeContainer_t() = delete;

        _hvaValTypeContainer_t(const _hvaValTypeContainer_t& ) = delete;

        _hvaValTypeContainer_t(_hvaValTypeContainer_t&& ) = delete;

        _hvaValTypeContainer_t& operator=(const _hvaValTypeContainer_t& ) = delete;

        _hvaValTypeContainer_t& operator=(_hvaValTypeContainer_t&& ) = delete;

        virtual _hvaValTypeContainerBase_t* clone() override{
            return new _hvaValTypeContainer_t(val);
        };

        ~_hvaValTypeContainer_t(){

        };

        T val;
    };

    hvaConfigStringParser_t();

    hvaConfigStringParser_t(const hvaConfigStringParser_t& parser);

    hvaConfigStringParser_t(hvaConfigStringParser_t&& parser);

    hvaConfigStringParser_t& operator=(const hvaConfigStringParser_t& parser);

    hvaConfigStringParser_t& operator=(hvaConfigStringParser_t&& parser);

    void reset();

    bool parse(const std::string& config);

    std::string getConfigString() const;

    template<typename T, typename std::enable_if<_hva_is_valid_val_type<T>::value>::type* = nullptr>
    bool getVal(const std::string& key, T& val) const;

    template<typename T, typename std::enable_if<_hva_is_valid_val_type<T>::value>::type* = nullptr>
    bool setVal(const std::string& key, const T& val);

private:
    bool parseKeyValPair(const std::string& keyValPair);

    std::unordered_map<std::string, _hvaValTypeContainerBase_t::Ptr> m_config;
};

template<typename T, typename std::enable_if<_hva_is_valid_val_type<T>::value>::type*>
bool hvaConfigStringParser_t::getVal(const std::string& key, T& val) const{
    // static_assert(_hva_is_valid_val_type<T>::value, "Unsupported type to getVal.");

    if(m_config.find(key) == m_config.end()){
        return false;
    }
    val = dynamic_cast<_hvaValTypeContainer_t<T>*>(m_config.at(key).get())->val;
    return true;
}

template<typename T, typename std::enable_if<_hva_is_valid_val_type<T>::value>::type*>
bool hvaConfigStringParser_t::setVal(const std::string& key, const T& val){
    // static_assert(_hva_is_valid_val_type<T>::value, "Unsupported type to setVal");
    m_config.emplace(key, _hvaValTypeContainerBase_t::Ptr(new _hvaValTypeContainer_t<T>(val)));
    return true;
}

}

#endif //#ifndef HVA_HVACONFIGSTRINGPARSER_HPP
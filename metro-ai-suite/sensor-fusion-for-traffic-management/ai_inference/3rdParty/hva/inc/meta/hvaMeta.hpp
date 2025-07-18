#ifndef HVA_HVAMETA_HPP
#define HVA_HVAMETA_HPP

#include <inc/util/hvaUtil.hpp>
#include <unordered_map>
#include <memory>

namespace hva{

/// @private
class HVA_DECLSPEC hvaMetaMap_t final{
public:

    hvaMetaMap_t();

    ~hvaMetaMap_t();

    hvaMetaMap_t(const hvaMetaMap_t& metaMap);

    hvaMetaMap_t(hvaMetaMap_t&& metaMap);

    hvaMetaMap_t& operator=(const hvaMetaMap_t& metaMap);

    hvaMetaMap_t& operator=(hvaMetaMap_t&& metaMap);

    template <typename T>
    bool add(T data);

    template <typename T>
    bool get(T& data) const;

    template <typename T>
    bool erase();

    template <typename T>
    bool contain() const;

    bool eraseAll();

private:

    class _hvaMetaHolderBase_t{
    public:
        _hvaMetaHolderBase_t(){ };

        virtual ~_hvaMetaHolderBase_t(){ };

        virtual _hvaMetaHolderBase_t* clone() = 0;
    };

    template <typename HOLDER_T>
    class _hvaMetaHolder_t:public _hvaMetaHolderBase_t{
    public:
        _hvaMetaHolder_t(HOLDER_T data):data(data){ };

        _hvaMetaHolder_t() = delete;

        _hvaMetaHolder_t(const _hvaMetaHolder_t& holder) = default;

        _hvaMetaHolder_t(_hvaMetaHolder_t&& holder):data{std::move(holder.data)}{ };

        _hvaMetaHolder_t& operator=(const _hvaMetaHolder_t& holder) = default;

        _hvaMetaHolder_t& operator=(_hvaMetaHolder_t&& holder){
            if(this != &holder){
                std::swap(data, holder.data);
            }
            return *this;
        };

        virtual _hvaMetaHolder_t* clone() override{
            return new _hvaMetaHolder_t(*this);
        };

        ~_hvaMetaHolder_t(){ };

        HOLDER_T data;

    };

    std::unordered_map<std::size_t, std::unique_ptr<_hvaMetaHolderBase_t>> m_meta;
};

template <typename T>
bool hvaMetaMap_t::add(T data){
    erase<T>();
    m_meta.emplace(typeid(T).hash_code(), std::unique_ptr<_hvaMetaHolderBase_t>(new _hvaMetaHolder_t<T>(data)));
    return true;
};

template <typename T>
bool hvaMetaMap_t::get(T& data) const{
    if(!contain<T>()){
        return false;
    }
    else{
        const std::unique_ptr<_hvaMetaHolderBase_t>& temp = m_meta.at(typeid(T).hash_code());
        data = dynamic_cast<_hvaMetaHolder_t<T>*>(temp.get())->data;
        return true;
    }
};

template <typename T>
bool hvaMetaMap_t::erase(){
    m_meta.erase(typeid(T).hash_code());
    return true;
};

template <typename T>
bool hvaMetaMap_t::contain() const{
    return m_meta.count(typeid(T).hash_code())? true : false;
};

}

#endif //#ifndef HVA_HVAMETA_HPP
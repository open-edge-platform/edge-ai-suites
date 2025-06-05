#ifndef HVA_HVABLOB_HPP
#define HVA_HVABLOB_HPP

#include <inc/api/hvaBuf.hpp>

#include <vector>

namespace hva{

/**
* @brief the container for zero or one or multiple hvaBuf_t
* 
* hvaBlob_t is the data struct that being trasmitted between every nodes. A hvaNode_t can contain
* zero or one or more hvaBuf_t. hvaBlob_t will hold a reference count of each hvaBuf_t it contains
* 
*/
class HVA_DECLSPEC hvaBlob_t final: public std::enable_shared_from_this<hvaBlob_t>{
public:
    using Ptr = std::shared_ptr<hvaBlob_t>;

    hvaBlob_t(hvaBlob_t&& blob) = delete;

    hvaBlob_t& operator=(const hvaBlob_t& blob) = delete;

    hvaBlob_t& operator=(hvaBlob_t&& blob) = delete;

    ~hvaBlob_t();

    /**
    * @brief push a raw pointer of hvaBuf_t into the blob
    * 
    * @param buf the hvaBuf_t to add
    * @return void
    * 
    * This blob will add a reference count to the pushed buffer
    */
    void push(hvaBuf_t::Ptr buf);

    /**
    * @brief emplace a hvaBuf_t in place 
    * 
    * @param buf any buffer to be wrapped into hvaBuf_t
    * @param size the size of buffer
    * @param d optional. custom deleter to buffer
    * @return shared pointer to hvaBuf_t constructued
    * 
    */
    template<typename HVA_BUF_T, typename T>
    typename HVA_BUF_T::Ptr emplace(T buf, std::size_t size, std::function<void(T)> d = {});

    /**
    * @brief get the idx hvaBuf_t in this blob in form of shared pointer
    * 
    * @param idx the index of hvaBuf_t to get in this blob
    * @return shared pointer to the buffer at idx
    * 
    * This blob will add a reference count to the pushed buffer
    */
    hvaBuf_t::Ptr get(std::size_t idx);

    /**
    * @brief static function to make a blob
    * 
    * @param void
    * @return shared pointer to the hvaBlob_t constructed
    * 
    * user expects to construct every blob through this function
    * 
    */
    static Ptr make_blob();

    /**
    * @brief get a shared pointer to this hvaBlob_t instance
    * 
    * @param void
    * @return shared pointer to blob
    * 
    */
    Ptr sharedFromThis();

    /**
    * @brief explicitly clone a blob
    * 
    * @param void
    * @return shared pointer to the cloned blob
    * 
    * this function will explicitly call hvaBuf_t::clone(), rather than
    * copy the pointer to original hvaBuf_t 
    * 
    */
    hvaBlob_t::Ptr clone() const;

    std::vector<hvaBuf_t::Ptr> vBuf; ///< vector holding pointer to buf
    unsigned streamId;  ///< stream index that this blob associates to
    unsigned frameId;   ///< frame index that this blob associates to
    int context;    ///< any custom context data, hva will not examine this value

private:
    hvaBlob_t();
    hvaBlob_t(const hvaBlob_t& blob);
};

template<typename HVA_BUF_T, typename T>
typename HVA_BUF_T::Ptr hvaBlob_t::emplace(T buf, std::size_t size, std::function<void(T)> d){
    typename HVA_BUF_T::Ptr temp = HVA_BUF_T::make_buffer(buf, size, d);
    push(temp);
    return temp;
}

}
#endif //#ifndef HVA_HVABLOB_HPP
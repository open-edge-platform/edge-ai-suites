#ifndef HVA_HVAVIDEOFRAMEBUF_HPP
#define HVA_HVAVIDEOFRAMEBUF_HPP

#include <inc/api/hvaBuf.hpp>
#include <inc/util/hvaUtil.hpp>

#define MAX_PLANE_NUM 8

namespace hva{

class HVA_DECLSPEC hvaVideoFrameBuf_t: public hvaBuf_t{
public:
    using Ptr = std::shared_ptr<hvaVideoFrameBuf_t>;

    hvaVideoFrameBuf_t() = delete;

    hvaVideoFrameBuf_t(hvaVideoFrameBuf_t&& buf) = delete;

    hvaVideoFrameBuf_t& operator=(const hvaVideoFrameBuf_t& buf) = delete;

    hvaVideoFrameBuf_t& operator=(hvaVideoFrameBuf_t&& buf) = delete;

    virtual ~hvaVideoFrameBuf_t();

    // write your own implementation in derived class of this function!
    template <typename T>
    static Ptr make_buffer(T buf, std::size_t size, std::function<void(T)> d = {});

    virtual hvaBuf_t::Ptr sharedFromThis();

    virtual hvaBufDescriptor_t::Ptr clone() const override;

    /**
    * @brief get the key string associated with the buffer type if specified
    * 
    * @param void
    * @return string of the key string
    * 
    */
    virtual std::string getKeyString() const override;

    unsigned frameId;
    unsigned width;
    unsigned height;
    unsigned planeNum;
    unsigned stride[MAX_PLANE_NUM];
    unsigned offset[MAX_PLANE_NUM];
    unsigned planeStride[MAX_PLANE_NUM];
    unsigned planeOffset[MAX_PLANE_NUM];
    unsigned tag;
    bool drop;

protected:
    template <typename T>
    hvaVideoFrameBuf_t(T buf, std::size_t size, std::function<void(T)> d = {});

    hvaVideoFrameBuf_t(const hvaVideoFrameBuf_t& buf);

    // hvaVideoFrameBuf_t(std::unique_ptr<_hvaBufHolderBase_t> ptr, const hvaMetaMap_t& meta);
};

template <typename T>
hvaVideoFrameBuf_t::hvaVideoFrameBuf_t(T buf, std::size_t size, std::function<void(T)> d):hvaBuf_t(buf, size, d), frameId(0u)
        , width(0u), height(0u), planeNum(3u), stride({0,0,0}), offset({0,0,0}), planeStride({0}), planeOffset({0}), tag(0u), drop(false){

}

template <typename T>
hvaVideoFrameBuf_t::Ptr hvaVideoFrameBuf_t::make_buffer(T buf, std::size_t size, std::function<void(T)> d){
    // return std::make_shared<hvaVideoFrameBuf_t>(buf, size, d);
    return Ptr(new hvaVideoFrameBuf_t(buf, size, d));
}

}

#endif //#ifndef HVA_HVAVIDEOFRAMEBUF_HPP
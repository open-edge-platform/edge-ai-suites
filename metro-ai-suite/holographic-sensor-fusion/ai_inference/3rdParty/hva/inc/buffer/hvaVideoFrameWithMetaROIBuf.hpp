#ifndef HVA_HVAVIDEOFRAMEWITHMETAROIBUF_HPP
#define HVA_HVAVIDEOFRAMEWITHMETAROIBUF_HPP

#include <inc/api/hvaMetaROI.hpp>
#include <inc/api/hvaBuf.hpp>
#include <inc/util/hvaUtil.hpp>
#include <inc/api/hvaLogger.hpp>
#include <vector>

#define MAX_PLANE_NUM 8

namespace hva{


class HVA_DECLSPEC hvaVideoFrameWithMetaROIBuf_t: public hvaBuf_t{
public:
    using Ptr = std::shared_ptr<hvaVideoFrameWithMetaROIBuf_t>;

    hvaVideoFrameWithMetaROIBuf_t() = delete;

    hvaVideoFrameWithMetaROIBuf_t(hvaVideoFrameWithMetaROIBuf_t&& buf) = delete;

    hvaVideoFrameWithMetaROIBuf_t& operator=(const hvaVideoFrameWithMetaROIBuf_t& buf) = delete;

    hvaVideoFrameWithMetaROIBuf_t& operator=(hvaVideoFrameWithMetaROIBuf_t&& buf) = delete;

    virtual ~hvaVideoFrameWithMetaROIBuf_t();

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
    
    std::vector<hvaMetaROI_t> rois;

protected:
    template <typename T>
    hvaVideoFrameWithMetaROIBuf_t(T buf, std::size_t size, std::function<void(T)> d = {});

    hvaVideoFrameWithMetaROIBuf_t(const hvaVideoFrameWithMetaROIBuf_t& buf);
};

template <typename T>
hvaVideoFrameWithMetaROIBuf_t::hvaVideoFrameWithMetaROIBuf_t(T buf, std::size_t size, std::function<void(T)> d):hvaBuf_t(buf, size, d), frameId(0u)
        , width(0u), height(0u), planeNum(3u), stride({0,0,0}), offset({0,0,0}), planeStride({0}), planeOffset({0}), tag(0u), drop(false){

}

template <typename T>
hvaVideoFrameWithMetaROIBuf_t::Ptr hvaVideoFrameWithMetaROIBuf_t::make_buffer(T buf, std::size_t size, std::function<void(T)> d){
    // return std::make_shared<hvaVideoFrameWithMetaROIBuf_t>(buf, size, d);
    return Ptr(new hvaVideoFrameWithMetaROIBuf_t(buf, size, d));
}

}

#endif //#ifndef HVA_HVAVIDEOFRAMEWITHMETAROIBUF_HPP
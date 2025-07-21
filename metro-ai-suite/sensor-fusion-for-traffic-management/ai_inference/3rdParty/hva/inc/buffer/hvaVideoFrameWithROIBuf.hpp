#ifndef HVA_HVAVIDEOFRAMEWITHROIBUF_HPP
#define HVA_HVAVIDEOFRAMEWITHROIBUF_HPP

#include <inc/api/hvaBuf.hpp>
#include <inc/util/hvaUtil.hpp>
#include <inc/api/hvaLogger.hpp>
#include <vector>

#define MAX_PLANE_NUM 8

namespace hva{

struct hvaROI_t {
    hvaROI_t(): x(0), y(0), width(0), height(0), labelIdClassification(0), confidenceClassification(0.0),
            labelIdDetection(0), confidenceDetection(0.0), pts(0), frameId(0), streamId(0), trackingId(0), trackingStatus(0){

    };

    ~hvaROI_t(){
        
    };

    int x;                          //Left of ROI
    int y;                          //Top of ROI
    int width;                      //Width of ROI
    int height;                     //Height of ROI
    std::string labelClassification;        //Classification label
    int labelIdClassification;      //Classification label id
    double confidenceClassification;  //Classfication confidence
    
    std::string labelDetection;             //Detection label
    int labelIdDetection;           //Detection label id
    double confidenceDetection;       //Detection confidence

    std::size_t pts;                    //Pts
    unsigned frameId;                   //Frame id
    unsigned streamId;                  //Stream id

    //for tracking
    unsigned trackingId;                //Tracking id
    unsigned trackingStatus;                //Tracking status, default to lost so jpeg won't encode by default
};

class HVA_DECLSPEC hvaVideoFrameWithROIBuf_t: public hvaBuf_t{
public:
    using Ptr = std::shared_ptr<hvaVideoFrameWithROIBuf_t>;

    hvaVideoFrameWithROIBuf_t() = delete;

    hvaVideoFrameWithROIBuf_t(hvaVideoFrameWithROIBuf_t&& buf) = delete;

    hvaVideoFrameWithROIBuf_t& operator=(const hvaVideoFrameWithROIBuf_t& buf) = delete;

    hvaVideoFrameWithROIBuf_t& operator=(hvaVideoFrameWithROIBuf_t&& buf) = delete;

    virtual ~hvaVideoFrameWithROIBuf_t();

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
    
    std::vector<hvaROI_t> rois;

protected:
    template <typename T>
    hvaVideoFrameWithROIBuf_t(T buf, std::size_t size, std::function<void(T)> d = {});

    hvaVideoFrameWithROIBuf_t(const hvaVideoFrameWithROIBuf_t& buf);
};

template <typename T>
hvaVideoFrameWithROIBuf_t::hvaVideoFrameWithROIBuf_t(T buf, std::size_t size, std::function<void(T)> d):hvaBuf_t(buf, size, d), frameId(0u)
        , width(0u), height(0u), planeNum(3u), stride({0,0,0}), offset({0,0,0}), planeStride({0}), planeOffset({0}), tag(0u), drop(false){

}

template <typename T>
hvaVideoFrameWithROIBuf_t::Ptr hvaVideoFrameWithROIBuf_t::make_buffer(T buf, std::size_t size, std::function<void(T)> d){
    // return std::make_shared<hvaVideoFrameWithROIBuf_t>(buf, size, d);
    return Ptr(new hvaVideoFrameWithROIBuf_t(buf, size, d));
}

}

#endif //#ifndef HVA_HVAVIDEOFRAMEWITHROIBUF_HPP
#ifndef BEV_IMPL_H
#define BEV_IMPL_H
#include <bev_datatypes.h>
#include <sycl/sycl.hpp>
class SyclImpl;
class Bev{
public:
    Bev() = delete;
    Bev(const Bev&) = delete;
    void operator=(const Bev&) = delete;
    Bev(sycl::queue& queue,
	uint32_t inputChannels,
	uint32_t outputChannels,
	uint32_t imageWidth,
	uint32_t imageHeight,
	uint32_t featureWidth,
	uint32_t featureHeight,
	const Bound& xBound,
	const Bound& yBound,
	const Bound& zBound,
	const Bound& dBound);
    ~Bev();
public:
    uint32_t viewTransform(NdArray* camResultsA, 
			   NdArray* camResultsB, 
			   NdArray* feat, 
			   NdArray* cam2ego, 
			   NdArray* lidar2ego, 
			   NdArray* camIntrinsics, 
			   NdArray* cam2Lidar, 
			   NdArray* imgAugMat, 
			   NdArray* bevFeat);
    uint32_t bevPool(void* cameraFeature,
		     void* depthWeights,
		     void* indices,
		     void* intervals,
		     void* bevFeatures,
		     uint32_t intervalNum,
		     uint32_t n,
		     uint32_t c,
		     uint32_t d,
		     uint32_t h,
		     uint32_t w,
		     uint32_t bevWidth,
		     uint32_t bevHeight);

    uint32_t nms3d(NdArray* boxes, /* batchSize x 5 fp32 array*/ 
		   uint32_t* keep, /* batchSize x 1 fp32 array*/ 
		   uint32_t  maxKeepLen, 
		   uint32_t* activeKeepLen, 
		   float     threshold);
private:
    SyclImpl* sycl;
};
#endif

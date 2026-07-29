#include <bev.h>
#include <bev_sycl.h>
#include <string.h>
Bev::Bev(sycl::queue& queue,
	uint32_t inputChannels,
	uint32_t outputChannels,
	uint32_t imageWidth,
	uint32_t imageHeight,
	uint32_t featureWidth,
	uint32_t featureHeight,
	const Bound& xBound,
	const Bound& yBound,
	const Bound& zBound,
	const Bound& dBound){
    sycl = new SyclImpl(queue,
			inputChannels,
			outputChannels,
			imageWidth,
			imageHeight,
			featureWidth,
			featureHeight,
			xBound,
			yBound,
			zBound,
			dBound);
}

Bev::~Bev(){
    delete sycl;
}
uint32_t Bev::viewTransform(NdArray* camResultsA, 
			   NdArray* camResultsB, 
			   NdArray* feat, 
			   NdArray* cam2ego, 
			   NdArray* lidar2ego, 
			   NdArray* camIntrinsics, 
			   NdArray* cam2Lidar, 
			   NdArray* imgAugMat, 
			   NdArray* bevFeat){
	return sycl->viewTransform(camResultsA, camResultsB,
				   feat, cam2ego, lidar2ego, camIntrinsics, cam2Lidar,
				   imgAugMat, bevFeat);
}
uint32_t Bev::bevPool(void* cf,
		     void* dw,
		     void* idx,
		     void* itv,
		     void* bf,
		     uint32_t itvN,
		     uint32_t n,
		     uint32_t c,
		     uint32_t d,
		     uint32_t h,
		     uint32_t w,
		     uint32_t bevWidth,
		     uint32_t bevHeight){
    return sycl->bevPool(cf, dw, idx, itv, bf, itvN, n, c, d, h, w, bevWidth, bevHeight);
}
uint32_t Bev::nms3d(NdArray* boxes, uint32_t* keep, uint32_t maxKeepLen, uint32_t* activeKeepLen, float threshold){
    return sycl->nms3d(boxes, keep, maxKeepLen, activeKeepLen, threshold);
}

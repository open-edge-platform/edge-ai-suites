#ifndef BEV_SYCL_H
#define BEV_SYCL_H
#include "bev_datatypes.h"
#include <sycl/sycl.hpp>
#include "common/dtype.hpp"
#include "bev.h"
#include <vector>
#include <iostream>  
#include <cstdio>
#include <cstdlib>

#ifdef BEV_DBG
#define DIE_IF(x, msg) do{if(x){fprintf(stdout, "\033[7m%s. %s:%d\033[0m\n", #x, __FILE__, __LINE__); asm("int3");}}while(0)
#else
#define DIE_IF(x, msg) do{if(x){fprintf(stdout, "\033[7m%s.\033[0m\n", msg); exit(-__LINE__);}}while(0)
#endif

#define AD(hostVarName) auto hostVarName##_ker = hostVarName
#define AR(hostVarName) hostVarName##_ker
#define TILE_SIZE 10
typedef struct alignas(4) CombinedHalf{
    sycl::half val[TILE_SIZE];
}CombinedHalf;
struct NdArray;
class SyclImpl{
public:
    SyclImpl() = delete;
    SyclImpl(const SyclImpl&) = delete;
    void operator=(const SyclImpl&) = delete;

    SyclImpl(sycl::queue& queue,
	     uint32_t inputChans,
	     uint32_t outputChans,
	     uint32_t imgWidth,
	     uint32_t imgHeight,
	     uint32_t featWidth,
	     uint32_t featHeight,
	     const Bound& xBound,
	     const Bound& yBound,
	     const Bound& zBound,
	     const Bound& dBound);
    ~SyclImpl();
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
    void enumerateDevices();
    void initNms3d();

    void destroyNms3d();
private:
    std::vector<sycl::device> devs;
    sycl::queue &que;
    uint32_t devIdx;
    uint32_t maxComputeUnits;
    uint32_t maxWorkItemPerWorkGroup;

private://3diou
    float*	dBoxesData; //prefix 'd' -> device, 'h' -> host
    uint32_t	boxesDims;
    uint32_t*	dMskData;
    uint32_t	mskCnt;
    uint32_t*	hMskData;
    uint32_t*	hRemove;
    uint32_t	rmCnt;
private:
    uint32_t	ic; //input channels
    uint32_t	iw; //image width
    uint32_t	ih; //image height
    uint32_t	fw; //feature width
    uint32_t	fh; //feature height
    uint32_t	dsf;//down sample factor
    uint32_t	oc; //output channels;
    Bound	x,
		y,
		z,
		d;
    Bound	dx,
		bx,
		nx;

};

void bevPoolKernel(const float* cf,
				const float* dw,
				const uint32_t* idx,
				const bevfusion::types::Int3* itvs,
				float* bf,
				uint32_t c,
				uint32_t itvN,
				uint32_t oW,
				uint32_t oH,
				uint32_t d,
				uint32_t farea,
				const sycl::nd_item<1>& it);
#endif //BEV_SYCL_H

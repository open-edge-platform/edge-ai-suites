#include "bev_sycl.h"
#include <dpct/dpct.hpp>
#include <string.h>
#include <algorithm>
#include <cmath> 
#include <iostream>
#include "common/dtype.hpp"
#include <cstring>

static_assert(TILE_SIZE > 0, "TILE_SIZE must be positive");
static_assert(TILE_SIZE <= 32, "TILE_SIZE should not be too large");
SyclImpl::SyclImpl(
	sycl::queue& queue,
	uint32_t inputChannels,
	uint32_t outputChannels,
	uint32_t imageWidth,
	uint32_t imageHeight,
	uint32_t featureWidth,
	uint32_t featureHeight,
	const Bound& xBound,
	const Bound& yBound,
	const Bound& zBound,
	const Bound& dBound) : que(queue) {
    DIE_IF(0 == featureHeight, "Zero feature height specified");

    // //init devs
    // enumerateDevices();
    // DIE_IF(0 == devs.size(), "No valid devices found");
    // DIE_IF(deviceIndex >= devs.size(), "Invalid device index specified");
    // sycl::property_list prop(sycl::property::queue::in_order{});
    // que = sycl::queue(devs[deviceIndex], prop);
    // maxComputeUnits = devs[deviceIndex].get_info<sycl::info::device::max_compute_units>();
    // maxWorkItemPerWorkGroup = devs[deviceIndex].get_info<sycl::info::device::max_work_group_size>();
    maxComputeUnits = que.get_device().get_info<sycl::info::device::max_compute_units>();
    maxWorkItemPerWorkGroup = que.get_device().get_info<sycl::info::device::max_work_group_size>();
    fprintf(stdout, "maxComputeUnits: %u, MaxGroupSize: %u\n", maxComputeUnits, maxWorkItemPerWorkGroup);
#ifdef _DEBUG
    std::cout << "Running on: \033[7m"
	      << que.get_device().get_info<sycl::info::device::name>() << ", "
	      << que.get_device().get_platform().get_info<sycl::info::platform::name>() << ", "
	      << que.get_device().get_backend()
	      << "\033[0m" << std::endl;
#endif

    //init 3diou;
    initNms3d();

    ic = inputChannels;
    iw = imageWidth;
    ih = imageHeight;
    fw = featureWidth;
    fh = featureHeight;
    dsf= ih / fh;
    oc = outputChannels;
    memcpy(&x, &xBound, sizeof(Bound));
    memcpy(&y, &yBound, sizeof(Bound));
    memcpy(&z, &zBound, sizeof(Bound));
    memcpy(&d, &dBound, sizeof(Bound));
}

SyclImpl::~SyclImpl(){
    destroyNms3d();
}

void checkDeviceResources(sycl::queue& queue) {
    auto device = queue.get_device();
    
    try {
        std::cout << "=== GPU Resource Information (Simple) ===" << std::endl;
        
        // basic info
        std::cout << "Device: " << device.get_info<sycl::info::device::name>() << std::endl;
        std::cout << "Vendor: " << device.get_info<sycl::info::device::vendor>() << std::endl;
        
        // memory info
        auto global_mem_size = device.get_info<sycl::info::device::global_mem_size>();
        std::cout << "Global memory: " << (global_mem_size / 1024 / 1024) << " MB" << std::endl;
        
        // compute resource
        auto max_compute_units = device.get_info<sycl::info::device::max_compute_units>();
        auto max_work_group_size = device.get_info<sycl::info::device::max_work_group_size>();
        
        std::cout << "Max compute units: " << max_compute_units << std::endl;
        std::cout << "Max work group size: " << max_work_group_size << std::endl;
        
        // device type
        auto device_type = device.get_info<sycl::info::device::device_type>();
        std::cout << "Device type: ";
        switch (device_type) {
            case sycl::info::device_type::gpu:
                std::cout << "GPU" << std::endl;
                break;
            case sycl::info::device_type::cpu:
                std::cout << "CPU" << std::endl;
                break;
            default:
                std::cout << "Other" << std::endl;
                break;
        }
        
    } catch (const std::exception& e) {
        std::cerr << "Error getting device info: " << e.what() << std::endl;
    }
}

void checkKernelLaunchParams(uint32_t c, uint32_t itvN, sycl::queue& queue) {
    auto device = queue.get_device();
    auto max_work_group_size = device.get_info<sycl::info::device::max_work_group_size>();
    auto max_compute_units = device.get_info<sycl::info::device::max_compute_units>();
    

    
    int xThread = c / TILE_SIZE;
    int yThread = (xThread > 0) ? (1024 / xThread) : 1024;
    
    std::cout << "=== Kernel Launch Parameters ===" << std::endl;
    std::cout << "TILE_SIZE: " << TILE_SIZE << std::endl;
    std::cout << "c (channels): " << c << std::endl;
    std::cout << "itvN (intervals): " << itvN << std::endl;
    std::cout << "xThread: " << xThread << std::endl;
    std::cout << "yThread: " << yThread << std::endl;
    std::cout << "Threads per work group: " << (xThread * yThread) << std::endl;
    std::cout << "Number of work groups: " << ((itvN + yThread - 1) / yThread) << std::endl;
    std::cout << "Total threads: " << (xThread * yThread * ((itvN + yThread - 1) / yThread)) << std::endl;
    
    std::cout << "Device limits:" << std::endl;
    std::cout << "Max work group size: " << max_work_group_size << std::endl;
    std::cout << "Max compute units: " << max_compute_units << std::endl;
    
    if (xThread * yThread > max_work_group_size) {
        std::cerr << "❌ Work group size exceeds device limit!" << std::endl;
        std::cerr << "Requested: " << (xThread * yThread) << ", Max: " << max_work_group_size << std::endl;
    }
    
    size_t total_threads = xThread * yThread * ((itvN + yThread - 1) / yThread);
    size_t reasonable_limit = max_compute_units * max_work_group_size * 10; 
    
    if (total_threads > reasonable_limit) {
        std::cerr << "⚠ Total thread count may be too high!" << std::endl;
        std::cerr << "Total threads: " << total_threads << ", Suggested limit: " << reasonable_limit << std::endl;
    }
}

// use opencl backend
void SyclImpl::enumerateDevices(){
#ifdef _DEBUG
    std::cout << "Available devices:" << std::endl;
#endif
    
    // try to find opencl device first
    for(auto& p: sycl::platform::get_platforms()){
        for(auto& d: p.get_devices()){
            if(sycl::backend::opencl == d.get_backend()){
#ifdef _DEBUG
                std::cout << "\tOpenCL Device: "
                          << d.get_info<sycl::info::device::name>() << ", "
                          << d.get_backend() 
                          << std::endl;
#endif
                devs.push_back(d);
            }
        }
    }
    
    // if no opencl device, try level-zero
    if(devs.empty()) {
        std::cout << "No OpenCL devices found, falling back to Level Zero..." << std::endl;
        for(auto& p: sycl::platform::get_platforms()){
            for(auto& d: p.get_devices()){
                if(sycl::backend::ext_oneapi_level_zero == d.get_backend()){
#ifdef _DEBUG
                    std::cout << "\tLevel Zero Device: "
                              << d.get_info<sycl::info::device::name>() << ", "
                              << d.get_backend() 
                              << std::endl;
#endif
                    devs.push_back(d);
                }
            }
        }
    }
    
    if(devs.empty()) {
        std::cout << "No suitable devices found!" << std::endl;
    } else {
        std::cout << "Selected backend: " << (devs[0].get_backend() == sycl::backend::opencl ? "OpenCL" : "Level Zero") << std::endl;
    }
}

uint32_t SyclImpl::viewTransform(NdArray* camResultsA, 
                                NdArray* camResultsB, 
                                NdArray* feat, 
                                NdArray* cam2ego, 
                                NdArray* lidar2ego, 
                                NdArray* camIntrinsics, 
                                NdArray* cam2Lidar, 
                                NdArray* imgAugMat, 
                                NdArray* bevFeat) {

    DIE_IF(NULL == camResultsA || NULL == camResultsB || NULL == feat || 
           NULL == cam2ego || NULL == lidar2ego || NULL == camIntrinsics || 
           NULL == cam2Lidar || NULL == imgAugMat || NULL == bevFeat, "NULL PTR in viewTransform");
    
#ifdef BEV_DBG
    std::cout << "SyclImpl::viewTransform called" << std::endl;
#endif
    
    // TODO: 
    
    return 0; 
}
void TO_DEV(void** ptr, uint32_t sz, sycl::queue& q){
    void* dev = sycl::malloc_device(sz, q);
    DIE_IF(NULL == dev, "failed to allocate mem on dev");
    q.memcpy(dev, *ptr, sz);
    *ptr = dev;
}

void bpkV2(const float* cf,          
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
           const sycl::nd_item<3>& it) {
    
    const uint32_t itvIdx = it.get_group(1) * it.get_local_range(1) + it.get_local_id(1);
    const uint32_t featBlk = it.get_local_id(2) * TILE_SIZE;

    if (itvIdx >= itvN) return;

    const bevfusion::types::Int3& itv = itvs[itvIdx];
    float acc[TILE_SIZE] = {0.f};

    // Step 1: Accumulate over all i in [itv.x, itv.y)
    for (int i = itv.x; i < itv.y; ++i) {
        uint32_t id = idx[i];
        uint32_t ci = id / (d * farea);
        uint32_t fii = id % farea;
        float dwFp32 = dw[id];  
        uint32_t cfo = (ci * farea + fii) * c + featBlk;
        const float* feat = cf + cfo;
        
#pragma unroll
        for (int j = 0; j < TILE_SIZE; ++j) {
            if (featBlk + j < c) {  
                acc[j] = sycl::fma(feat[j], dwFp32, acc[j]);
            }
        }
    }

    // Step 2: Write back ONCE after accumulation
#pragma unroll
    for (int j = 0; j < TILE_SIZE; ++j) {
        if (featBlk + j < c) {
            uint32_t o = itv.z + (featBlk + j) * oH * oW;
            bf[o] = acc[j];
        }
    }
}

uint32_t SyclImpl::bevPool(void* cf,
                          void* dw,
                          void* idx,
                          void* itv,
                          void* bf,
                          uint32_t itvN,
                          uint32_t n, //cameraShape[0]
                          uint32_t c, //cameraShape[1]
                          uint32_t d, //cameraShape[2]
                          uint32_t h, //cameraShape[3]
                          uint32_t w, //cameraShape[4]
                          uint32_t bevWidth,
                          uint32_t bevHeight){
    DIE_IF(NULL == cf || NULL == dw || NULL == idx || NULL == itv || NULL == bf, "NULL PTR");
#ifdef _DEBUG
    checkDeviceResources(que);
    checkKernelLaunchParams(c, itvN, que); 
#endif 
    uint32_t cfDim  = n * c * h * w;
    uint32_t dwDim  = n * d * h * w;
    uint32_t idxDim = n * d * h * w;
    uint32_t bfDim  = c * bevWidth * bevHeight;

#ifdef _DEBUG
    std::cout << "SyclImpl::bevPool called with dimensions:" << std::endl;
    std::cout << "  n=" << n << ", c=" << c << ", d=" << d << ", h=" << h << ", w=" << w << std::endl;
    std::cout << "  bevWidth=" << bevWidth << ", bevHeight=" << bevHeight << std::endl;
    std::cout << "  itvN=" << itvN << std::endl;
#endif

    // if bf is null, allocate it
    if (!bf) {
        bf = sycl::malloc_device(sizeof(float) * bfDim, que);
        std::cout << "Allocated output buffer: " << bf << std::endl;
    } else {
        std::cout << "Using provided output buffer: " << bf << std::endl;
    }
    
    // check bf allocation
    if (!bf) {
        std::cerr << "Failed to allocate output buffer" << std::endl;
        return 1;
    }

    // Match the kernel's channel tiling: local_id(2) selects a TILE_SIZE channel block.
    // Keep a ~1024-thread workgroup when possible.
    // int xThread = static_cast<int>((c + TILE_SIZE - 1) / TILE_SIZE);
    // if (xThread <= 0) xThread = 1;
    // int yThread = 1024 / xThread;
    // if (yThread <= 0) yThread = 1;
    int xThread = 5;
    int yThread = 204;
    sycl::range<3> threads(1, yThread, xThread);
    sycl::range<3> blks(1, (int)((itvN + yThread - 1) / yThread), 1);
#ifdef _DEBUG    
    std::cout << "BEVPool configuration:" << std::endl;
    std::cout << "  Threads per work group: " << (xThread * yThread) << std::endl;
    std::cout << "  Number of work groups: " << blks[1] << std::endl;
    std::cout << "  Total threads: " << (xThread * yThread * blks[1]) << std::endl;
    std::cout << "  GPU utilization: " << (float)(xThread * yThread * blks[1]) / (160 * 1024) * 100 << "%" << std::endl;
#endif    
    // clear output buffer
    que.memset(bf, 0, sizeof(float) * bfDim).wait();
    
    uint32_t farea = w * h;
    
    try {
#ifdef _DEBUG
        std::cout << "Submitting BEVPool kernel..." << std::endl;
#endif        
        auto event = que.submit([&](sycl::handler& h) {
            h.parallel_for(sycl::nd_range<3>(blks * threads, threads), [=](sycl::nd_item<3> it) {
                auto gid = it.get_global_id();
                
#ifdef _DEBUG
                if (gid[0] == 0 && gid[1] == 0 && gid[2] == 0) {
                    sycl::ext::oneapi::experimental::printf("BEVPool kernel started! itvN=%u, c=%u\n", itvN, c);
                }
#endif
                
                // check bounds
                if (gid[1] >= itvN) return;
                
                bpkV2(
                    (const float*)cf,
                    (const float*)dw,
                    (const uint32_t*)idx,
                    (const bevfusion::types::Int3*)itv,
                    (float*)bf,
                    c, itvN, bevWidth, bevHeight, d, farea, it
                );
            });
        });
#ifdef _DEBUG        
        std::cout << "✓ BEVPool kernel completed successfully" << std::endl;
#endif
        
    } catch (const sycl::exception& e) {
        std::cerr << "❌ BEVPool kernel failed: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}



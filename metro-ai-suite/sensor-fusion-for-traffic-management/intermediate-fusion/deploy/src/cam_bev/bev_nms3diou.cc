#include "bev_sycl.h"
#include <sycl/sycl.hpp>
#include <dpct/dpct.hpp>
#define THREADS_PER_BLOCK 16
#define DIVUP(m, n) ( (m) / (n) + ( (m) % (n) > 0 ) )

//using namespace dpct;
const uint32_t THREADS_PER_BLOCK_NMS = sizeof(uint32_t) * 8;
inline dpct::global_memory<const float, 0> EPS(1e-8);
struct Point {
  float x, y;
  Point() {}
  Point(float _x, float _y) { x = _x, y = _y; }

  void set(float _x, float _y) {
    x = _x;
    y = _y;
  }

  Point operator+(const Point &b) const {
    return Point(x + b.x, y + b.y);
  }

  Point operator-(const Point &b) const {
    return Point(x - b.x, y - b.y);
  }
};

inline float cross(const Point &a, const Point &b) {
  return a.x * b.y - a.y * b.x;
}

inline float cross(const Point &p1, const Point &p2, const Point &p0) {
  return (p1.x - p0.x) * (p2.y - p0.y) - (p2.x - p0.x) * (p1.y - p0.y);
}

int checkRectCross(const Point &p1, const Point &p2, const Point &q1, const Point &q2) {
  int ret = sycl::min(p1.x, p2.x) <= sycl::max(q1.x, q2.x) &&
            sycl::min(q1.x, q2.x) <= sycl::max(p1.x, p2.x) &&
            sycl::min(p1.y, p2.y) <= sycl::max(q1.y, q2.y) &&
            sycl::min(q1.y, q2.y) <= sycl::max(p1.y, p2.y);
  return ret;
}

inline int checkInBox2d(const float *box, const Point &p) {
  const float MARGIN = 1e-5;

  float xCenter = (box[0] + box[2]) / 2;
  float yCenter = (box[1] + box[3]) / 2;
  float angleCos = sycl::cos(-box[4]),
        angleSin = sycl::sin( -box[4]); // rotate the point in the opposite direction of box
  float xRot = (p.x - xCenter) * angleCos + (p.y - yCenter) * angleSin + xCenter;
  float yRot = -(p.x - xCenter) * angleSin + (p.y - yCenter) * angleCos + yCenter;
  return (xRot > box[0] - MARGIN && xRot < box[2] + MARGIN &&
          yRot > box[1] - MARGIN && yRot < box[3] + MARGIN);
}

inline int intersection(const Point &p1, const Point &p0, const Point &q1, const Point &q0, Point &ans, const float &EPS) {
  // fast exclusion
  if (checkRectCross(p0, p1, q0, q1) == 0) return 0;

  // check cross standing
  float s1 = cross(q0, p1, p0);
  float s2 = cross(p1, q1, p0);
  float s3 = cross(p0, q1, q0);
  float s4 = cross(q1, p1, q0);

  if (!(s1 * s2 > 0 && s3 * s4 > 0)) return 0;

  // calculate intersection of two lines
  float s5 = cross(q1, p1, p0);
  if (sycl::fabs(s5 - s1) > EPS) {
    ans.x = (s5 * q0.x - s1 * q1.x) / (s5 - s1);
    ans.y = (s5 * q0.y - s1 * q1.y) / (s5 - s1);

  } else {
    float a0 = p0.y - p1.y, b0 = p1.x - p0.x, c0 = p0.x * p1.y - p1.x * p0.y;
    float a1 = q0.y - q1.y, b1 = q1.x - q0.x, c1 = q0.x * q1.y - q1.x * q0.y;
    float D = a0 * b1 - a1 * b0;

    ans.x = (b0 * c1 - b1 * c0) / D;
    ans.y = (a1 * c0 - a0 * c1) / D;
  }

  return 1;
}

inline void rotateByCenter(const Point &center, const float angleCos, const float angleSin, Point &p) {
  float xNew = (p.x - center.x) * angleCos + (p.y - center.y) * angleSin + center.x;
  float yNew = -(p.x - center.x) * angleSin + (p.y - center.y) * angleCos + center.y;
  p.set(xNew, yNew);
}

inline int cmpPoint(const Point &a, const Point &b, const Point &center) {
  return sycl::atan2(a.y - center.y, a.x - center.x) > sycl::atan2(b.y - center.y, b.x - center.x);
}

inline float boxOverlap(const float *aBox, const float *bBox, const float &EPS) {
  float x1A = aBox[0], y1A = aBox[1], x2A = aBox[2], y2A = aBox[3],
        aAngle = aBox[4];
  float x1B = bBox[0], y1B = bBox[1], x2B = bBox[2], y2B = bBox[3],
        b_angle = bBox[4];

  Point aCenter((x1A + x2A) / 2, (y1A + y2A) / 2);
  Point bCenter((x1B + x2B) / 2, (y1B + y2B) / 2);

  Point aBoxCorners[5];
  aBoxCorners[0].set(x1A, y1A);
  aBoxCorners[1].set(x2A, y1A);
  aBoxCorners[2].set(x2A, y2A);
  aBoxCorners[3].set(x1A, y2A);

  Point bBoxCorners[5];
  bBoxCorners[0].set(x1B, y1B);
  bBoxCorners[1].set(x2B, y1B);
  bBoxCorners[2].set(x2B, y2B);
  bBoxCorners[3].set(x1B, y2B);

  // get oriented corners
  float aAngleCos = sycl::cos(aAngle), aAngleSin = sycl::sin(aAngle);
  float bAngleCos = sycl::cos(b_angle), bAngleSin = sycl::sin(b_angle);

  for (int k = 0; k < 4; k++) {
    rotateByCenter(aCenter, aAngleCos, aAngleSin, aBoxCorners[k]);
    rotateByCenter(bCenter, bAngleCos, bAngleSin, bBoxCorners[k]);
  }

  aBoxCorners[4] = aBoxCorners[0];
  bBoxCorners[4] = bBoxCorners[0];

  // get intersection of lines
  Point crossPoints[16];
  Point polyCenter;
  int cnt = 0, flag = 0;

  polyCenter.set(0, 0);
  for (int i = 0; i < 4; i++) {
    for (int j = 0; j < 4; j++) {
      flag = intersection(aBoxCorners[i + 1], aBoxCorners[i], bBoxCorners[j + 1], bBoxCorners[j], crossPoints[cnt], EPS);
      if (flag) {
        polyCenter = polyCenter + crossPoints[cnt];
        cnt++;
      }
    }
  }

  // check corners
  for (int k = 0; k < 4; k++) {
    if (checkInBox2d(aBox, bBoxCorners[k])) {
      polyCenter = polyCenter + bBoxCorners[k];
      crossPoints[cnt] = bBoxCorners[k];
      cnt++;
    }
    if (checkInBox2d(bBox, aBoxCorners[k])) {
      polyCenter = polyCenter + aBoxCorners[k];
      crossPoints[cnt] = aBoxCorners[k];
      cnt++;
    }
  }

  polyCenter.x /= cnt;
  polyCenter.y /= cnt;

  // sort the points of polygon
  Point temp;
  for (int j = 0; j < cnt - 1; j++) {
    for (int i = 0; i < cnt - j - 1; i++) {
      if (cmpPoint(crossPoints[i], crossPoints[i + 1], polyCenter)) {
        temp = crossPoints[i];
        crossPoints[i] = crossPoints[i + 1];
        crossPoints[i + 1] = temp;
      }
    }
  }

  // get the overlap areas
  float area = 0;
  for (int k = 0; k < cnt - 1; k++) {
    area += cross(crossPoints[k] - crossPoints[0], crossPoints[k + 1] - crossPoints[0]);
  }

  return sycl::fabs(area) / 2.0;
}

inline float iovBev(const float *aBox, const float *bBox, const float &EPS) {
  float sa = (aBox[2] - aBox[0]) * (aBox[3] - aBox[1]);
  float sb = (bBox[2] - bBox[0]) * (bBox[3] - bBox[1]);
  float sOverlap = boxOverlap(aBox, bBox, EPS);
  return sOverlap / sycl::fmax(sa + sb - sOverlap, (float)EPS);
}

void nmsKernel(const int boxesCnt, const float nmsOverlapThresh, const float *boxes, uint32_t *mask, const sycl::nd_item<3> &itemCt1, const float &EPS, float *blkBoxes) {
  const int rowStart = itemCt1.get_group(1);
  const int colStart = itemCt1.get_group(2);

  const int szRow = sycl::fmin((float)(boxesCnt - rowStart * THREADS_PER_BLOCK_NMS), (float)THREADS_PER_BLOCK_NMS);
  const int szCol = sycl::fmin((float)(boxesCnt - colStart * THREADS_PER_BLOCK_NMS), (float)THREADS_PER_BLOCK_NMS);

  if (itemCt1.get_local_id(2) < szCol) {
    blkBoxes[itemCt1.get_local_id(2) * 5 + 0] = boxes[(THREADS_PER_BLOCK_NMS * colStart + itemCt1.get_local_id(2)) * 5 + 0];
    blkBoxes[itemCt1.get_local_id(2) * 5 + 1] = boxes[(THREADS_PER_BLOCK_NMS * colStart + itemCt1.get_local_id(2)) * 5 + 1];
    blkBoxes[itemCt1.get_local_id(2) * 5 + 2] = boxes[(THREADS_PER_BLOCK_NMS * colStart + itemCt1.get_local_id(2)) * 5 + 2];
    blkBoxes[itemCt1.get_local_id(2) * 5 + 3] = boxes[(THREADS_PER_BLOCK_NMS * colStart + itemCt1.get_local_id(2)) * 5 + 3];
    blkBoxes[itemCt1.get_local_id(2) * 5 + 4] = boxes[(THREADS_PER_BLOCK_NMS * colStart + itemCt1.get_local_id(2)) * 5 + 4];
  }
  itemCt1.barrier(); // Wait for different threads at boundary

  if (itemCt1.get_local_id(2) < szRow) {
    const int curBoxIdx = THREADS_PER_BLOCK_NMS * rowStart + itemCt1.get_local_id(2);
    const float *curBox = boxes + curBoxIdx * 5;

    int i = 0;
    uint32_t t = 0;
    int start = 0;
    if (rowStart == colStart) {
      start = itemCt1.get_local_id(2) + 1;
    }
    for (i = start; i < szCol; i++) {
      if (iovBev(curBox, blkBoxes + i * 5, EPS) > nmsOverlapThresh) {
        t |= 1ULL << i;
      }
    }
    const int colBlks = DIVUP(boxesCnt, THREADS_PER_BLOCK_NMS);
    mask[curBoxIdx * colBlks + colStart] = t;
  }
}

uint32_t SyclImpl::nms3d(NdArray* boxes, uint32_t* keep, uint32_t mkl, uint32_t* akl, float thresh){
    DIE_IF(NULL == boxes || NULL == keep || NULL == akl, "NULL PTR");
    const int32_t batchSize	= boxes->dims[0];
    const int32_t colBlks	= DIVUP(batchSize, THREADS_PER_BLOCK_NMS);
    /**
     *	colBlks * colBlks blocks, each block has THREADS_PER_BLOCK_NMS threads
     */

    uint32_t ndims = 0;
    float*   sel   = NULL;
    getArrayLen(boxes, &ndims);

    /***
     * cuda:
     *	nmsKernel<<<Dg, Db, Ns, S>>(parameters of nmsKernel)
     *	    Dg: type of dim3, used to specify grid dim and size, Dg.x * Dg.y * Dg.z = number of blocks to launch
     *	    Db: type of dim3, used to specify block dim and size, Db.x * Db.y * Db.z = number of threads per block
     *	    Ns: type of size_t, used to specify dynamically allocated memory size in shared mem, optional parameter, default is 0
     *	    S:  type of cudaStream_t, default is 0
     */
    // copy data to device
    if(HOST_MEM == boxes->type){
	if(ndims > boxesDims){
	    if(NULL != dBoxesData) sycl::free(dBoxesData, que);
	    boxesDims = ndims;
	    dBoxesData = (float*)sycl::malloc_device(ndims * sizeof(float), que);
	}
	que.memcpy(dBoxesData, boxes->data, sizeof(float) * ndims);
	sel = dBoxesData;
    }else{
	sel = boxes->data;
    }

    // update the mskData;
    const uint32_t mskNum = batchSize * colBlks;
    const uint32_t sz = sizeof(uint32_t) * mskNum;
    if(mskNum > mskCnt){
	if(NULL != dMskData) sycl::free(dMskData, que);
	if(NULL != hMskData) free(hMskData);
	mskCnt = mskNum;
	dMskData = (uint32_t*)sycl::malloc_device(sz, que);
	hMskData = (uint32_t*)aligned_alloc(64, sz);
    }

    // update the remove ptr
    if(colBlks > rmCnt){
	if(NULL == hRemove) free(hRemove);
	hRemove = (uint32_t*)aligned_alloc(64, colBlks);
	rmCnt = colBlks;
    }
    // sycl kernel for 
    {
	sycl::range<3> blocks(1, DIVUP(batchSize, THREADS_PER_BLOCK_NMS), DIVUP(batchSize, THREADS_PER_BLOCK_NMS));
	sycl::range<3> threads(1, 1, THREADS_PER_BLOCK_NMS);
	que.submit([&](sycl::handler& h){
	    AD(dMskData);
	    EPS.init();
	    auto epsCtxPtr = EPS.get_ptr(); 
	    sycl::local_accessor<float, 1> blkBoxesAccCt1( sycl::range<1>(320 /*THREADS_PER_BLOCK_NMS * 5*/), h); 
	    h.parallel_for(sycl::nd_range<3>(blocks * threads, threads), [=](sycl::nd_item<3> itemCt1) {
           nmsKernel(batchSize,
                     thresh,
                     sel,
                     AR(dMskData),
                     itemCt1,
                     *epsCtxPtr,
                     blkBoxesAccCt1.get_multi_ptr<sycl::access::decorated::no>().get());
			   });

	});
    }
    que.memcpy(hMskData, dMskData, sz);
    que.wait();
    
    int ntk = 0; // number to keep
    for(int i = 0; i < batchSize; ++i){
	int nBlk = i / THREADS_PER_BLOCK;
	int iBlk = i % THREADS_PER_BLOCK;

	if(!(hRemove[nBlk] & (1UL << iBlk))){
	    keep[ntk++] = i;
	    uint32_t* p = hMskData + i * colBlks;
	    for(int j = nBlk; j < colBlks; ++j){
		hRemove[j] |= p[j];
	    }
	}
    }
    *akl = ntk;
    return 0;
}

void SyclImpl::initNms3d(){
    dBoxesData	= NULL;
    boxesDims	= 0;
    dMskData	= NULL;
    mskCnt	= 0;
    hMskData	= NULL;
    hRemove	= NULL;
    rmCnt	= 0;
}

void SyclImpl::destroyNms3d(){
    if(NULL != dBoxesData) sycl::free(dBoxesData, que);
    if(NULL != dMskData) sycl::free(dMskData, que);
    if(NULL != hMskData) free(hMskData);
    if(NULL != hRemove) free(hRemove);
}
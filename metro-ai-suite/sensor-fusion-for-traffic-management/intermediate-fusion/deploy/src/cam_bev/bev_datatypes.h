#ifndef BEV_DATATYPES_H
#define BEV_DATATYPES_H
#include <stdint.h>
//return code for functions
#define BEV_SUCCESS		0
#define BEV_NULLPTR		1
#define BEV_INVALID_PARAM	2
typedef enum MemoryType{
    HOST_MEM = 0,
    DEVICE_MEM
}MemoryType;
typedef struct NdArray{
    uint32_t	nd;
    uint32_t*	dims;
    float*	data;
    MemoryType	type;
}NdArray;
typedef struct Bound{
    float	x;
    float	y;
    float	z;
}Bound;

void freeArray(NdArray* arr);
void getArrayLen(NdArray* arr, uint32_t* len);
#endif

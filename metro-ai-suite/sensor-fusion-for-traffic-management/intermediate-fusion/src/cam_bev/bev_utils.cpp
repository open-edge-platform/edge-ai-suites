#include "bev_datatypes.h"
#include <stddef.h>
#include <stdlib.h>
void freeArray(NdArray* a){
    if(NULL != a){
	if(NULL != a->dims){
	    free(a->dims);
	    a->dims = NULL;
	}
	if(NULL != a->data){
	    free(a->data);
	    a->data = NULL;
	}
    }
}
void getArrayLen(NdArray* arr, uint32_t* len){
    if(NULL != arr){
	uint32_t k = 1;
	for(uint32_t i = 0; i < arr->nd; ++i){
	    k *= arr->dims[i];
	}
	*len = k;
	return;
    }
    *len = 0;
}

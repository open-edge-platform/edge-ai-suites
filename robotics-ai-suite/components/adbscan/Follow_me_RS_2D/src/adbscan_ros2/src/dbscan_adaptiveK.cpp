// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "dbscan_adaptiveK.h"
#include <math.h>
#include "pcl/point_cloud.h"
#include "pcl/kdtree/kdtree_flann.h"

#include <iostream>
#include <vector>

#ifdef ADD_FPGA_SUPPORT
#include <iostream>
#include <fstream>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <time.h>
//export CL_CONTEXT_EMULATOR_DEVICE_INTELFPGA=a10gx
//unset CL_CONTEXT_EMULATOR_DEVICE_INTELFPGA
#define EPSILON (1e-2f)
using namespace std;
double diff(timespec start, timespec end);
#endif

#ifndef NULL
#define NULL 0
#endif

using namespace std;

void get_active_map(LiDAR_data_3D_t *x, FPDS_t *esp_array, vector<int> *neighbors, INT32_t num_points)
{
    pcl::PointCloud<pcl::PointXYZ>::Ptr cloud (new pcl::PointCloud<pcl::PointXYZ>);

    cloud->points.resize (num_points);

    //transform input data into PointCloud format; 
    for (size_t i = 0; i < cloud->size (); ++i)
    {
        (*cloud)[i].x = x[i].val[0];
        (*cloud)[i].y = x[i].val[1];
        (*cloud)[i].z = x[i].val[2];
    }

    pcl::KdTreeFLANN<pcl::PointXYZ> kdtree;

    kdtree.setInputCloud (cloud);

    pcl::PointXYZ searchPoint;

    std::vector<int> pointIdxRadiusSearch;
    std::vector<float> pointRadiusSquaredDistance;

    for (size_t i=0; i< num_points; i++) 
    {
        searchPoint.x = x[i].val[0];
        searchPoint.y = x[i].val[1];
        searchPoint.z = x[i].val[2];

        float radius = esp_array[i];
		//cout << "i=" << i << "; eps=" << radius << endl;

        int num_of_neighbors = kdtree.radiusSearch (searchPoint, radius, pointIdxRadiusSearch, pointRadiusSquaredDistance);
        if ( num_of_neighbors > 0 )  //found neighboring points
        {
			//cout << "num_of_neighbors = " << num_of_neighbors << endl;
            for (size_t j = 0; j < num_of_neighbors; ++j) //j is point in neighborhood
            {   
				//cout << "j=" << j <<  "pointIdxRadiusSearch[j]" << pointIdxRadiusSearch[j] << endl;
                //active[pointIdxRadiusSearch[j]] = 1;
				neighbors[i].push_back(pointIdxRadiusSearch[j]);
                //cout << "    "  <<   (*cloud)[ pointIdxRadiusSearch[j] ].x 
                //<< " " << (*cloud)[ pointIdxRadiusSearch[j] ].y 
                //<< " " << (*cloud)[ pointIdxRadiusSearch[j] ].z 
                //<< " (squared distance: " << pointRadiusSquaredDistance[j] << ")" << std::endl;
            }
        }
    }
  
}



/*--------------------------------------------------------------------------*
 * \brief This function calculates Euclidean distance in 3D space
 * betwean one point and a point from an array of points
 *--------------------------------------------------------------------------*/
void dist(LiDAR_data_3D_t o, LiDAR_data_3D_t x[], FPDS_t D[], int num_points)
{
	FPDS_t t0, t1, t2;
	
	for (int i = 0; i < num_points; i++)
	{
		t0 = o.val[0] - x[i].val[0];
		t1 = o.val[1] - x[i].val[1];
		t2 = o.val[2] - x[i].val[2];
		D[i] = sqrt(t0*t0 + t1*t1 + t2*t2);
	}
}

#ifdef USE_LINKED_LISTS
/*-----------------------------------------------------------------------*
 * \brief This functin is used to add an item to the item list
 *-----------------------------------------------------------------------*/
void listInit(ADBSCAN_list_t *p_list, int num_items)
{
	p_list->max_size = num_items;
	for (int i = 0; i < num_items; i++)
	{
		p_list->items[i].active = 0;
#ifdef USE_LINKED_LISTS
		p_list->items[i].index = i;
		p_list->items[i].p_next = NULL;
		p_list->items[i].p_prev = NULL;
#endif
	}
#ifdef USE_LINKED_LISTS
	p_list->pFirst = NULL;
	p_list->pLast = NULL;
#endif
	p_list->count = 0;
}

/*-----------------------------------------------------------------------*
 * \brief This functin is used to add an item to the item list
 *-----------------------------------------------------------------------*/
void listAddItem(ADBSCAN_list_t *p_list, int index)
{
	ADBSCAN_list_item_t *p_item = &p_list->items[index];

	if (p_item->active)
	{
		/* If this item is already in the list we don't have to do anything */
	}
	else
	{ 
		if (p_list->count == 0)
		{
			p_list->pFirst = &p_list->items[index];
			p_list->pLast = &p_list->items[index]; 
			p_list->count = 1;
		}
		else
		{
			p_item->p_prev = p_list->pLast;
			p_list->pLast->p_next = p_item;
			p_item->p_next = NULL;
			p_list->pLast = p_item;
			p_list->count += 1;
		}
		p_item->active = 1;
	}
}

/*-----------------------------------------------------------------------*
 * \brief This functin is used to remove an item from the item list
 *-----------------------------------------------------------------------*/
void listRemoveItem(ADBSCAN_list_t *p_list, int index)
{
	ADBSCAN_list_item_t *p_item = &p_list->items[index];
	
	if (p_item != p_list->pFirst)
	{
		while (1) ;
	}
	
	if (p_list->count == 0)
	{
		/* ERROR? If the list is emplty we have an error */
		while (1) ;
	}
	else
	{
		if (p_item->p_next != NULL && p_item->p_prev != NULL)
		{
			/* we are in the middle of the list */
			p_item->p_next->p_prev = p_item->p_prev;
			p_item->p_prev->p_next = p_item->p_next;
		}
		else if (p_item->p_next != NULL)
		{
			/* we are at the beginning of the list */
			p_item->p_next->p_prev = NULL;
			p_list->pFirst = p_item->p_next;
		}
		else
		{
			/* we are at the end of the list */
			if (p_list->count > 1)
			{
				if (p_item->p_prev == NULL)
				{
					/* ERROR? If we are at the end of the list, we have more than 1 item in the list, but
					 * we don't have a pointer to the previous item..., so we probably have an error */
					while (1) {;}
				}
				
				p_item->p_prev->p_next = NULL;
				p_list->pLast = p_item->p_prev;
			}
		}
		p_item->p_prev = NULL;
		p_item->p_next = NULL;
		p_item->active = 0;
		p_list->count--;
	}
}

/*-----------------------------------------------------------------------*
 * \brief This function finds points with distance <= eps and adds them  
 * to the object list.
 *-----------------------------------------------------------------------*/
INT32_t find(FPDS_t D[], FPDS_t esp, int num_points, ADBSCAN_list_t *p_list)
{
	INT32_t count = 0;
	
	for (int i = 0; i < num_points; i++)
	{
		if (D[i] <= esp)
		{
			listAddItem(p_list, i);
		}
	}
	
	return p_list->count;
}

#ifndef INLINE_FUNCTIONS
/*-----------------------------------------------------------------------*
 * \brief This function assigns a class to each object in the list
 *-----------------------------------------------------------------------*/
void setClass(INT32_t oclass[], ADBSCAN_list_t *p_list, INT32_t value)
{
	ADBSCAN_list_item_t *p_item = p_list->pFirst;
		
	while (p_item)
	{
		oclass[p_item->index] = value;
		p_item = p_item->p_next;
	}
}
	
/*----------------------------------------------------------------------------------------------*
 * \brief This function assigns a class to objects in the list that were not touched yet.
 *----------------------------------------------------------------------------------------------*/
void setClassTouched(
	INT32_t oclass[], 
	UINT8_t touched[], 
	ADBSCAN_list_t *p_list, 
	ADBSCAN_list_t *p_list1, 
	INT32_t value)
{
	ADBSCAN_list_item_t *p_item = p_list->pFirst;
	int result;
		
	while (p_item)
	{
		if (touched[p_item->index] == 0)
		{
			/* Mark as touched */
			touched[p_item->index] = 1;
			/* Add this point the main object list only if it is NOT already in the list  */
			listAddItem(p_list1, p_item->index);
			/* Set the class */
			oclass[p_item->index] = value;
		}
		p_item = p_item->p_next;
		//TW_TODO - We can clean the list here so we don't have to re-initialize it in the main loop
	}
}

/*---------------------------------------------------------------*
 * \brief This function implements the Adaptive DBScan algorithm
 *---------------------------------------------------------------*/
void dbscan_adaptiveK(
	LiDAR_data_3D_t *x, 
	FPDS_t *k_array, 
	FPDS_t *esp_array, 
	INT32_t *oclass, 
	INT32_t *type, 
	INT32_t num_points)
{
	UINT8_t touched[num_points];
	FPDS_t D[num_points];
	FPDS_t k, esp;
	LiDAR_data_3D_t ob;
	INT32_t length;
	INT32_t no = 1;
	INT32_t ind;
	ADBSCAN_list_t list[2];
	ADBSCAN_list_item_t items[2][num_points];
	ADBSCAN_list_item_t *p_item;
	
	list[0].items = items[0];
	list[1].items = items[1];
	
	/* Group points into objects */
	for (int i = 0; i < num_points; i++)
	{
		touched[i] = 0;
	}
		
	for (int i = 0; i < num_points; i++)
	{
		k = k_array[i];
		esp = esp_array[i];
		if (touched[i] == 0)
		{
			ob = x[i];
			dist(ob, x, D, num_points);
				
			/* Initalize the object list */
			listInit(&list[0], num_points);
				
			length = find(D, esp, num_points, &list[0]);
				
			if ((length > 1) && (length < k + 1))
			{
				type[i] = 0;
				oclass[i] = 0;
			}
				
			if (length == 1)
			{
				type[i] = -1;
				oclass[i] = -1;
				touched[i] = 1;
			}
				
			if (length >= k + 1)
			{
				type[i] = 1;
				oclass[i] = length * no;
			
				setClass(&oclass[0], &list[0], no);
				
				while (list[0].count)
				{
					ind = list[0].pFirst->index;
					ob = x[ind];
					touched[ind] = 1;
					listRemoveItem(&list[0], ind);
					
					dist(ob, x, D, num_points);
						
					listInit(&list[1], num_points);
					length = find(D, esp, num_points, &list[1]);
					
					if (length > 1)
					{
						setClass(&oclass[0], &list[1], no);
					
						type[ind] = (length >= k + 1) ? 1 : 0;
						
						setClassTouched(&oclass[0], &touched[0], &list[1], &list[0], no);
					}
				}
				no = no + 1;
			}
		}
	}
	
	for (int i = 0; i < num_points; i++)
	{
		if (oclass[i] == 0)
		{
			oclass[i] = -1;
			type[i] = -1;
		}	
	}
}

#else /* #ifndef INLINE_FUNCTIONS */

/*---------------------------------------------------------------*
 * \brief This function implements the Adaptive DBScan algorithm
 *---------------------------------------------------------------*/
void dbscan_adaptiveK(
	LiDAR_data_3D_t *x, 
	FPDS_t *k_array, 
	FPDS_t *esp_array, 
	INT32_t *oclass, 
	INT32_t *type, 
	INT32_t num_points)
{
	UINT8_t touched[num_points];
	FPDS_t D[num_points];
	FPDS_t k, esp;
	LiDAR_data_3D_t ob;
	INT32_t length;
	INT32_t no = 1;
	INT32_t ind;
	ADBSCAN_list_t list[2];
	ADBSCAN_list_item_t items[2][num_points];
	ADBSCAN_list_item_t *p_item;
	
	list[0].items = items[0];
	list[1].items = items[1];
	
	/* Group points into objects */
	for (int i = 0; i < num_points; i++)
	{
		touched[i] = 0;
	}
		
	for (int i = 0; i < num_points; i++)
	{
		k = k_array[i];
		esp = esp_array[i];
		if (touched[i] == 0)
		{
			ob = x[i];
			dist(ob, x, D, num_points);
				
			/* Initalize the object list */
			listInit(&list[0], num_points);
				
			length = find(D, esp, num_points, &list[0]);
				
			if ((length > 1) && (length < k + 1))
			{
				type[i] = 0;
				oclass[i] = 0;
			}
				
			if (length == 1)
			{
				type[i] = -1;
				oclass[i] = -1;
				touched[i] = 1;
			}
				
			if (length >= k + 1)
			{
				type[i] = 1;
				oclass[i] = length * no;
			
				p_item = list[0].pFirst;
				while (p_item)
				{
					oclass[p_item->index] = no;
					p_item = p_item->p_next;
				}
			
				while (list[0].count)
				{
					ind = list[0].pFirst->index;
					ob = x[ind];
					touched[ind] = 1;
					listRemoveItem(&list[0], ind);
					
					dist(ob, x, D, num_points);
						
					listInit(&list[1], num_points);
					length = find(D, esp, num_points, &list[1]);
					
					if (length > 1)
					{
						//p_item = list[1].pFirst;
						//while (p_item)
						//{
						//	oclass[p_item->index] = no;
						//	p_item = p_item->p_next;
						//}
						
						type[ind] = (length >= k + 1) ? 1 : 0;
						
						p_item = list[1].pFirst;
						while (p_item)
						{
							oclass[p_item->index] = no;
							
							if (touched[p_item->index] == 0)
							{
								/* Mark as touched */
								touched[p_item->index] = 1;
								/* Add this point to the main object list only if it is NOT already in the list  */
								if (list[0].items[p_item->index].active == 0)
								{
									listAddItem(&list[0], p_item->index);
								}
								
								/* Set the class */
								oclass[p_item->index] = no;
							}
							p_item = p_item->p_next;
						}
					}
				}
				no = no + 1;
			}
		}
	}
	
	for (int i = 0; i < num_points; i++)
	{
		if (oclass[i] == 0)
		{
			oclass[i] = -1;
			type[i] = -1;
		}	
	}
}
#endif /* #ifndef INLINE_FUNCTIONS */

#else /* #ifdef USE_LINKED_LISTS */

/*---------------------------------------------------------------*
 * \brief This function implements the Adaptive DBScan algorithm
 *---------------------------------------------------------------*/
void dbscan_adaptiveK(
	LiDAR_data_3D_t *x, 
	FPDS_t *k_array, 
	FPDS_t *esp_array, 
	INT32_t *oclass, 
	INT32_t *type, 
	INT32_t num_points)
{
	UINT8_t touched[num_points];
	INT32_t active[num_points];
	INT32_t active_count;
	INT32_t active_count_at[num_points]; //KDTree
	INT32_t active1[num_points];
	INT32_t active1_count;
	FPDS_t k, esp;
	LiDAR_data_3D_t ob;
	INT32_t length;
	INT32_t no = 1;
	INT32_t ind;
	FPDS_t Dist, t0, t1, t2;

	
	//use KDTree to index the point cloud
	vector<int> neighbors[num_points]; //list of neighbors for each point
    get_active_map(x, esp_array, neighbors, num_points);
	
	/* Group points into objects */
	for (int i = 0; i < num_points; i++)
	{
		touched[i] = 0;
	}
		
	for (int i = 0; i < num_points; i++)
	{
		k = k_array[i];
		esp = esp_array[i];
		if (touched[i] == 0)
		{
			ob = x[i];
			//dist(ob, x, D, num_points);
			//listInit(&list[0], num_points);
			//length = find(D, esp, num_points, &list[0]);

			//active_count = 0;
			//for (int j = 0; j < num_points; j++)
			//{
			//	t0 = ob.val[0] - x[j].val[0];
			//	t1 = ob.val[1] - x[j].val[1];
			//	t2 = ob.val[2] - x[j].val[2];
			//	Dist = sqrt(t0*t0 + t1*t1 + t2*t2);
			//	active[j] = (Dist <= esp) ? 1 : 0;
			//	active_count = (Dist <= esp) ? active_count + 1 : active_count;
			//} 
			for (int j = 0; j < num_points; j++)  //set all active[] to 0
			    active[j] = 0;
			
			//look up KDTree to find neighboring points
			active_count = neighbors[i].size();
			if ( active_count > 0 ) 
			{
				for (int j = 0; j < active_count; j++)
					active[neighbors[i][j]] = 1;//the index of neighbors indexed 
			}

			length = active_count;
				
			if ((length > 1) && (length < k + 1))
			{
				type[i] = -1;
				oclass[i] = -1;
			}
				
			if (length == 1)
			{
				type[i] = -1;
				oclass[i] = -1;
				touched[i] = 1;
			}
				
			if (length >= k + 1)
			{
				type[i] = 1;
				oclass[i] = no;

				for (int j = 0; j < num_points; j++)
				{
					oclass[j] = active[j] ? no : oclass[j];
				}
				
				while(active_count)
				{
					for (ind = 0; ind < num_points; ind++)
					{
						if (active[ind])
						{
							break;
						}
					}
						
					if(active[ind])
					{
						ob = x[ind];
						touched[ind] = 1;
						
						//listRemoveItem(&list[0], ind);
						active[ind] = 0;
						active_count = active_count - 1;
					
						//dist(ob, x, D, num_points);
						//listInit(&list[1], num_points);
						//length = find(D, esp, num_points, &list[1]);
						/*active1_count = 0;					
						for (int j = 0; j < num_points; j++)
						{
							t0 = ob.val[0] - x[j].val[0];
							t1 = ob.val[1] - x[j].val[1];
							t2 = ob.val[2] - x[j].val[2];
							Dist = sqrt(t0*t0 + t1*t1 + t2*t2);
							active1[j] = (Dist <= esp) ? 1 : 0;
							active1_count = (Dist <= esp) ? active1_count + 1 : active1_count;
						}  */

						for (int j = 0; j < num_points; j++)  //set all active[] to 0
			                active1[j] = 0;
			
			            //look up KDTree to find neighboring points
			            active1_count = neighbors[ind].size();
			            if ( active1_count > 0 ) 
			            {
				            for (int j = 0; j < active1_count; j++)
					            active1[neighbors[ind][j]] = 1;//the index of neighbors indexed 
			            }

						length = active1_count;
					
						if (length > 1)
						{
							type[ind] = (length >= k + 1) ? 1 : 0;
							
							for (int j = 0; j < num_points; j++)
							{
								if (active1[j])
								{
									oclass[j] = no;

									if (touched[j] == 0)
									{
										/* Mark as touched */
										touched[j] = 1;
										/* Add this point to the main object list only if it is NOT already in the list  */
										if (active[j] == 0)
										{
											//listAddItem(&list[0], j);
											active[j] = 1;
											active_count = active_count + 1;
										}
									}
								}
							}
						}
					}
				}
				no = no + 1;
			}
		}
	}
}
#endif /* #ifdef USE_LINKED_LISTS */

#ifdef ADD_FPGA_SUPPORT

void checkErr(cl_int err, const char * name)
{
	if (err != CL_SUCCESS) 
	{
		std::cerr << "ERROR: " << name << " (" << err << ")" << std::endl;
		exit(EXIT_FAILURE);
	}
}
void print_platform_info(std::vector<cl::Platform>* PlatformList)
{ 
	//Grab Platform Info for each platform
	for(int i = 0 ; i < PlatformList->size() ; i++)
	{
		printf("Platform Number: %d\n", i);
		std::cout << "Platform Name: "<<PlatformList->at(i).getInfo<CL_PLATFORM_NAME>() << "\n";
		std::cout << "Platform Profile: "<<PlatformList->at(i).getInfo<CL_PLATFORM_PROFILE>() << "\n";
		std::cout << "Platform Version: "<<PlatformList->at(i).getInfo<CL_PLATFORM_VERSION>() << "\n";
		std::cout << "Platform Vendor: "<<PlatformList->at(i).getInfo<CL_PLATFORM_VENDOR>() << "\n\n";
	}
}
void print_device_info(std::vector<cl::Device>* DeviceList)
{
	/* Grab Device Info for each device */
	for (int i = 0; i < DeviceList->size(); i++)
	{
		printf("Device Number: %d\n", i);
		std::cout << "Device Name: "<<DeviceList->at(i).getInfo<CL_DEVICE_NAME>() << "\n";
		std::cout << "Device Vendor: "<<DeviceList->at(i).getInfo<CL_DEVICE_VENDOR>() << "\n";
		std::cout << "Is Device Available?: "<<DeviceList->at(i).getInfo<CL_DEVICE_AVAILABLE>() << "\n";
		std::cout << "Is Device Little Endian?: "<<DeviceList->at(i).getInfo<CL_DEVICE_ENDIAN_LITTLE>() << "\n";
		std::cout << "Device Max Compute Units: "<<DeviceList->at(i).getInfo<CL_DEVICE_MAX_COMPUTE_UNITS>() << "\n";
		std::cout << "Device Max Work Item Dimensions: "<<DeviceList->at(i).getInfo<CL_DEVICE_MAX_WORK_ITEM_DIMENSIONS>() << "\n";
		std::cout << "Device Max Work Group Size: "<<DeviceList->at(i).getInfo<CL_DEVICE_MAX_WORK_GROUP_SIZE>() << "\n";
		std::cout << "Device Max Frequency: "<<DeviceList->at(i).getInfo<CL_DEVICE_MAX_CLOCK_FREQUENCY>() << "\n";
		std::cout << "Device Max Mem Alloc Size: "<<DeviceList->at(i).getInfo<CL_DEVICE_MAX_MEM_ALLOC_SIZE>() << "\n\n";
	}
}
void fill_generate(cl_float X[], cl_float Y[], cl_float Z[], cl_float LO, cl_float HI, size_t vectorSize)
{
	/* Assigns randome number from LO to HI to all locatoin of X and Y */
	for (int i = 0; i < vectorSize; ++i) 
	{
		X[i] =  LO + (cl_float)rand() / ((cl_float)RAND_MAX / (HI - LO));
		Y[i] =  LO + (cl_float)rand() / ((cl_float)RAND_MAX / (HI - LO));
		Z[i] =  LO + (cl_float)rand() / ((cl_float)RAND_MAX / (HI - LO));
	}
}

bool verification(float X[], float Y[], float Z[], float D[], float CalcD[], size_t vectorSize)
{
	/* Verify if OpenCL Calculation is Same as C Result */
	for (int i = 0; i < vectorSize - 4; i++) 
	{
		if (fabs(CalcD[i] - D[i]) > EPSILON) 
		{
			printf("\nVERIFICATION FAILED! index %d, X:%f, Y:%f, Z:%f, OpenCL Result:%f != Result %f)", i, X[i], Y[i], Z[i], D[i], CalcD[i]);
			return false;
		}
	}

	/* Print 10 Sample Data to Standard Out */
	printf("\n\nVERIFICATION PASSED!!!\n\nSome Sample of Results\n");
	printf("------------------------------------\n");
	for (int i = 0; i < (int)vectorSize; i = i + ((int)vectorSize) / 5) 
	{
		printf("Index %d: Input 1 is %f, Input 2 is %f, Input 3 is %f, Result is %f\n", i, ((float*)X)[i], ((float*)Y)[i], ((float*)Z)[i], ((float*)D)[i]);
	}
	return true;
}
#if 0
/*--------------------------------------------------------------------------------*
 * \brief This function initializes FPGA context for the Adaptive DBScan algorithm
 *--------------------------------------------------------------------------------*/
void dbscan_adaptiveK_fpga_init(ADBScan_fpga_context_t *pContext, int vectorSize)
{
	cl_int err;
	timespec time1, time2;
	timespec diff_time;
	
	/*=====================
	 * Setup FPGA Platform
	 *=====================*/

	/* Get Platform ID */
	err = cl::Platform::get(&pContext->PlatformList);
	assert(err == CL_SUCCESS);
	checkErr(pContext->PlatformList.size() == 1 ? CL_SUCCESS : -1, "cl::Platform::get");
	print_platform_info(&pContext->PlatformList);
	
	/*----------------
	/ Setup Device
	/----------------*/
	
	/* Get Device ID */
	err = pContext->PlatformList[0].getDevices(CL_DEVICE_TYPE_ALL, &pContext->DeviceList);
	assert(err == CL_SUCCESS);
	print_device_info(&pContext->DeviceList);
	
	/* Create Context */
	cl::Context mycontext(pContext->DeviceList);
	pContext->mycontext = mycontext;
	assert(err == CL_SUCCESS);
	
	/* Create Command queue */
	cl::CommandQueue myqueue(mycontext, pContext->DeviceList[0]); 
	assert(err == CL_SUCCESS);
		
	/* Create Buffers for input and output */
	cl::Buffer Buffer_InX(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InY(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InZ(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InK(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InE(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_Out1(mycontext, CL_MEM_WRITE_ONLY, sizeof(cl_int)*vectorSize);
	cl::Buffer Buffer_Out2(mycontext, CL_MEM_WRITE_ONLY, sizeof(cl_int)*vectorSize);
	
	// create the kernel
	const char *kernel_name = "dbscan_adaptiveK";
		
	//Read in binaries from file
	
	pContext->aocx_stream = std::ifstream("../Fpga/OpenCL/dbscan_adaptiveK_hw.aocx", std::ios::in | std::ios::binary);
	checkErr(pContext->aocx_stream.is_open() ? CL_SUCCESS : -1, "dbscan_adaptiveK_hw.aocx");
	pContext->prog = std::string(std::istreambuf_iterator<char>(pContext->aocx_stream), (std::istreambuf_iterator<char>()));
	pContext->mybinaries = cl::Program::Binaries(1, std::make_pair(pContext->prog.c_str(), pContext->prog.length() + 1));

	// Create the Program from the AOCX file.
	cl::Program program(mycontext, pContext->DeviceList, mybinaries);

	// Build the program
	// Compile the Kernel.... For Intel FPGA, nothing is done here, but this comforms to the standard
	err = program.build(pContext->DeviceList);
	assert(err == CL_SUCCESS);
}

/*----------------------------------------------------------------------*
 * \brief This function executes the Adaptive DBScan algorithm on FPGA
 *----------------------------------------------------------------------*/
void dbscan_adaptiveK_fpga_run(
	LiDAR_data_3D_t *x, 
	FPDS_t *k_array, 
	FPDS_t *esp_array, 
	INT32_t *oclass, 
	INT32_t *type, 
	INT32_t num_points)
{
}
#endif

/*---------------------------------------------------------------*
 * \brief This function implements the Adaptive DBScan algorithm
 *---------------------------------------------------------------*/
void dbscan_adaptiveK_fpga(
	LiDAR_data_3D_t *x, 
	FPDS_t *k_array, 
	FPDS_t *esp_array, 
	INT32_t *oclass, 
	INT32_t *type, 
	INT32_t num_points,
	INT32_t num_iter)
{
	cl_uint vectorSize = num_points;
	cl_int err;
	timespec time1, time2;
	timespec diff_time;
	double time[4][num_iter];
	double avr[4];
	clockid_t clk_id = CLOCK_MONOTONIC_RAW;  //CLOCK_REALTIME;
	
	avr[0] = 0;
	avr[1] = 0;
	avr[2] = 0;
	avr[3] = 0;
	
	//=====================
	// Setup FPGA Platform
	//=====================
	vectorSize = num_points;

	//Get Platform ID
	std::vector<cl::Platform> PlatformList;
	err = cl::Platform::get(&PlatformList);
	assert(err == CL_SUCCESS);
	checkErr(PlatformList.size() == 1 ? CL_SUCCESS : -1, "cl::Platform::get");
//	print_platform_info(&PlatformList);
	
	//Setup Device
	//Get Device ID
	std::vector<cl::Device> DeviceList;
	err = PlatformList[0].getDevices(CL_DEVICE_TYPE_ALL, &DeviceList);
	assert(err == CL_SUCCESS);
//	print_device_info(&DeviceList);
	
	//Create Context 
	cl::Context mycontext(DeviceList);
	assert(err == CL_SUCCESS);
	
	//Create Command queue
	cl::CommandQueue myqueue(mycontext, DeviceList[0]); 
	assert(err == CL_SUCCESS);
		
	//Create Buffers for input and output
	cl::Buffer Buffer_InX(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InY(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InZ(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InK(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InE(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_Out1(mycontext, CL_MEM_WRITE_ONLY, sizeof(cl_int)*vectorSize);
	cl::Buffer Buffer_Out2(mycontext, CL_MEM_WRITE_ONLY, sizeof(cl_int)*vectorSize);
	
	//Inputs and Outputs to Kernel, X and Y are inputs, Z is output
	//The aligned attribute is used to ensure alignment
	//so that DMA could be used if we were working with a real FPGA board
	cl_float X[vectorSize]  __attribute__((aligned(64)));
	cl_float Y[vectorSize]  __attribute__((aligned(64)));
	cl_float Z[vectorSize]  __attribute__((aligned(64)));
	cl_float K[vectorSize]  __attribute__((aligned(64)));
	cl_float E[vectorSize]  __attribute__((aligned(64)));
	cl_int Out1[vectorSize]  __attribute__((aligned(64)));
	cl_int Out2[vectorSize]  __attribute__((aligned(64)));
	float CalcD[vectorSize];

	//Allocates memory with value from 0 to 1000
	cl_float LO = 0; 
	cl_float HI = 1000;
	//fill_generate(X, Y, Z, LO, HI, vectorSize);
	for(int i = 0 ; i < num_points ; i++)
	{
		X[i] = x[i].val[0];
		Y[i] = x[i].val[1];
		Z[i] = x[i].val[2];
		K[i] = k_array[i];
		E[i] = esp_array[i];
	}

	//Write data to device
#if 0
	clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &time1);
	err = myqueue.enqueueWriteBuffer(Buffer_InX, CL_FALSE, 0, sizeof(cl_float)*vectorSize, X);
	err = myqueue.enqueueWriteBuffer(Buffer_InY, CL_FALSE, 0, sizeof(cl_float)*vectorSize, Y);
	err = myqueue.enqueueWriteBuffer(Buffer_InZ, CL_FALSE, 0, sizeof(cl_float)*vectorSize, Z);
	err = myqueue.enqueueWriteBuffer(Buffer_InK, CL_FALSE, 0, sizeof(cl_float)*vectorSize, K);
	err = myqueue.enqueueWriteBuffer(Buffer_InE, CL_FALSE, 0, sizeof(cl_float)*vectorSize, E);
	assert(err == CL_SUCCESS);
	myqueue.finish();
	clock_gettime(CLOCK_PROCESS_CPUTIME_ID, &time2);
	cout << "FPGA: Buffers write time :"  << diff(time1, time2).tv_sec << "." << diff(time1, time2).tv_nsec << " [s]" << endl;
#endif	
//	std::cout << "Done!" << std::endl; 

	// create the kernel
	const char *kernel_name = "dbscan_adaptiveK";
		
	//Read in binaries from file
	std::ifstream aocx_stream("../Fpga/OpenCL/dbscan_adaptiveK_hw.aocx", std::ios::in | std::ios::binary);
	if (!aocx_stream.is_open())
	{
		aocx_stream.open("./Fpga/OpenCL/dbscan_adaptiveK_hw.aocx", std::ios::in | std::ios::binary);
	}
	checkErr(aocx_stream.is_open() ? CL_SUCCESS : -1, "dbscan_adaptiveK_hw.aocx");
	std::string prog(std::istreambuf_iterator<char>(aocx_stream), (std::istreambuf_iterator<char>()));
	cl::Program::Binaries mybinaries(1, std::make_pair(prog.c_str(), prog.length() + 1));

	// Create the Program from the AOCX file.
	cl::Program program(mycontext, DeviceList, mybinaries);

	// Build the program
	// Compile the Kernel.... For Intel FPGA, nothing is done here, but this comforms to the standard
	err = program.build(DeviceList);
	assert(err == CL_SUCCESS);

	// Create the kernel
	// Find Kernel in Program
	cl::Kernel kernel(program, kernel_name, &err);

	assert(err == CL_SUCCESS);

	// Set Arguments to the Kernels
	err = kernel.setArg(0, Buffer_InX);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(1, Buffer_InY);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(2, Buffer_InZ);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(3, Buffer_InK);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(4, Buffer_InE);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(5, Buffer_Out1);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(6, Buffer_Out2);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(7, vectorSize);
	assert(err == CL_SUCCESS);
	
	
	for (int i = 0; i < num_iter; i++)
	{
		//Write data to device
	    clock_gettime(clk_id, &time1);
		err = myqueue.enqueueWriteBuffer(Buffer_InX, CL_FALSE, 0, sizeof(cl_float)*vectorSize, X);
		err = myqueue.enqueueWriteBuffer(Buffer_InY, CL_FALSE, 0, sizeof(cl_float)*vectorSize, Y);
		err = myqueue.enqueueWriteBuffer(Buffer_InZ, CL_FALSE, 0, sizeof(cl_float)*vectorSize, Z);
		if (i == 0)
		{
			err = myqueue.enqueueWriteBuffer(Buffer_InK, CL_FALSE, 0, sizeof(cl_float)*vectorSize, K);
			err = myqueue.enqueueWriteBuffer(Buffer_InE, CL_FALSE, 0, sizeof(cl_float)*vectorSize, E);
		}
		assert(err == CL_SUCCESS);
		myqueue.finish();
		clock_gettime(clk_id, &time2);
		time[0][i] = diff(time1, time2);
		avr[0] += time[0][i];
		cout << i << " FPGA: Buffers write time: " << time[0][i] << " [s]" << endl;
		
		//cout << "Launching the kernel..." << endl;
		clock_gettime(clk_id, &time1);
		// Launch Kernel
		//err=myqueue.enqueueNDRangeKernel(kernel, cl::NullRange, cl::NDRange(vectorSize), cl::NDRange(workSize));
		err = myqueue.enqueueTask(kernel);
		assert(err == CL_SUCCESS);
		myqueue.finish();
		clock_gettime(clk_id, &time2);
		time[1][i] = diff(time1, time2);;
		avr[1] += time[1][i];
		cout << i << " FPGA: ADBScan execution time: "  << time[1][i] << " [s]" << endl;

		// Read the output
		clock_gettime(clk_id, &time1);
		err = myqueue.enqueueReadBuffer(Buffer_Out1, CL_TRUE, 0, sizeof(cl_int)*vectorSize, Out1);
		err = myqueue.enqueueReadBuffer(Buffer_Out2, CL_TRUE, 0, sizeof(cl_int)*vectorSize, Out2);
		assert(err == CL_SUCCESS);

		err = myqueue.finish();
		assert(err == CL_SUCCESS);
	
		clock_gettime(clk_id, &time2);
		time[2][i] = diff(time1, time2);
		avr[2] += time[2][i];
		avr[3] += time[0][i] + time[1][i] + time[2][i];
		
		cout << i << " FPGA: Buffers read time: "  << time[2][i] << " [s]" << endl;
		cout << i << " FPGA: Total time: "  << (time[0][i] + time[1][i] + time[2][i]) << " [s]" << endl;
		cout << "" << endl;
	}
	
	if (num_iter > 1)
	{
		avr[0] = avr[0] / num_iter;
		avr[1] = avr[1] / num_iter;
		avr[2] = avr[2] / num_iter;
		avr[3] = avr[3] / num_iter;
		cout << "FPGA: Average Buffers write time: "  << avr[0] << " [s]" << endl;
		cout << "FPGA: Average ADBScan execution time: "  << avr[1] << " [s]" << endl;
		cout << "FPGA: Average Buffers read time: "  << avr[2] << " [s]" << endl;
		cout << "FPGA: Average Total time: "  << avr[3] << " [s]" << endl;
	}
	
	for (int i = 0; i < num_points; i++)
	{
		oclass[i] = Out1[i];
		type[i] = Out2[i];
	}
}

/*---------------------------------------------------------------*
 * \brief This function implements the Adaptive DBScan algorithm
 *---------------------------------------------------------------*/
void simple_test_fpga(
	LiDAR_data_3D_t *x, 
	FPDS_t *k_array, 
	FPDS_t *esp_array, 
	INT32_t *oclass, 
	INT32_t *type, 
	INT32_t num_points)
{
	cl_uint vectorSize = num_points;
	cl_int err;
	
	//=====================
	// Setup FPGA Platform
	//=====================
	vectorSize = num_points;

	//Get Platform ID
	std::vector<cl::Platform> PlatformList;
	err = cl::Platform::get(&PlatformList);
	assert(err == CL_SUCCESS);
	checkErr(PlatformList.size() == 1 ? CL_SUCCESS : -1, "cl::Platform::get");
	print_platform_info(&PlatformList);
	
	//Setup Device
	//Get Device ID
	std::vector<cl::Device> DeviceList;
	err = PlatformList[0].getDevices(CL_DEVICE_TYPE_ALL, &DeviceList);
	assert(err == CL_SUCCESS);
	print_device_info(&DeviceList);
	
	//Create Context 
	//cl::Context mycontext(DeviceList);
	cl::Context mycontext;
	mycontext = cl::Context(DeviceList);
	assert(err == CL_SUCCESS);
	
	//Create Command queue
	cl::CommandQueue myqueue(mycontext, DeviceList[0]); 
	assert(err == CL_SUCCESS);
		
	//Create Buffers for input and output
	cl::Buffer Buffer_InX(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InY(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_InZ(mycontext, CL_MEM_READ_ONLY, sizeof(cl_float)*vectorSize);
	cl::Buffer Buffer_OutD(mycontext, CL_MEM_WRITE_ONLY, sizeof(cl_float)*vectorSize);
	
	//Inputs and Outputs to Kernel, X and Y are inputs, Z is output
	//The aligned attribute is used to ensure alignment
	//so that DMA could be used if we were working with a real FPGA board
	cl_float X[vectorSize]  __attribute__((aligned(64)));
	cl_float Y[vectorSize]  __attribute__((aligned(64)));
	cl_float Z[vectorSize]  __attribute__((aligned(64)));
	cl_float D[vectorSize]  __attribute__((aligned(64)));
	float CalcD[vectorSize];

	//Allocates memory with value from 0 to 1000
	cl_float LO = 0; 
	cl_float HI = 1000;
	//fill_generate(X, Y, Z, LO, HI, vectorSize);
	for(int i = 0 ; i < num_points ; i++)
	{
		X[i] = x[i].val[0];
		Y[i] = x[i].val[1];
		Z[i] = x[i].val[2];
	}

	//Write data to device
	err = myqueue.enqueueWriteBuffer(Buffer_InX, CL_FALSE, 0, sizeof(cl_float)*vectorSize, X);
	err = myqueue.enqueueWriteBuffer(Buffer_InY, CL_FALSE, 0, sizeof(cl_float)*vectorSize, Y);
	err = myqueue.enqueueWriteBuffer(Buffer_InZ, CL_FALSE, 0, sizeof(cl_float)*vectorSize, Z);
	assert(err == CL_SUCCESS);
	myqueue.finish();
	
	std::cout << "Done!" << std::endl; 

	// create the kernel
	const char *kernel_name = "simple_test";
		
	//Read in binaries from file
	std::ifstream aocx_stream("../Fpga/OpenCL/simple_test_hw.aocx", std::ios::in | std::ios::binary);
	checkErr(aocx_stream.is_open() ? CL_SUCCESS : -1, "simple_test_hw.aocx");
	std::string prog(std::istreambuf_iterator<char>(aocx_stream), (std::istreambuf_iterator<char>()));
	cl::Program::Binaries mybinaries(1, std::make_pair(prog.c_str(), prog.length() + 1));

	// Create the Program from the AOCX file.
	cl::Program program(mycontext, DeviceList, mybinaries);

	// Build the program
	// Compile the Kernel.... For Intel FPGA, nothing is done here, but this comforms to the standard
	err = program.build(DeviceList);
	assert(err == CL_SUCCESS);

	// Create the kernel
	// Find Kernel in Program
	cl::Kernel kernel(program, kernel_name, &err);

	assert(err == CL_SUCCESS);

	// Set Arguments to the Kernels
	err = kernel.setArg(0, Buffer_InX);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(1, Buffer_InY);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(2, Buffer_InZ);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(6, Buffer_OutD);
	assert(err == CL_SUCCESS);
	err = kernel.setArg(7, vectorSize);
	assert(err == CL_SUCCESS);

	printf("\nLaunching the kernel...\n");
	
	// Launch Kernel
	//err=myqueue.enqueueNDRangeKernel(kernel, cl::NullRange, cl::NDRange(vectorSize), cl::NDRange(workSize));
	err = myqueue.enqueueTask(kernel);
	assert(err == CL_SUCCESS);

	// Read the output
	err = myqueue.enqueueReadBuffer(Buffer_OutD, CL_TRUE, 0, sizeof(cl_float)*vectorSize, D);
	assert(err == CL_SUCCESS);

	err = myqueue.finish();
	assert(err == CL_SUCCESS);

	// Equivalent Code runnign on CPUs
	float d, t0, t1, t2;
	float ob[3];
	ob[0] = X[0];
	ob[1] = Y[0];
	ob[2] = Z[0];
	for (int i = 0; i < vectorSize; i++)
	{
		t0 = ob[0] - X[i];
		t1 = ob[1] - X[i];
		t2 = ob[2] - X[i];
		d = sqrt(t0*t0 + t1*t1 + t2*t2);
		CalcD[i] = d;	
	}

	// Print Performance Results
	verification(X, Y, Z, D, CalcD, vectorSize);
}

#endif /* #ifdef ADD_FPGA_SUPPORT */

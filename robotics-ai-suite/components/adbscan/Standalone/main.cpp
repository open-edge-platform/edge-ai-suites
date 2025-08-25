// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing,
// software distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions
// and limitations under the License.

#include "ADBScan.h"
#include <iostream>
#include <fstream>
#include <assert.h>
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <string.h>
#include <time.h>
#include <cstdlib>
#include <vector>
#include "Util.hpp"

using namespace std;

/*---------------------------------------------------------------------------------------*
 * \brief This function loads ADBSCan configuration parameters from a file
 *---------------------------------------------------------------------------------------*/
ADBSCAN_Result_t load_config_params(std::string file_name, ADBSCAN_params_t &adbscan_params)
{
	ADBSCAN_Result_t result = ADBSCAN_SUCCESS;
	FILE *p_inFile;
	const char *pInFileName = file_name.c_str();
	char par_name[ADBSCAN_MAX_PAR_NAME_SIZE];
	char dummy[ADBSCAN_MAX_PAR_NAME_SIZE];
	int ival;
	float fval;
	char *p_line = NULL;
	size_t line_size = 0;
	int flags;
	ssize_t ret;
	
	p_inFile = fopen(pInFileName, "r");
	if (p_inFile == NULL)
	{
		std::cout << "Cannot open configuration parameters file:" << file_name << std::endl;
		result = ADBSCAN_CONFIG_PARAMS_FILE_OPEN_FAILED;
	}
	else
	{
		flags = SUBSAMPLE_RATIO_BIT | X_FILTER_BACK_BIT	| Y_FILTER_LEFT_BIT	| Y_FILTER_RIGHT_BIT | Z_FILTER_BIT | GROUND_REMOVAL_BIT;
		
		/* Load configuration parameters line-by-line */
		while ((ret = getline(&p_line, &line_size, p_inFile)) != -1)
		{
			sscanf(p_line, "%s", &par_name[0]);
			
			if (strcmp(par_name, "subsample_ratio") == 0)
			{
				sscanf(p_line, "%s %s %d", &par_name[0], &dummy[0], &ival);
				adbscan_params.subsample_ratio = ival;
				flags &= ~SUBSAMPLE_RATIO_BIT;
			}
			else if (strcmp(par_name, "x_filter_back") == 0)
			{
				sscanf(p_line, "%s %s %d", &par_name[0], &dummy[0], &ival);
				adbscan_params.x_filter_back = ival;
				flags &= ~X_FILTER_BACK_BIT;
			}
			else if (strcmp(par_name, "y_filter_left") == 0)
			{
				sscanf(p_line, "%s %s %d", &par_name[0], &dummy[0], &ival);
				adbscan_params.y_filter_left = ival;
				flags &= ~Y_FILTER_LEFT_BIT;
			}
			else if (strcmp(par_name, "y_filter_right") == 0)
			{
				sscanf(p_line, "%s %s %d", &par_name[0], &dummy[0], &ival);
				adbscan_params.y_filter_right = ival;
				flags &= ~Y_FILTER_RIGHT_BIT;
			}
			else if (strcmp(par_name, "z_filter") == 0)
			{
				sscanf(p_line, "%s %s %f", &par_name[0], &dummy[0], &fval);
				adbscan_params.z_filter = fval;
				flags &= ~Z_FILTER_BIT;
			}
			else if (strcmp(par_name, "Z_based_ground_removal") == 0)
			{
				sscanf(p_line, "%s %s %d", &par_name[0], &dummy[0], &ival);
				adbscan_params.Z_based_ground_removal = ival;
				flags &= ~GROUND_REMOVAL_BIT;
			}
			else
			{
				std::cout << "Unrecognized configuration parameter:" << std::endl;
				std::cout << "   " << p_line << std::endl;
			}
			
			/* Free memory allocated by the getline() function */
			if (p_line) 
			{
				free(p_line);
				line_size = 0;
			}
		}
		
		/* Make sure all configuration parameters were loaded */
		if (flags != 0)
		{
			result = ADBSCAN_CONFIG_PARAM_MISSING;
			
			std::cout << "Missing configuration parameters:" << std::endl;
			if (flags & SUBSAMPLE_RATIO_BIT) { std::cout << "   subsample_ratio" << std::endl; }
			if (flags & X_FILTER_BACK_BIT) { std::cout << "   x_filter_back" << std::endl; }
			if (flags & Y_FILTER_LEFT_BIT) { std::cout << "   y_filter_left" << std::endl; }
			if (flags & Y_FILTER_RIGHT_BIT) { std::cout << "   y_filter_right" << std::endl; }
			if (flags & Z_FILTER_BIT) { std::cout << "   z_filter" << std::endl; }
			if (flags & GROUND_REMOVAL_BIT) { std::cout << "   Z_based_ground_removal" << std::endl; }
		}
	}
	
	return result;
}

/*---------------------------------------------------------------------------------------*
 * \brief This function loads ADBScan adaptive parameters from a file
 *---------------------------------------------------------------------------------------*/
ADBSCAN_Result_t load_adaptive_params(std::string file_name, Adaptive_params_t &adaptive_params)
{
	ADBSCAN_Result_t result = ADBSCAN_SUCCESS;
	FILE *p_inFile;
	const char *pInFileName = file_name.c_str();
	float fval1, fval2, fval3;
	char *p_line = NULL;
	size_t line_size = 0;
	ssize_t ret;
	
	p_inFile = fopen(pInFileName, "r");
	if (p_inFile == NULL)
	{
		std::cout << "Cannot open adaptive parameters file:" << file_name << std::endl;
		result = ADBSCAN_ADAPTIVE_PARAMS_FILE_OPEN_FAILED;
	}
	else
	{
		/* Load configuration parameters line-by-line */
		ret = getline(&p_line, &line_size, p_inFile);
		if (ret > 0)
		{
			//std::cout << p_line << std::endl;
			sscanf(p_line, "%f %f %f", &fval1, &fval2, &fval3);
			adaptive_params.base = (FP32_t) fval3;
			adaptive_params.coeff_1 = (FP32_t) fval2;
			adaptive_params.coeff_2 = (FP32_t) fval1;
		}
		else
		{
			std::cout << "Cannot load adaptive parameters." << file_name << std::endl;
			result = ADBSCAN_ADAPTIVE_PARAMS_LOAD_FAILED;
		}
		
		/* Free memory allocated by the getline() function */
		if (p_line) 
		{
			free(p_line);
			line_size = 0;
		}
	}
	
	return result;
}

/*---------------------------------------------------------------------------------------*
 * \brief This function loads data from a LiDAR input file into an internal structure
 *---------------------------------------------------------------------------------------*/
ADBSCAN_Result_t load_LiDAR_data(std::string file_name, void * &p_LiDAR_data, int &LiDAR_data_size)
{
	ADBSCAN_Result_t result = ADBSCAN_SUCCESS;
	FILE *p_inFile;
	const char *pInFileName = file_name.c_str();
	void *  pBuf;
	
	p_inFile = fopen(pInFileName, "rb");
	if (p_inFile == NULL)
	{
		std::cout << "Cannot open LiDAR input file:" << file_name << std::endl;
		result = ADBSCAN_IN_LiDAR_FILE_OPEN_FAILED;
	}
	else
	{
		fseek(p_inFile, 0, SEEK_END);
		int fileSize = ftell(p_inFile);
		pBuf = malloc(fileSize);
		if (pBuf == NULL)
		{
			result = ADBSCAN_IN_LiDAR_FILE_MEMALLOC_FAILED;
		}
		else
		{
			fseek(p_inFile, 0L, SEEK_SET);
			int readCnt = fread(pBuf, 1, fileSize, p_inFile);
			if (readCnt == fileSize)
			{
				p_LiDAR_data =  pBuf;
				LiDAR_data_size = readCnt;
			}
			else
			{
				result = ADBSCAN_IN_LiDAR_FILE_READ_FAILED;
			}
		}
		fclose(p_inFile);
	}
	
	return result;
}

ADBSCAN_Result_t load_ROS2_LiDAR_data(std::string file_name, LiDAR_data_4D_t * &p_LiDAR_data, int &LiDAR_data_size)
{
	ADBSCAN_Result_t result = ADBSCAN_SUCCESS;
	FILE *p_inFile;
	const char *pInFileName = file_name.c_str();
	void *  pBuf;
	
	p_inFile = fopen(pInFileName, "rb");
	if (p_inFile == NULL)
	{
		std::cout << "Cannot open LiDAR input file:" << file_name << std::endl;
		result = ADBSCAN_IN_LiDAR_FILE_OPEN_FAILED;
	}
	else
	{
		fseek(p_inFile, 0, SEEK_END);
		int fileSize = ftell(p_inFile);
		pBuf = malloc(fileSize);
		if (pBuf == NULL)
		{
			result = ADBSCAN_IN_LiDAR_FILE_MEMALLOC_FAILED;
		}
		else
		{
			fseek(p_inFile, 0L, SEEK_SET);
			int readCnt = fread(pBuf, 1, fileSize, p_inFile);
			if (readCnt == fileSize)
			{
				//p_LiDAR_data =  pBuf;
				LiDAR_data_size = readCnt;
			}
			else
			{
				result = ADBSCAN_IN_LiDAR_FILE_READ_FAILED;
			}
		}
		fclose(p_inFile);
	}

	LiDAR_data_4D_t *velo_n = (LiDAR_data_4D_t*) pBuf;
	LiDAR_data_3D_t *xyz_n;
	INT32_t num_points = LiDAR_data_size / sizeof(LiDAR_data_4D_t);
	
	//velo_n is an array of type LiDAR_data_4D_t, size of num_points
	//iterate each data point and re-assemble into array of LiDAR_data_4D_t
	p_LiDAR_data = (LiDAR_data_4D_t *)malloc(num_points*sizeof(LiDAR_data_4D_t)); //allocate for return type
	for (int i=0; i<num_points; i++) // need to cast into LiDAR_data_4D_t
	{
		//XXX increment pointer value to load to array
		p_LiDAR_data = velo_n;
		p_LiDAR_data ++;
		velo_n ++;
	}

	
	return result;
}

/*------------------------------------------------------*
 * \brief This function subsamples the LiDAR input data
 *------------------------------------------------------*/
int subsample_LiDAR_data(LiDAR_data_4D_t* p_LiDAR_data, int num_points, unsigned int ratio)
{
	LiDAR_data_4D_t* pIn = p_LiDAR_data;
	LiDAR_data_4D_t* pOut = p_LiDAR_data;
	int count = 0;
	
	do
	{
		*pOut++ = *pIn;
		pIn += ratio;
		num_points -= ratio;
		count++;
	} while (num_points > 0);

	return count;
}

/*---------------------------------------------------*
 * \brief This function filters the LiDAR input data
 *---------------------------------------------------*/
int filter_LiDAR_data(LiDAR_data_4D_t* p_LiDAR_data, int num_points, int index, FILTER_op_t operation, float value)
{
	LiDAR_data_4D_t* pIn = p_LiDAR_data;
	LiDAR_data_4D_t* pOut = p_LiDAR_data;
	int count = 0;
	
	if (operation == FILTER_OP_GREATER_THAN)
	{
		while (num_points--)
		{
		
			if (pIn->val[index] <= value)
			{	
				*pOut++ = *pIn;
				count++;
			}
			pIn++;
		}
	}
	else /* operation == FILTER_OP_LESS_THAN */
	{
		while (num_points--)
		{
		
			if (pIn->val[index] >= value)
			{	
				*pOut++ = *pIn;
				count++;
			}
			pIn++;
		}
	}

	return count;
}

/*---------------------------------------------------------------------------------------*
 * \brief This function calculated the k and esp arrays based on the adaptive parameters 
 *	and LiDAR data
 *---------------------------------------------------------------------------------------*/
ADBSCAN_Result_t adaptive_parameters(
		LiDAR_data_3D_t *p_d, 
	FPDS_t *p_k, 
	FPDS_t *p_k_floor, 
	FPDS_t *p_esp,
	FPDS_t *p_esp_cont, 
	Adaptive_params_t *p_ap, 
	INT32_t num_points)
{
	ADBSCAN_Result_t result = ADBSCAN_SUCCESS;
	FPDS_t in;
	FPDS_t out;
	LiDAR_data_3D_t max, min, diff;
	FPDS_t prod;
	int i, k;
	double m, n;
	LiDAR_data_3D_t *p_d_tmp = p_d;
	double gamma_val;
	double denominator;
	
	/* 
	 * Calculate max and min values for the LiDAR input data
	 */
	for (k = 0; k < LIDAR_DATA_SIZE_3D; k++)
	{
		/* Initialize all fields with the first item */
		max.val[k] = p_d_tmp->val[k];
		min.val[k] = p_d_tmp->val[k];
	}
	p_d_tmp++;
	
	for (i = 1; i < num_points; i++)
	{
		for (k = 0; k < LIDAR_DATA_SIZE_3D; k++)
		{
			if (p_d_tmp->val[k] > max.val[k]) { max.val[k] = p_d_tmp->val[k]; }
			if (p_d_tmp->val[k] < min.val[k]) { min.val[k] = p_d_tmp->val[k]; }
		}
		p_d_tmp++;
	} 
	
	/* Calculate product of the diff = max(x)-min(x) */
	prod = 1.0;
	
	for (k = 0; k < LIDAR_DATA_SIZE_3D; k++)
	{
		diff.val[k] = max.val[k] - min.val[k];
		prod *= diff.val[k]; 
	}
	
	/*
	 * Calculate k, k_floor, esp, and esp_cont arrays 
	 */
	m = num_points;
	n = LIDAR_DATA_SIZE_3D;
	gamma_val = ADBSCAN_GAMMA;   // gamma_val = gamma(0.5*n+1); - difference between Matlab and C implementation
	denominator = m*sqrt(pow(ADBSCAN_PI, n));
	for (i = 0; i < num_points; i++)
	{
		in = p_d[i].val[0];
		out = ((in*in)*p_ap->coeff_2) + (in*p_ap->coeff_1) + p_ap->base;
		p_k[i] = (out < 1.0) ? 1.0 : out;
		p_k_floor[i] = floor(p_k[i]);
		
		/* Matlab: Eps_array_cont=((prod(max(x)-min(x))*(k_array)*gamma(.5*n+1))/(m*sqrt(pi.^n))).^(1/n); */
		p_esp_cont[i] = pow(((prod * p_k[i] * gamma_val) / denominator), (1 / n));
		
		/* Matlab: Eps_array=((prod(max(x)-min(x))*k_array_floor*gamma(.5*n+1))/(m*sqrt(pi.^n))).^(1/n); */
		p_esp[i] = pow(((prod * p_k_floor[i] * gamma_val) / denominator), (1 / n));
		p_esp[i] *= 0.7;
		if (p_esp[i] < 0.9)
		{
			p_esp[i] = 0.9;
		}
	}
	
	return result;
}

/*---------------------------------------------------------------*
 * \brief This functin copies data from 4D array to 3D array
 *---------------------------------------------------------------*/
ADBSCAN_Result_t copy4Dto3D(LiDAR_data_3D_t *p_3D, LiDAR_data_4D_t *p_4D, int num_points)
{
	ADBSCAN_Result_t result = ADBSCAN_SUCCESS;
	for (int i = 0; i < num_points; i++)
	{
		p_3D->val[0] = p_4D->val[0];
		p_3D->val[1] = p_4D->val[1];
		p_3D->val[2] = p_4D->val[2];
		p_3D++;
		p_4D++;
	}
	
	return result;
}

/*---------------------------------------------------------------------------------------------------------------*
 * \brief This function calculates time difference between two timer captured using the clock_gettime() function.
 *---------------------------------------------------------------------------------------------------------------*/
double diff(timespec start, timespec end)
{
	timespec temp;
	double result;
	
	if ((end.tv_nsec - start.tv_nsec) < 0) 
	{
		temp.tv_sec = end.tv_sec - start.tv_sec - 1;
		temp.tv_nsec = 1000000000 + end.tv_nsec - start.tv_nsec;
	}
	else 
	{
		temp.tv_sec = end.tv_sec - start.tv_sec;
		temp.tv_nsec = end.tv_nsec - start.tv_nsec;
	}
	
	result = (double)temp.tv_sec + ((double)temp.tv_nsec / (double)1000000000);
	
	return result;
}



/*=================================================================*
 *		MAIN FUNCTION
 *=================================================================*/
int main(int argc, char *argv[])
{ 
	ADBSCAN_Result_t result;
	ADBSCAN_params_t adbscan_params;
	Adaptive_params_t adaptive_params;
	std::string input_LiDAR_filename;
	FILE *p_outFile = NULL;
	void *p_data;
	int LiDAR_data_size;
	INT32_t *p_type = NULL;
	INT32_t *p_class = NULL;
	FPDS_t *p_k = NULL;
	FPDS_t *p_k_floor = NULL;
	FPDS_t *p_esp = NULL;
	FPDS_t *p_esp_cont = NULL;
	clock_t start, stop;
	double time;
	INT32_t num_iter = 1;
	clockid_t clk_id = CLOCK_MONOTONIC_RAW; //CLOCK_REALTIME;
	vector<Point> points_in_frame;
	
	/*
	 * Parse command line parameters
	 */
	
    result = load_config_params("config_params.txt", adbscan_params);
	if (result != ADBSCAN_SUCCESS)
	{
	    return 1;
	}
	
	
	// Use the default adaptive parameter file
	//adaptive_params.base = 3.4694;
	//adaptive_params.coeff_1 = -0.0335;
	//adaptive_params.coeff_2 = 0.00015124;
	
	/* Adaptive parmeters */
	string adaptive_params_fname = "./adaptive_params_default.txt" ;
	result = load_adaptive_params(adaptive_params_fname, adaptive_params);
	if (result != ADBSCAN_SUCCESS)
	{
		return 1;
	}
	
	const char *pInFileName = argv[2];
	p_outFile = fopen(pInFileName, "w");
	if (p_outFile == NULL)
	{
		std::cout << "ERROR: Cannot open the output file:" << pInFileName << std::endl;
		return 1;
	}
	
	/* Number of iterations */
	
	num_iter = 1;
	/*
	 * Load LiDAR data points
	 */

	input_LiDAR_filename = argv[1];
	result = load_LiDAR_data(input_LiDAR_filename, p_data, LiDAR_data_size);

	//the data needs to be loaded into p_data
	if (result == ADBSCAN_SUCCESS)
	{
		LiDAR_data_4D_t *velo_n = (LiDAR_data_4D_t*) p_data;
		LiDAR_data_3D_t *xyz_n;
		INT32_t num_points = LiDAR_data_size / sizeof(LiDAR_data_4D_t);
		
		/* Subsample the LiDAR data */
		num_points = subsample_LiDAR_data(velo_n, num_points, adbscan_params.subsample_ratio);
		
		/* X filter the LiDAR data */
		num_points = filter_LiDAR_data(velo_n, num_points, X_INDEX, FILTER_OP_LESS_THAN, adbscan_params.x_filter_back);
		
		/* Z filter the LiDAR data */
		if (adbscan_params.Z_based_ground_removal)
		{
			num_points = filter_LiDAR_data(velo_n, num_points, Z_INDEX, FILTER_OP_LESS_THAN, adbscan_params.z_filter);
		}
		
		/* Y filter the LiDAR data */
		num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_LESS_THAN, adbscan_params.y_filter_right);
		num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_GREATER_THAN, adbscan_params.y_filter_left);
		
		/* 
		 * Allocate memory for the Adaptive DBScan algorithm
		 */
		p_k = (FPDS_t *) malloc(num_points*sizeof(FPDS_t));
		result = (p_k == NULL) ? ADBSCAN_K_ARRAY_MEMALLOC_FAILED : ADBSCAN_SUCCESS;

		if (result == ADBSCAN_SUCCESS)
		{
			p_k_floor = (FPDS_t *) malloc(num_points*sizeof(FPDS_t));
			result = (p_k_floor == NULL) ? ADBSCAN_K_FLOOR_ARRAY_MEMALLOC_FAILED : ADBSCAN_SUCCESS;
		}
		
		if (result == ADBSCAN_SUCCESS)
		{
			p_esp = (FPDS_t *) malloc(num_points*sizeof(FPDS_t));
			result = (p_esp == NULL) ? ADBSCAN_ESP_ARRAY_MEMALLOC_FAILED : ADBSCAN_SUCCESS;
		}
		
		if (result == ADBSCAN_SUCCESS)
		{
			p_esp_cont = (FPDS_t *) malloc(num_points*sizeof(FPDS_t));
			result = (p_esp_cont == NULL) ? ADBSCAN_ESP_CONT_ARRAY_MEMALLOC_FAILED : ADBSCAN_SUCCESS;
		}
		
		if (result == ADBSCAN_SUCCESS)
		{
			p_class = (INT32_t *) malloc(num_points*sizeof(INT32_t));
			result = (p_class == NULL) ? ADBSCAN_CLASS_MEMALLOC_FAILED : ADBSCAN_SUCCESS;
		}
		
		if (result == ADBSCAN_SUCCESS)
		{
			p_type = (INT32_t *) malloc(num_points*sizeof(INT32_t));
			result = (p_type == NULL) ? ADBSCAN_TYPE_MEMALLOC_FAILED : ADBSCAN_SUCCESS;
		}
		
		if (result == ADBSCAN_SUCCESS)
		{
			xyz_n = (LiDAR_data_3D_t *) malloc(num_points*sizeof(LiDAR_data_3D_t));
			result = (xyz_n == NULL) ? ADBSCAN_3D_DATA_MEMALLOC_FAILED : ADBSCAN_SUCCESS;
		}
		
		/* 
		 * Execute the AdaptiveDBScan algorithm
		 */
		if (result == ADBSCAN_SUCCESS)
		{
			/* 4D to 3D data conversion */
			copy4Dto3D(xyz_n, velo_n, num_points);
			
			/* Calculate the k and esp arrays */
			result = adaptive_parameters(xyz_n, p_k, p_k_floor, p_esp, p_esp_cont, &adaptive_params, num_points);
			
			if (num_points > MAX_POINTS)
			{
				result = ADBSCAN_MAX_NUM_OF_POINT_EXCEEDED;
				cout << "ERROR!: ADBScan: Max number of points exeeded. Can not continue." << endl;
			}
			
			/* Execute the Adaptive DbScan algorithm */
			if (result == ADBSCAN_SUCCESS)
			{
				if (true) //for CPU
				{
					timespec t1, t2;
					double total = 0.0;
					double avr = 0.0;
					for (int i = 0; i < num_iter; i++)
					{
						clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
					
						dbscan_adaptiveK(xyz_n, p_k_floor, p_esp, p_class, p_type, num_points);
					
						clock_gettime(clk_id, &t2);		
						cout << i << ". CPU: ADBScan execution time: "  << diff(t1, t2) << " [s]" << endl;
						total += diff(t1, t2);
					}
					if (num_iter > 1)
					{
						avr = total / num_iter;
						cout << "CPU: Average ADBScan execution time: "  << avr << " [s]" << endl;
					}
				}
				else
				{
#ifdef ADD_FPGA_SUPPORT			
					dbscan_adaptiveK_fpga(xyz_n, p_k_floor, p_esp, p_class, p_type, num_points, num_iter);
#else
					cout << "ERROR: " << "FPGA not Supported" << endl;
#endif
				}
				
				if (result == ADBSCAN_SUCCESS)
				{   
					for (int i = 0; i < num_points; i++)
					{
						if (p_outFile)
						{
							fprintf(p_outFile, "%d %f %f %f %d %d \n", i + 1, xyz_n[i].val[0], xyz_n[i].val[1], xyz_n[i].val[2], p_class[i], p_type[i]);
						}
						else
						{
							std::cout << i << " " << xyz_n[i].val[0] << " " << xyz_n[i].val[1] << " " << xyz_n[i].val[2] << " " << p_class[i] << " " << p_type[i]  << std::endl;
						}
                    //jcao7: output to a vector of points
                        points_in_frame.push_back(Point(xyz_n[i].val[0], xyz_n[i].val[1], xyz_n[i].val[2], p_class[i]));
					}
					if (p_outFile)
					{
						fclose(p_outFile);
					}
				}
			}
		}

		//if frame is not empty, regroup into clusters
		if (points_in_frame.size() > 0)
		{
			vector<Cluster> clusters = get_clusters(points_in_frame);
    		cout << "number of clusters:" << clusters.size() << endl;
    		for (int i = 0; i<clusters.size(); i++)
    		{
        		cout << i << ": " << clusters[i].cluster_id << " "<< clusters[i].size <<endl;
        		clusters[i].print_list();
        		cout << i << ": " << "centroid: " << clusters[i].get_centroid().x << " " <<  clusters[i].get_centroid().y 
           			<< " " << clusters[i].get_centroid().z << endl;
           
        		vector<Point> BB_pts = get_boundingbox(clusters[i].point_list);
        		cout << "bounding box corner points:"  <<endl;
        		for (int j=0; j<BB_pts.size(); j++)
            		cout << BB_pts[j].x <<" "<< BB_pts[j].y <<" "<< BB_pts[j].z<< endl;
    		}
            
		}
		
		/* Free memory */
		free(velo_n);
		if (xyz_n) free(xyz_n);
		if (p_k) free(p_k);
		if (p_k_floor) free(p_k_floor);
		if (p_esp) free(p_esp);
		if (p_esp_cont) free(p_esp_cont);
		if (p_class) free(p_class);
		if (p_type) free(p_type);
	}
}
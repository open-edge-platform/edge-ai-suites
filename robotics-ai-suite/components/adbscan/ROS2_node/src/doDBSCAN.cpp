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

#include "doDBSCAN.hpp"
Config_params_t CONFIG_PARAMS;
using namespace std;

/*---------------------------------------------------------------------------------------*
 * \brief This function loads ADBSCan configuration parameters from a file
 *---------------------------------------------------------------------------------------*/
ADBSCAN_Result_t load_config_params(ADBSCAN_params_t &adbscan_params)
{
	adbscan_params.subsample_ratio = CONFIG_PARAMS.subsample_ratio;
    adbscan_params.x_filter_back = CONFIG_PARAMS.x_filter_back;
    adbscan_params.y_filter_left = CONFIG_PARAMS.y_filter_left;
    adbscan_params.y_filter_right = CONFIG_PARAMS.y_filter_right;
    adbscan_params.z_filter = CONFIG_PARAMS.z_filter;
	adbscan_params.Z_based_ground_removal = CONFIG_PARAMS.Z_based_ground_removal;

	return ADBSCAN_SUCCESS;
}

/*---------------------------------------------------------------------------------------*
 * \brief This function loads ADBScan adaptive parameters from a file
 *---------------------------------------------------------------------------------------*/
ADBSCAN_Result_t load_adaptive_params(Adaptive_params_t &adaptive_params)
{
    adaptive_params.base = CONFIG_PARAMS.base;
	adaptive_params.coeff_1 = CONFIG_PARAMS.coeff_1;
	adaptive_params.coeff_2 = CONFIG_PARAMS.coeff_2;

	return ADBSCAN_SUCCESS;
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

	float max_x = 0;
	float min_x = 0;
	for (i = 0; i < num_points; i++)
	{
		if (p_d[i].val[0] > max_x) max_x = p_d[i].val[0];
		if (p_d[i].val[0] < min_x) min_x = p_d[i].val[0];
	}

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

        string Lidar_type = CONFIG_PARAMS.Lidar_type;
        if ( Lidar_type == "2D" || Lidar_type == "RS")
		{
		  p_esp[i] *= CONFIG_PARAMS.scale_factor;
		
	      if (p_esp[i] <=0)
			p_esp[i] = 0.02 * (max_x - min_x);
		  
		}
		else //3D lidar
		{
	      p_esp[i] *= CONFIG_PARAMS.scale_factor; //0.7;
		  if (p_esp[i] < 0.9)
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
	
	//cout << "start :"  << start.tv_sec << "[s]  " << start.tv_nsec << "[ns]" << endl;
	//cout << "end :"  << end.tv_sec << "[s]  " << end.tv_nsec << "[ns]" << endl;
	
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

vector<Obstacle> doDBSCAN(void *p_Data, int LiDAR_data_size, int dimension, std::vector<double>* benchmarking_time)
{
	ADBSCAN_Result_t result;
	ADBSCAN_params_t adbscan_params;
	Adaptive_params_t adaptive_params;
	
	//FILE *p_outFile = NULL;
	//void *p_data;
	//int LiDAR_data_size;
	INT32_t *p_type = NULL;
	INT32_t *p_class = NULL;
	FPDS_t *p_k = NULL;
	FPDS_t *p_k_floor = NULL;
	FPDS_t *p_esp = NULL;
	FPDS_t *p_esp_cont = NULL;
	//clock_t start, stop;
	//double time;
	INT32_t num_iter = 1;
	clockid_t clk_id = CLOCK_MONOTONIC_RAW; //CLOCK_REALTIME;
	timespec t1, t2;
	vector<Point> points_in_frame;
	vector<Obstacle> obstacles;

	clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
	
	/*
	 * Parse command line parameters
	 */
    result = load_config_params(adbscan_params);
	
	// Use the default adaptive parameter file
	//adaptive_params.base = 3.4694;
	//adaptive_params.coeff_1 = -0.0335;
	//adaptive_params.coeff_2 = 0.00015124;
	
	/* Adaptive parmeters */
	result = load_adaptive_params(adaptive_params);

	/*
	 * Load LiDAR data points
	 */
	LiDAR_data_4D_t *velo_n = (LiDAR_data_4D_t*) p_Data;
	LiDAR_data_3D_t *xyz_n = NULL;
	INT32_t num_points = LiDAR_data_size / sizeof(LiDAR_data_4D_t);

	if (dimension == 3)
	{
		/* Subsample the LiDAR data */
		num_points = subsample_LiDAR_data(velo_n, num_points, adbscan_params.subsample_ratio);
		cout << "number of points after subsampling: " << num_points << std::endl;
		/* X filter the LiDAR data */
		//num_points = filter_LiDAR_data(velo_n, num_points, X_INDEX, FILTER_OP_LESS_THAN, adbscan_params.x_filter_back);

		/* Z filter the LiDAR data */
		if (adbscan_params.Z_based_ground_removal)
		{
			num_points = filter_LiDAR_data(velo_n, num_points, Z_INDEX, FILTER_OP_LESS_THAN, adbscan_params.z_filter);
		}
	
		/* Y filter the LiDAR data */
		//num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_LESS_THAN, adbscan_params.y_filter_right);
		//num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_GREATER_THAN, adbscan_params.y_filter_left);
	}
	else if (dimension == 4)  //RealSense data
	{
		/* Subsample the RealSense data */
		num_points = subsample_LiDAR_data(velo_n, num_points, adbscan_params.subsample_ratio);
		cout << "number of points after subsampling: " << num_points << std::endl;
		/* Z filter the RealSense data to remove ground */
		if (adbscan_params.Z_based_ground_removal)
		{
			num_points = filter_LiDAR_data(velo_n, num_points, Z_INDEX, FILTER_OP_LESS_THAN, adbscan_params.z_filter);
		}

		/* X filter the LiDAR data */
		num_points = filter_LiDAR_data(velo_n, num_points, X_INDEX, FILTER_OP_GREATER_THAN, adbscan_params.x_filter_back);

		/* Y filter the LiDAR data */
		num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_LESS_THAN, adbscan_params.y_filter_right);
		num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_GREATER_THAN, adbscan_params.y_filter_left);
		cout << "number of points after filtering: " << num_points << std::endl;
	}
	clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
	(*benchmarking_time)[0] = diff(t1, t2);
	cout << "test CPU: ADBScan subsampling & filtering time: "  << diff(t1, t2) << " [s]" << endl;
	
	/* 
	 Allocate memory for the Adaptive DBScan algorithm
	*/
	clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
	
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
	Execute the AdaptiveDBScan algorithm
	*/
	if(num_points > 0)
	{
		if (result == ADBSCAN_SUCCESS)
		{
			/* 4D to 3D data conversion */
			copy4Dto3D(xyz_n, velo_n, num_points);
			
			/* Calculate the k and esp arrays */
			result = adaptive_parameters(xyz_n, p_k, p_k_floor, p_esp, p_esp_cont, &adaptive_params, num_points);
			clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
			(*benchmarking_time)[1] = diff(t1, t2);
			cout << "test CPU: ADBScan param generation time: "  << diff(t1, t2) << " [s]" << endl;
			//cout << "num_points: " << num_points << endl;
			if (num_points > MAX_POINTS)
			{
				result = ADBSCAN_MAX_NUM_OF_POINT_EXCEEDED;
				cout << "ERROR!: ADBScan: Max number of points exeeded. Can not continue." << endl;
			}
				
			/* Execute the Adaptive DbScan algorithm */
			if (result == ADBSCAN_SUCCESS)
			{	
#ifdef ADD_FPGA_SUPPORT			
				dbscan_adaptiveK_fpga(xyz_n, p_k_floor, p_esp, p_class, p_type, num_points, num_iter);
#else
				clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
				dbscan_adaptiveK(xyz_n, p_k_floor, p_esp, p_class, p_type, num_points, CONFIG_PARAMS.oneapi_library);
				clock_gettime(clk_id, &t2);		
				(*benchmarking_time)[2] = diff(t1, t2);
				cout << "test CPU: ADBScan execution time: "  << diff(t1, t2) << " [s]" << endl;
#endif	
				clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */			  
				for (int i = 0; i < num_points; i++)
				{   
					// output to a vector of points
					points_in_frame.push_back(Point(xyz_n[i].val[0], xyz_n[i].val[1], xyz_n[i].val[2], p_class[i]));
				}
				clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
				(*benchmarking_time)[3] = diff(t1, t2);
			}
		}

		//if frame is not empty, regroup into clusters
		//time the cluster
		clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
		if (points_in_frame.size() > 0)
		{
			vector<Cluster> clusters = get_clusters(std::move(points_in_frame));
			cout << "number of clusters:" << clusters.size() << endl;
			for (long unsigned int i = 0; i<clusters.size(); i++)
			{
				//cout << i << ": " << clusters[i].cluster_id << " "<< clusters[i].size <<endl;
				//clusters[i].print_list();
				//cout << i << ": " << "centroid: " << clusters[i].get_centroid().x << " " <<  clusters[i].get_centroid().y 
				//	<< " " << clusters[i].get_centroid().z << endl;
				Obstacle obstacle = get_obstacle(clusters[i].point_list);
				//cout << obstacle.c_x <<", " << obstacle.c_y <<", " << obstacle.c_z << endl;
				//cout << obstacle.x <<", "<<obstacle.y<<", " << obstacle.z << endl;
				obstacles.push_back(obstacle);
			}
			
		}
		clock_gettime(clk_id, &t2); /* CLOCK_PROCESS_CPUTIME_ID */
		(*benchmarking_time)[4] = diff(t1, t2);
		cout << "test CPU: ADBScan cluster regrouping time : "  << diff(t1, t2) << " [s]" << endl;
	}
	else
	{
		Obstacle obstacle;
    	obstacle.c_x = 0.0;
    	obstacle.c_y = 0.0;
    	obstacle.c_z = 0.0;
    	obstacle.x = 0.0;
    	obstacle.y = 0.0;
    	obstacle.z = 0.0;
		obstacles.push_back(obstacle);
		std::cout << "[IMPORTANT] ADBSCAN is not executed, since number of points is zero after subsampling and filtering. Please try reducing subsampling_ratio parameter or increasing the absolute value of x_filter_back, y_filter_left or y_filter_right parameters to ensure nonzero number of points after subsampling and filtering" << std::endl; 
	}
	/* Free memory */
	// if (velo_n) free(velo_n); //jcao7
	if (xyz_n) free(xyz_n);
	if (p_k) free(p_k);
	if (p_k_floor) free(p_k_floor);
	if (p_esp) free(p_esp);
	if (p_esp_cont) free(p_esp_cont);
	if (p_class) free(p_class);
	if (p_type) free(p_type);
		
	return obstacles;
}


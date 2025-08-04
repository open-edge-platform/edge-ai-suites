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

using namespace std;

/*---------------------------------------------------------------------------------------*
 * \brief This function loads ADBSCan configuration parameters from a file
 *---------------------------------------------------------------------------------------*/

float distance(Point_xyz pt1, Point_xyz pt2)
{ 
    float dist;
    dist = sqrt((pt2.x-pt1.x)*(pt2.x-pt1.x) + (pt2.y-pt1.y)*(pt2.y-pt1.y) + (pt2.z-pt1.z)*(pt2.z-pt1.z));
    return dist;
}

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
		//cout << "d=" << in << "  out value: " << out ;
		p_k[i] = (out < 1.0) ? 1.0 : out;
	    //cout << "  -- p_k[" << i << "]:" << p_k[i] << ";  ";  //debug
		p_k_floor[i] = floor(p_k[i]);
		
		/* Matlab: Eps_array_cont=((prod(max(x)-min(x))*(k_array)*gamma(.5*n+1))/(m*sqrt(pi.^n))).^(1/n); */
		p_esp_cont[i] = pow(((prod * p_k[i] * gamma_val) / denominator), (1 / n));
		
		/* Matlab: Eps_array=((prod(max(x)-min(x))*k_array_floor*gamma(.5*n+1))/(m*sqrt(pi.^n))).^(1/n); */
		p_esp[i] = pow(((prod * p_k_floor[i] * gamma_val) / denominator), (1 / n));

        string Lidar_type = CONFIG_PARAMS.Lidar_type;
        if ( Lidar_type == "2D" || Lidar_type == "RS")
		{
		  //p_esp[i] *= 0.7; //changed from 0.7 to 0.07 for 2D lidar; debug, change from 0.07 to 0.7; then change to 1
		  p_esp[i] *= CONFIG_PARAMS.scale_factor;
		
	      if (p_esp[i] <=0)
			p_esp[i] = 0.02 * (max_x - min_x);

		  //p_esp[i] = 0.15; //debug; this works
		  
		}
		else //3D lidar
		{
	      p_esp[i] *= 0.7;
		  if (p_esp[i] < 0.9)
			p_esp[i] = 0.9;
		}
		//cout << "p_esp[" << i << "] = " <<  p_esp[i] << endl;

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

Point_xyz doDBSCAN(void *p_Data, int LiDAR_data_size, int dimension, Point_xyz target_loc, \
                   int& nbr_frame_blocked, vector<Obstacle>& obstacle_list)
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
	vector<Point> points_in_frame;
	vector<Obstacle> obstacles;
	Point_xyz new_target_loc;
	
	/*
	 * Parse command line parameters
	 */
    result = load_config_params(adbscan_params);

	/* Adaptive parmeters */
	result = load_adaptive_params(adaptive_params);

	/* Number of iterations */
	num_iter = 1;
	/*
	 * Load LiDAR data points
	 */
	if (true)   //if (result == ADBSCAN_SUCCESS)
	{
		LiDAR_data_4D_t *velo_n = (LiDAR_data_4D_t*) p_Data;
		LiDAR_data_3D_t *xyz_n;
		INT32_t num_points = LiDAR_data_size / sizeof(LiDAR_data_4D_t);

		if (dimension == 3)
		{

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
		}
		else if (dimension == 4)  //RealSense data
		{
			/* Subsample the RealSense data */
		    num_points = subsample_LiDAR_data(velo_n, num_points, adbscan_params.subsample_ratio);

           
			/* Z filter the RealSense data to remove ground */
			if (adbscan_params.Z_based_ground_removal)
			{
				num_points = filter_LiDAR_data(velo_n, num_points, Z_INDEX, FILTER_OP_LESS_THAN, adbscan_params.z_filter);
			}

			/* X filter the LiDAR data */
			//num_points = filter_LiDAR_data(velo_n, num_points, X_INDEX, FILTER_OP_LESS_THAN, 0.5);
			num_points = filter_LiDAR_data(velo_n, num_points, X_INDEX, FILTER_OP_GREATER_THAN, adbscan_params.x_filter_back);

		    /* Y filter the LiDAR data */
			num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_LESS_THAN, adbscan_params.y_filter_right);
			num_points = filter_LiDAR_data(velo_n, num_points, Y_INDEX, FILTER_OP_GREATER_THAN, adbscan_params.y_filter_left);
		    
		}
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

			//jcao 06-22-22 
			/*
			FILE *p_outFile = fopen("output_RS_raw.txt", "w");
			for (int i = 0; i < num_points; i++)
			{   
                // output to a vector of points
			    if (p_outFile)
			        fprintf(p_outFile, "%d %f %f %f \n", i + 1, xyz_n[i].val[0], xyz_n[i].val[1], xyz_n[i].val[2]);
			
			}
			if (p_outFile)  fclose(p_outFile);
			*/
			//exit(0);
			
			/* Calculate the k and esp arrays */
			result = adaptive_parameters(xyz_n, p_k, p_k_floor, p_esp, p_esp_cont, &adaptive_params, num_points);
			
			cout << "num_points: " << num_points << endl;
			if (num_points > MAX_POINTS)
			{
				result = ADBSCAN_MAX_NUM_OF_POINT_EXCEEDED;
				cout << "ERROR!: ADBScan: Max number of points exeeded. Can not continue." << endl;
			}
			
			/* Execute the Adaptive DbScan algorithm */
			if (result == ADBSCAN_SUCCESS)
			{
				bool use_cpu = true;
				if (use_cpu) //for CPU
				{
					timespec t1, t2;
					double total = 0.0;
					double avr = 0.0;
					for (int i = 0; i < num_iter; i++)
					{
						clock_gettime(clk_id, &t1); /* CLOCK_PROCESS_CPUTIME_ID */
					
						dbscan_adaptiveK(xyz_n, p_k_floor, p_esp, p_class, p_type, num_points);
					
						clock_gettime(clk_id, &t2);		
						cout << i << ". test CPU: ADBScan execution time: "  << diff(t1, t2) << " [s]" << endl;
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
					// FILE *p_outFile = fopen("output_CPU.txt", "w");
					for (int i = 0; i < num_points; i++)
					{   
                    // output to a vector of points
					    // if (p_outFile)
				            //fprintf(p_outFile, "%d %f %f %f %d %d \n", i + 1, xyz_n[i].val[0], xyz_n[i].val[1], xyz_n[i].val[2], p_class[i], p_type[i]);
			
                        points_in_frame.push_back(Point(xyz_n[i].val[0], xyz_n[i].val[1], xyz_n[i].val[2], p_class[i]));
					}
					// if (p_outFile)  fclose(p_outFile);
				}
			}
		}

		//if frame is not empty, regroup into clusters
		new_target_loc.x = -1.0; //set it negative to mark no new target found
		new_target_loc.y = 0;
		new_target_loc.z = 0;

		bool target_found = false;
		if (points_in_frame.size() > 0)
		{
			vector<Cluster> clusters = get_clusters(points_in_frame);
    		cout << "number of clusters: " << clusters.size() << endl;

			//get obstacle list for RVIZ2 visualization
    		for (long unsigned int i = 0; i<clusters.size(); i++)
    		{
        		//cout << i << ": " << clusters[i].cluster_id << " "<< clusters[i].size <<endl;
        		//clusters[i].print_list();
        		cout << i << ": " << "centroid: " << clusters[i].get_centroid().x << " " <<  clusters[i].get_centroid().y 
           			<< " " << clusters[i].get_centroid().z << endl;
           
		        Obstacle obstacle = get_obstacle(clusters[i].point_list);
				//cout << obstacle.c_x <<", " << obstacle.c_y <<", " << obstacle.c_z << endl;
				//cout << obstacle.x <<", "<<obstacle.y<<", " << obstacle.z << endl;
				obstacles.push_back(obstacle);
    		}

			//get new target location given prevous target_loc:
			int cluster_size = clusters.size();
			//go through each cluster to find one closest to previous target_loc within 0.2 m
			for (int i = 0; i< cluster_size; i++)
			{
				//convert centroid from Point class to Point_xyz struct
				Point_xyz cluster_centroid;
				Point cluster_centroid_org = clusters[i].get_centroid();
				cluster_centroid.x = cluster_centroid_org.x;
				cluster_centroid.y = cluster_centroid_org.y;
				cluster_centroid.z = cluster_centroid_org.z;
				float dist= distance(target_loc, cluster_centroid);
				
				if (dist < CONFIG_PARAMS.tracking_radius)
				{
				  new_target_loc = cluster_centroid;
				  target_found = true;
				}	 
				cout << "cluster " << i << " distance: " << dist << std::endl; 
				cout << i << ": new_target_loc x,y,z: " << new_target_loc.x <<","<< new_target_loc.y <<"," << new_target_loc.z << endl;
				cout << i << ": target_found= " << target_found << std::endl;
			}
		}
		cout << "Before: nbr_frame_blocked = " << nbr_frame_blocked << std::endl;
		if (target_found) //reset num_blocked_frame to 5
          nbr_frame_blocked = CONFIG_PARAMS.max_frame_blocked;
        //if blocked less than 5 frames, send back original; 
		else if (nbr_frame_blocked > 0 ) //target not found
		{
           new_target_loc.x = target_loc.x;
		   new_target_loc.y = target_loc.y;
		   new_target_loc.z = target_loc.z;
		   nbr_frame_blocked --;
		}
		cout << "After: nbr_frame_blocked = " << nbr_frame_blocked << std::endl;
		//else nbr_frame_blocked == 0, send (-1.0, 0, 0)
		
		cout << "target_loc x,y,z: " << target_loc.x <<","<< target_loc.y <<"," << target_loc.z << endl;
		cout << "new_target_loc x,y,z: " << new_target_loc.x <<","<< new_target_loc.y <<"," << new_target_loc.z << endl;
		
		/* Free memory */
		if (velo_n) free(velo_n); //jcao7
		if (xyz_n) free(xyz_n);
		if (p_k) free(p_k);
		if (p_k_floor) free(p_k_floor);
		if (p_esp) free(p_esp);
		if (p_esp_cont) free(p_esp_cont);
		if (p_class) free(p_class);
		if (p_type) free(p_type);
	}

    obstacle_list = obstacles;	

	return new_target_loc;
}


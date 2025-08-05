// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "Util.hpp"

using namespace std;

Point calc_centroid(vector<Point> point_list)
{
    double total_x = 0;
    double total_y = 0;
    double total_z = 0;

    int num_pt = point_list.size();
    for (int i = 0; i< num_pt; i++ )
    {
        total_x += point_list[i].x;
        total_y += point_list[i].y;
        total_z += point_list[i].z;
    }

    return Point(total_x/(double)num_pt,total_y/(double)num_pt,total_z/(double)num_pt);
}


//given a vector of point(x,y,z, cluster_id), return a vector of clusters
vector<Cluster> get_clusters(vector<Point> points_in_frame)  //input is a vector of points (x,y,z).
{  
    vector<Cluster> clusters; //emplty cluster, to be filled
    for (unsigned i=0; i<points_in_frame.size(); i++) //for each input point
    {
        Point cur_point(points_in_frame[i].x, points_in_frame[i].y, points_in_frame[i].z, points_in_frame[i].cluster_id );
        int cluster_id = cur_point.cluster_id;
        //cout << "cur_point.cluster_id: " << cluster_id << endl;
        if ( cluster_id > 0) //valid cluster 
        {
            if ( clusters.size() == 0) //empty cluster list, first cluster in the frame
            {
                Cluster cur_cluster; //create first cluster in the frame
                cur_cluster.cluster_id = cluster_id;
                cur_cluster.add_point(cur_point);

                clusters.push_back(cur_cluster);
            }
            else //traverse the point_list to find same cluster number; if cluster found, append point to it 
            {
                bool cluster_nbr_found = false;
                for (unsigned j = 0; j < clusters.size(); j++ ) //for each cluster
                {
                    if (clusters[j].cluster_id == cluster_id) //cluster found
                    {
                        clusters[j].add_point(cur_point);
                        cluster_nbr_found = true;
                    }
                }
                if (cluster_nbr_found == false)
                {
                    Cluster cur_cluster; //create new cluster
                    cur_cluster.cluster_id = cluster_id;
                    cur_cluster.add_point(cur_point);

                    clusters.push_back(cur_cluster);
                }
            }
        }
    }
    return clusters;
}

vector<double> get_val_vec(string line, string delimiter)
{
    vector<double> vec1;
    // int pos = 0;
    std::string::size_type pos = 0;
    string token;
    while ((pos = line.find(delimiter)) != string::npos)
    {
        token = line.substr(0, pos);
        vec1.push_back(stod(token));
        line.erase(0, pos + delimiter.length());
    }
    //vec1.push_back(stod(token));

    return vec1;
}

//given a cluster of points, return bounding box
vector<Point> get_boundingbox(vector<Point> point_list)
{
    const double MAX_RANGE = 10000.0;
   //get min and max of each dimension
    double min_x =MAX_RANGE, max_x=-MAX_RANGE;
    double min_y=MAX_RANGE, max_y=-MAX_RANGE;
    double min_z=MAX_RANGE, max_z=-MAX_RANGE;

    int point_list_size = point_list.size();
    for (int i=0; i<point_list_size; i++)
    {
        if (point_list[i].x < min_x)
            min_x = point_list[i].x;
        if (point_list[i].y < min_y)
            min_y = point_list[i].y;
        if (point_list[i].z < min_z)
            min_z = point_list[i].z;

        if (point_list[i].x > max_x)
            max_x = point_list[i].x;
        if (point_list[i].y > max_y)
            max_y = point_list[i].y;
        if (point_list[i].z > max_z)
            max_z = point_list[i].z;
   }

   vector<Point> BB_pts; //bounding box corner points
   BB_pts.push_back(Point(min_x,max_y,min_z));
   BB_pts.push_back(Point(max_x,max_y,min_z));
   BB_pts.push_back(Point(max_x,min_y,min_z));
   BB_pts.push_back(Point(min_x,min_y,min_z));
   BB_pts.push_back(Point(min_x,max_y,max_z));
   BB_pts.push_back(Point(max_x,max_y,max_z));
   BB_pts.push_back(Point(max_x,min_y,max_z));
   BB_pts.push_back(Point(min_x,min_y,max_z));

   return BB_pts; 

}

//given a point cloud cluster, return an obstacle object
Obstacle get_obstacle(vector<Point> point_list)
{
    const double MAX_RANGE = 10000.0;
   //get min and max of each dimension
    double min_x =MAX_RANGE, max_x=-MAX_RANGE;
    double min_y=MAX_RANGE, max_y=-MAX_RANGE;
    double min_z=MAX_RANGE, max_z=-MAX_RANGE;

    int point_list_size = point_list.size();
    for (int i=0; i<point_list_size; i++)
    {
        if (point_list[i].x < min_x)
            min_x = point_list[i].x;
        if (point_list[i].y < min_y)
            min_y = point_list[i].y;
        if (point_list[i].z < min_z)
            min_z = point_list[i].z;

        if (point_list[i].x > max_x)
            max_x = point_list[i].x;
        if (point_list[i].y > max_y)
            max_y = point_list[i].y;
        if (point_list[i].z > max_z)
            max_z = point_list[i].z;
   }

    double width = max_x - min_x;
    double length = max_y - min_y;
    double height = max_z - min_z;

    double c_x = min_x + width/2.0;
    double c_y = min_y + length/2.0;
    double c_z = min_z + height/2.0;

    Obstacle obstacle;
    obstacle.c_x = c_x;
    obstacle.c_y = c_y;
    obstacle.c_z = c_z;
    obstacle.x = width;
    obstacle.y = length;
    obstacle.z = height;

    return obstacle; 

}

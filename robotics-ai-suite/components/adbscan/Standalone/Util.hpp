// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <iostream>
#include <fstream>
#include <string>
#include <vector>

using namespace std;

class Point
{ 
  public:
    double x, y, z;
    int cluster_id;

    Point(double x, double y, double z, int cluster_id)
    {
      this->x = x;
      this->y = y;
      this->z = z;
      this->cluster_id = cluster_id;
    }
    Point(double x, double y, double z)
    {
      this->x = x;
      this->y = y;
      this->z = z;
      this->cluster_id = 0;
    }
};

Point calc_centroid(vector<Point> point_list);

//Cluster class to represent a point cloud as a vector of point
class Cluster
{
  public:
    vector<Point> point_list;

    int size;
    int cluster_id;

    Cluster()
    {}
    void add_point(Point pt)
    {
        point_list.push_back(pt);
        this->size = point_list.size();
    }

    void print_list()
    {
        for (int i=0; i<point_list.size(); i++)
            std::cout << point_list[i].x <<" " << point_list[i].y << " " <<point_list[i].z <<" " <<point_list[i].cluster_id<< endl;
    }

    Point get_centroid()
    { 
        Point pt(calc_centroid(this->point_list));
        return (pt);
    }

};

//given a vector of point(x,y,z, cluster_id), return a vector of clusters
vector<Cluster> get_clusters(vector<Point> points_in_frame); //parameter is a vector of points

vector<double> get_val_vec(string line, string delimiter);

//given a list of points, return bounding box
vector<Point> get_boundingbox(vector<Point> point_list);

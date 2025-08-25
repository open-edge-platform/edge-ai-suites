// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include "Util.hpp"

using namespace std;

int main(int argc, char *argv[])
{
    vector<Point> points_in_frame;

    string delimiter = " ";

    ifstream in_file("input.txt");
    //ifstream in_file(argv[1]);
    string str;

    string line;
    vector<double> vec1;

    int counter=0;
    while (getline(in_file, line))
    {
        //cout << line << endl;
        vector<double> vec1 = get_val_vec(line, delimiter);
        //cout <<"num: " << vec1.size() << endl;
        points_in_frame.push_back(Point(vec1[1], vec1[2], vec1[3], (int)vec1[4]));
        //cout << vec1[1] << " " << vec1[2] <<" "<< vec1[3] << " " << (int)vec1[4] << endl;
        counter ++;
    }
    cout <<"number of points: " << points_in_frame.size() << endl;
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
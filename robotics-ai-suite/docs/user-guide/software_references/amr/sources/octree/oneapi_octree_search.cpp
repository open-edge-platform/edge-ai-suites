// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <iostream>
#include <fstream>
#include <numeric>
#include <pcl/oneapi/octree/octree.hpp>
#include <pcl/oneapi/containers/device_array.h>
#include <pcl/point_cloud.h>

using namespace pcl::oneapi;

float dist(Octree::PointType p, Octree::PointType q) {
    return std::sqrt((p.x-q.x)*(p.x-q.x) + (p.y-q.y)*(p.y-q.y) + (p.z-q.z)*(p.z-q.z));
}

int main (int argc, char** argv)
{
    std::cout << "Running on device: " << dpct::get_default_queue().get_device().get_info<sycl::info::device::name>() << "\n";

    std::size_t data_size = 871000;
    std::size_t query_size = 10000;
    float cube_size = 1024.f;
    float max_radius    = cube_size / 30.f;
    float shared_radius = cube_size / 30.f;
    const int max_answers = 5;
    const int k = 5;
    std::size_t i;
    std::vector<Octree::PointType> points;
    std::vector<Octree::PointType> queries;
    std::vector<float> radiuses;
    std::vector<int> indices;

    //Generate point cloud data, queries, radiuses, indices
    srand (0);
    points.resize(data_size);
    for(i = 0; i < data_size; ++i)
    {
        points[i].x = ((float)rand())/(float)RAND_MAX * cube_size;
        points[i].y = ((float)rand())/(float)RAND_MAX * cube_size;
        points[i].z = ((float)rand())/(float)RAND_MAX * cube_size;
    }

    queries.resize(query_size);
    radiuses.resize(query_size);
    for (i = 0; i < query_size; ++i)
    {
        queries[i].x = ((float)rand())/(float)RAND_MAX * cube_size;
        queries[i].y = ((float)rand())/(float)RAND_MAX * cube_size;
        queries[i].z = ((float)rand())/(float)RAND_MAX * cube_size;
        radiuses[i]  = ((float)rand())/(float)RAND_MAX * max_radius;
    };

    indices.resize(query_size / 2);
    for(i = 0; i < query_size / 2; ++i)
    {
        indices[i] = i * 2;
    }

    //Prepare oneAPI cloud
    pcl::oneapi::Octree::PointCloud cloud_device;
    cloud_device.upload(points);

    //oneAPI build 
    pcl::oneapi::Octree octree_device;
    octree_device.setCloud(cloud_device);
    octree_device.build();

    //Upload queries and radiuses
    pcl::oneapi::Octree::Queries queries_device;
    pcl::oneapi::Octree::Radiuses radiuses_device;
    queries_device.upload(queries);
    radiuses_device.upload(radiuses);

    //Prepare output buffers on device
    pcl::oneapi::NeighborIndices result_device1(queries_device.size(), max_answers);
    pcl::oneapi::NeighborIndices result_device2(queries_device.size(), max_answers);
    pcl::oneapi::NeighborIndices result_device3(indices.size(), max_answers);
    pcl::oneapi::NeighborIndices result_device_ann(queries_device.size(), 1);
    pcl::oneapi::Octree::ResultSqrDists dists_device_ann;
    pcl::oneapi::NeighborIndices result_device_knn(queries_device.size(), k);
    pcl::oneapi::Octree::ResultSqrDists dists_device_knn;

    //oneAPI octree radius search with shared radius
    octree_device.radiusSearch(queries_device, shared_radius, max_answers, result_device1);

    //oneAPI octree radius search with individual radius
    octree_device.radiusSearch(queries_device, radiuses_device, max_answers, result_device2);

    //oneAPI octree radius search with shared radius using indices to specify 
    //the queries.
    pcl::oneapi::Octree::Indices cloud_indices;
    cloud_indices.upload(indices);
    octree_device.radiusSearch(queries_device, cloud_indices, shared_radius, max_answers, result_device3);

    //oneAPI octree ANN search
    //if neighbor points distances results are not required, can just call
    //octree_device.approxNearestSearch(queries_device, result_device_ann)
    octree_device.approxNearestSearch(queries_device, result_device_ann, dists_device_ann);

    //oneAPI octree KNN search
    //if neighbor points distances results are not required, can just call
    //octree_device.nearestKSearchBatch(queries_device, k, result_device_knn)
    octree_device.nearestKSearchBatch(queries_device, k, result_device_knn, dists_device_knn);

    //Download results
    std::vector<int> sizes1;
    std::vector<int> sizes2;
    std::vector<int> sizes3;
    result_device1.sizes.download(sizes1);
    result_device2.sizes.download(sizes2);
    result_device3.sizes.download(sizes3);

    std::vector<int> downloaded_buffer1, downloaded_buffer2, downloaded_buffer3, results_batch;
    result_device1.data.download(downloaded_buffer1);
    result_device2.data.download(downloaded_buffer2);
    result_device3.data.download(downloaded_buffer3);

    int query_idx = 2;
    std::cout << "Neighbors within shared radius search at ("
              << queries[query_idx].x << " "
              << queries[query_idx].y << " "
              << queries[query_idx].z << ") with radius=" << shared_radius << std::endl;
    for (i = 0; i < sizes1[query_idx]; ++i)
    {
        std::cout << "    "  << points[downloaded_buffer1[max_answers * query_idx + i]].x
                  << " "     << points[downloaded_buffer1[max_answers * query_idx + i]].y
                  << " "     << points[downloaded_buffer1[max_answers * query_idx + i]].z
                  << " (distance: " << dist(points[downloaded_buffer1[max_answers * query_idx + i]], queries[query_idx])  << ")" << std::endl;
    }

    std::cout << "Neighbors within individual radius search at ("
              << queries[query_idx].x << " "
              << queries[query_idx].y << " "
              << queries[query_idx].z << ") with radius=" << radiuses[query_idx] << std::endl;
    for (i = 0; i < sizes2[query_idx]; ++i)
    {
        std::cout << "    "  << points[downloaded_buffer2[max_answers * query_idx + i]].x
                  << " "     << points[downloaded_buffer2[max_answers * query_idx + i]].y
                  << " "     << points[downloaded_buffer2[max_answers * query_idx + i]].z
                  << " (distance: " << dist(points[downloaded_buffer2[max_answers * query_idx + i]], queries[query_idx])  << ")" << std::endl;
    }

    std::cout << "Neighbors within indices radius search at ("
              << queries[query_idx].x << " "
              << queries[query_idx].y << " "
              << queries[query_idx].z << ") with radius=" << shared_radius << std::endl;
    for (i = 0; i < sizes3[query_idx/2]; ++i)
    {
        std::cout << "    "  << points[downloaded_buffer3[max_answers * query_idx / 2 + i]].x
                  << " "     << points[downloaded_buffer3[max_answers * query_idx / 2 + i]].y
                  << " "     << points[downloaded_buffer3[max_answers * query_idx / 2 + i]].z
                  << " (distance: " << dist(points[downloaded_buffer3[max_answers * query_idx / 2 + i]], queries[2])  << ")" << std::endl;
    }

    std::cout << "Approximate nearest neighbor at ("
              << queries[query_idx].x << " "
              << queries[query_idx].y << " "
              << queries[query_idx].z << ")" << std::endl;
    std::cout << "    "  << points[result_device_ann.data[query_idx]].x
              << " "     << points[result_device_ann.data[query_idx]].y
              << " "     << points[result_device_ann.data[query_idx]].z
              << " (distance: " << std::sqrt(dists_device_ann[query_idx])  << ")" << std::endl;

    std::cout << "K-nearest neighbors (k = " << k << ") at ("
              << queries[query_idx].x << " "
              << queries[query_idx].y << " "
              << queries[query_idx].z << ")" << std::endl;
    for (i = query_idx * k; i < (query_idx + 1) * k; ++i)
    {
        std::cout << "    "  << points[result_device_knn.data[i]].x
                  << " "     << points[result_device_knn.data[i]].y
                  << " "     << points[result_device_knn.data[i]].z
                  << " (distance: " << std::sqrt(dists_device_knn[i])  << ")" << std::endl;
    }
}

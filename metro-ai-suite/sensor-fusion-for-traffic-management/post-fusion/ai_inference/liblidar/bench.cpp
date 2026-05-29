#include <string>
#include <unistd.h>
#include <cstring>
#include <fstream>
#include <iostream>
#include <istream>
#include <sstream>
#include <cstdlib>
#include <chrono>
#include "src/liblidar.hpp"
/**
 * Read in a LiDAR point cloud from a file in Point Cloud Data format (as ascii)
 * https://pointclouds.org/documentation/tutorials/pcd_file_format.html
 *
 * @param[in] file_name is the name of the PCD file
 * @param[in] points are the parsed points from the PCD as x,y,z,intensity values
 * @return number of of points in the point cloud
 */
std::size_t ReadPointCloud(std::string const &file_name, std::vector<float> &points)
{
    if (file_name.empty() || access(file_name.c_str(), F_OK) != 0)
        return 0;
    std::size_t number_of_points = 0;
    std::ifstream in(file_name);
    std::string line;
    bool parse_data = false;
    while (std::getline(in, line) && points.size() <= 4 * number_of_points) {
        if (parse_data) {
            std::istringstream iss(line);
            float x, y, z, intensity;
            double timestamp;
            if (!(iss >> x >> y >> z >> intensity >> timestamp)) {
                return 0;
            }
            points.push_back(x);
            points.push_back(y);
            points.push_back(z);
            points.push_back(intensity);
        }
        else if (line.find("POINTS") != std::string::npos) {
            number_of_points = atoll(line.substr(7).c_str());
        }
        else if (line.find("DATA") != std::string::npos) {
            parse_data = true;
        }
    }
    return number_of_points;
}

void saveDetectionsToCSV(const std::vector<pointpillars::ObjectDetection> &detections,
                         const pointpillars::PointPillarsConfig &config,
                         const std::string &filename)
{
    std::ofstream file(filename);
    file << "pos_x,pos_y,pos_z,Length,Width,Height,rot_y,pred_scores,pred_labels\n";
    for (size_t i = 0; i < detections.size(); ++i) {
        const auto &detection = detections[i];
        file << detection.x << "," << detection.y << "," << detection.z << "," << detection.length << "," << detection.width << "," << detection.height << ","
             << detection.yaw << "," << detection.likelihood << "," << config.classes[detection.class_id] << "\n";
    }
    file.close();
}
int main(int argc, char *argv[])
{
    size_t devIdx = 0, loop = 1;
    int c;
    std::string device = "CPU";
    char *cval = NULL;
    while (-1 != (c = getopt(argc, argv, "cgi:l:"))) {  //-c: cpu, -g: gpu, -i idx, l: loop
        switch (c) {
            case 'c': device = "CPU"; break;
            case 'g': device = "GPU"; break;
            case 'i':
                if (NULL != optarg)
                    devIdx = atol(optarg);
                break;
            case 'l':
                if (NULL != optarg)
                    loop = atol(optarg);
                break;
        }
    }

    device += "." + std::to_string(devIdx);
    std::cout << "Device: " << device << ", Loop: " << loop << std::endl;

    pointpillars::PointPillarsConfig config;
    std::vector<pointpillars::ObjectDetection> object_detections;
    std::size_t number_of_points;
    std::vector<float> points;
    number_of_points = ReadPointCloud("data/kitti/pcd/000004.pcd", points);
    std::cout << "number_of_points: " << number_of_points << std::endl;
    if ((number_of_points == 0) || points.empty()) {
        std::cout << "Unable to read point cloud file. Please put the point cloud file into the data/ folder." << std::endl;
        return -1;
    }
#if 1  // fp16 model
    config.pfe_model_file = "data/pfe.onnx";
    config.rpn_model_file = "data/rpn.onnx";
#else  // int8 model
    config.pfe_model_file = "data/pfe.xml";
    config.rpn_model_file = "data/rpn.xml";
#endif
    const char *str[6] = {"Preprocess", "AnchorMask", "PFE", "Scatter", "RPN", "Postprocess"};
    size_t dur[6];

    pointpillars::PointPillars point_pillars(0.5f, 0.5f, config, device);
    std::cout << "point_pillars created" << std::endl;
    memset(dur, 0, sizeof(size_t) * 6);
    const auto start_time = std::chrono::high_resolution_clock::now();
    std::cout << "points size: " << points.size() << std::endl;
    std::cout << "number_of_points: " << number_of_points << std::endl;
    try {
        for (size_t i = 0; i < loop; ++i) {
            point_pillars.Detect(points.data(), number_of_points, object_detections, dur);
        }
    }
    catch (const std::runtime_error &e) {
        std::cout << "Exception during PointPillars execution\n";
        std::cout << e.what() << std::endl;
        return -1;
    }
    const auto end_time = std::chrono::high_resolution_clock::now();
    std::cout << "Execution time: " << std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count() / (float)loop << "ms\n";
    for (size_t i = 0; i < 6; ++i) {
        fprintf(stdout, "\t%s: %f ms\n", str[i], dur[i] / (float)loop);
    }
    std::cout << object_detections.size() << " cars detected\n";
    for (auto const &detection : object_detections) {
        std::cout << config.classes[detection.class_id] << ": Probability = " << detection.class_probabilities[0] << " Position = (" << detection.x << ", "
                  << detection.y << ", " << detection.z << ") Length = " << detection.length << " Width = " << detection.width << "\n";
    }
    // saveDetectionsToCSV ( object_detections, config, "detections.csv" );
    std::cout << "\n\n";

    return 0;
}

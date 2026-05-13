#include <boost/filesystem.hpp>
#include <boost/program_options.hpp>
#include <boost/range/iterator_range.hpp>
#include <chrono>
#include <fstream>
#include <iostream>
#include <cstdlib>
#include <filesystem>
#include "src/liblidar.hpp"
#include <vector>
#include <sstream>
#include <string>
#include <map>
#include <Eigen/Dense>
#include <opencv2/opencv.hpp>
struct DataRow
{
    std::vector<float> values;
    std::string label;
};
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
    if (!boost::filesystem::exists(file_name) || file_name.empty()) {
        return 0;
    }

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
int getFolderFile(const std::string &path, std::vector<std::string> &files, const std::string &suffix = ".pcd")
{
    try {
        for (const auto &entry : std::filesystem::directory_iterator(path)) {
            if (entry.is_regular_file()) {
                std::string file = entry.path().filename().string();

                if (file.size() >= suffix.size() && file.compare(file.size() - suffix.size(), suffix.size(), suffix) == 0) {
                    files.push_back(file.substr(0, file.length() - suffix.size()));
                }
            }
        }
    }
    catch (const std::filesystem::filesystem_error &e) {
        std::cerr << "Error accessing folder: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    return EXIT_SUCCESS;
}
struct CalibrationData
{
    std::map<std::string, Eigen::MatrixXd> matrices;
};
CalibrationData readCalib(const std::string &filename)
{
    CalibrationData calibData;
    std::ifstream file(filename);
    std::string line;

    while (std::getline(file, line)) {
        std::stringstream lineStream(line);
        std::string key;
        std::getline(lineStream, key, ':');
        std::string values;
        std::getline(lineStream, values);
        std::stringstream valuesStream(values);
        std::vector<double> valuesVec;
        std::string value;

        while (std::getline(valuesStream, value, ' ')) {
            if (!value.empty()) {
                valuesVec.push_back(std::stod(value));
            }
        }

        Eigen::MatrixXd matrix;

        if (key.find("P") != std::string::npos) {
            matrix.resize(3, 4);
        }
        else if (key.find("R0_rect") != std::string::npos) {
            matrix.resize(3, 3);
        }
        else if (key.find("Tr") != std::string::npos) {
            matrix.resize(3, 4);
        }

        if (valuesVec.size() != matrix.size()) {
            std::cerr << "Error: Mismatch in the number of elements for " << key << std::endl;
            continue;
        }

        int index = 0;

        for (int i = 0; i < matrix.rows(); ++i) {
            for (int j = 0; j < matrix.cols(); ++j) {
                matrix(i, j) = valuesVec[index++];
            }
        }

        calibData.matrices[key] = matrix;
    }

    return calibData;
}
int main(int argc, char *argv[])
{
    pointpillars::PointPillarsConfig config;
    boost::program_options::options_description desc("Allowed options");
    boost::filesystem::path datasetPath;
    std::string device;

    desc.add_options()("help", "produce help message")("pfe_model", boost::program_options::value<std::string>(&(config.pfe_model_file)),
                                                       "PFE model file path (.onnx, .xml)")(
        "rpn_model", boost::program_options::value<std::string>(&(config.rpn_model_file)),
        "RPN model file path (.onnx, .xml)")("data", boost::program_options::value<boost::filesystem::path>(&datasetPath), "data path")(
        "device", boost::program_options::value<std::string>(&device)->default_value("CPU"), "execution device (CPU, GPU.0)");
    boost::program_options::variables_map vm;
    boost::program_options::store(boost::program_options::parse_command_line(argc, argv, desc), vm);
    boost::program_options::notify(vm);
    const char *backend = std::getenv("SYCL_BE");

    if (backend == nullptr) {
        setenv("SYCL_BE", "PI_OPENCL", 1);
        std::cout << "Environment variable SYCL_BE was not set. Defaulting to PI_OPENCL." << std::endl;
    }
    else {
        std::cout << "Environment variable SYCL_BE is set to: " << backend << std::endl;
    }

    if (vm.count("help")) {
        std::cout << desc << std::endl;
        return 1;
    }

    std::vector<pointpillars::ObjectDetection> object_detections;
    std::size_t number_of_points;
    std::vector<float> points;
    std::vector<std::string> files;

    const boost::filesystem::path pcdDir = datasetPath / "pcd";
    const boost::filesystem::path calibDir = datasetPath / "calib";
    const boost::filesystem::path imgDir = datasetPath / "image";
    const boost::filesystem::path binDir = datasetPath / "bin";
    getFolderFile(pcdDir.string(), files);  // read pcd files
    std::sort(files.begin(), files.end());
    auto rotatePointsAroundCenter = [](const Eigen::Vector3d &point, const Eigen::Vector3d &center, double yaw_angle) {
        double cos_yaw = std::cos(yaw_angle);
        double sin_yaw = std::sin(yaw_angle);
        Eigen::Matrix3d R_yaw;
        R_yaw << cos_yaw, -sin_yaw, 0, sin_yaw, cos_yaw, 0, 0, 0, 1;
        Eigen::Vector3d points_centered = point - center;
        Eigen::Vector3d rotated_points_centered = R_yaw * points_centered;
        Eigen::Vector3d rotated_points = rotated_points_centered + center;
        return rotated_points;
    };

    for (const auto &file : files) {
        boost::filesystem::path dataFile = pcdDir / (file + ".pcd");
        boost::filesystem::path calibFile = calibDir / (file + ".txt");
        boost::filesystem::path imgFile = imgDir / (file + ".png");
        CalibrationData calib = readCalib(calibFile.string());
        cv::Mat image = cv::imread(imgFile.string());
        Eigen::MatrixXd P2 = calib.matrices["P2"];
        Eigen::MatrixXd Tr = calib.matrices["Tr_velo_to_cam"];
        Eigen::MatrixXd R0 = calib.matrices["R0_rect"];
        points.clear();
        number_of_points = ReadPointCloud(dataFile.string(), points);
        std::cout << "number_of_points: " << number_of_points << std::endl;

        if ((number_of_points == 0) || points.empty()) {
            std::cout << "Unable to read point cloud file. Please put the point cloud file into the data/ folder." << std::endl;
            return -1;
        }


        pointpillars::PointPillars point_pillars(0.5f, 0.5f, config, device);
        const auto start_time = std::chrono::high_resolution_clock::now();

        try {
            point_pillars.Detect(points.data(), number_of_points, object_detections, NULL);
        }
        catch (const std::runtime_error &e) {
            std::cout << "Exception during PointPillars execution\n";
            std::cout << e.what() << std::endl;
            return -1;
        }

        const auto end_time = std::chrono::high_resolution_clock::now();
        std::cout << "Execution time: " << std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count() << "ms\n\n";
        std::cout << object_detections.size() << " cars detected\n";

        for (auto const &detection : object_detections) {
            float x = detection.x;
            float y = detection.y;
            float z = detection.z;
            z = z - 1;
            float l = detection.length;
            float w = detection.width;
            float h = detection.height;
            float rot_y = detection.yaw;
            std::vector<Eigen::Vector3d> bbox_corners = {
                {x - l / 2, y - w / 2, z - h / 2}, {x + l / 2, y - w / 2, z - h / 2}, {x + l / 2, y - w / 2, z + h / 2}, {x - l / 2, y - w / 2, z + h / 2},
                {x - l / 2, y + w / 2, z - h / 2}, {x + l / 2, y + w / 2, z - h / 2}, {x + l / 2, y + w / 2, z + h / 2}, {x - l / 2, y + w / 2, z + h / 2}};
            std::vector<Eigen::Vector3d> points;

            for (const auto &corner : bbox_corners) {
                points.push_back(rotatePointsAroundCenter(corner, {x, y, z}, rot_y));
            }

            std::vector<cv::Point> vertices;
            Eigen::MatrixXd R0_rect_4x4(4, 4);
            R0_rect_4x4 << R0, Eigen::Vector3d::Zero(), 0, 0, 0, 1;
            Eigen::MatrixXd Tr_4x4(4, 4);
            Tr_4x4 << Tr, 0, 0, 0, 1;

            for (const auto &point : points) {
                Eigen::Vector4d P_velo(point[0], point[1], point[2], 1);
                Eigen::Vector4d P_cam_unrect = Tr_4x4 * P_velo;
                Eigen::Vector4d P_cam_rect = R0_rect_4x4 * P_cam_unrect;
                Eigen::Vector3d P_image = P2 * P_cam_rect;
                int u = static_cast<int>(std::round(P_image[0] / P_image[2]));
                int v = static_cast<int>(std::round(P_image[1] / P_image[2]));
                vertices.emplace_back(u, v);
                cv::circle(image, cv::Point(u, v), 3, cv::Scalar(0, 255, 0), -1);
            }

            std::vector<std::pair<int, int>> lines = {{0, 1}, {1, 2}, {2, 3}, {3, 0}, {4, 5}, {5, 6}, {6, 7}, {7, 4}, {0, 4}, {1, 5}, {2, 6}, {3, 7}};

            for (const auto &line : lines) {
                cv::line(image, vertices[line.first], vertices[line.second], cv::Scalar(0, 255, 255), 2);
            }
        }

        std::cout << "\n\n";


        cv::imshow("3D Bounding Boxes", image);
        cv::waitKey(100);
    }

    cv::destroyAllWindows();
    return 0;
}

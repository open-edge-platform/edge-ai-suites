#include "kitti_loader.hpp"
#include <iomanip>
#include <iostream>
#include <set>
#include <cctype>
#include <sstream>
#include <algorithm>
// OpenCV for image processing
#include <opencv2/opencv.hpp>
#include <fstream>

/*************************************************************************************************
 * @brief Utility functions implementation
 *************************************************************************************************/
namespace KittiLoaderUtils {

// Delegate to global inline functions from header
std::string getFileExtension(const std::string &file_path)
{
    return get_file_extension(file_path);
}

std::string getFileNameWithoutExtension(const std::string &file_path)
{
    return get_filename_without_extension(file_path);
}

std::string joinPath(const std::string &path1, const std::string &path2)
{
    return join_path(path1, path2);
}

void printMatrix3x3(const float *matrix, const std::string &name)
{
    std::cout << name << ":" << std::endl;
    for (int i = 0; i < 3; ++i) {
        for (int j = 0; j < 3; ++j) {
            std::cout << std::setw(12) << std::fixed << std::setprecision(6) << matrix[i * 3 + j] << " ";
        }
        std::cout << std::endl;
    }
}

void printMatrix4x4(const float *matrix, const std::string &name)
{
    std::cout << name << ":" << std::endl;
    for (int i = 0; i < 4; ++i) {
        for (int j = 0; j < 4; ++j) {
            std::cout << std::setw(12) << std::fixed << std::setprecision(6) << matrix[i * 4 + j] << " ";
        }
        std::cout << std::endl;
    }
}
}  // namespace KittiLoaderUtils

/*************************************************************************************************
 * @brief KittiDataLoader implementation
 *************************************************************************************************/

KittiDataLoader::KittiDataLoader(const std::string &data_root, const DatasetConfig &config) : config_(config)
{
    if (config_.dataset_type.empty()) {
        config_ = createKittiConfig();  // Default to KITTI
    }

    setDataRoot(data_root);
}

bool KittiDataLoader::setDataRoot(const std::string &data_root)
{
    paths_.data_root = data_root;

    // Build camera paths - conditionally use multiple cameras or just first one
    paths_.camera_paths.clear();
    if (config_.use_multiple_cameras && config_.has_multiple_cameras) {
        // Use all available cameras
        for (const auto &camera_folder : config_.camera_folders) {
            paths_.camera_paths.push_back(KittiLoaderUtils::joinPath(data_root, camera_folder));
        }
    }
    else {
        // Use only the first camera
        if (!config_.camera_folders.empty()) {
            paths_.camera_paths.push_back(KittiLoaderUtils::joinPath(data_root, config_.camera_folders[0]));
        }
    }

    paths_.pointcloud_path = KittiLoaderUtils::joinPath(data_root, config_.pointcloud_folder);
    paths_.calib_path = KittiLoaderUtils::joinPath(data_root, config_.calib_folder);

    // Build label paths - corresponding to camera paths
    paths_.label_paths.clear();
    if (config_.use_multiple_cameras && config_.has_multiple_cameras && !config_.label_folders.empty()) {
        // Use all available label folders
        for (const auto &label_folder : config_.label_folders) {
            paths_.label_paths.push_back(KittiLoaderUtils::joinPath(data_root, label_folder));
        }
    }
    else if (!config_.label_folders.empty()) {
        // Use only the first label folder
        paths_.label_paths.push_back(KittiLoaderUtils::joinPath(data_root, config_.label_folders[0]));
    }

    // Verify at least one path exists
    bool valid = file_exists(data_root);
    if (!valid) {
        std::cerr << "Data root does not exist: " << data_root << std::endl;
        return false;
    }

    std::cout << "Set data root to: " << data_root << std::endl;
    return true;
}

bool KittiDataLoader::setDatasetConfig(const DatasetConfig &config)
{
    config_ = config;
    return setDataRoot(paths_.data_root);
}

void KittiDataLoader::enableMultipleCameras(bool enable)
{
    if (config_.has_multiple_cameras) {
        config_.use_multiple_cameras = enable;
        // Rebuild paths
        setDataRoot(paths_.data_root);
        std::cout << "Multiple cameras are now " << (enable ? "enabled" : "disabled") << std::endl;
    }
    else {
        std::cout << "Dataset does not support multiple cameras" << std::endl;
    }
}

DatasetConfig KittiDataLoader::createKittiConfig()
{
    DatasetConfig config;
    config.dataset_type = "kitti";
    config.camera_folders = {"image_2"};
    config.pointcloud_folder = "velodyne";
    config.calib_folder = "calib";
    config.label_folders = {"label_2"};  // Corresponding to image_2
    config.images_are_encoded = false;
    config.has_multiple_cameras = false;
    config.use_multiple_cameras = false;
    return config;
}

DatasetConfig KittiDataLoader::createPandasetConfig()
{
    DatasetConfig config;
    config.dataset_type = "pandaset";
    config.camera_folders = {"image_2"};  // May have multiple cameras
    config.pointcloud_folder = "velodyne";
    config.calib_folder = "calib";
    config.label_folders = {"label_2"};  // Label folders corresponding to cameras
    config.images_are_encoded = false;   // May have encoded images
    config.has_multiple_cameras = false;
    config.use_multiple_cameras = false;  // Default to use only first camera (image_2)
    return config;
}

DatasetConfig KittiDataLoader::createDairV2XConfig()
{
    DatasetConfig config;
    config.dataset_type = "dair-v2x-i";
    config.camera_folders = {"image_2"};
    config.pointcloud_folder = "velodyne";
    config.calib_folder = "calib";
    config.label_folders = {"label_2"};  // Corresponding to image_2
    config.images_are_encoded = false;   // May have encoded images
    config.has_multiple_cameras = false;
    config.use_multiple_cameras = false;
    return config;
}

std::string KittiDataLoader::buildFilePath(const std::string &sample_id, FileType type, int camera_id) const
{
    switch (type) {
        case FileType::POINTCLOUD: {
            auto bin_path = KittiLoaderUtils::joinPath(paths_.pointcloud_path, sample_id + ".bin");
            if (fileExists(bin_path))
                return bin_path;
            return KittiLoaderUtils::joinPath(paths_.pointcloud_path, sample_id + ".pcd");
        }

        case FileType::IMAGE: {
            if (camera_id >= 0 && camera_id < static_cast<int>(paths_.camera_paths.size())) {
                std::string base_path = paths_.camera_paths[camera_id];

                // Try different extensions
                std::vector<std::string> extensions = getImageExtensions();
                for (const auto &ext : extensions) {
                    std::string file_path = KittiLoaderUtils::joinPath(base_path, sample_id + ext);
                    if (fileExists(file_path)) {
                        return file_path;
                    }
                }

                // Default to .jpg if none found
                return KittiLoaderUtils::joinPath(base_path, sample_id + ".jpg");
            }
            return "";
        }

        case FileType::CALIBRATION: return KittiLoaderUtils::joinPath(paths_.calib_path, sample_id + ".txt");

        case FileType::LABEL: {
            // Use corresponding label path for the camera_id
            if (camera_id >= 0 && camera_id < static_cast<int>(paths_.label_paths.size())) {
                return KittiLoaderUtils::joinPath(paths_.label_paths[camera_id], sample_id + ".txt");
            }
            else if (!paths_.label_paths.empty()) {
                // Fall back to first label path if camera_id is out of range
                return KittiLoaderUtils::joinPath(paths_.label_paths[0], sample_id + ".txt");
            }
            else {
                return "";  // No label paths configured
            }
        }

        default: return "";
    }
}

std::vector<std::string> KittiDataLoader::getImageExtensions() const
{
    if (config_.images_are_encoded) {
        return {".bin", ".png", ".jpg", ".jpeg"};
    }
    else {
        return {".jpg", ".png", ".jpeg", ".bin"};
    }
}

bool KittiDataLoader::fileExists(const std::string &file_path) const
{
    return file_exists(file_path);
}

bool KittiDataLoader::isEncodedImageFile(const std::string &file_path) const
{
    return KittiLoaderUtils::getFileExtension(file_path) == ".bin";
}

// === SAMPLE ID BASED LOADING (Direct Read) ===
bool KittiDataLoader::getPointCloud(const std::string &sample_id, lidarVec_t &output)
{
    current_sample_id_ = sample_id;
    std::string file_path = buildFilePath(sample_id, FileType::POINTCLOUD);
    return getPointCloudFromPath(file_path, output);
}

bool KittiDataLoader::getImage(const std::string &sample_id, ImageData_t &output, int camera_id)
{
    current_sample_id_ = sample_id;
    if (camera_id < 0 || camera_id >= getCameraCount()) {
        std::cerr << "Invalid camera ID: " << camera_id << ". ";
        return false;
    }
    std::string file_path = buildFilePath(sample_id, FileType::IMAGE, camera_id);
    return getImageFromPath(file_path, output);
}

bool KittiDataLoader::getCalibration(const std::string &sample_id, CalibField_t &calib)
{
    current_sample_id_ = sample_id;
    std::string file_path = buildFilePath(sample_id, FileType::CALIBRATION);
    return getCalibrationFromPath(file_path, calib);
}

bool KittiDataLoader::getLabels(const std::string &sample_id, std::vector<BBox3D> &output, int camera_id)
{
    current_sample_id_ = sample_id;
    std::string file_path = buildFilePath(sample_id, FileType::LABEL, camera_id);
    return getLabelsFromPath(file_path, output);
}

bool KittiDataLoader::getData(const std::string &sample_id, Data_t &output, int camera_id)
{
    current_sample_id_ = sample_id;

    // Get point cloud
    if (!getPointCloud(sample_id, output.lidar)) {
        std::cerr << "Failed to get point cloud for sample: " << sample_id << std::endl;
        return false;
    }

    // Get image
    if (!getImage(sample_id, output.img, camera_id)) {
        std::cerr << "Failed to get image for sample: " << sample_id << std::endl;
        return false;
    }

    // Get calibration
    if (!getCalibration(sample_id, output.calib)) {
        std::cerr << "Failed to get calibration for sample: " << sample_id << std::endl;
        return false;
    }

    // Get labels
    if (!getLabels(sample_id, output.labels, camera_id)) {
        std::cerr << "Failed to get labels for sample: " << sample_id << std::endl;
        return false;
    }

    return true;
}

// === FILE PATH BASED LOADING (Direct Read) ===
bool KittiDataLoader::getPointCloudFromPath(const std::string &file_path, lidarVec_t &output)
{
    if (!fileExists(file_path)) {
        std::cerr << "Point cloud file not found: " << file_path << std::endl;
        return false;
    }

    // Dispatch by extension
    auto ext_pos = file_path.find_last_of('.');
    std::string ext = (ext_pos != std::string::npos) ? file_path.substr(ext_pos + 1) : "";
    for (auto &c : ext)
        c = static_cast<char>(tolower(c));

    bool success = false;
    if (ext == "pcd") {
        success = readPointCloudFromPCD(file_path, output);
    }
    else {
        success = readPointCloudFromFile(file_path, output);
    }

    if (success) {
        std::cout << "Point cloud loaded successfully from: " << file_path << std::endl;
    }
    return success;
}

// PCD file reader (ASCII or binary, expects x y z intensity)
bool KittiDataLoader::readPointCloudFromPCD(const std::string &file_path, lidarVec_t &output)
{
    std::ifstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "Failed to open PCD file: " << file_path << std::endl;
        return false;
    }

    std::string line;
    size_t num_points = 0;
    bool is_binary = false;
    std::streampos data_pos{};

    // Parse header
    while (std::getline(file, line)) {
        if (line.rfind("DATA", 0) == 0) {
            if (line.find("binary") != std::string::npos) {
                is_binary = true;
            }
            data_pos = file.tellg();
            break;
        }
        auto pos = line.find("POINTS");
        if (pos != std::string::npos) {
            num_points = std::stoul(line.substr(pos + 6));
        }
    }

    if (num_points == 0) {
        std::cerr << "PCD header missing POINTS field: " << file_path << std::endl;
        return false;
    }

    output.clear();
    output.reserve(num_points * 4);

    if (is_binary) {
        file.seekg(data_pos);
        const size_t byte_size = num_points * 4 * sizeof(float);
        output.resize(num_points * 4);
        file.read(reinterpret_cast<char *>(output.data()), byte_size);
        if (!file) {
            std::cerr << "Failed to read binary PCD data: " << file_path << std::endl;
            return false;
        }
    }
    else {
        size_t count = 0;
        while (std::getline(file, line) && count < num_points) {
            std::istringstream iss(line);
            float x, y, z, intensity;
            if (!(iss >> x >> y >> z >> intensity)) {
                continue;
            }
            output.push_back(x);
            output.push_back(y);
            output.push_back(z);
            output.push_back(intensity);
            ++count;
        }
        if (output.size() != num_points * 4) {
            std::cerr << "PCD ASCII parse mismatch: " << file_path << std::endl;
            return false;
        }
    }
    return true;
}

bool KittiDataLoader::getImageFromPath(const std::string &file_path, ImageData_t &output)
{
    if (!fileExists(file_path)) {
        std::cerr << "Image file not found: " << file_path << std::endl;
        return false;
    }

    bool success = readImageFromFile(file_path, output);
    if (success) {
        std::cout << "Loaded image from: " << file_path << std::endl;
    }
    return success;
}

bool KittiDataLoader::getCalibrationFromPath(const std::string &file_path, CalibField_t &calib)
{
    if (!fileExists(file_path)) {
        std::cerr << "Calibration file not found: " << file_path << std::endl;
        return false;
    }
    bool success = readCalibrationFromFile(file_path, calib.transforms, calib.cameraParams);
    if (success) {
        std::cout << "Loaded calibration from: " << file_path << std::endl;
    }
    return success;
}

bool KittiDataLoader::getLabelsFromPath(const std::string &file_path, std::vector<BBox3D> &output)
{
    if (!fileExists(file_path)) {
        std::cerr << "Label file not found: " << file_path << std::endl;
        return false;
    }

    bool success = readLabelsFromFile(file_path, output);
    if (success) {
        std::cout << "Loaded labels from: " << file_path << std::endl;
    }
    return success;
}

// === INTERNAL FILE LOADING IMPLEMENTATIONS ===
bool KittiDataLoader::readPointCloudFromFile(const std::string &file_path, lidarVec_t &output)
{
    std::ifstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "Failed to open point cloud file: " << file_path << std::endl;
        return false;
    }

    // Get file size
    file.seekg(0, std::ios::end);
    size_t file_size = file.tellg();
    file.seekg(0, std::ios::beg);

    // KITTI point cloud format: 4 float values per point (x, y, z, intensity)
    size_t num_points = file_size / (4 * sizeof(float));
    size_t total_floats = num_points * 4;

    output.clear();
    output.resize(total_floats);

    file.read(reinterpret_cast<char *>(output.data()), file_size);

    return !output.empty();
}

bool KittiDataLoader::readImageFromFile(const std::string &file_path, ImageData_t &output)
{
    bool is_encoded = isEncodedImageFile(file_path);

    if (is_encoded) {
        // Load encoded binary data and decode to cv::Mat
        std::ifstream file(file_path, std::ios::binary);
        if (!file.is_open()) {
            std::cerr << "Failed to open encoded image file: " << file_path << std::endl;
            return false;
        }

        // Get file size and read entire file
        file.seekg(0, std::ios::end);
        size_t file_size = file.tellg();
        file.seekg(0, std::ios::beg);

        std::vector<uchar> buffer(file_size);
        file.read(reinterpret_cast<char *>(buffer.data()), file_size);
        file.close();
        output = cv::imdecode(buffer, cv::IMREAD_COLOR);
        if (output.empty()) {
            std::cerr << "Failed to decode image from bin file: " << file_path << std::endl;
            return false;
        }
        return true;
    }
    else {
        // Load image directly using OpenCV
        output = cv::imread(file_path, cv::IMREAD_COLOR);
        if (output.empty()) {
            std::cerr << "Failed to load image: " << file_path << std::endl;
            return false;
        }
        return true;
    }
}

bool KittiDataLoader::readCalibrationFromFile(const std::string &file_path, TransformMap_t &transforms, CameraParamsMap_t &camera_params)
{
    std::ifstream file(file_path);
    if (!file.is_open()) {
        std::cerr << "Failed to open calibration file: " << file_path << std::endl;
        return false;
    }

    transforms.clear();
    camera_params.clear();

    std::string line;
    while (std::getline(file, line)) {
        std::istringstream iss(line);
        std::string key;
        iss >> key;

        if (key.substr(0, 2) == "P0" || key.substr(0, 2) == "P1" || key.substr(0, 2) == "P2" || key.substr(0, 2) == "P3") {
            // Camera projection matrix
            CameraParams params;
            float p[12];
            for (int i = 0; i < 12; ++i) {
                iss >> p[i];
            }

            // Extract intrinsics from projection matrix
            for (int i = 0; i < 12; ++i) {
                params.intrinsics[i] = p[i];
            }

            camera_params[key.substr(0, 2)] = params;
        }
        else if (key == "R0_rect:") {
            // Rectification rotation matrix
            Transform4x4 transform;
            for (int i = 0; i < 9; ++i) {
                float val;
                iss >> val;
                int row = i / 3;
                int col = i % 3;
                transform(row, col) = val;
            }
            transform(3, 3) = 1.0f;
            transforms["R0_rect"] = transform;
        }
        else if (key == "Tr_velo_to_cam:") {
            // LiDAR to camera transformation
            Transform4x4 transform;
            for (int i = 0; i < 12; ++i) {
                iss >> transform.data[i];
            }
            transform.data[12] = 0;
            transform.data[13] = 0;
            transform.data[14] = 0;
            transform.data[15] = 1;
            transforms["lidar_to_camera"] = transform;
            transforms["Tr_velo_to_cam"] = transform;
        }
        else if (key == "Tr_imu_to_velo:") {
            // IMU to LiDAR transformation
            Transform4x4 transform;
            for (int i = 0; i < 12; ++i) {
                iss >> transform.data[i];
            }
            transform.data[12] = 0;
            transform.data[13] = 0;
            transform.data[14] = 0;
            transform.data[15] = 1;
            transforms["imu_to_lidar"] = transform;
            transforms["Tr_imu_to_velo"] = transform;
        }
    }

    return true;
}

bool KittiDataLoader::readLabelsFromFile(const std::string &file_path, std::vector<BBox3D> &output)
{
    std::ifstream file(file_path);
    if (!file.is_open()) {
        std::cerr << "Failed to open label file: " << file_path << std::endl;
        return false;
    }

    output.clear();

    std::string line;
    while (std::getline(file, line)) {
        std::istringstream iss(line);

        BBox3D bbox;
        std::string class_name;
        float truncated, occluded, alpha;
        float bbox_2d[4];

        // Parse KITTI label format
        iss >> class_name >> truncated >> occluded >> alpha;
        iss >> bbox_2d[0] >> bbox_2d[1] >> bbox_2d[2] >> bbox_2d[3];
        iss >> bbox.h >> bbox.w >> bbox.l;
        iss >> bbox.x >> bbox.y >> bbox.z;
        iss >> bbox.yaw;

        // Map class name to label ID (align with PostProcessParams::class_name)
        std::string cls = class_name;
        std::transform(cls.begin(), cls.end(), cls.begin(), [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
        cls.erase(std::remove(cls.begin(), cls.end(), '_'), cls.end());

        if (cls == "car")
            bbox.label = 0;
        else if (cls == "truck")
            bbox.label = 1;
        else if (cls == "constructionvehicle")
            bbox.label = 2;
        else if (cls == "bus")
            bbox.label = 3;
        else if (cls == "trailer")
            bbox.label = 4;
        else if (cls == "barrier")
            bbox.label = 5;
        else if (cls == "motorcycle")
            bbox.label = 6;
        else if (cls == "bicycle")
            bbox.label = 7;
        else if (cls == "pedestrian")
            bbox.label = 8;
        else if (cls == "trafficcone" || cls == "traffic_cone")
            bbox.label = 9;
        else
            bbox.label = -1;

        bbox.score = 1.0f;
        output.push_back(bbox);
    }

    return true;
}

// === CONVENIENCE METHODS (return by value for single-use scenarios) ===
lidarVec_t KittiDataLoader::getPointCloud(const std::string &sample_id)
{
    lidarVec_t output;
    if (getPointCloud(sample_id, output)) {
        return output;
    }
    std::cerr << "PointCloud not available for sample: " << sample_id << std::endl;
    return output;
}

ImageData_t KittiDataLoader::getImage(const std::string &sample_id, int camera_id)
{
    ImageData_t output;
    if (getImage(sample_id, output, camera_id)) {
        return output;
    }
    std::cerr << "Image not available for sample: " << sample_id << std::endl;
    return output;
}

std::vector<BBox3D> KittiDataLoader::getLabels(const std::string &sample_id, int camera_id)
{
    std::vector<BBox3D> output;
    if (getLabels(sample_id, output, camera_id)) {
        return output;
    }
    std::cerr << "Labels not available for sample: " << sample_id << std::endl;
    return output;
}

CalibField_t KittiDataLoader::getCalibration(const std::string &sample_id)
{
    CalibField_t calib;
    if (getCalibration(sample_id, calib)) {
        return calib;
    }
    std::cerr << "Calibration not available for sample: " << sample_id << std::endl;
    return calib;
}

Data_t KittiDataLoader::getData(const std::string &sample_id, int camera_id)
{
    current_sample_id_ = sample_id;
    Data_t data;
    if (getData(sample_id, data, camera_id)) {
        return data;
    }
    std::cerr << "Data not available for sample: " << sample_id << std::endl;
    return data;
}

// === SAMPLE MANAGEMENT ===
std::vector<std::string> KittiDataLoader::scanSampleIds() const
{
    std::vector<std::string> sample_ids;

    // Priority order: images > pointcloud > calibration > labels
    std::vector<std::string> search_paths;
    if (!paths_.camera_paths.empty()) {
        search_paths.push_back(paths_.camera_paths[0]);
    }
    search_paths.push_back(paths_.pointcloud_path);
    search_paths.push_back(paths_.calib_path);
    if (!paths_.label_paths.empty()) {
        search_paths.push_back(paths_.label_paths[0]);
    }

    std::vector<std::string> search_extensions = {
        ".bin", ".pcd",           // Point cloud
        ".jpg", ".png", ".jpeg",  // Images
        ".txt"                    // Calibration and labels
    };

    // Try each search path until we find files
    for (const auto &search_path : search_paths) {
        if (search_path.empty() || !file_exists(search_path)) {
            continue;
        }

        std::vector<std::string> files = list_directory_files(search_path);
        std::set<std::string> unique_sample_ids;  // Use set to avoid duplicates

        for (const auto &file : files) {
            // Extract sample ID (filename without extension)
            std::string sample_id = KittiLoaderUtils::getFileNameWithoutExtension(file);

            // Check if file has a valid extension
            std::string ext = KittiLoaderUtils::getFileExtension(file);
            bool valid_extension = false;
            for (const auto &valid_ext : search_extensions) {
                if (ext == valid_ext) {
                    valid_extension = true;
                    break;
                }
            }

            if (valid_extension && !sample_id.empty()) {
                unique_sample_ids.insert(sample_id);
            }
        }

        // Convert set to vector
        sample_ids.assign(unique_sample_ids.begin(), unique_sample_ids.end());

        // If we found samples, use them
        if (!sample_ids.empty()) {
            break;
        }
    }

    // Sort sample IDs (assuming they are numeric with zero padding)
    std::sort(sample_ids.begin(), sample_ids.end());

    return sample_ids;
}

std::vector<std::string> KittiDataLoader::getSampleList() const
{
    return scanSampleIds();
}

size_t KittiDataLoader::getSampleCount() const
{
    return getSampleList().size();
}

bool KittiDataLoader::hasSample(const std::string &sample_id) const
{
    // Check if at least one file exists for this sample
    return fileExists(buildFilePath(sample_id, FileType::POINTCLOUD)) || fileExists(buildFilePath(sample_id, FileType::IMAGE, 0)) ||
           fileExists(buildFilePath(sample_id, FileType::CALIBRATION)) || fileExists(buildFilePath(sample_id, FileType::LABEL));
}

bool KittiDataLoader::isValid() const
{
    return file_exists(paths_.data_root);
}

// === UTILITY METHODS ===
void KittiDataLoader::printDatasetInfo() const
{
    std::cout << "=== Dataset Information ===" << std::endl;
    std::cout << "Dataset Type: " << config_.dataset_type << std::endl;
    std::cout << "Data Root: " << paths_.data_root << std::endl;
    std::cout << "Camera Count: " << getCameraCount() << std::endl;

    // Show current camera configuration
    if (config_.has_multiple_cameras) {
        std::cout << "Multiple Cameras Available: Yes" << std::endl;
        std::cout << "Multiple Cameras Enabled: " << (config_.use_multiple_cameras ? "Yes" : "No") << std::endl;

        if (config_.use_multiple_cameras) {
            std::cout << "Available Cameras:" << std::endl;
            for (size_t i = 0; i < config_.camera_folders.size(); ++i) {
                std::cout << "  Camera " << i << ": " << config_.camera_folders[i] << std::endl;
            }
        }
        else {
            std::cout << "Active Camera: " << config_.camera_folders[0] << " (others disabled)" << std::endl;
        }
    }
    else {
        for (int i = 0; i < getCameraCount(); ++i) {
            std::cout << "  Camera " << i << ": " << config_.camera_folders[i] << std::endl;
        }
    }

    std::cout << "Point Cloud Folder: " << config_.pointcloud_folder << std::endl;
    std::cout << "Calibration Folder: " << config_.calib_folder << std::endl;

    // Show label folder configuration
    if (config_.has_multiple_cameras && config_.use_multiple_cameras && !config_.label_folders.empty()) {
        std::cout << "Label Folders:" << std::endl;
        for (size_t i = 0; i < config_.label_folders.size(); ++i) {
            std::cout << "  Camera " << i << " Labels: " << config_.label_folders[i] << std::endl;
        }
    }
    else if (!config_.label_folders.empty()) {
        std::cout << "Label Folder: " << config_.label_folders[0] << std::endl;
    }

    std::cout << "Images Are Encoded: " << (config_.images_are_encoded ? "Yes" : "No") << std::endl;
}

// === PREFETCH API ===

void KittiDataLoader::prefetch(const std::string &sample_id, int camera_id)
{
    std::lock_guard<std::mutex> lock(prefetch_mutex_);
    // If there is already an in-flight prefetch for the same sample, skip.
    if (prefetch_future_.valid() && prefetch_sample_id_ == sample_id && prefetch_camera_id_ == camera_id) {
        return;
    }
    // Launch background I/O.  getData() is self-contained (reads from disk),
    // so it is safe to run on a detached thread.
    prefetch_sample_id_ = sample_id;
    prefetch_camera_id_ = camera_id;
    prefetch_future_ = std::async(std::launch::async, [this, sample_id, camera_id]() {
        return this->getData(sample_id, camera_id);
    });
}

Data_t KittiDataLoader::getDataPrefetched(const std::string &sample_id, int camera_id)
{
    std::lock_guard<std::mutex> lock(prefetch_mutex_);
    // If the outstanding prefetch matches what the caller wants, wait for it.
    if (prefetch_future_.valid() && prefetch_sample_id_ == sample_id && prefetch_camera_id_ == camera_id) {
        Data_t result = prefetch_future_.get();  // blocks until I/O done
        prefetch_sample_id_.clear();
        return result;
    }
    // Mismatch or no prefetch — fall back to synchronous load.
    return getData(sample_id, camera_id);
}

void KittiDataLoader::cancelPrefetch()
{
    std::lock_guard<std::mutex> lock(prefetch_mutex_);
    if (prefetch_future_.valid()) {
        // Let the background thread finish but discard the result.
        prefetch_future_.get();
    }
    prefetch_sample_id_.clear();
}

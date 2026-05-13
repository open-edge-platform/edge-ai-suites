#ifndef _KITTI_LOADER_HPP_
#define _KITTI_LOADER_HPP_

#include <cstring>
#include <future>
#include <mutex>
#include <string>
#include <vector>

// OpenCV for image processing
#include <opencv2/opencv.hpp>

#include "configs.hpp"
#include "utils.hpp"

/*************************************************************************************************
 * @brief Enhanced KittiDataLoader with flexible loading strategies
 *************************************************************************************************/
class KittiDataLoader {
  private:
    struct DataPaths
    {
        std::string data_root;
        std::vector<std::string> camera_paths;  // Multiple camera paths
        std::string pointcloud_path;
        std::string calib_path;
        std::vector<std::string> label_paths;  // Label paths corresponding to camera_paths
    };

    enum class FileType { POINTCLOUD, IMAGE, CALIBRATION, LABEL };

    // Configuration and paths
    DatasetConfig config_;
    DataPaths paths_;
    std::string current_sample_id_;

    // Internal helper functions for direct file reading
    bool readPointCloudFromFile(const std::string &file_path, lidarVec_t &output);
    bool readImageFromFile(const std::string &file_path, ImageData_t &output);
    bool readCalibrationFromFile(const std::string &file_path, TransformMap_t &transforms, CameraParamsMap_t &camera_params);
    bool readLabelsFromFile(const std::string &file_path, std::vector<BBox3D> &output);

    // === SAMPLE ID BASED LOADING (Direct Read) ===
    bool getPointCloud(const std::string &sample_id, lidarVec_t &output);
    bool getImage(const std::string &sample_id, ImageData_t &output, int camera_id = 0);
    bool getCalibration(const std::string &sample_id, CalibField_t &calib);
    bool getLabels(const std::string &sample_id, std::vector<BBox3D> &output, int camera_id = 0);
    bool getData(const std::string &sample_id, Data_t &output, int camera_id = 0);

    std::string buildFilePath(const std::string &sample_id, FileType type, int camera_id = 0) const;
    bool fileExists(const std::string &file_path) const;

    // File format detection
    bool isEncodedImageFile(const std::string &file_path) const;
    std::vector<std::string> scanSampleIds() const;
    std::vector<std::string> getImageExtensions() const;

  public:
    explicit KittiDataLoader(const std::string &data_root, const DatasetConfig &config = DatasetConfig());
    ~KittiDataLoader()
    {
        // Drain any outstanding prefetch to avoid dangling references.
        if (prefetch_future_.valid()) {
            try { prefetch_future_.get(); } catch (...) {}
        }
    }

    // Configuration methods
    bool setDataRoot(const std::string &data_root);
    bool setDatasetConfig(const DatasetConfig &config);
    DatasetConfig getDatasetConfig() const
    {
        return config_;
    }

    // Multi-camera control methods
    void enableMultipleCameras(bool enable = true);
    void disableMultipleCameras()
    {
        enableMultipleCameras(false);
    }
    bool isMultipleCamerasEnabled() const
    {
        return config_.use_multiple_cameras;
    }
    bool hasMultipleCameras() const
    {
        return config_.has_multiple_cameras;
    }

    // Factory methods for different datasets
    static DatasetConfig createKittiConfig();
    static DatasetConfig createPandasetConfig();
    static DatasetConfig createDairV2XConfig();

    // === FILE PATH BASED LOADING (Direct Read) ===
    bool getPointCloudFromPath(const std::string &file_path, lidarVec_t &output);
    bool readPointCloudFromPCD(const std::string &file_path, lidarVec_t &output);
    bool getImageFromPath(const std::string &file_path, ImageData_t &output);
    bool getCalibrationFromPath(const std::string &file_path, CalibField_t &calib);
    bool getLabelsFromPath(const std::string &file_path, std::vector<BBox3D> &output);

    // === CONVENIENCE METHODS (return by value for single-use scenarios) ===
    lidarVec_t getPointCloud(const std::string &sample_id);
    ImageData_t getImage(const std::string &sample_id, int camera_id = 0);
    std::vector<BBox3D> getLabels(const std::string &sample_id, int camera_id = 0);
    CalibField_t getCalibration(const std::string &sample_id);
    Data_t getData(const std::string &sample_id, int camera_id = 0);

    // === SAMPLE MANAGEMENT ===
    std::vector<std::string> getSampleList() const;
    size_t getSampleCount() const;
    bool hasSample(const std::string &sample_id) const;
    bool isValid() const;
    std::string getCurrentSampleId() const
    {
        return current_sample_id_;
    }

    // === CAMERA MANAGEMENT ===
    int getCameraCount() const
    {
        return static_cast<int>(config_.camera_folders.size());
    }
    std::vector<std::string> getCameraFolders() const
    {
        return config_.camera_folders;
    }

    // === PREFETCH API ===
    // Start loading a sample in a background thread.  The result is cached
    // and returned by the next call to getDataPrefetched().  Only one
    // prefetch may be outstanding at a time; calling prefetch() again
    // implicitly discards the previous one (the background I/O still runs
    // to completion but the result is dropped when getDataPrefetched()
    // is called for the new id).
    void prefetch(const std::string &sample_id, int camera_id = 0);

    // Return the result of a preceding prefetch() call.  If the background
    // I/O hasn't finished yet this blocks until it does.  If no prefetch is
    // outstanding, falls back to a synchronous getData().
    Data_t getDataPrefetched(const std::string &sample_id, int camera_id = 0);

    // Cancel / discard any outstanding prefetch.
    void cancelPrefetch();

    // === UTILITY METHODS ===
    void printDatasetInfo() const;

  private:
    // Prefetch state
    std::future<Data_t> prefetch_future_;
    std::string prefetch_sample_id_;
    int prefetch_camera_id_{0};
    std::mutex prefetch_mutex_;
};

/*************************************************************************************************
 * @brief Utility functions
 *************************************************************************************************/
namespace KittiLoaderUtils {
// File path utilities (delegating to global inline functions)
std::string getFileExtension(const std::string &file_path);
std::string getFileNameWithoutExtension(const std::string &file_path);
std::string joinPath(const std::string &path1, const std::string &path2);

// Additional file system utilities
inline bool fileExists(const std::string &path)
{
    return file_exists(path);
}
inline bool isDirectory(const std::string &path)
{
    return is_directory(path);
}
inline bool isRegularFile(const std::string &path)
{
    return is_regular_file(path);
}
inline std::string absolutePath(const std::string &path)
{
    return absolute_path(path);
}
inline std::vector<std::string> listDirectoryFiles(const std::string &path, const std::string &ext = "")
{
    return list_directory_files(path, ext);
}

// Enhanced file operations (based on testUtils.hpp patterns)
inline bool checkFileExtension(const std::string &fileName, const std::string &target = "")
{
    return check_file_extension(fileName, target);
}

// Matrix utilities
void printMatrix3x3(const float *matrix, const std::string &name = "Matrix");
void printMatrix4x4(const float *matrix, const std::string &name = "Matrix");
}  // namespace KittiLoaderUtils


#endif  // _KITTI_LOADER_H_

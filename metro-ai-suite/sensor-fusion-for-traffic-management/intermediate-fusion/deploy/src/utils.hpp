#ifndef _UTILS_HPP_
#define _UTILS_HPP_

#include <algorithm>

// Boost filesystem for cross-platform file operations
#include <boost/filesystem.hpp>

// Linux filesystem operations
#include <sys/stat.h>
#include <unistd.h>
#include <dirent.h>


// Utility functions for filesystem operations
// Using boost filesystem for robust cross-platform file operations

inline bool file_exists(const std::string &path)
{
    boost::filesystem::path p(path);
    return boost::filesystem::exists(p);
}

inline bool is_directory(const std::string &path)
{
    boost::filesystem::path p(path);
    return boost::filesystem::is_directory(p);
}

inline bool is_regular_file(const std::string &path)
{
    boost::filesystem::path p(path);
    return boost::filesystem::is_regular_file(p);
}

// Boost absolute path
inline std::string absolute_path(const std::string &path)
{
    boost::filesystem::path p(path);
    return boost::filesystem::absolute(p).string();
}

// Path joining utility using boost
inline std::string join_path(const std::string &path1, const std::string &path2)
{
    boost::filesystem::path p1(path1);
    boost::filesystem::path p2(path2);
    return (p1 / p2).string();
}

// Get file extension using boost
inline std::string get_file_extension(const std::string &file_path)
{
    boost::filesystem::path p(file_path);
    return p.extension().string();
}

// Get filename without extension using boost
inline std::string get_filename_without_extension(const std::string &file_path)
{
    boost::filesystem::path p(file_path);
    return p.stem().string();
}

// Check if filename has specific extension/suffix (from testUtils.hpp pattern)
inline bool check_file_extension(const std::string &fileName, const std::string &target = "")
{
    if (fileName.empty()) {
        return false;
    }

    int nStartPos = fileName.rfind(".");
    if (nStartPos == -1) {
        return false;
    }

    std::string strPostFix = fileName.substr(fileName.rfind("."));
    if (target.empty() || strPostFix.find(target) != std::string::npos) {
        return true;
    }

    return false;
}

// List directory files with optional extension filter
inline std::vector<std::string> list_directory_files(const std::string &directory_path, const std::string &extension_filter = "")
{
    std::vector<std::string> files;

    // Check directory existence
    if (!file_exists(directory_path) || !is_directory(directory_path)) {
        return files;
    }

    // Check directory accessibility
    DIR *pDir;
    if (!(pDir = opendir(directory_path.c_str()))) {
        return files;
    }

    // Read files with specific suffix from the folder
    struct dirent *ptr;
    while ((ptr = readdir(pDir)) != 0) {
        if (strcmp(ptr->d_name, ".") != 0 && strcmp(ptr->d_name, "..") != 0) {
            std::string filename = std::string(ptr->d_name);
            std::string full_path = join_path(directory_path, filename);

            // Only include regular files
            if (is_regular_file(full_path)) {
                if (extension_filter.empty() || check_file_extension(filename, extension_filter)) {
                    files.push_back(filename);
                }
            }
        }
    }

    // Sort files for consistent ordering
    std::sort(files.begin(), files.end());

    // Remember to close the pDir handle
    closedir(pDir);

    return files;
}

#endif  // _UTILS_H_
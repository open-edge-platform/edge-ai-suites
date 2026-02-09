/* ********************************************************************************
 # INTEL CONFIDENTIAL
 # Copyright 2020 Intel Corporation.

 # This software and the related documents are Intel copyrighted materials, and
 # your use of them is governed by the express license under which they were
 # provided to you (License). Unless the License provides otherwise, you may not
 # use, modify, copy, publish, distribute, disclose or transmit this software or
 # the related documents without Intel's prior written permission.

 # This software and the related documents are provided as is, with no express or
 # implied warranties, other than those that are expressly stated in the License.
 # ********************************************************************************/
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <signal.h>
#include <string.h>
#include <stddef.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <iostream>
#include <sstream>
#include <iterator>
#include <vector>
#include <list>
#include <algorithm>
#include <set>
#include <memory>
#include <iomanip>

#include "socwatch_data.h"
#include "socwatch_lib.h"

#ifdef WINDOWS
    #include <Windows.h>
    #include <direct.h>
    #define SLEEP(seconds) ::Sleep((unsigned long)seconds * 1000)
    #define getCurrentDir _getcwd
    #define usleep(usec) ::Sleep(usec / 1000)
    #define DL_ERROR() getFormattedLastError()
    #define DL_OPEN(a,b) ::LoadLibraryA(a)
    #define DL_SYM(a,b) ::GetProcAddress((HMODULE)a,b)
    #define DL_CLOSE(a) ::FreeLibrary((HMODULE)a)
#else
    #include <unistd.h>
    #include <dlfcn.h>
    #include <getopt.h>

    #define SLEEP(seconds) sleep(seconds)
    #define getCurrentDir getcwd
    #define DL_ERROR() dlerror()
    #define DL_OPEN(a,b) dlopen(a,b)
    #define DL_SYM(a,b) dlsym(a,b)
    #define DL_CLOSE(a) dlclose(a)
#endif

#ifndef MAX_PATH
    #define MAX_PATH 1024
#endif // MAX_PATH

#define TAB "\t"

#if defined(_WIN32)
    #define SPRINTF_S(str, strlength, format, ...) sprintf_s(str, strlength, format, __VA_ARGS__)
    static const std::string s_libSoCWatchName = "libSOCWatch.dll";
    // Returns error string from the Windows GetLastError error code.
    static char* getFormattedLastError() {
        static char buffer[1024];
        buffer[0] = '\0';

        DWORD err = ::GetLastError();
        if (err != 0) {
            ::FormatMessage(FORMAT_MESSAGE_FROM_SYSTEM | FORMAT_MESSAGE_IGNORE_INSERTS, NULL, err,
                            MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT), (LPTSTR)buffer, sizeof(buffer)/sizeof(TCHAR), NULL);
        }
        return buffer;
    }
#else
    #define SPRINTF_S(str, strlength, format, ...) snprintf(str, strlength, format, __VA_ARGS__)
    static const std::string s_libSoCWatchName = "libSOCWatch.so";
#endif

/*
 * Helper macro to convert 'u64' to 'unsigned long long' to avoid gcc warnings.
 */
#define TO_ULL(x) (unsigned long long)(x)

/*
 * An enumeration of extended command line values.
 */
enum ExtendedOptions {
    CONT = 1000,
    SOC,
    CPORT,
    DPORT,
};

/**
 * class that should be implemented by the library users
 */
class DataCallback_i : public pwr::lib::DataCallback {
  public:
    ~DataCallback_i() {}
    virtual void log(DataCallback::LogLevel level, const char* msg) { fprintf(stdout, "Level %u: %s", (unsigned int)level, msg); }

    /**
     * @param[in] bundle of data sent from the collector
     */
    virtual void onDataReady(const pwr::lib::DataBundle* bundle) {
        // always the same system data

        /*
         * Reference code to print bundle data
         */
        static bool printOnce = true;

        if (printOnce) {
            auto metadata = bundle->getMetadata();
            fprintf(stderr, "DEBUG: Printing system meta-data from collection once!\n\n");
            fprintf(stderr, "DEBUG: PLATFORM ID = %u\n", metadata->getPlatformId());
            fprintf(stderr, "DEBUG: PLATFORM NAME = %s\n", metadata->getPlatformName().c_str());
            fprintf(stderr, "DEBUG: PCH NAME = %s\n", metadata->getPCHName().c_str());
            fprintf(stderr, "DEBUG: CPU NAME = %s\n", metadata->getCPUName().c_str());
            fprintf(stderr, "DEBUG: CPU NATIVE NAME = %s\n", metadata->getCPUNativeName().c_str());
            fprintf(stderr, "DEBUG: HOST NAME = %s\n", metadata->getHostName().c_str());
            fprintf(stderr, "DEBUG: BUS FREQ = %f\n", metadata->getBusFrequency());
            fprintf(stderr, "DEBUG: CPU FREQ = %f\n", metadata->getCPUFreqency());
            fprintf(stderr, "DEBUG: HFM FREQ = %f\n", metadata->getHFMFreqency());
            fprintf(stderr, "DEBUG: LFM FREQ = %f\n", metadata->getLFMFreqency());
            fprintf(stderr, "DEBUG: NUM CORES = %u\n", metadata->getNumCores());
            fprintf(stderr, "DEBUG: NUM MODULES = %u\n", metadata->getNumModules());
            fprintf(stderr, "DEBUG: NUM PKGS = %u\n", metadata->getNumPackages());
            fprintf(stderr, "DEBUG: NUM THREADS = %u\n", metadata->getNumThreads());
            fprintf(stderr, "DEBUG: OS NAME = %s\n", metadata->getOSName().c_str());
            fprintf(stderr, "DEBUG: OS TYPE = %s\n", metadata->getOSType().c_str());
            fprintf(stderr, "DEBUG: OS VERSION = %s\n", metadata->getOSVersion().c_str());
            fprintf(stderr, "DEBUG: CLOCK FREQ = %f\n\n", metadata->getClockFrequencyMHz());
            printOnce = false;
        }

        // current group of data info
        fprintf(stderr, "DEBUG: START TS = %llu\n", TO_ULL(bundle->getStartTimestamp()));
        fprintf(stderr, "DEBUG: END TS = %llu\n", TO_ULL(bundle->getEndTimestamp()));
        fprintf(stderr, "DEBUG: DURATION = %f\n", bundle->getDuration());

        std::set<int> ids;
        // individual data points
        for (auto data : bundle->getData()) {
            fprintf(stderr, "DEBUG: ENTITY = %s\n", data->getEntity().c_str());
            fprintf(stderr, "DEBUG: DESC = %s\n", data->getDescriptor().c_str());
            fprintf(stderr, "DEBUG: ID = %i\n", data->getId());
            fprintf(stderr, "DEBUG: TIMESTAMP = %llu\n", TO_ULL(data->getTimestamp()));
            fprintf(stderr, "DEBUG: VALUE = %f\n", data->getValue());
            fprintf(stderr, "DEBUG: DURATION = %f\n", data->getDuration());

            // getting individual information for this data (based on the data->getId()
            if (ids.find(data->getId()) == ids.end()) {
                auto desc = bundle->getDataDescription(*data);
                fprintf(stderr, "DEBUG: FEATURE = %s\n", desc->getFeatureName().c_str());
                fprintf(stderr, "DEBUG: NAME = %s\n", desc->getName().c_str());
                fprintf(stderr, "DEBUG: UNITS = %s\n", desc->getUnitDescription().c_str());
                fprintf(stderr, "DEBUG: UNIT TEXT = %s\n", desc->getUnitText().c_str());
            }
        }
        fprintf(stderr, "\n\n");
    }
};


/**
 * Structure to save the parsed command line options
 */
struct InputOptions {
    size_t m_timeSecs, m_intervalMSecs;
    bool m_isContinuous;
    std::string m_configDir;
    std::list <std::string> m_features, m_reports;
    DataCallback_i::LogLevel m_logLevel;
    friend std::ostream& operator<<(std::ostream&, struct InputOptions const&);

    InputOptions()
        : m_timeSecs(0), m_intervalMSecs(0), m_isContinuous(false), m_configDir(""),
          m_logLevel(DataCallback_i::LogLevel::Error) {}
};
/**
 * Output operator for \ref InputOptions  sends \p opts to an output stream
 * @param[in,out]   str     The output stream
 * @param[in]       opts    The set of options being printed
 *
 * @returns         The output stream
 */
std::ostream& operator<<(std::ostream& str, struct InputOptions const& opts)
{
    str << "Time: " << opts.m_timeSecs << std::endl;
    str << "Interval: " << opts.m_intervalMSecs << std::endl;
    str << "Log Level: " << (int)opts.m_logLevel << std::endl;
    str << "Is continuous: " << (opts.m_isContinuous ? "true" : "false") << std::endl;
    str << "SoC Watch config directory: " << opts.m_configDir << std::endl;
    str << "Features: "; std::copy(opts.m_features.begin(), opts.m_features.end(), std::ostream_iterator<std::string>(std::cerr, " ")); str << std::endl;
    str << "Reports: "; std::copy(opts.m_reports.begin(), opts.m_reports.end(), std::ostream_iterator<std::string>(std::cerr, " ")); str << std::endl;
    return str;
}

/**
 * Determine the current working directory.
 * @returns     The current working directory
 */
static std::string getCurrentWorkingDir() {
    char buff[FILENAME_MAX];
    char *ret;
    ret = getCurrentDir(buff, FILENAME_MAX);
    if (ret) {
        return ret;
    }
    return "";
}

/**
 * Identify 'Info' instance with the given name and type.
 * @param[in]   array   The list of 'Info' instances to parse
 * @param[in]   name    The name to search for
 *
 * @returns     Info with the given name and type
 */
template <typename T> T* getInfo(const Info **array,
                                 const std::string& name)
{
    for (const Info **_arr = array; *_arr; ++_arr) {
        const Info *info = *_arr;
        if (info->getName() == name) {
            if (T *_info = dynamic_cast<T *>(info)) {
                return _info;
            } else {
                fprintf(stderr, "ERROR: wrong type?! info type = %d\n", info->getType());
            }
        }
    }
    return NULL;
}

/**
 * Retrieve a list of @ref FeatureInfo instances corresponding to features of interest
 * @param[in,out]   handle          Handle to SoC Watch API
 * @param[in]       featureNames    Names of features we're interested in
 * @param[in]       isContinuous    True if called for a continuous collection
 * @param[out]      list            Retrieved 'FeatureInfo' list
 *
 * @returns         0 on success, -1 on failure
 */
int getFeatures(APIHandle *handle,
                std::list<std::string>& featureNames, bool isContinuous,
                std::list <const FeatureInfo *>& list)
{
    /*
     * Retrieve a list of 'info' classes corresponding to some features of interest.
     *
     * There are three ways of discovering which features are supported by socwatch:
     * 1. Use the 'getCollectionOptions' API to retrieve a list of all collection
     * options, including feature options.
     * 2. Use the 'getAvailableFeatures' API to retrieve a list of all supported feature
     * options only.
     * 3. Use the 'getAvailableFeatures' API to retrieve a list of supported feature
     * options corresponding to a list of feature names.
     *
     * We illustrate all three here.
     */
    if (featureNames.empty()) {
        return -1;
    }
    const FeatureInfo *featureInfo = NULL;
    /*
     * First method: use 'getCollectionOptions'
     */
    const Info **infoArray = NULL;
    if (handle->getCollectionOptions(&infoArray)) { /* Alt: supply 'isContinuous' here to avoid check in "if" clause below */
        fprintf(stderr, "Couldn't retrieve collection options from API\n");
        return -1;
    }
    featureInfo = getInfo<const FeatureInfo>(infoArray, featureNames.front());
    if (featureInfo == NULL ||
            (isContinuous && !featureInfo->doesSupportContinuousCollection())) { // Alt: avoid 'continuous' check by supplying
                                                                                 // 'isContinuous' to 'getCollectionOptions' above
        fprintf(stderr, "Couldn't retrieve an instance of \"%s\" feature from API -- not supported?\n",
                featureNames.front().c_str());
    } else {
        list.push_back(featureInfo);
    }

    featureNames.pop_front();
    if (featureNames.empty()) {
        return 0;
    }

    /*
     * Second method: use 'getAvailableFeatures' API to retrive a map of all
     * features, then iterate through the map to retrieve the feature of interest.
     */
    FeatureInfo const **features = NULL;
    if (handle->getAvailableFeatures(&features, isContinuous)) {
        fprintf(stderr, "Couldn't retrieve a map of available features from API\n");
        return -1;
    }
    while (*features) {
        if (!strcmp((*features)->getName(), featureNames.front().c_str())) {
            list.push_back(*features);
            break;
        }
        ++features;
    }
    if (!*features) {
        fprintf(stderr, "Couldn't retrieve an instance of \"%s\" feature from API -- not supported?\n",
                featureNames.front().c_str());
    }
    featureNames.pop_front();
    if (featureNames.empty()) {
        return 0;
    }

    /*
     * Third method: use 'getAvailableFeatures' API together with the feature names to retrieve
     * a map of features of interest.
     */
    std::vector <char const *> _featureNames;
    std::for_each(featureNames.begin(), featureNames.end(), [&](const std::string& str) {
            _featureNames.emplace_back(str.c_str());
            });
    _featureNames.push_back(NULL); // array must be NULL terminated

    if (handle->getAvailableFeatures(&_featureNames[0], &features, isContinuous)) {
        fprintf(stderr, "Couldn't retrieve a map of available features from API\n");
        return -1;
    }
    FeatureInfo const **feature = features;
    while (!featureNames.empty() && *feature) {
        if (!strcmp((*feature)->getName(), featureNames.front().c_str())) {
            list.push_back(*feature);
            ++feature;
        } else {
            fprintf(stderr, "Couldn't retrieve an instance of \"%s\" feature from API -- not supported?\n",
                    featureNames.front().c_str());
        }
        featureNames.pop_front();
    }

    return 0;
}

/**
 * Retrieve a list of @ref OutputformatInfo instances corresponding to output formats of interest
 * @param[in,out]   handle          Handle to SoC Watch API
 * @param[in]       names           Names of output formats we're interested in (e.g. "int")
 * @param[in]       isContinuous    True if called for a continuous collection
 * @param[out]      list            Retrieved 'OutputformatInfo' list
 *
 * @returns         0 on success, -1 on failure
 */
int getOutputformats(APIHandle *handle,
                     std::list<std::string>& names,
                     bool isContinuous,
                     std::list <const OutputformatInfo *>& list)
{
    /*
     * Retrieve a list of desired output formats.
     *
     * There are three ways of discovering which output formats are supported by socwatch:
     * 1. Use the 'getPostProcessingOptions' API to retrieve a list of all post-processing
     * options, including output format options.
     * 2. Use the 'getAvailableOutputFormats' API to retrieve a list of all supported output format
     * options only.
     * 3. Use the 'getAvailableOutputFormats' API to retrieve a list of supported output format
     * options corresponding to a list of feature names.
     *
     * We demonstrate only the first two here; see function 'getFeatures' for an example of how to use
     * the other method.
     */
    if (names.empty()) {
        return -1;
    }
    const OutputformatInfo *outputInfo = NULL;
    /*
     * Method 1
     */
    const Info **infoArray = NULL;
    if (handle->getPostProcessingOptions(&infoArray, isContinuous)) { // Alt: don't provide 'isContinuous' but then check
                                                                     // the 'outputInfo' instance retrieved from 'getInfo'
                                                                     // to see if it supports continuous collection; see
                                                                     // 'getFeatures' for example
        fprintf(stderr, "Couldn't retrieve a list of post-processing options from API\n");
        return -1;
    }
    outputInfo = getInfo<const OutputformatInfo>(infoArray, names.front());
    if (!outputInfo) {
        fprintf(stderr, "Couldn't retrieve an instance of \"%s\" output from API -- not supported?\n",
                names.front().c_str());
    } else {
        list.push_back(outputInfo);
    }

    names.pop_front();
    if (names.empty()) {
        return 0;
    }
    /*
     * Method 2
     */
    OutputformatInfo const **allOutputFormats = NULL;
    if (handle->getAvailableOutputFormats(&allOutputFormats, isContinuous)) {
        fprintf(stderr, "Couldn't retrieve a list of output formats from API\n");
        return -1;
    }
    while (!names.empty()) {
        OutputformatInfo const **outputFormat = allOutputFormats;
        while (*outputFormat) {
            if (!strcmp((*outputFormat)->getName(), names.front().c_str())) {
                list.push_back(*outputFormat);
                break;
            }
            ++outputFormat;
        }
        if (!*outputFormat) {
            fprintf(stderr, "Couldn't retrieve an instance of \"%s\" Output from API -- not supported?\n",
                    names.front().c_str());
        }
        names.pop_front();
    }
    return 0;
}

/**
 * Dynamically create an array of @ref Info pointers, and copy a list of pointers to
 * classes derived from @ref Info into it.
 * @param[in]   list    The list of pointers to copy
 *
 * @returns     array of copied pointers
 */
template <typename T> static const Info **createInfoArray(const std::list<const T*>& list)
{
    static std::list <std::shared_ptr<const Info*>> ptrList;
    size_t size = list.size() + 1; // +1 because array must be NULL terminated
    const Info **arr = new const Info *[size];
    size_t i=0;
    for (auto& val : list) {
        arr[i++] = val;
    }
    arr[i] = NULL;

    ptrList.emplace_back(std::shared_ptr<Info const *>(arr, std::default_delete<Info const *[]>()));

    return arr;
}


/**
 * A function illustrating how to use the API to control a non-continuous socwatch collection
 * @param[in,out]   handle          Handle to SoC Watch API
 *
 * @returns         0 on success, -1 on failure
 */
int stop(APIHandle *handle) {
    /*
     * Tell socwatch to stop collecting.
     */
    if (handle->stopCollection()) {
        fprintf(stderr, "Couldn't stop collection\n");
        /* Check stderr logs for error messages */
        return -1;
    }

    return 0;
}

/**
 * A function illustrating how to use the API to control a continuous socwatch collection
 * @param[in,out]   handle          Handle to SoC Watch API
 * @param[in]       sysInfo         System information
 * @param[in]       opts            Parsed command line options
 *
 * @returns         0 on success, -1 on failure
 */
int start_i(APIHandle *handle, SystemInfo const *sysInfo, const struct InputOptions& opts)
{
    /*
     * Retrieve target info
     */
    if (!sysInfo) {
        fprintf(stderr, "Couldn't get target info!\n");
        return -1;
    }

    /*
     * Retrieve a list of features that we wish to collect
     */
    std::list <const FeatureInfo *> features;
    std::list <std::string> featureNames = opts.m_features;
    if (featureNames.empty()) {
        fprintf(stderr, "No feature options provided!\n");
        return -1;
    }
    if (getFeatures(handle, featureNames, false/* not continuous */, features)) {
        fprintf(stderr, "Couldn't retrieve some features from API\n");
        return -1;
    }
    /*
     * Retrieve a list of output formats we're interested in
     */
    std::list <const OutputformatInfo *> outputFormats;
    std::list <std::string> names = opts.m_reports;
    if (names.empty()) {
        fprintf(stderr, "No output options provided!\n");
        return -1;
    }
    if (getOutputformats(handle, names, false/* not continuous */, outputFormats)) {
        fprintf(stderr, "Couldn't retrieve some output formats from API\n");
        return -1;
    }
    /*
     * Configure the socwatch collection
     */
    CollectionInfo* info = handle->getConfigurationInfo();
    info->setCollectionTime(opts.m_timeSecs); // Collection time of 0 means infinite collection duration; collection
                                    // will be terminated manually via call to 'stopCollection'
    info->setSamplingInterval(opts.m_intervalMSecs); // Sampling interval for sampled metrics; the default is 100 msecs if not specified
    info->setMaxDetail(true); // Tells socwatch to collect in max-detail mode
    info->setContinuous(opts.m_isContinuous); // Tells socwatch to not enable continuous profiling mode
    info->setOutputPath("SoCWatchOutput"); // Tells socwatch to write results to file "foo"
    info->setCollectionOptions(createInfoArray(features)); // Provides feature switches
    info->setPostProcessingOptions(createInfoArray(outputFormats)); // Provides requested output formats
                                                                 // An empty list means you only want the
                                                                 // summary CSV file

    /*
     * Configure the collection
     */
    if (handle->configureCollection(info)) {
        fprintf(stderr, "Couldn't configure collection\n");
        return -1;
    }
    /*
     * 'getReturnValue' will retrieve a return code from the last transaction
     */
    fprintf(stderr, "DEBUG: return code from 'configure' is %d\n", handle->getReturnValue());

    fprintf(stderr, "Starting collection...\n");
    /*
     * Tell socwatch to start collecting
     */
    if (handle->startCollection()) {
        fprintf(stderr, "Couldn't start collection\n");
        return -1;
    }

    return 0;
}

/**
 * initialize the handle state
 */
int initialize(APIHandle *handle, const struct InputOptions& opts)
{
    std::cout << "LIB Example called with the following parameters: " << std::endl;
    std::cout << opts << std::endl;

    if (!handle) {
        fprintf(stderr, "Couldn't retrieve a valid API handle!\n");
        return -1;
    }

    std::string workingDir = getCurrentWorkingDir();
    if (workingDir == "") {
        fprintf(stderr, "Error when determining current working directory : errnum %d\n", (int)(errno));
        return -1;
    }

    char const *configDir = opts.m_configDir.c_str();
    if (handle->initialize(configDir, workingDir.c_str(), true)) {
        fprintf(stderr, "Couldn't initialize API\n");
        return -1;
    }
    return 0;
}

/**
 * Function that configures a socwatch collection, controls it and then writes results to disk.
 *
 * @returns         0 on success, -1 on failure
 */
int start(APIHandle *handle, const struct InputOptions& opts)
{
    int retval = 0;
    // /*
    //  * Retrieve target info
    //  */

    const SystemInfo *sysInfo = NULL;
    if (handle->getTargetInfo(&sysInfo)) {
        fprintf(stderr, "Couldn't get target info!\n");
        return -1;
    } else {
        /*
        * Uncomment below to print debug info about target platform.
        */
        fprintf(stderr, "DEBUG: FMS = %s\n", sysInfo->getFMS());
        fprintf(stderr, "DEBUG: platform name = %s\n", sysInfo->getPlatformName());
        fprintf(stderr, "DEBUG: Host name = %s\n", sysInfo->getHostName());
        fprintf(stderr, "DEBUG: OS name = %s\n", sysInfo->getOSName());
        fprintf(stderr, "DEBUG: OS Type = %s\n", sysInfo->getOSType());
        fprintf(stderr, "DEBUG: OS Version = %s\n", sysInfo->getOSVersion());
        fprintf(stderr, "DEBUG: Bus freq = %s\n", sysInfo->getBusFreqMHz());
        fprintf(stderr, "DEBUG: Max Non-turbo freq = %s\n", sysInfo->getMaxNonTurboFreqMHz());
        fprintf(stderr, "DEBUG: LFM freq = %s\n", sysInfo->getLFMFreqMHz());
        fprintf(stderr, "DEBUG: HFM freq = %s\n", sysInfo->getHFMFreqMHz());
    }

    retval = start_i(handle, sysInfo, opts);
    return retval;
}

/**
 * Function that checks the correctness of the command line options.
 * @param[in]     parsedOpts      The datastructure with the options from cmd line.
 *
 * @returns       bool            Returns whether the cmd line options are acceptable.
 */
static bool checkParsedOptions(InputOptions& parsedOpts)
{
    if (parsedOpts.m_features.empty()) {
        fprintf(stderr, "ERROR: No feature options provided!\n");
        return false;
    }
    if (parsedOpts.m_reports.empty()) {
        if (parsedOpts.m_isContinuous == true) {
            fprintf(stderr, "WARNING: \"continuous\" collection requested, but no \"-r\" option selected; assuming \"-r lib\"\n");
            parsedOpts.m_reports.push_back("lib"); /* Default to 'binary' output */
        } else {
            parsedOpts.m_reports.push_back("int");
        }
    }

    return true;
}

/**
 * A structure detailing a commandline option.
 */
struct Option {
    std::string m_shortOption;
    std::string m_longOption;
    int m_value;
    bool m_requiresArg;
    std::string m_description;
    std::string m_usage;
    Option() : m_value(-1), m_requiresArg(false) {}
    Option(std::string const& s, std::string const& l,
           int v, bool r, std::string const& d, std::string const& h = "") : m_shortOption(s), m_longOption(l),
                                                                             m_value(v), m_requiresArg(r),
                                                                             m_description(d), m_usage(h) {}
};

/**
 * A basic commandline parser.
 */
class CmdlineParser {
    private:
        /**
         * An enumeration of token types for command line parsing.
         */
        enum TokType {
            TokType_NONE = 0,
            TokType_SHORT,
            TokType_LONG,
            TokType_DATA,
        };
    public:

        /**
         * An enumeration of possible return values from the command line parser
         */
        enum ParseVal {
            ParseVal_OK,
            ParseVal_HELP,
            ParseVal_ERROR,
        };

        CmdlineParser(std::list <struct Option> const& options) {}

        /**
         * The main parse function.
         * @param[in]   argc            Number of arguments passed via the commandline
         * @param[in]   argv            The commandline arguments
         * @param[in]   allowedOpts     Supported options
         * @param[out]  opts            The parsed options
         *
         * @returns     an @ref enum ParseVal value containing the parsing result
         */
        enum ParseVal parse(int argc, char *argv[], std::list<struct Option> const& allowedOpts, struct InputOptions& opts) {
            if (argc == 1) {
                return ParseVal_HELP;
            }

            size_t idx = 1;
            std::pair <TokType, std::string> currToken = nextToken_i(argv, idx), prevToken;
            struct Option prevOption;

            while (currToken.first != TokType_NONE) {
                std::string& arg = currToken.second;
                struct Option option;
                if (currToken.first == TokType_DATA) {
                    /* TODO: the below actions should really be retrieved from the 'allowdOpts' array */
                    switch (prevOption.m_value) {
                        case 'f':
                            if (std::find(opts.m_features.begin(), opts.m_features.end(), arg)
                                    == opts.m_features.end()) {
                                opts.m_features.emplace_back(arg);
                            }
                            break;
                        case 'r':
                            if (std::find(opts.m_reports.begin(), opts.m_reports.end(), arg)
                                    == opts.m_reports.end()) {
                                opts.m_reports.emplace_back(arg);
                            }
                            break;
                        case 't':
                            opts.m_timeSecs = strtoul(arg.c_str(), NULL, 0);
                            break;
                        case 'd':
                            opts.m_logLevel = (DataCallback_i::LogLevel)strtoul(arg.c_str(), NULL, 0);
                            break;
                        case 'n':
                            opts.m_intervalMSecs = strtoul(arg.c_str(), NULL, 0);
                            break;
                        default:
                            fprintf(stderr, "ERROR: unexpected data token %s\n", arg.c_str());
                            return ParseVal_ERROR;
                    }
                } else {
                    for (const auto &opt : allowedOpts) {
                        switch (currToken.first) {
                            case TokType_SHORT:
                                if (opt.m_shortOption != "") {
                                    if (arg == opt.m_shortOption) {
                                        option = opt;
                                    }
                                }
                                break;
                            case TokType_LONG:
                                if (opt.m_longOption != "") {
                                    if (arg == opt.m_longOption) {
                                        option = opt;
                                    }
                                }
                                break;
                            default:
                                break;
                        }
                        /* Short circuit for 'help' */
                        if (option.m_value == 'h') {
                            return ParseVal_HELP;
                        }
                        if (option.m_value != -1) {
                            break;
                        }
                    }
                    switch (option.m_value) {
                        case -1:
                            switch (currToken.first) {
                                case TokType_LONG: // fall-through
                                    arg = "-" + arg;
                                case TokType_SHORT:
                                    arg = "-" + arg;
                                    break;
                                default:
                                    break;
                            }
                            fprintf(stderr, "PARSE ERROR: invalid option %s\n", arg.c_str());
                            return ParseVal_ERROR;
                        case CONT:
                            opts.m_isContinuous = true;
                            break;
                    }
                }
                prevOption = option;
                prevToken = currToken;
                currToken = nextToken_i(argv, idx);
            }
            if (prevOption.m_requiresArg) {
                /* The last option parsed requires an argument but none was provided */
                fprintf(stderr, "ERROR: option \"%s\" requires an argument but none was provided!\n", prevToken.second.c_str());
                return ParseVal_ERROR;
            }
            return ParseVal_OK;
        }
    private:
        /**
         * Helper function that retrieves the next commandline token type
         * @param[in]       argv        The list of commandline arguments
         * @param[in,out]   currIdx     The current argument being parsed
         *
         * @returns     A {token type, token value} pair. A value of @ref TokType_NONE
         *              indicates an error
         */
        std::pair <TokType, std::string> nextToken_i(char *argv[], size_t& currIdx) {
            int tokType = TokType_NONE;
            char *arg = argv[currIdx++];
            if (!arg || !*arg) {
                /* Empty string */
                return {TokType_NONE, ""};
            }
            while (*arg == '-') {
                ++tokType;
                ++arg;
            }
            if (tokType > TokType_LONG) {
                /* More than 2 '-' not allowed */
                return {TokType_NONE, ""};
            }
            if (tokType == TokType_NONE) {
                tokType = TokType_DATA;
            }
            return {(enum TokType)tokType, std::string(arg)};
        }
};

/**
 * Function to print usage info
 * @param[in]   options     The list of allowed command line options
 */
static void usage_i(std::list<struct Option> const& options)
{
    std::cerr << "Usage: a.out <options>" << std::endl;
    std::cerr << "Where options are:" << std::endl;
    std::cerr << std::endl;
    std::cerr << std::setfill('-') << std::setw(117) << "-" << std::setfill(' ') << std::endl;
    std::cerr << std::setw(12) << "Short option" << std::setw(15) << "Long option" << std::setw(30) << "Usage" << std::setw(60) << "Description" << std::endl;
    std::cerr << std::setfill('-') << std::setw(117) << "-" << std::setfill(' ') << std::endl;
    for (const auto &opt : options) {
        std::string shortOpt = " ", longOpt = " ", usage = " ", desc = " ";
        if (opt.m_shortOption != "") {
            shortOpt = "-" + opt.m_shortOption;
        }
        if (opt.m_longOption != "") {
            longOpt = "--" + opt.m_longOption;
        }
        if (opt.m_usage != "") {
            usage = opt.m_usage;
        }
        if (opt.m_description != "") {
            desc = opt.m_description;
        }
        std::cerr << std::setw(12) << shortOpt;
        std::cerr << std::setw(15) << longOpt;
        std::cerr << std::setw(30) << usage;
        std::cerr << std::setw(60) << desc;
        std::cerr << std::endl;
    }
    std::cerr << std::endl;
}

/**
 * Main function
 * @param[in]   argc    Number of command line args
 * @param[in]   argv    Command line args
 *
 * @returns         0 on success, -1 on failure
 */
int main(int argc, char** argv)
{
    struct InputOptions parsedOpts;

    const std::list <struct Option> allowedOpts = {
        /* short opt, long opt, value, takes args?, help description, help usage */
        { "h", "help", 'h', false, "Display help output" },
        { "f", "feature", 'f', true, "Add a feature to collect", "-f <feature>" },
        { "r", "result", 'r', true, "Specify an output report", "-r <report>" },
        { "d", "debug-level", 'd', false, "Change debug logging level", "-d <[0-4]>"},
        { "t", "time", 't', true, "Specify collection time in seconds", "-t <seconds>" },
        { "n", "interval", 'n', true, "Specify collection sampling interval, in milliseconds", "-n <msec>" },
        { "", "continuous", CONT, false, "Specify continuous collection" },
        { "", "config-dir", SOC, true, "Specify socwatch configuration folder", "--config-dir <folder>" }
    };

    CmdlineParser parser(allowedOpts);

    switch (parser.parse(argc, argv, allowedOpts, parsedOpts)) {
    case CmdlineParser::ParseVal_HELP:
    case CmdlineParser::ParseVal_ERROR:
        usage_i(allowedOpts);
        return -1;
    default:
        break;
    }

    if (checkParsedOptions(parsedOpts) == false) {
        usage_i(allowedOpts);
        return -1;
    }

    {
        typedef struct APIHandle* (*get_api_handle_t)();
        get_api_handle_t getAPIHandle;
        void* libHandle = DL_OPEN(s_libSoCWatchName.c_str(), RTLD_NOW);
        if (libHandle) {
            getAPIHandle = (get_api_handle_t)DL_SYM(libHandle, "getAPIHandle");
            if (!getAPIHandle) {
                std::cout << "Unable to get getAPIHandle calls" << std::endl;
                return -1;
            }
        } else {
            std::cout << "Unable to open libSOCWatch: " << s_libSoCWatchName << std::endl;
            const char *_error = DL_ERROR();
            if (_error) {
                fprintf(stderr, "dlopen error: %s\n", _error);
            }
            return -1;
        }

        APIHandle* handle = (*getAPIHandle)();
        if (!handle) {
            fprintf(stderr, "Couldn't retrieve a valid API handle!\n");
            return -1;
        }

        // initialize the library
        initialize(handle, parsedOpts);
        handle->setCallback(new DataCallback_i());
        handle->setLoggingLevel(parsedOpts.m_logLevel);

        FeatureInfo const** features = NULL;
        if (handle->getAvailableFeatures(&features, parsedOpts.m_isContinuous)) {
            fprintf(stderr, "Couldn't retrieve a map of available features from API\n");
            return -1;
        }
        else {
            while (*features) {
                fprintf(stderr, "DEBUG: FEATURE = %s\n", (*features)->getName());
                ++features;
            }
        }

        OutputformatInfo const** outputs = NULL;
        if (handle->getAvailableOutputFormats(&outputs, parsedOpts.m_isContinuous)) {
            fprintf(stderr, "Couldn't retrieve a map of available outputs from API\n");
            return -1;
        }
        else {
            while (*outputs) {
                fprintf(stderr, "DEBUG: OUTPUT FORMAT = %s\n", (*outputs)->getName());
                ++outputs;
            }
        }

        start(handle, parsedOpts);
        std::cout << "LIB EXAMPLE RUNNING" << std::endl;
        size_t timeSecs = parsedOpts.m_timeSecs;
        if (!parsedOpts.m_isContinuous) {
            /*
             * If it's a specified duration collection, the collection stops correctly after the
             * duration, but give an additional second before calling stopCollection()
             */
            timeSecs++;
        }
        SLEEP(timeSecs);
        std::cout << "LIB EXAMPLE STOPPING" << std::endl;
        /*
         * If running a non-continuous collection and for a specified duration, please make
         * sure to call stopCollection() after the specified duration.
         */
        stop(handle);
        std::cout << "LIB EXAMPLE STOPPED" << std::endl;

        /*
         * Explicitly tell library to release resources before closing the library
         */
        handle->destroy();

        typedef void (*free_api_handle_t)();
        free_api_handle_t freeAPIHandle;
        freeAPIHandle = (free_api_handle_t)DL_SYM(libHandle, "freeAPIHandle");
        if (!freeAPIHandle) {
            std::cout << "Unable to free API handle" << std::endl;
            return -1;
        }
        (*freeAPIHandle)();

        if (libHandle) {
            DL_CLOSE(libHandle);
        }
    }

    return 0;
}

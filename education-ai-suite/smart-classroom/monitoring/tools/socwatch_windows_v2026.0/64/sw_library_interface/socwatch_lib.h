/* ********************************************************************************
 # INTEL CONFIDENTIAL
 # Copyright 2018 - 2019 Intel Corporation.

 # This software and the related documents are Intel copyrighted materials, and
 # your use of them is governed by the express license under which they were
 # provided to you (License). Unless the License provides otherwise, you may not
 # use, modify, copy, publish, distribute, disclose or transmit this software or
 # the related documents without Intel's prior written permission.

 # This software and the related documents are provided as is, with no express or
 # implied warranties, other than those that are expressly stated in the License.
 # ********************************************************************************/

#ifndef __SOCWATCH_LIB_H__
#define __SOCWATCH_LIB_H__

#ifdef SWW_MERGE
    #ifdef LIBSWAPI_EXPORTS
        #define SW_LIBRARY_API __declspec(dllexport)
    #else
        #define SW_LIBRARY_API __declspec(dllimport)
    #endif // LIBSWAPI_EXPORTS
#else // !SWW_MERGE
    #define SW_LIBRARY_API
#endif // SWW_MERGE

/**
 * An enumeration of 'Info' types
 */
enum InfoType {
    InfoType_FEATURE,
    InfoType_OUTPUT,
    InfoType_SYSTEM,
    InfoType_NONE,
};

/**
 * Base for all 'Info' instances
 */
struct SW_LIBRARY_API Info {
    virtual ~Info() = default;

    /**
     * Retrieve the type of this info instance
     *
     * @returns     the @ref Info type
     */
    virtual enum InfoType getType() const = 0;

    /**
     * Retrieve name for this Info.
     *
     * @returns     the name
     */
    virtual char const *getName() const = 0;

    /**
     * Retrieve descriptor for this Info.
     *
     * @returns     the descriptor
     */
    virtual char const *getDescription() const = 0;

    /**
     * Check if this @ref Info instance supports continuous collections
     *
     * @returns     true if supports continuous collections
     */
    virtual bool doesSupportContinuousCollection() const = 0;
};

/**
 * An Info type to describe collection features i.e. "-f core-temp" and "-f sys"
 */
struct SW_LIBRARY_API FeatureInfo : virtual public Info {
    virtual ~FeatureInfo() = default;

    /**
     * Check if this FeatureInfo instance is actually a 'group' feature.
     *
     * @returns     true    if group.
     */
    virtual bool isGroup() const = 0;
};

/**
 * An Info type to describe output formats i.e. "-r int"
 */
struct SW_LIBRARY_API OutputformatInfo : virtual public Info {
    virtual ~OutputformatInfo() = default;

    /**
     * Retrieve the suffix associated with this @ref OutputformatInfo instance
     * For instance, "-r vtune " has a suffix of ".pwr" while "-r int" has a suffix
     * of "_trace.csv"
     *
     * @returns     The suffix
     */
    virtual char const *getFileSuffix() const = 0;
};

/**
 * An Info type to describe  information about the target system
 */
struct SW_LIBRARY_API SystemInfo : virtual public Info {
    virtual ~SystemInfo() = default;

    /**
     * Retrieve target system cpuid i.e. Family, Model, Stepping
     *
     * @returns     the FMS value
     */
    virtual char const *getFMS() const = 0;

    /**
     * Retrieve target system platform name
     *
     * @returns     the platform name
     */
    virtual char const *getPlatformName() const = 0;

    /**
     * Retrieve target system host name
     *
     * @returns     the host name
     */
    virtual char const *getHostName() const = 0;

    /**
     * Retrieve target system OS name
     *
     * @returns     the OS name
     */
    virtual char const *getOSName() const = 0;

    /**
     * Retrieve target system OS type
     *
     * @returns     the OS type
     */
    virtual char const *getOSType() const = 0;

    /**
     * Retrieve target system OS version
     *
     * @returns     the OS version
     */
    virtual char const *getOSVersion() const = 0;

    /**
     * Retrieve target system bus frequency
     *
     * @returns     the bus frequency
     */
    virtual char const *getBusFreqMHz() const = 0;

    /**
     * Retrieve max non-turbo frequency of target system (i.e. TSC frequency)
     *
     * @returns     the max non-turbo frequency
     */
    virtual char const *getMaxNonTurboFreqMHz() const = 0;

    /**
     * Retrieve LFM frequency of target system
     *
     * @returns     the LFM frequency
     */
    virtual char const *getLFMFreqMHz() const = 0;

    /**
     * Retrieve HFM frequency of target system
     *
     * @returns     the HFM frequency
     */
    virtual char const *getHFMFreqMHz() const = 0;

    /**
     * Retrieve SoC Watch EXE version
     *
     * @returns     the app version
     */
    virtual char const *getEXEVersion() const = 0;

    /**
     * Retrieve SoC Watch driver version
     *
     * @returns     the driver version
     */
    virtual char const *getDriverVersion() const = 0;
};

/**
 * A structure to encode arguments to pass to socwatch
 * to configure the collection.
 */
class SW_LIBRARY_API CollectionInfo {
    public:
    /**
     * set the collection duration if desired
     *
     * @param[in] timeSec   time in seconds
     */
    virtual void setCollectionTime(size_t timeSec) = 0;

    /**
     * get the collection duration
     *
     * @returns time in seconds
     */
    virtual size_t getCollectionTime() const = 0;

    /**
     * set the sampling interval (defaults to 100 milli-seconds)
     *
     * @param[in] timeMilliSec  time in milli-seconds
     */
    virtual void setSamplingInterval(size_t timeMilliSec) = 0;

    /**
     * get the sampling interval
     *
     * @returns time in milli seconds
     */
    virtual size_t getSamplingInterval() const = 0;

    /**
     * set the callback interval (defaults to 1 second)
     *
     * @param[in] timeMilliSec time in milli-seconds
     */
    virtual void setCallbackInterval(size_t timeMilliSec) = 0;

    /**
     * get the callback interval
     *
     * @returns time in milli seconds
     */
    virtual size_t getCallbackInterval() const = 0;

    /**
     * set max detail flag
     *
     * @param[in] isMax true to set the flag
     */
    virtual void setMaxDetail(bool isMax) = 0;

    /**
     * check if max detail flag is set
     *
     * @returns flag state
     */
    virtual bool isMaxDetail() const = 0;

    /**
     * set continuous flag
     *
     * @param[in] isContinuous  true to set the flag
     */
    virtual void setContinuous(bool isContinuous) = 0;

    /**
     * check if continuous mode flag is set
     *
     * @returns flag state
     */
    virtual bool isContinuous() const = 0;

    /**
     * set the output path
     *
     * @param[in] outputPath   the output path for any file writer
     */
    virtual void setOutputPath(const char *outputPath) = 0;

    /**
     * get the output path
     *
     * @returns the output path for any file writer
     */
    virtual const char *getOutputPath() const = 0;

    /**
     * set the path of a program to run
     *
     * @param[in] exePath   the path of a program to run
     */
    virtual void setProgramToProfile(const char *exePath) = 0;

    /**
     * get the path of a program to run
     *
     * @returns get path of a program to run
     */
    virtual const char *getProgramToProfile() const = 0;

    /**
     * set data to collect
     *
     * @param[in] collectionOptions array of @ref FeatureInfo pointers of data to collect
     */
    virtual void setCollectionOptions(const Info **collectionOptions) = 0;

    /**
     * get the @ref FeatureInfo pointers selected for this configuration
     *
     * @returns the @ref FeatureInfo pointers selected for this configuration
     */
    virtual const Info** getCollectionOptions() const = 0;

    /**
     * set post processing info
     *
     * @param[in] postProcessingOptions     array of @ref OutputformatInfo* pointers for this configuration
     */
    virtual void setPostProcessingOptions(const Info **postProcessingOptions) = 0;

    /**
     * get post processing info
     *
     * @returns array of OutputformatInfo* pointers for this configuration
     */
    virtual const Info** getPostProcessingOptions() const = 0;
};

/**
 * Handle to the API interface.
 */
struct SW_LIBRARY_API APIHandle {
    virtual ~APIHandle() = 0;

    /**
     * Initialize API instance. Must be first function called.
     * @param[in]   configFilePath  Directory(s) where plugin config files are located
     * @param[in]   workingDir      Directory for API to use to store logs and results
     * @param[in]   create          True if the path pointed to by @ref workingDir
     *                              must be created
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int initialize(const char *configFilePath, char const *workingDir, bool create) = 0;

    /**
     * Destroy API instance. Must be called once SoCWatch library use is complete.
     * Essentially, the last function called.
     */
    virtual void destroy() = 0;

    /**
     * Set the debug output level
     *
     * @param[in]  level    set the level of debug information output from 0-4 with 0 being least verbose
     */
    virtual void setLoggingLevel(pwr::lib::DataCallback::LogLevel level) = 0;

    /**
     * Retrieve a list of collection options.
     *
     * @param[out]  options                         Pointer to an array of @ref Info pointers. On successful return this
     *                                              will contain all @ref Info instances supported by the current architecture
     *                                              and will be NULL terminated. Must be feed by caller.
     * @param[in]   requireContinuousCollection     True if the options should be valid for continuous collections
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int getCollectionOptions(Info const ***options, /* Will be NULL terminated */
                                     bool requireContinuousCollection=false) = 0;

    /**
     * Retrieve features that may be collected on the target machine. This is a subset of
     * the list of collection options retrieved via @ref getCollectionOptions; it includes
     * only the features (i.e. "-f <feature>").
     *
     * @param[out]  features                        Pointer to an array of @ref FeatureInfo pointers. On successful return this
     *                                              will contain a list of @ref FeatureInfo instances supported by the current
     *                                              architecture, and will be NULL terminated. Must be freed by called.
     * @param[in]   requireContinuousCollection     True if the options should be valid for continuous collections
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int getAvailableFeatures(FeatureInfo const ***features, /* NULL terminated */
                                     bool requireContinuousCollection=false) = 0;

    /**
     * Retrieve features corresponding to the various names contained in @ref featureNames and store in
     * an array of @ref FeatureInfo pointers. The array will be NULL terminated.
     * NULL value indicates the requested feature is not supported on the target platform.
     *
     * @param[in]   featureNames                    A NULL-terminated list of requested feature names.
     * @param[out]  features                        Pointer to an array of @ref FeatureInfo pointers. On successful return
     *                                              this will contain a NULL terminated list of @ref FeatureInfo instances
     *                                              corresponding to the individual feature names specified in @ref featureNames
     *                                              (a NULL indicates the feature is not supported). Must be feed by caller.
     * @param[in]   requireContinuousCollection     True if the options should be valid for continuous collections
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int getAvailableFeatures(char const **featureNames, /* NULL terminated */
                                     FeatureInfo const ***features, /* Will be NULL terminated */
                                     bool requireContinuousCollection=false) = 0;

    /**
     * Retrieve a list of post-processing options.
     *
     * @param[out]  options                         Pointer to an array of @ref Info pointers. On successful return this
     *                                              will contain a NULL terminated list of all @ref Info instances that are
     *                                              valid for the current architecture. Must be feed by caller.
     * @param[in]   requireContinuousCollection     True if the options should be valid for continuous collections
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int getPostProcessingOptions(const Info ***options, /* Will be NULL terminated */
                                         bool requireContinuousCollection=false) = 0;

    /**
     * Retrieve valid output formats. This is a subset of the list of post-processing options retrieved via
     * @ref getPostProcessingOptions; it includes only the output formats (i.e. "-r <format>").
     *
     * @param[out]  formats                         Pointer to an array of @ref OutputformatInfo pointers. On successful return
     *                                              this will contain a NULL terminated list of all @ref OutputformatInfo instances
     *                                              that are supported on the current architecture. Must be feed by caller.
     * @param[in]   requireContinuousCollection     True if the options should be valid for continuous collections
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int getAvailableOutputFormats(OutputformatInfo const ***formats, /* Will be NULL terminated */
                                          bool requireContinuousCollection=false) = 0;

    /**
     * Retrieve output formats corresponding to the various names contained in @ref outputFormatNames and store in
     * a map with key == output format name and value == OutputformatInfo class corresponding to the format name. A
     * NULL value indicates the requested format is not supported on the target platform.
     *
     * @param[in]   outputformatNames               A NULL-terminated list of requested output format names.
     * @param[out]  formats                         Pointer to an array of @ref OutputformatInfo pointers. On successful return
     *                                              this will contain a NULL-terminated list of @ref OutputformatInfo instances
     *                                              corresponding to the output formats in @ref outputformatNames (a NULL indicates
     *                                              the corresponding output format is not supported).
     * @param[in]   requireContinuousCollection     True if the options should be valid for continuous collections
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int getAvailableOutputFormats(char const **outputformatNames, /* NULL terminated */
                                          OutputformatInfo const ***formats, /* Will be NULL terminated */
                                          bool requireContinuousCollection=false) = 0;

    /**
     * Retrieve information about the target system.
     *
     * @param[out]  info    Pointer to memory area containing information @ref SystemInfo
     *                      about the target system.
     *
     * @returns 0 on success, negative on error (error code is TBD). On error
     * the contents of @ref info are undefined.
     */
    virtual int getTargetInfo(SystemInfo const **info) = 0;

    /**
     * Get API version number.
     *
     * @param[out]  major       The major version
     * @param[out]  minor       The minor version
     * @param[out]  other       The bugfix version
     */
    virtual void getAPIVersion(uint8_t& major, uint8_t& minor, uint8_t& other) = 0;

    /**
     * Get an object to configure the collection
     *
     * @returns an object the user can use to configure a collection
     */
    virtual CollectionInfo* getConfigurationInfo() = 0;

    /**
     * Configure an SoC Watch collection.
     *
     * @param[in]   info    Structure containing parameters for collection.
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int configureCollection(const CollectionInfo* info) = 0;

    /**
     * Start a previously configured collection.
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int startCollection() = 0;

    /**
     * Stop a running collection.
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int stopCollection() = 0;

    /**
     * Cancel a running collection.
     *
     * @returns 0 on success, negative on error (error code is TBD)
     */
    virtual int cancelCollection() = 0;

    /**
     * Retrieve return code of last completed transaction.
     *
     * @returns 0 on success, negative on failure (error code is TBD)
     */
    virtual int getReturnValue() const = 0;

    /**
     * Reset API instance. Must be called between collections. Use this API only
     * if you wish to conduct back-to-back collections. This function MUST be called
     * before the next invocation of 'configureCollection'
     * NOTE: Multiple collections are currently not supported
     *
     * @returns     0 on success
     */
    virtual int reset() = 0;

    /**
     * Retrieve return code of last completed transaction.
     *
     * @returns 0 on success, negative on failure (error code is TBD)
     */
    virtual int setCallback(pwr::lib::DataCallback* callback) = 0;
};

/**
 * Clients call this function to retrieve a pointer to an API handle
 * that they can then use to manipulate socwatch
 *
 * @returns Pointer to API handle if successful, NULL on failure.
 */
extern "C" SW_LIBRARY_API APIHandle *getAPIHandle();

/**
 * Clients call this function to free the instance of the APIHandle
 *
 * @returns void
 */
extern "C" SW_LIBRARY_API void freeAPIHandle();

#endif // __SOCWATCH_LIB_H__

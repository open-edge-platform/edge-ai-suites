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

#ifndef __SOCWATCH_DATA_H__
#define __SOCWATCH_DATA_H__

#include <string>

namespace pwr {
    namespace lib {
#ifdef _WIN32
        typedef unsigned int pw_u32_t;
        typedef unsigned long long pw_u64_t;
#else
        typedef uint32_t pw_u32_t;
        typedef uint64_t pw_u64_t;
#endif

        /**
         * This class decodes a single element of data in the data stream
         */
        class MetricData {
        public:
            virtual ~MetricData() = default;
            /**
             * get the unique id for this data
             *
             * @returns an id that identifies the metric
             */
            virtual int getId() const = 0;

            /**
             *  A unique object describing an hardware or software entity to
             *  to which the data we collect pertains.
             *  Examples of entities:
             *  Core_0, Core_1, etc are entities when collecting CPU C-States
             *  Core_0, Core_1, etc are entities when collecting Core Temperature
             *  GPU is an entity for Graphics C-States
             *
             * @returns string identifying the entity
             */
            virtual std::string getEntity() const = 0;

            /**
             *  A description or state for this data
             *
             * @returns string of the state if it exists
             */
            virtual std::string getDescriptor() const = 0;

            /**
             *  The end timestamp for this data
             *
             * @returns 64 bit value for the timestamp of this value
             */
            virtual pw_u64_t getTimestamp() const = 0;

            /**
             *  The duration for this data
             *
             * @returns the duration of this sample
             */
            virtual double getDuration() const = 0;

            /**
             *  The value for this data
             *
             * @returns value associated with this data
             */
            virtual double getValue() const = 0;
        };

        /**
         * A set of meta data for the system
         */
        class Metadata {
        public:
            virtual ~Metadata() = default;
            /**
             * @returns the system platform id
             */
            virtual pw_u32_t getPlatformId() const = 0;

            /**
             * @returns the system platform name
             */
            virtual std::string getPlatformName() const = 0;

            /**
             * @returns the system cpu name
             */
            virtual std::string getCPUName() const = 0;

            /**
             * @returns the system cpu name
             */
            virtual std::string getCPUNativeName() const = 0;

            /**
             * @returns the system pch name
             */
            virtual std::string getPCHName() const = 0;

            /**
             * @returns the system host name
             */
            virtual std::string getHostName() const = 0;

            /**
             * @returns the number of packages in the system
             */
            virtual int getNumPackages() const = 0;

            /**
             * @returns the number of modules in the system
             */
            virtual int getNumModules() const = 0;

            /**
             * @returns the number of cores in the system
             */
            virtual int getNumCores() const = 0;

            /**
             * @returns the number of hardware threads in the system
             */
            virtual int getNumThreads() const = 0;

            /**
             * @returns the HFM frequency
             */
            virtual float getHFMFreqency() const = 0;

            /**
             * @returns the LFM frequency
             */
            virtual float getLFMFreqency() const = 0;

            /**
             * @returns the nominal CPU frequency
             */
            virtual float getCPUFreqency() const = 0;

            /**
             * @returns the bus frequency
             */
            virtual float getBusFrequency() const = 0;

            /**
             * @returns os name
             */
            virtual std::string getOSName() const = 0;

            /**
             * @returns os type
             */
            virtual std::string getOSType() const = 0;

            /**
             * @returns os version
             */
            virtual std::string getOSVersion() const = 0;
            /**
             * @returns clock frequency (in MHz)
             */
            virtual float getClockFrequencyMHz() const = 0;
        };

        /**
         * class used to decode the data descriptions from the library
         */
        class DataDescription {
        public:
            virtual ~DataDescription() = default;
            /**
             * @returns name of the feature associated with the data id
             */
            virtual std::string getFeatureName() const = 0;

            /**
             * @returns name of the feature associated with the data id
             */
            virtual std::string getName() const = 0;

            /**
             * @returns description of the units associated with the data id
             */
            virtual std::string getUnitDescription() const = 0;

            /**
             * @returns unit string associated with the data id
             */
            virtual std::string getUnitText() const = 0;

            /**
             * @returns string describing the type of data
             */
            virtual std::string getType() const = 0;

            /**
             * @returns string describing the type of data
             */
            virtual std::vector<std::string> getStates() const = 0;
        };

        /**
         * class used to decode the data bundle from the library
         */
        class DataBundle {
        public:
            virtual ~DataBundle() = default;

            /**
             * @returns start timestamp for this group of data
             */
            virtual pw_u64_t getStartTimestamp() const = 0;

            /**
             * @returns end timestamp for this group of data
             */
            virtual pw_u64_t getEndTimestamp() const = 0;

            /**
             * @returns duration for this group of data in seconds
             */
            virtual double getDuration() const = 0;

            /**
             * @returns system metadata
             */
            virtual Metadata* getMetadata() const = 0;

            /**
             * @returns vector of data
             */
            virtual std::list<MetricData*> getData() const = 0;

            /**
             * @param[in] data  the data object to get the description for
             * @returns the description of this data
             */
            virtual DataDescription* getDataDescription(const MetricData& data) const = 0;
        };

        /**
         * Class that should be implemented by the library users
         */
        class DataCallback {
            public:
                // TODO: Consider changing to enum class
                /**
                 * Enumeration listing the logging severity levels used by SoCWatch
                 */
                enum class LogLevel {
                    Fatal=0,     /* Print FATALs */
                    Error=1,     /* Print FATALs + ERRORs */
                    Warning=2,   /* Print FATALs + ERRORs + WARNINGs */
                    Debug=3,     /* Print FATALs + ERRORs + WARNINGs + DEBUGs */
                    Info=4,      /* Print FATALs + ERRORs + WARNINGs + DEBUGs + INFORMATIONALs */
                    Force=Fatal, /* Print FATALs */
                };

                /**
                 * Callback to send socwatch log statements to a socwatch library user
                 * @param[in] level log statement severity level, one of @ref LogLevel
                 * @param[in] msg   log statement string sent from socwatch
                 */
                virtual void log(LogLevel level, const char* msg) = 0;

                /**
                 * Callback to send data to a socwatch library user
                 * NOTE: Data objects are not guaranteed to live past the callback function invocation
                 * @param[in] bundle    bundle of data sent from the collector
                 */
                virtual void onDataReady(const DataBundle* bundle) = 0;

                /**
                 * Virtual destructor
                 */
                virtual ~DataCallback() {};
        };
    }
}
#endif

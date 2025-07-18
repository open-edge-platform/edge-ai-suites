/*
 * INTEL CONFIDENTIAL
 * 
 * Copyright (C) 2021-2024 Intel Corporation.
 * 
 * This software and the related documents are Intel copyrighted materials, and your use of
 * them is governed by the express license under which they were provided to you (License).
 * Unless the License provides otherwise, you may not use, modify, copy, publish, distribute,
 * disclose or transmit this software or the related documents without Intel's prior written permission.
 * 
 * This software and the related documents are provided as is, with no express or implied warranties,
 * other than those that are expressly stated in the License.
*/
#ifndef HVA_HVANODE_HPP
#define HVA_HVANODE_HPP

#include <memory>
#include <deque>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <unordered_map>
#include <inc/api/hvaBlob.hpp>
#include <inc/util/hvaUtil.hpp>
#include <inc/api/hvaEvent.hpp>
#include <inc/impl/hvaEventManager.hpp>
#include <inc/buffer/hvaProtocol.hpp>
#include <inc/api/hvaNodeRegistry.hpp>
#include <inc/impl/hvaState.hpp>
#include <inc/util/hvaPerformanceMonitor.hpp>
#include <list>
#include <atomic>
#include <vector>

namespace hva{

enum hvaPortPolicy_t{
    HVA_BLOCKING_IF_FULL = 0,   // block the call if port is full 
    HVA_DISCARD_IF_FULL         // discard the content and return the call if port is full
};

using hvaConvertFunc = std::function<hvaBlob_t::Ptr(hvaBlob_t::Ptr)>;
using hvaDataQueue_t = std::list<hvaBlob_t::Ptr>;

class hvaInPort_t;
class hvaOutPort_t;
class hvaNode_t;

/**
* hvaInPort_t and hvaOutPort_t are structs that connects each pair of successive nodes. Besides
* hvaInPort_t additionally holds a buffer queue where all input buffers are stored.
*
* Users normally should not construct the class by themselves but rather through hvaNode_t::hvaNode_t()
*/
class hvaInPort_t{
friend class hvaPipeline_t;
friend class hvaNode_t;
friend class hvaBatchingConfig_t;
public:
    hvaInPort_t(hvaNode_t* parentNode, hvaOutPort_t* prevPort, size_t queueSize = 4);

    hvaInPort_t(hvaNode_t* parentNode);

    void setProtocol(const hvaProtocol_t& proto);

    const hvaProtocol_t& getProtocol() const;

    hvaBlob_t::Ptr& front();

    void pop();

    hvaStatus_t tryPush(hvaBlob_t::Ptr data);

    /**
    * @brief push a blob to this port's buffer queue
    * 
    * @param data blob to be pushed
    * @param timeout timeout before this call returns. Set to 0 to make it blocking forever
    * @return status code
    * 
    */
    hvaStatus_t push(hvaBlob_t::Ptr data, ms timeout = ms(0));

    void clear();

    void setPortQueuePolicy(hvaPortPolicy_t policy);

    const hvaState_t& getState() const;

    hvaStatus_t transitStateTo(hvaState_t state);

    void transitStateToStopForced();

    bool selectProtocol(const std::string keystring);

    void setQueueSize(size_t size);

private:
    void setPrevPort(hvaOutPort_t* prevPort);

    std::mutex m_mutex;
    std::condition_variable m_cv_empty;
    std::condition_variable m_cv_full;
    size_t m_queueSize;
    hvaPortPolicy_t m_policy;
    hvaNode_t* m_parentNode;
    hvaOutPort_t* m_prevPort;
    hvaDataQueue_t m_inQueue;
    hvaState_t m_state;
    hvaProtocol_t m_protocol;
};

class hvaPipeline_t;

/**
* hvaInPort_t and hvaOutPort_t are structs that connects each pair of successive nodes. Besides
* hvaOutPort_t holds a function pointer used for user-defined blob conversion function in case
* the blob transmitted between two successive nodes does not match
*
* Users normally should not construct the class by themselves but rather through hvaNode_t::hvaNode_t()
*/
class hvaOutPort_t{
friend class hvaPipeline_t;
friend class hvaNode_t;
public:
    hvaOutPort_t(hvaNode_t* parentNode, hvaInPort_t* nextPort);

    hvaOutPort_t(hvaNode_t* parentNode);

    std::vector<hvaInPort_t*>& getNextPorts();

    /**
    * @brief call the holded blob conversion function
    * 
    * @param data the blob to be converted 
    * @return a shared pointer to the blob after conversion
    * 
    */
    hvaBlob_t::Ptr convert(hvaBlob_t::Ptr data) const;

    /**
    * @brief check if the holded conversion function is valid
    * 
    * @param void
    * @return true if valid
    * 
    */
    bool isConvertValid() const;

    void setProtocol(const hvaProtocol_t& proto);

    const hvaProtocol_t& getProtocol() const;

    bool selectProtocol(const std::string keystring);

private:
    void setNextPort(hvaInPort_t* nextPort);

    void setConvertFunc(hvaConvertFunc func);

    hvaNode_t* m_parentNode;
    // one output port can be connected to multiple input ports
    std::vector<hvaInPort_t*> m_nextPorts;
    hvaConvertFunc m_convertFunc;
    hvaProtocol_t m_protocol;
};

class HVA_DECLSPEC hvaBatchingConfig_t{
public:
    enum BatchingPolicy : unsigned{
        BatchingIgnoringStream = 0x1,           ///< batching algorithm ignoring the blob's stream id and frame id. default

        BatchingWithStream = 0x2,               ///< if set to BatchingWithStream, node workers only fetches the
                                                ///<  blobs corrosponding to its assigned batch index, and frame id would be fetched strictly in order.
                                                // Note that:
                                                ///<  according to user definition, a single batch index may refer 
                                                ///<  to multiple stream id
        BatchingIgnoreOrderWithStream = 0x3,  ///< if set to BatchingIgnoreOrderWithStream, node workers only fetches the
                                                ///<  blobs corrosponding to its assigned batch index, and frame id order can be ignored.
                                                // Note that:
                                                ///<  according to user definition, a single batch index may refer 
                                                ///<  to multiple stream id
        Reserved = 0x4
    };

    hvaBatchingConfig_t();

    unsigned batchingPolicy;
    std::size_t batchSize;
    std::size_t streamNum;
    std::size_t threadNumPerBatch;

    /**
    * @brief function pointer to batching algorithm
    *           batching algorithm could be default batching or provided by user
    *           batching algorithm should control mutex and cv
    * 
    * @param batchIdx batch index
    * @param vPortIdx vector of port index
    * @param pNode pointer to node
    * @return output blob vector(when batching fail, vector is empty)
    * 
    */
    std::function<std::vector<hvaBlob_t::Ptr> (std::size_t batchIdx, std::vector<std::size_t> vPortIdx, hvaNode_t* pNode)> batchingAlgo = nullptr;

    /**
     * @brief default batching algorithm 
     *  action: ignoring the blob's stream id and frame id.
     * @param batchIdx batch index
     * @param vPortIdx vector of port index
     * @param pNode pointer to node
     * @return output blob vector(when batching fail, vector is empty)
    */
    static std::vector<hvaBlob_t::Ptr> defaultBatching(std::size_t batchIdx, std::vector<std::size_t> vPortIdx, hvaNode_t* pNode);

    /**
     * @brief node workers only fetches the blobs corrosponding to its assigned batch index, 
     *          and frame id would be fetched strictly in order.
     * @param batchIdx batch index
     * @param vPortIdx vector of port index
     * @param pNode pointer to node
     * @return output blob vector(when batching fail, vector is empty)
    */
    static std::vector<hvaBlob_t::Ptr> streamBatching(std::size_t batchIdx, std::vector<std::size_t> vPortIdx, hvaNode_t* pNode);

    /**
     * @brief node workers only fetches the blobs corrosponding to its assigned batch index, 
     *          and frame id order can be ignored
     * @param batchIdx batch index
     * @param vPortIdx vector of port index
     * @param pNode pointer to node
     * @return output blob vector(when batching fail, vector is empty)
    */
    static std::vector<hvaBlob_t::Ptr> streamBatchingIgnoreOrder(std::size_t batchIdx, std::vector<std::size_t> vPortIdx, hvaNode_t* pNode);
};

class hvaNodeWorker_t;

/**
* @brief elementary nodes to form a pipeline
* 
* hvaNode_t, different from hvaNodeWorker_t, is the struct that stores a pipeline node's topological
* information, e.g. nodes it connects to, as well as some common utilities that will be shared across
* the node workers it spawned. A node may spawn multiple copies of node workers it associates to
*/
class HVA_DECLSPEC hvaNode_t{
friend class hvaPipeline_t;
friend class hvaBatchingConfig_t;
friend class hvaInPort_t;
public:
    
    /**
    * @brief constructor of a node
    * 
    * @param inPortNum number of in ports this node should have. Note that those ports can leave as 
    *           not-connected
    * @param outPortNum number of out ports this node should have. Note that those ports can leave as 
    *           not-connected
    * @param totalThreadNum number of workers it should spawn
    * @return void
    * 
    */
    hvaNode_t(std::size_t inPortNum, std::size_t outPortNum, std::size_t totalThreadNum);

    virtual ~hvaNode_t();

    /**
    * @brief Constructs and returns a nodeworker instance. Users are expected to 
    *           implement this function while extending node class. 
    * 
    * @param void
    * @return share pointer to the node worker constructed
    * 
    */
    virtual std::shared_ptr<hvaNodeWorker_t> createNodeWorker() const = 0;

    /**
    * @brief configure the batching config and policy of this node
    * 
    * @param config the batching config
    * @return void
    * @sa hvaBatchingConfig_t
    * 
    */
    virtual void configBatch(const hvaBatchingConfig_t& config);
    /**
    * @copydoc hvaBuf_t::configBatch(const hvaBatchingConfig_t& config)
    */
    virtual void configBatch(hvaBatchingConfig_t&& config);

    /**
    * @brief configure the time interval between each successive call of process. This defaults 
    *           to zero if not called and thus will free-wheeling or blocked on getBatchedInput
    * 
    * @param interval time interval in ms
    * @return void 
    * 
    */
    void configLoopingInterval(ms interval);

    /**
    * @brief get inputs stored in node's in port. For active nodes this call is set to blocking while
    *           for passive nodes this would set to non-blocking
    * 
    * @param batchIdx the batch index that node would like fetch. This usually sets to the argument passed
    *           from process() call
    * @return vector of shared pointer to blobs fetched. If no requested blobs found in port, this will 
    *           return an empty vector
    * 
    */
    virtual std::vector<hvaBlob_t::Ptr> getBatchedInput(std::size_t batchIdx, std::vector<std::size_t> vPortIdx, ms timeout = ms(0));

    /**
    * @brief get number of in ports
    * 
    * @param void
    * @return number of in ports
    * 
    */
    std::size_t getInPortNum();

    /**
    * @brief get number of out ports
    * 
    * @param void
    * @return number of outports
    * 
    */
    std::size_t getOutPortNum();

    /**
    * @brief clear all the caching buffers stored within in ports
    * 
    * @param void
    * @return void
    * 
    */
    void clearAllPorts();

    /**
    * @brief send output to the next node connected at port index
    * 
    * @param data blob to be sent
    * @param portId the port index blob would be sent to
    * @param timeout the maximal timeout before this function returns. Set to zero to make it blocking
    * @return status code
    * 
    */
    hvaStatus_t sendOutput(hvaBlob_t::Ptr data, std::size_t portId, ms timeout);

    /**
    * @brief To perform any necessary operations when pipeline's rearm is called
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    * this rearm function is expected to be called when pipeline resides in state of stop, and users 
    * wish to reuse this pipeline instance and transit it into prepared state. By calling this function
    * each node's rearm function is also called
    * @sa hvaPipeline_t::rearm()
    * 
    */
    virtual hvaStatus_t rearm();

    /**
    * @brief reset this node
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    virtual hvaStatus_t reset();

    /**
    * @brief prepare and intialize this hvaNode_t instance
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    * Note that users expect not to call this function by themselves but rather through hvaPipeline_t::prepare()
    * Node writers can have various initialization steps within implementation of this function. 
    * 
    */
    virtual hvaStatus_t prepare();

    /**
    * @brief finalize this node instance before stop
    * 
    * @param void
    * @return void
    * 
    * no return value as each node should guarantee it could stop successfully, even by force. This function will
    * only be triggered once per pipeline lifetime before pipeline stops
    */
    virtual void finalize();

    /**
    * @brief return the number of threads associated with this node
    * 
    * @param void
    * @return number of threads
    * 
    */
    std::size_t getTotalThreadNum();

    /**
    * @brief return a pointer to batching config of this node
    * 
    * @param void
    * @return pointer to batching config
    * 
    */
    const hvaBatchingConfig_t* getBatchingConfigPtr();

    /**
    * @brief return a const reference to batching config of this node
    * 
    * @param void
    * @return const reference to batching config
    * 
    */
    const hvaBatchingConfig_t& getBatchingConfig();

    /**
    * @brief get the looping iterval configured by hvaNode_t::configLoopingInterval()
    * 
    * @param void
    * @return interval in terms of ms
    * 
    */
    ms getLoopingInterval() const;
    
    /**
    * @brief stop the getting batched input logic. Once this is stoped, every following getBatchedInput()
    *           will return an empty vector
    * 
    * @param void
    * @return void
    * 
    * Normally this function should only by called by hva framework
    * 
    */
    void stopBatching();

    /**
    * @brief turn on the getting batched input logic
    * 
    * @param void
    * @return void
    * 
    * Normally this function should only by called by hva framework
    * 
    */
    void turnOnBatching();

    /**
    * @brief register a callback that this node would like to listen on
    * 
    * @param event the event callback associates to
    * @param callback callback function to be invoked with this event
    * @return status code
    * 
    */
    hvaStatus_t registerCallback(hvaEvent_t event, std::shared_ptr<hvaEventListener_t> callback);

    /**
    * @brief emit an event within the node. This event will populate throughout the entire pipeline
    * 
    * @param event event to be emitted
    * @param data user-defined data to be passed to each callback function
    * @return status code
    * 
    */
    hvaStatus_t emitEvent(hvaEvent_t event, void* data);

    /// @private
    void setEventManager(hvaEventManager_t* evMng);

    /// @private
    const std::unordered_map<hvaEvent_t, std::shared_ptr<hvaEventListener_t>>& getCallbackMap() const;

    /**
    * @brief get current state of this node
    * 
    * @param void
    * @return current state
    * @sa hvaState_t
    * 
    */
    const hvaState_t& getState() const;

    /**
    * @brief transit the node and its underlying components' state to a certain state
    * 
    * @param state state trasmitts to 
    * @return hvaSuccss if success
    * @sa hvaState_t
    * 
    * Users can only transmit state to a connecting state of current state, except for 
    * transmitting to stop by force, where hvaNode_t::transitStateToStopForced() should
    * be used
    * 
    */
    hvaStatus_t transitStateTo(hvaState_t state);

    /**
    * @brief forcefully transits to stop state
    * 
    * @param void
    * @return void
    * 
    */
    void transitStateToStopForced();

    /**
    * @brief return the human-readable name of this hvaNode_t (or its derived) class
    * 
    * @param void
    * @return node class name
    * 
    * Node writers expect to implement this function in their derived class of hvaNode_t, and 
    * try to make this class name unique. This name refers to a common class name that is shared 
    * by all its instances
    * 
    */
    virtual const std::string nodeClassName() const;

    /**
    * @brief the interface where node receives its configurations from application
    * 
    * @param config a string containing configurations
    * @return hvaSuccess if success
    * 
    * It is recommended, but not compulsory, to use a format specified with in hvaConfigStringParser_t.
    * 
    * Users can call this function multiple times.
    * 
    * Node writers should parse the config string received within this function's implementation and once
    * all minimum required configurations are received, make sure to transit node state to configured, otherwise
    * it will fail at hvaPipeline_t::prepare()
    * 
    */
    virtual hvaStatus_t configureByString(const std::string& config);

    /**
    * @brief this function is called by hva framework to query node whether it has all its configurations
    * received and make sure the configurations are correct
    * 
    * @param void
    * @return hvaSuccess if node has received all its configuration and have them validated
    * 
    * This function will be called by hva framework at hvaPipeline_t::prepare(), so as to make sure each 
    * node is ready to be preparable and runnable. Node writers should perform valiation within implementation
    * of this function and report its status by return value
    * 
    */
    virtual hvaStatus_t validateConfiguration() const;

    /**
    * @brief get the config string previously saved in internal member of hvaNode_t
    * 
    * @param void
    * @return string saved
    * @sa hvaNode_t::savetoConfigString()
    */
    virtual std::string getConfigString() const;

    /**
    * @brief function used to deplete the node upon depleting state and determine node's status by hva
    * 
    * @param void
    * @return true if a node is fully depleted  
    * 
    * Users should not overwrite or call this function
    * 
    */
    bool deplete();

    /**
    * @brief get the reference to the portIdx-th out port
    * 
    * @param portIdx out port index to retrieve
    * @return reference to the out port instance
    * 
    */
    hvaOutPort_t& getOutputPort(std::size_t portIdx);

    /**
    * @brief get the reference to the portIdx-th in port
    * 
    * @param portIdx in port index to retrieve
    * @return reference to the in port instance
    * 
    */
    hvaInPort_t& getInputPort(std::size_t portIdx);

    /**
    * @brief save a config string to a internal member of hvaNode_t
    * 
    * @param config config string to be saved
    * @return void
    * 
    * Node writers may like to save part of the config string to an internal member of hvaNode_t but
    * it is not compulsory
    * @sa hvaNode_t::getConfigString()
    * 
    */
    void savetoConfigString(const std::string& config);

    /**
    * @brief add a reference count to prevent node exiting depleting state
    * 
    * @param void
    * @return void
    * 
    * This function is mainly used in case some node is implemented in a callback manner, where at 
    * depleting state, though no more incoming buffers arrived, there are still a few callbacks not returned
    * yet. In this case at each callback to be triggered, call this function to add a reference count. At the 
    * end of callback function, call hvaNode_t::releaseDepleting() to release the reference count so as to
    * make the node exitable from depleting state
    * 
    */
    void holdDepleting();

    /**
    * @brief release a reference count to the current node
    * 
    * @param void
    * @return void
    * @sa hvaNode_t::holdDepleting()
    */
    void releaseDepleting();

    /// @private
    void wakeupBatching();

private:
    static std::size_t m_workerCtr;
    
    std::vector<std::unique_ptr<hvaInPort_t>> m_inPorts;
    std::vector<std::unique_ptr<hvaOutPort_t>> m_outPorts;

    const std::size_t m_inPortNum;
    const std::size_t m_outPortNum;
    hvaBatchingConfig_t m_batchingConfig;
    std::unordered_map<int, int> m_mapStream2LastFrameId;
    std::size_t m_totalThreadNum;

    ms m_loopingInterval;
    std::mutex m_batchingMutex;
    std::condition_variable m_batchingCv;
    std::atomic_bool m_batchingStoped;

    hvaEventManager_t* m_pEventMng;
    std::unordered_map<hvaEvent_t,std::shared_ptr<hvaEventListener_t>> m_callbackMap;

    hvaState_t m_state;

    std::string m_configString;

    std::atomic<std::size_t> m_depletingHold;
    bool m_waitingForDepletingHold; // flag for only waiting for depelting hold
};

/**
* @brief hvaNodeWorker_t is the stuct that actually does the workload within its process() function. 
* Node workers are spawned from nodes, where all workers spawned from the same node share every
* thing within the node struct, but will NOT share anything within the node worker itself
* 
*/
class HVA_DECLSPEC hvaNodeWorker_t{
public:
    hvaNodeWorker_t(hvaNode_t* parentNode);

    virtual ~hvaNodeWorker_t();

    /**
    * @brief the function that main workload should conduct at. This function will be invoked by framework
    *           repeatedly and in parrallel with each other node worker's process() function
    * 
    * @param batchIdx a batch index that framework will assign to each node worker. This is usually
    *           passed to getBatchedInput()
    * @return void
    * 
    */
    virtual void process(std::size_t batchIdx) = 0;

    /**
    * @brief specialization of process() where this function will be called only once before the usual
    *           process() being called
    * 
    * @param batchIdx a batch index that framework will assign to each node worker. This is usually
    *           passed to getBatchedInput()
    * @return void
    * 
    */
    virtual void processByFirstRun(std::size_t batchIdx);

    /**
    * @brief specialization of process() where this function will be called only once after all other calls
    *           of process()
    * 
    * @param batchIdx a batch index that framework will assign to each node worker. This is usually
    *           passed to getBatchedInput()
    * @return void
    * 
    */
    virtual void processByLastRun(std::size_t batchIdx);

    /**
    * @brief initialization of this node. This is called sequentially by the framework at the very beginning
    *           of pipeline begins
    * 
    * @param void
    * @return void
    * 
    */
    virtual void init();

    /**
    * @brief deinitialization of this node. This is called by framework after stop() being called
    * 
    * @param void
    * @return void
    * 
    */
    virtual void deinit();

    /**
    * @brief To perform any necessary operations when pipeline's rearm is called
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    virtual hvaStatus_t rearm();

    /**
    * @brief reset this node
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    virtual hvaStatus_t reset();

    /**
    * @brief get the pointer to its parent hvaNode_t instance
    * 
    * @param void
    * @return a pointer to hvaNode_t
    * 
    */
    hvaNode_t* getParentPtr() const;

    /**
    * @brief tell if this node worker has been stopped or not
    * 
    * @param void
    * @return true if stopped
    * 
    */
    bool isStopped() const;

    /**
    * @brief get the current state of this node worker
    * 
    * @param void
    * @return current state
    * @sa hvaState_t
    */
    const hvaState_t& getState() const;

    /// @copydoc hvaNode_t::transitStateTo()
    hvaStatus_t transitStateTo(const hvaState_t& state);

    /// @copydoc hvaNode_t::transitStateToStopForced()
    void transitStateToStopForced();

    hvaNodeLatencyMonitor_t& getLatencyMonitor();

protected:
    
    /**
    * @brief send output to the next node connected at port index
    * 
    * @param data blob to be sent
    * @param portId the port index blob would be sent to
    * @param timeout the maximal timeout before this function returns. Set to zero to make it blocking
    * @return status code
    * 
    */
    hvaStatus_t sendOutput(hvaBlob_t::Ptr data, std::size_t portId, ms timeout = ms(1000));

    void breakProcessLoop();

private:
    hvaNode_t* m_parentNode;
    volatile bool m_internalStop;
    hvaState_t m_state;
    hvaNodeLatencyMonitor_t m_latencyMonitor;
};

#define HVA_ENABLE_DYNAMIC_LOADING(NODE_CLASS_NAME, CONSTRUCTED_OBJECT) \
    extern "C" { \
    ::hva::hvaNode_t* HVA_PP_CONCAT(NODE_CLASS_NAME,_create)(std::size_t threadNum){ \
        return new CONSTRUCTED_OBJECT; \
    }; \
    class HVA_PP_CONCAT(HVA_PP_CONCAT(_,NODE_CLASS_NAME),AutoRegistration){ \
    public: \
        HVA_PP_CONCAT(HVA_PP_CONCAT(_,NODE_CLASS_NAME), AutoRegistration)(){ \
        ::hva::hvaNodeRegistry::getInstance().registerNodeClassName(#NODE_CLASS_NAME); \
        ::hva::hvaNodeRegistry::getInstance().registerNodeCtor(#NODE_CLASS_NAME, HVA_PP_CONCAT(NODE_CLASS_NAME,_create)); \
        }; \
        HVA_PP_CONCAT(HVA_PP_CONCAT(~_,NODE_CLASS_NAME), AutoRegistration)(){ \
        ::hva::hvaNodeRegistry::getInstance().unregisterNodeCtor(#NODE_CLASS_NAME); \
        }; \
    }; \
    HVA_PP_CONCAT(HVA_PP_CONCAT(_,NODE_CLASS_NAME), AutoRegistration) _proxy; \
    };

}
#endif //#ifndef HVA_HVANODE_HPP
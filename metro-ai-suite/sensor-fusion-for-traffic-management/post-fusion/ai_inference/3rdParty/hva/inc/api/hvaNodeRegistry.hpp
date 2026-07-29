#ifndef HVA_HVANODEREGISTRY_HPP
#define HVA_HVANODEREGISTRY_HPP

#include <inc/util/hvaUtil.hpp>
// #include <inc/api/hvaNode.hpp>

#define HVA_NODE_REGISTRY_NO_DLCLOSE 0x0001 ///< Do Not dlclose libraries unless program exits 
#define HVA_NODE_REGISTRY_RTLD_GLOBAL 0x0002 ///< Pass RTLD_GLOBAL flag upon dlopen()                           

namespace hva{

class hvaNode_t;

/**
* @brief the registry used to manage all dynamical-loadable nodes
* 
*/
class HVA_DECLSPEC hvaNodeRegistry final{
public:
    /**
    * @brief get the reference to registry instance
    * 
    * @param void
    * @return reference to registry instance
    * 
    */
    static hvaNodeRegistry& getInstance();

    hvaNodeRegistry(const hvaNodeRegistry&) = delete;

    hvaNodeRegistry(hvaNodeRegistry&&) = delete;

    hvaNodeRegistry& operator=(const hvaNodeRegistry&) = delete;

    hvaNodeRegistry& operator=(hvaNodeRegistry&&) = delete;

    typedef hvaNode_t* (*NodeCtor_t)(std::size_t);

    /**
    * @brief get a reference to the node constructor by its class name
    * 
    * @param key the class name the dynamic-loadable nodes register
    * @return the constructor of specified class
    * 
    */
    const NodeCtor_t& operator[](const std::string& key) const;

    /**
    * @brief register a node constructor to registry
    * 
    * @param key the class name of node to be registered. This class name should be
    * registered beforehand by hvaNodeRegistry::registerNodeClassName()
    * @param ctor constructor to be registered 
    * @return void
    * 
    * This function should only be called within the same library file where the implementation
    * of the node to be registered resides!
    * 
    */
    void registerNodeCtor(const std::string& key, NodeCtor_t ctor);

    /**
    * @brief unregister a node. After un-registration, node will no longer be
    * dynamically loadable
    * 
    * @param key the class name to be unregistered
    * @return void
    * 
    * This function should only be called within the same library file where the implementation
    * of the node to be registered resides!
    * 
    */
    void unregisterNodeCtor(const std::string& key);

    /**
    * @brief register a node class name
    * 
    * @param nodeClassName the class name to be registered 
    * @return void
    * 
    * This function should only be called within the same library file where the implementation
    * of the node to be registered resides!
    * 
    */
    void registerNodeClassName(const std::string& nodeClassName);

    /// @private
    void clearAllNodeClassName();

    /**
    * @brief load a library file containing a hvaNode_t implementation
    * 
    * @param path the path to the library or its containing folder
    * @return hvaSuccess if success
    * 
    */
    hvaStatus_t load(const std::string& path);

    /**
    * @brief unload the file previously openned by hvaNodeRegistry::load()
    * 
    * @param path the path to the library or its containing folder
    * @return void
    * @sa hvaNodeRegistry::load()
    * 
    */
    void unload(const std::string& path);

    /**
    * @brief initialize the hva node registry
    * 
    * @param flag optional. values could be
    *   HVA_NODE_REGISTRY_NO_DLCLOSE
    *   HVA_NODE_REGISTRY_RTLD_GLOBAL
    * @return void
    * @sa HVA_NODE_REGISTRY_NO_DLCLOSE HVA_NODE_REGISTRY_NO_DLCLOSE
    * 
    * Upon initialization, the node registry will try to load the libraries specified
    * under the path of environment variable HVA_NODE_DIR recursively
    * 
    */
    void init(int flag = 0);
private:
    hvaNodeRegistry();

    /// @private
    class Impl;
    std::unique_ptr<Impl> m_impl;
};

}

#endif //#ifndef HVA_HVANODEREGISTRY_HPP
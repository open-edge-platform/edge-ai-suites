#ifndef HVA_HVABUF_HPP
#define HVA_HVABUF_HPP

#include <chrono>
#include <memory>
#include <type_traits>
#include <functional>
#include <iostream>
#include <inc/util/hvaUtil.hpp>
#include <inc/meta/hvaMeta.hpp>

namespace hva{

/**
* @brief base for all hvaBuf_t and all its derived classes
* 
* This could be used in case application/plugin writers are unsure about the type
* of a certain buf, where they can cast it to hvaBufDescriptor_t and determine
* by hvaBufDescriptor_t::getKeyString() or hvaBufDescriptor_t::getUID()
*
*/
class HVA_DECLSPEC hvaBufDescriptor_t{
public:
    using Ptr=std::shared_ptr<hvaBufDescriptor_t>;

    virtual ~hvaBufDescriptor_t();

    virtual Ptr clone() const = 0;

    /**
    * @brief get the key string associated with the buffer type if specified
    * 
    * @param void
    * @return string of the key string
    * 
    * Any derived class of hvaBuf_t is expected to implement this function to return
    * a unique key string from other buffer types.
    */
    virtual std::string getKeyString() const = 0;

    /**
    * @brief get the unique ID associated with this buffer type if specified
    * 
    * @param void
    * @return int value of the UID
    * 
    * Derived classes no need to rewrite this function. This function will return a unique
    * ID by each different derived class of hvaBuf_t. Please note that this function only 
    * guarantees unique-ness wihtin a SINGLE process but not consistency from run to run, i.e.
    * different application/process, or same application on different host may give different UID
    * to the exact same type of buffer 
    * 
    */
    int getUID() const;

    /**
    * @brief get the size argument at construction
    * 
    * @param void
    * @return size
    * 
    */
    std::size_t getSize() const;

    /**
    * @brief get the tag associated with this descriptor/buffer
    * 
    * @param void
    * @return unsigned tag value
    * @sa hvaBuf_t::tagAs()
    * 
    */
    unsigned getTag() const;

    /**
    * @brief reset the descriptor
    * 
    * @param void
    * @return void
    * 
    */
    virtual void reset();

protected: 
    /**
    * @brief users are not expected to initialize a hvaBufDescriptor_t directly, but get it 
    * through a hvaBuf_t instead
    */
    hvaBufDescriptor_t();

    /// @copydoc hvaBufDescriptor_t()
    hvaBufDescriptor_t(std::size_t size);

    /// @copydoc hvaBufDescriptor_t()
    hvaBufDescriptor_t(const hvaBufDescriptor_t& buf) = delete;

    /// @copydoc hvaBufDescriptor_t()
    hvaBufDescriptor_t(hvaBufDescriptor_t&& buf);

    /// @copydoc hvaBufDescriptor_t()
    hvaBufDescriptor_t& operator=(const hvaBufDescriptor_t& buf) = delete;

    /// @copydoc hvaBufDescriptor_t()
    hvaBufDescriptor_t& operator=(hvaBufDescriptor_t&& buf);

    /**
    * @brief users are not expected to change size via hvaBufDescriptor_t itself, but 
    * changed it within an hvaBuf_t
    */
    void _setSize(std::size_t size);

    /**
    * @brief users are not expected to change tag via hvaBufDescriptor_t itself, but 
    * changed it within an inherited hvaBuf_t
    */
    void _tagAs(unsigned tag);

private:
    /// @private
    class Impl;
    std::unique_ptr<Impl> m_impl;
};

/**
* @brief type to wrap any data transitting through hva pipeline framwork
* 
* Users can derive from this class to write their own buffer types
*/
class HVA_DECLSPEC hvaBuf_t: public hvaBufDescriptor_t, public std::enable_shared_from_this<hvaBuf_t>{
public:
    using Ptr = std::shared_ptr<hvaBuf_t>;

    hvaBuf_t() = delete;

    hvaBuf_t(hvaBuf_t&& buf) = delete;

    hvaBuf_t& operator=(const hvaBuf_t& buf) = delete;

    hvaBuf_t& operator=(hvaBuf_t&& buf) = delete;

    virtual ~hvaBuf_t();

    /**
    * @brief static function to make a hvaBuf_t
    * 
    * @param buf any content to be wrapped within hvaBuf_t
    * @param size reported size of the content
    * @param d optional. custom deleter for the content
    * @return shared pointer to the hvaBuf_t made
    * 
    * Please note that any derived class should write their own implementation of this function! 
    */
    template <typename T>
    static Ptr make_buffer(T buf, std::size_t size, std::function<void(T)> d = {});

    /**
    * @brief return a shared pointer to this object
    * 
    * @param void
    * @return shared pointer to the object
    * 
    */
    virtual Ptr sharedFromThis();

    /**
    * @brief clone a hvaBuf_t
    * 
    * @param void
    * @return shared pointer to hvaBufDescriptor_t, where users can dynamically cast to 
    * any derived class
    * @sa hvaBufDescriptor_t
    * 
    */
    virtual hvaBufDescriptor_t::Ptr clone() const override;

    /**
    * @brief get the key string associated with the buffer type if specified
    * 
    * @param void
    * @return string of the key string
    * 
    */
    virtual std::string getKeyString() const override;

    /**
    * @brief try to convert to a other-typed hvaBuf_t specified by the keystring
    * 
    * @param keyString the key string of the buffer type users try to convert to
    * @param otherBuf the converted hvaBuf_t
    * @return hvaStatus_t on success status
    * 
    */
    virtual hvaStatus_t convertTo(std::string keyString, hvaBuf_t::Ptr& otherBuf) const;

    /**
    * @brief get the data buffer it contains
    * 
    * @param void
    * @return a raw buffer wrapped in this hvaBuf_t
    * 
    */
    template <typename T>
    T get() const;

    /**
    * @brief overwrite the content of this hvaBuf_t to data
    * 
    * @param data the content to be set into this hvaBuf_t
    * @param d optional. Custom deleter for the raw content
    * @return void
    * 
    */
    template <typename T>
    void set(const T& data, std::function<void(T)> d = {});

    /**
    * @brief reset the hvaBuf_t
    * 
    * @param void
    * @return void
    * 
    */
    virtual void reset() override;

    /**
    * @brief overwrite the reported size of content
    * 
    * @param size the reported size
    * @return void
    * 
    */
    void setSize(std::size_t size);

    /**
    * @brief tag this hvaBuf_t with a specific unsigned value
    * 
    * @param tag any user specified tag in form of unsigned
    * @return void
    * 
    */
    void tagAs(unsigned tag);

    /**************************
     * Meta data related APIs *
     **************************/

    /**
    * @brief add a meta with this hvaBuf_t
    * 
    * @param metadata any metadata, which can be any type
    * @return hvaSuccess if success
    * 
    * Note that each instance of hvaBuf_t can only hold a single copy of metadata
    * of the same type! For example, if we have a hvaBuf_t holding an unsigned meta,
    * then calling again hvaBuf_t::setMeta() will overwrite the previous meta, but user
    * can still add another meta of other type, e.g. int type, and co-exists with 
    * previous meta
    * 
    */
    template <typename META_T>
    hvaStatus_t setMeta(META_T metadata);

    /**
    * @brief erase the metadata of type META_T
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    template <typename META_T>
    hvaStatus_t eraseMeta();

    /**
    * @brief get the metadata of type META_T
    * 
    * @param[out] metadata 
    * @return hvaSuccess if success
    * 
    */
    template <typename META_T>
    hvaStatus_t getMeta(META_T& metadata) const;

    /**
    * @brief erase all metadata within this hvaBuf_t
    * 
    * @param void
    * @return hvaSuccess if success
    * 
    */
    hvaStatus_t eraseAllMeta();

    /**
    * @brief check if this hvaBuf_t contains a meta of type META_T
    * 
    * @param void
    * @return true if containing a meta of type META_T
    * 
    */
    template <typename META_T>
    bool containMeta() const;

    /**************************************
     * Buffer pool operation related APIs *
     **************************************/
    /// @private
    virtual hvaStatus_t onBufferPoolInit(std::size_t poolSize, void* context=nullptr);

    /// @private
    virtual hvaStatus_t onBufferPoolAllocateBuffer(hvaBuf_t::Ptr bufAllocated, void* context=nullptr);

    /// @private
    virtual hvaStatus_t onBufferPoolFreeBuffer(hvaBuf_t::Ptr bufToBeFreed, void* context=nullptr);

    /// @private
    virtual hvaStatus_t onBufferPoolGetBuffer(hvaBuf_t::Ptr bufToBeGet, void* context=nullptr);

    /// @private
    virtual hvaStatus_t onBufferPoolReturnBuffer(hvaBuf_t::Ptr bufToBeReturned, void* context=nullptr);

    /// @private
    virtual hvaStatus_t onBufferPoolDeinit(void* context=nullptr);
    
private:

    class _hvaBufHolderBase_t{
    public:
        _hvaBufHolderBase_t(){ };
        virtual ~_hvaBufHolderBase_t(){ };
        virtual _hvaBufHolderBase_t* clone() = 0;
    };

    template <typename HOLDER_T>
    class _hvaBufHolder_t : public _hvaBufHolderBase_t{
    public:
        _hvaBufHolder_t(HOLDER_T data, std::function<void(HOLDER_T)> d = {}):data(data), deleter(d){ };

        ~_hvaBufHolder_t(){
            if(deleter){
                deleter(data);
            }
        };

        _hvaBufHolder_t() = delete;

        _hvaBufHolder_t(const _hvaBufHolder_t& holder) = default;

        _hvaBufHolder_t(_hvaBufHolder_t&& holder):data{std::move(holder.data)}, deleter{std::move(holder.deleter)}{ };

        _hvaBufHolder_t& operator=(const _hvaBufHolder_t& holder) = default;

        _hvaBufHolder_t& operator=(_hvaBufHolder_t&& holder){
            if(this != &holder){
                std::swap(data, holder.data);
                std::swap(deleter, holder.deleter);
            }
            return *this;
        };

        virtual _hvaBufHolder_t* clone() override{
            return new _hvaBufHolder_t(*this);
        };

        HOLDER_T data;
        std::function<void(HOLDER_T)> deleter;
    };

    std::unique_ptr<_hvaBufHolderBase_t> m_buf;
    hvaMetaMap_t m_meta;

protected:
    template <typename T>
    hvaBuf_t(T buf, std::size_t size, std::function<void(T)> d = {});

    // hvaBuf_t(std::unique_ptr<_hvaBufHolderBase_t> ptr, const hvaMetaMap_t& meta);

    hvaBuf_t(const hvaBuf_t& buf);
};

template <typename T>
hvaBuf_t::hvaBuf_t(T buf, std::size_t size, std::function<void(T)> d): m_buf(new _hvaBufHolder_t<T>(buf, d))
        , hvaBufDescriptor_t(size){

};

template <typename T>
hvaBuf_t::Ptr hvaBuf_t::make_buffer(T buf, std::size_t size, std::function<void(T)> d){
    // return std::make_shared<hvaBuf_t>(buf, size, d);
    return Ptr(new hvaBuf_t(buf, size, d));
};

template <typename T>
T hvaBuf_t::get() const{
    return dynamic_cast<_hvaBufHolder_t<T>*>(m_buf.get())->data;
};

template <typename T>
void hvaBuf_t::set(const T& data, std::function<void(T)> d){
    m_buf.reset(new _hvaBufHolder_t<T>(data,d));
};

template <typename META_T>
hvaStatus_t hvaBuf_t::setMeta(META_T metadata){
    if(m_meta.add(std::move(metadata)))
        return hvaSuccess;
    else
        return hvaFailure;
};

template <typename META_T>
hvaStatus_t hvaBuf_t::eraseMeta(){
    if(m_meta.erase<META_T>())
        return hvaSuccess;
    else
        return hvaFailure;
};

template <typename META_T>
hvaStatus_t hvaBuf_t::getMeta(META_T& metadata) const{
    if(m_meta.get(metadata))
        return hvaSuccess;
    else
        return hvaFailure;
};

template <typename META_T>
bool hvaBuf_t::containMeta() const{
    return m_meta.contain<META_T>();
};

}
#endif // HVA_HVABUF_HPP
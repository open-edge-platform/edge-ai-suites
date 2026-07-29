#ifndef HVA_HVATHREADSAFEQUEUE_HPP
#define HVA_HVATHREADSAFEQUEUE_HPP

#include <queue>
#include <mutex>
#include <condition_variable>

namespace hva
{

template <typename T>
class hvaThreadSafeQueue_t {
public:

    hvaThreadSafeQueue_t(std::size_t maxSize=SIZE_MAX)
    : m_maxSize(maxSize), m_close(false)
    {

    };
    // hvaThreadSafeQueue_t() = delete;
    hvaThreadSafeQueue_t(const hvaThreadSafeQueue_t& ) = delete;
    hvaThreadSafeQueue_t& operator =(const hvaThreadSafeQueue_t& ) = delete;
    
    bool push(T value)
    {
        std::unique_lock<std::mutex> lk(m_mutex);             
        m_cv_full.wait(lk,[this]{return (m_queue.size() < m_maxSize || true == m_close);});
        if (true == m_close)
        {
            return false;
        }   
        m_queue.push_back(std::move(value));
        m_cv_empty.notify_one();
        return true;
    }

    bool tryPush(T value)
    {
        std::lock_guard<std::mutex> lk(m_mutex);
        if (true == m_close)
        {
            return false;
        }
        if(m_queue.size() >= m_maxSize)
        {
            return false;
        }
        m_queue.push_back(std::move(value));
        m_cv_empty.notify_one();
        return true;
    }

    bool pop(T& value)
    {
        std::unique_lock<std::mutex> lk(m_mutex);
        m_cv_empty.wait(lk,[this]{return (!m_queue.empty() || true == m_close);});
        if (true == m_close)
        {
            return false;
        }
        value=std::move(m_queue.front());
        m_queue.pop();
        m_cv_full.notify_one();
        return true;
    } 

    bool tryPop(T& value)
    {
        std::lock_guard<std::mutex> lk(m_mutex);
        if (true == m_close)
        {
            return false;
        }
        if(m_queue.empty())
        {
            return false;
        }
        value=std::move(m_queue.front());
        m_queue.pop();
        m_cv_full.notify_one();
        return true;
    }

    bool empty() const
    {
        std::lock_guard<std::mutex> lk(m_mutex);
        return m_queue.empty();
    }

    void close()
    {
        std::lock_guard<std::mutex> lk(m_mutex);
        m_close = true;
        m_cv_empty.notify_all();
        m_cv_full.notify_all();
        return;
    }

private:
    mutable std::mutex m_mutex;
    std::queue<T> m_queue;
    std::condition_variable m_cv_empty;
    std::condition_variable m_cv_full;
    std::size_t m_maxSize; //max queue size
    bool m_close;
};



    
} // namespace hva



#endif //#ifndef HVA_HVATHREADSAFEQUEUE_HPP
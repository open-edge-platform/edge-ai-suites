// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#include <queue>
#include <mutex>
#include <atomic>
#include <condition_variable>

template <typename T>
DataQueue<T>::DataQueue(size_t max_length) : queue_max_length(max_length) {}

template <typename T>
bool DataQueue<T>::force_push(const T& data)
{
    if (queue_closed) { 
        return false;
    }

    std::unique_lock<std::mutex> lock(queue_mutex);

#ifndef NDEBUG
    ++enqueue_in_progress;
#endif
    if (queue_max_length > 0) {
        while (queue.size() >= queue_max_length) {
            queue.pop();
        }
    }
    queue.push(data);
#ifndef NDEBUG
    --enqueue_in_progress;
#endif
    
    cond_enqueue.notify_one();
    return true;
}

template <typename T>
bool DataQueue<T>::wait_push(const T& data)
{
    if (queue_closed) return false;

    std::unique_lock<std::mutex> lock(queue_mutex);

#ifndef NDEBUG
    ++enqueue_in_progress;
#endif
    if (queue_max_length > 0) {
        while (queue.size() >= queue_max_length) {
            cond_dequeue.wait(lock);
            if (queue_closed) return false;
        }
    }
    queue.push(data);
#ifndef NDEBUG
    --enqueue_in_progress;
#endif
    lock.unlock();

    cond_enqueue.notify_one();
    return true;
}

template <typename T>
bool DataQueue<T>::try_push(const T& data)
{
    if (queue_closed) return false;

    std::unique_lock<std::mutex> lock(queue_mutex);

    if (queue_max_length > 0) {
        if (queue.size() >= queue_max_length) {
            return false;
        }
    }
    queue.push(data);
    lock.unlock();

    cond_enqueue.notify_one();
    return true;
}

template <typename T>
bool DataQueue<T>::close()
{
    if (queue_closed) {
        return false;
    }

    std::unique_lock<std::mutex> lock(queue_mutex);
    queue_closed = true;

    cond_enqueue.notify_all();
    cond_dequeue.notify_all();
        
    // Wait for all pop() operations to finish
    cond_dequeue.wait(lock, [this]() { return active_pop_calls.load() == 0; });
    return true;
}

template <typename T>
bool DataQueue<T>::wait_pop(T& data)
{
    if (queue_closed) {
        return false;
    }

    std::unique_lock<std::mutex> lock(queue_mutex);
    // Increment active pop calls
    active_pop_calls++;

    while (queue.empty()) {
        cond_enqueue.wait(lock);
        if (queue_closed) { 
            active_pop_calls--; // Decrement if exiting early
            return false; 
        }
    }

    data = queue.front();
    queue.pop();
    
    cond_dequeue.notify_one();
    // Decrement active pop calls
    active_pop_calls--;
    return true;
}

template <typename T>
bool DataQueue<T>::try_pop(T& data)
{
    if (queue_closed) return false;

    std::unique_lock<std::mutex> lock(queue_mutex);

    if (queue.empty()) return false;

    data = queue.front();
    queue.pop();
    lock.unlock();

    cond_dequeue.notify_one();
    return true;
}

template <typename T>
void DataQueue<T>::clean() {
    std::unique_lock<std::mutex> lock(queue_mutex);
    while (!queue.empty())
        queue.pop();
    lock.unlock();

    cond_enqueue.notify_all();
}

template <typename T>
bool DataQueue<T>::empty() const
{
    std::scoped_lock<std::mutex> lock(queue_mutex);
    return queue.empty();
}

template <typename T>
bool DataQueue<T>::closed() const { return queue_closed; }
 
template <typename T>
size_t DataQueue<T>::max_length() const { return queue_max_length; }

template <typename T>
size_t DataQueue<T>::size() const
{
    std::scoped_lock<std::mutex> lock(queue_mutex);
    return queue.size();
}

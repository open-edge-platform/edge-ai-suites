/*

 * INTEL CONFIDENTIAL

 *

 * Copyright (C) 2023-2024 Intel Corporation

 *

 * This software and the related documents are Intel copyrighted materials, and your use of them is governed by the

 * express license under which they were provided to you ("License"). Unless the License provides otherwise, you may not

 * use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without Intel's

 * prior written permission.

 *

 * This software and the related documents are provided as is, with no express or implied warranties, other than those

 * that are expressly stated in the License.

 */

#pragma once

#include <queue>
#include <mutex>
#include <condition_variable>
#include <iostream>

template <typename T>
class SampleQueue
{
    public:
        SampleQueue();
        ~SampleQueue();

        T& front();
        void pop_front();
        void push_back(const T& item);
        int size();
        bool empty();

    private:
        std::deque<T> m_queue;
        std::mutex m_rw_lock;
        std::condition_variable m_cond;
}; 

template <typename T>
SampleQueue<T>::SampleQueue(){}

template <typename T>
SampleQueue<T>::~SampleQueue(){}

template <typename T>
T& SampleQueue<T>::front()
{
    std::unique_lock<std::mutex> mlock(m_rw_lock);
    while (m_queue.empty())
    {
        m_cond.wait(mlock);
    }
    return m_queue.front();
}

template <typename T>
void SampleQueue<T>::pop_front()
{
    std::unique_lock<std::mutex> mlock(m_rw_lock);
    while (m_queue.empty())
    {
        m_cond.wait(mlock);
    }
    return m_queue.pop_front();
}     

template <typename T>
void SampleQueue<T>::push_back(const T& item)
{
    std::unique_lock<std::mutex> mlock(m_rw_lock);
    m_queue.push_back(item);
    mlock.unlock();     
    m_cond.notify_one();

}

template <typename T>
int SampleQueue<T>::size()
{
    std::unique_lock<std::mutex> mlock(m_rw_lock);
    int size = m_queue.size();
    mlock.unlock();
    return size;
}

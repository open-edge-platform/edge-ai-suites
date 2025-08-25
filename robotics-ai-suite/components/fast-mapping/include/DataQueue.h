// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once

#include <queue>
#include <mutex>
#include <atomic>
#include <condition_variable>

template <typename T>
class DataQueue {
public:
    DataQueue(size_t max_length = 0);

    // Push a new element into the queue
    // If the queue is full, pop out oldest elements immediately
    // Return false if the queue is closed
    bool force_push(const T& data);

    // Push a new element into the queue
    // If the queue is full, wait until it is not
    // Return false if the queue is closed
    bool wait_push(const T& data);

    // Push a new element into the queue
    // If the queue is full or closed, return false
    bool try_push(const T& data);

    bool close();

    // Clear the queue with any remaining objects
    void clean();

    bool wait_pop(T& data);

    bool try_pop(T& data);

    bool empty() const;

    bool closed() const;

    size_t max_length() const;

    size_t size() const;

private:
    std::queue<T> queue;
    mutable std::mutex queue_mutex;
    std::condition_variable cond_enqueue, cond_dequeue;

    const size_t queue_max_length;
    std::atomic<bool> queue_closed = false;
    std::atomic<int> active_pop_calls{0}; 

#ifndef NDEBUG
    size_t enqueue_in_progress = 0;
#endif
};

#include "DataQueue.cc"

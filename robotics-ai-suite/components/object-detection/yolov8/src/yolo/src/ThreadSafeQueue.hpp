// SPDX-License-Identifier: Apache-2.0
// Copyright (C) 2025 Intel Corporation
#pragma once
#include <queue>     
#include <mutex>      
#include <optional>   

template <typename T> class ThreadSafeQueue
{
private:
    queue<T> internal_queue;
    mutex queue_mutex;

public:
    size_t max_queue_size;

    void push( T query_frame )
    {
        lock_guard<mutex> lock( queue_mutex );
        internal_queue.push( query_frame );
        if ( internal_queue.size() > max_queue_size )
        {
            internal_queue.pop();
        }
    }

    bool empty()
    {
        lock_guard<mutex> lock( queue_mutex );
        return internal_queue.empty();
    }

    optional<T> try_pop()
    {
        lock_guard<mutex> lock( queue_mutex );
        if ( internal_queue.empty() )
        {
            return {};
        }
        T query_frame = internal_queue.front();
        internal_queue.pop();
        return { query_frame };
    }

    T pop()
    {
        lock_guard<mutex> lock( queue_mutex );
        T query_frame = internal_queue.front();
        internal_queue.pop();
        return query_frame;
    }

    int size()
    {
        lock_guard<mutex> lock( queue_mutex );
        return internal_queue.size();
    }
};

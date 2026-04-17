/*
 * Copyright (C) 2025 Intel Corporation
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#pragma once

#include <queue>
#include <mutex>
#include <atomic>
#include <condition_variable>

template <typename T>
class DataQueue
{
public:
  DataQueue(size_t max_length = 0);

  // push a new element into the queue
  // if the queue is full, pop out oldest elements immediately
  // return false if the queue is closed
  bool force_push(const T & data);

  // push a new element into the queue
  // if the queue is full, wait until it is not
  // return false if the queue is closed
  bool wait_push(const T & data);

  // push a new element into the queue
  // if the queue is full or closed, return false
  bool try_push(const T & data);

  bool close();

  // clear the queue with any remaining objects
  void clean();

  bool wait_pop(T & data);

  bool try_pop(T & data);

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

#ifndef NDEBUG
  size_t enqueue_in_progress = 0;
#endif
};

#include "DataQueue.cc"

#pragma once
#include <sycl/sycl.hpp>
#include <iostream>
#include <dpc_common.hpp>
#include <vector>
class DeviceManager {
  public:
    void printDevices();
    bool SelectDevice(int idx);
    sycl::queue &getQue();
    sycl::device &getDev();

  public:
    DeviceManager();
    DeviceManager(const DeviceManager &) = delete;
    DeviceManager &operator=(const DeviceManager &) = delete;
    DeviceManager(DeviceManager &&) = delete;
    DeviceManager &operator=(DeviceManager &&) = delete;

  private:
    std::vector<sycl::device> devs;
    sycl::queue que;
    int selDevIdx;
};

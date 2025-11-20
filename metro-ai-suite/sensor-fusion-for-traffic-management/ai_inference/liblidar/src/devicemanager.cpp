#include <devicemanager.hpp>
void DeviceManager::printDevices()
{
    std::cout << "Available device(s): \n";
    for (auto &d : devs) {
        std::cout << "\tName: " << d.get_info<sycl::info::device::name>() << "," << "Platform: " << d.get_platform().get_info<sycl::info::platform::name>()
                  << ", " << "Backend: " << d.get_backend() << std::endl;
    }
}
DeviceManager::DeviceManager()
{
    for (auto &p : sycl::platform::get_platforms()) {
        for (auto &d : p.get_devices()) {
            devs.push_back(d);
        }
    }
    printDevices();
}
sycl::queue &DeviceManager::getQue()
{
    return que;
}
sycl::device &DeviceManager::getDev()
{
    return devs[selDevIdx];
}
bool DeviceManager::SelectDevice(int idx)
{
    if (idx >= 0 && idx < devs.size())
        selDevIdx = idx;
    else
        return false;
    auto exception_handler = [](sycl::exception_list exceptions) {
        for (std::exception_ptr const &e : exceptions) {
            try {
                std::rethrow_exception(e);
            }
            catch (sycl::exception const &e) {
                std::cout << "Caught asynchronous SYCL exception:\n";
                std::cout << e.what() << std::endl;
            }
        }
    };
    que = sycl::queue(devs[selDevIdx], sycl::property::queue::in_order{});
    return true;
}

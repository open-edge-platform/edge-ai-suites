#include "ze_api.h"
#include "zes_api.h"
#include <windows.h>
#include <iostream>
#include <vector>
#include <string>
#include <cstdlib>

// -------- Engine Class --------
class Engine {
public:
    ze_result_t status;
    zes_engine_group_t type;
    zes_engine_handle_t engine_handle;
    zes_engine_stats_t engine_statsT0{};
    zes_engine_stats_t engine_statsT1{};

    Engine(zes_engine_handle_t engine_handle) {
        this->engine_handle = engine_handle;
        zes_engine_properties_t props{};
        props.stype = ZES_STRUCTURE_TYPE_ENGINE_PROPERTIES;
        status = zesEngineGetProperties(engine_handle, &props);
        type = props.type;
    }

    std::string get_engine_type() {
        return std::to_string(type);
    }

    double get_MemoryUtilizationByNPU() {
        double utilization = 0.0;
        status = zesEngineGetActivity(engine_handle, &engine_statsT1);
        if (status != ZE_RESULT_SUCCESS) {
            std::cout << "Could not get Engine Stats --> " << status << std::endl;
            return -1.0;
        }

        if (engine_statsT0.timestamp != 0) {
            utilization = 100.0 *
                (static_cast<double>(engine_statsT1.activeTime) - static_cast<double>(engine_statsT0.activeTime)) /
                (static_cast<double>(engine_statsT1.timestamp) - static_cast<double>(engine_statsT0.timestamp));
        }

        engine_statsT0 = engine_statsT1;
        return utilization;
    }
};

// -------- Device Class --------
class Device {
public:
    std::string device_name;
    ze_device_handle_t device_handle;
    ze_device_type_t type;
    std::vector<Engine> engines;

    Device(std::string device_name, ze_device_type_t type, ze_device_handle_t device_handle) {
        this->device_handle = device_handle;
        this->device_name = device_name;
        this->type = type;
    }

    void device_init() {
        ze_result_t status;
        uint32_t engineGroupCount = 0;
        status = zesDeviceEnumEngineGroups(device_handle, &engineGroupCount, nullptr);

        std::vector<zes_engine_handle_t> engine_handles(engineGroupCount);
        status = zesDeviceEnumEngineGroups(device_handle, &engineGroupCount, engine_handles.data());

        if (status != ZE_RESULT_SUCCESS) {
            std::cout << "No Engine Modules Found --> " << status << std::endl;
            exit(1);
        } else {
            std::cout << "Engine Modules Found --> " << engineGroupCount << std::endl;
        }

        for (const auto& engine_handle : engine_handles) {
            Engine e(engine_handle);
            engines.push_back(e);
        }
    }

    std::string get_device_name() {
        return device_name;
    }
};

// -------- LevelZero Class --------
class LevelZero {
private:
    bool init_levelZero() {
        ze_result_t result = zeInit(ZE_INIT_FLAG_VPU_ONLY);
        if (result != ZE_RESULT_SUCCESS) {
            std::cout << "Ze Driver not initialized: " << result << std::endl;
            return false;
        }
        std::cout << "Ze Driver initialized.\n";
        return true;
    }

    std::vector<ze_device_handle_t> findAllDevices(ze_driver_handle_t pDriver) {
        uint32_t deviceCount = 0;
        zeDeviceGet(pDriver, &deviceCount, nullptr);

        std::vector<ze_device_handle_t> devices(deviceCount);
        zeDeviceGet(pDriver, &deviceCount, devices.data());

        std::vector<ze_device_handle_t> found;
        for (uint32_t i = 0; i < deviceCount; ++i) {
            auto phDevice = devices[i];

            ze_device_properties_t device_properties{};
            device_properties.stype = ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
            zeDeviceGetProperties(phDevice, &device_properties);

            found.push_back(phDevice);
        }
        return found;
    }

public:
    std::vector<Device> devices;
    bool flag = false;
    uint32_t driverCount = 0;
    ze_result_t status;
    ze_driver_handle_t pDriver = nullptr;
    std::vector<ze_device_handle_t> device_handle_list;
    ze_device_properties_t pProperties{};

    int init() {
        _putenv_s("ZES_ENABLE_SYSMAN", "1");
        auto zes_enable_sysman = std::getenv("ZES_ENABLE_SYSMAN");
        if (zes_enable_sysman == nullptr || std::string("1") != zes_enable_sysman) {
            std::cout << "Warning: environment variable ZES_ENABLE_SYSMAN is not 1." << std::endl;
        }

        flag = init_levelZero();
        if (!flag) return -1;

        status = zeDriverGet(&driverCount, nullptr);
        if (status != ZE_RESULT_SUCCESS) return -2;

        std::vector<ze_driver_handle_t> drivers(driverCount);
        status = zeDriverGet(&driverCount, drivers.data());
        if (status != ZE_RESULT_SUCCESS) return -3;

        for (const auto& driver : drivers) {
            auto found_devices = findAllDevices(driver);
            device_handle_list.insert(device_handle_list.end(), found_devices.begin(), found_devices.end());
        }

        for (size_t i = 0; i < device_handle_list.size(); i++) {
            pProperties.stype = ZE_STRUCTURE_TYPE_DEVICE_PROPERTIES;
            status = zeDeviceGetProperties(device_handle_list[i], &pProperties);
            if (status != ZE_RESULT_SUCCESS) return -4;

            Device d(pProperties.name, pProperties.type, device_handle_list[i]);
            std::cout << "Added Device : " << pProperties.name << std::endl;
            d.device_init();
            devices.push_back(d);
        }
        return 0;
    }

    double get_engine_utilization(int did, int eid) {
        return devices[did].engines[eid].get_MemoryUtilizationByNPU();
    }
};

// -------- main --------
int main() {
    LevelZero zero;
    if (zero.init() != 0) {
        std::cout << "Failed to initialize Level Zero.\n";
        return -1;
    }

    std::cout << "Monitoring NPU Utilization...\n";
    while (true) {
        double util = zero.get_engine_utilization(0, 0);
        std::cout << "Utilization : " << util << " %\n";
        Sleep(1000); // 1 second delay (Windows)
    }

    return 0;
}

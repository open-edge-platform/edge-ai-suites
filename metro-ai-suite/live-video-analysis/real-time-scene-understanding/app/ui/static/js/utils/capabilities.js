/* Copyright (C) 2026 Intel Corporation */
/* SPDX-License-Identifier: Apache-2.0 */

/**
 * Capability-domain utility helpers.
 * Interprets capability payloads and builds metric-chip tooltip details.
 */

function numberOrNull(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatGiBFromBytes(value) {
    const bytes = numberOrNull(value);
    if (bytes === null || bytes <= 0) return null;

    const gib = bytes / (1024 ** 3);
    return `${gib >= 10 ? gib.toFixed(0) : gib.toFixed(1)} GiB`;
}

function formatInstalledMemory(platform) {
    if (!platform || !platform.system_memory) return null;

    const installedGiB = numberOrNull(platform.system_memory.installed_gib);
    if (installedGiB === null || installedGiB <= 0) return null;

    const value = Number.isInteger(installedGiB) ? installedGiB : installedGiB.toFixed(2);
    return `${value} GiB`;
}

export function hasOpenvinoGpuInference(device) {
    return Array.isArray(device && device.sw_functional_capabilities)
        && device.sw_functional_capabilities.includes("openvino_gpu_inference");
}

function normalizeCategory(device) {
    const raw = device && typeof device.category === "string" ? device.category.trim() : "";
    return raw ? raw.toLowerCase() : "";
}

function isDevicePresent(device) {
    if (!device || typeof device !== "object") return false;

    if (typeof device.present === "boolean") return device.present;
    if (typeof device.present === "number") return device.present !== 0;
    if (typeof device.present === "string") {
        const value = device.present.trim().toLowerCase();
        return value !== "" && value !== "0" && value !== "false" && value !== "no";
    }

    // Treat missing/unknown present flags as present to avoid false negatives.
    return true;
}

function isGpuCategory(category) {
    return category === "igpu" || category === "dgpu";
}

function hasOpenvinoNpuInference(device) {
    const caps = Array.isArray(device && device.sw_functional_capabilities)
        ? device.sw_functional_capabilities
        : [];

    return caps.some((capability) => (
        typeof capability === "string"
        && (capability.toLowerCase() === "openvino_npu_inference"
            || capability.toLowerCase().includes("npu"))
    ));
}

function isNpuDevice(device) {
    const category = normalizeCategory(device);
    return category === "npu" || category === "vpu" || hasOpenvinoNpuInference(device);
}

function readFirstString(source, keys) {
    if (!source || typeof source !== "object") return null;

    for (const key of keys) {
        const value = source[key];
        if (typeof value === "string" && value.trim()) return value.trim();
    }

    return null;
}

function readCpuModelFromDevice(cpuDevice) {
    if (!cpuDevice || typeof cpuDevice !== "object") return null;

    return readFirstString(cpuDevice, ["commercial_reference", "name", "model"])
        || readFirstString(cpuDevice.details, ["model_name", "model", "name"]);
}

function readDeviceModel(device, fallback) {
    if (!device || typeof device !== "object") return fallback || null;

    return readFirstString(device, ["commercial_reference", "name", "model"])
        || readFirstString(device.details, ["model_name", "model", "name"])
        || fallback
        || null;
}

export function buildCapabilitiesFallback() {
    return {
        has_gpu: null,
        has_npu: null,
        devices: [],
        platform: null,
    };
}

function deviceName(device, fallback) {
    const name = device && device.commercial_reference;
    return typeof name === "string" && name.trim() ? name.trim() : fallback;
}

function buildDetailLinesFromDevice(device) {
    const lines = [];
    if (!device) return lines;

    if (device.vendor) lines.push(`Vendor: ${device.vendor}`);
    if (device.category) lines.push(`Category: ${String(device.category).toUpperCase()}`);

    const driver = device.details && device.details.driver_name;
    if (driver) lines.push(`Driver: ${driver}`);

    const memory = device.details && device.details.memory ? device.details.memory.total_bytes : null;
    const memoryLabel = formatGiBFromBytes(memory);
    if (memoryLabel) lines.push(`Memory: ${memoryLabel}`);

    return lines;
}

export function enrichCapabilities(data) {
    const devices = Array.isArray(data && data.devices) ? data.devices : null;
    if (!devices) throw new Error("Invalid capability response");

    return {
        ...data,
        has_gpu: devices.some((device) => {
            const category = normalizeCategory(device);
            return isDevicePresent(device)
                && isGpuCategory(category)
                && hasOpenvinoGpuInference(device);
        }),
        has_npu: devices.some((device) => isDevicePresent(device) && isNpuDevice(device)),
    };
}

export function buildMetricChipDetailMap(capabilities) {
    const rawDevices = Array.isArray(capabilities && capabilities.devices) ? capabilities.devices : [];
    const devices = rawDevices.filter((device) => isDevicePresent(device));
    const cpu = devices.find((device) => normalizeCategory(device) === "cpu");
    const gpus = devices.filter((device) => {
        const category = normalizeCategory(device);
        return isGpuCategory(category) && hasOpenvinoGpuInference(device);
    });
    const npu = devices.find((device) => isNpuDevice(device));

    const map = {
        cpu: cpu ? buildDetailLinesFromDevice(cpu) : [],
        ram: [],
        gpu: [],
        npu: npu ? buildDetailLinesFromDevice(npu) : [],
    };

    const installedMemory = formatInstalledMemory(capabilities && capabilities.platform ? capabilities.platform : null);
    if (installedMemory) {
        map.ram.push(`Installed memory: ${installedMemory}`);
    }

    if (Array.isArray(gpus) && gpus.length > 0) {
        const names = gpus.map((device) => deviceName(device, "GPU"));
        map.gpu.push(`Detected GPUs: ${names.join(", ")}`);
        gpus.forEach((device) => {
            buildDetailLinesFromDevice(device).forEach((line) => {
                if (!map.gpu.includes(line)) {
                    map.gpu.push(line);
                }
            });
        });
    }

    return map;
}

export function buildHostSystemInfo(capabilities) {
    const rawDevices = Array.isArray(capabilities && capabilities.devices) ? capabilities.devices : [];
    const devices = rawDevices.filter((device) => isDevicePresent(device));
    const platform = capabilities && capabilities.platform ? capabilities.platform : null;
    const cpu = devices.find((device) => normalizeCategory(device) === "cpu");
    const gpus = devices.filter((device) => {
        const category = normalizeCategory(device);
        return isGpuCategory(category) && hasOpenvinoGpuInference(device);
    });
    const npu = devices.find((device) => isNpuDevice(device));

    const gpuModels = gpus
        .map((gpu) => {
            const model = readDeviceModel(gpu, "GPU");
            const category = typeof gpu.category === "string" && gpu.category.trim()
                ? gpu.category.trim().toLowerCase()
                : null;

            return category ? `${model} (${category})` : model;
        })
        .filter((name) => Boolean(name));

    const uniqueGpuModels = Array.from(new Set(gpuModels));
    const installedMemory = formatInstalledMemory(platform);

    return {
        cpuModel: readCpuModelFromDevice(cpu)
            || "-",
        ramTotal: installedMemory || "-",
        gpuModel: uniqueGpuModels.length > 0 ? uniqueGpuModels.join(", ") : "-",
        npuModel: npu ? (readDeviceModel(npu, "NPU") || "NPU") : "-",
    };
}

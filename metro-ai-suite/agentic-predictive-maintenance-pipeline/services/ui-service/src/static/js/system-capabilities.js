// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
//
// Fetches system capability info (CPU/GPU/NPU presence + specs) from the
// metrics-manager minimal-profile API (proxied via nginx at
// /api/v1/capabilities) and renders compact device cards in the header.

(function () {
  "use strict";

  const CAPABILITIES_URL = "/api/v1/capabilities?profile=minimal";

  function numberOrNull(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function deviceName(device, fallback) {
    const name = device && device.commercial_reference;
    return typeof name === "string" && name.trim() ? name.trim() : fallback;
  }

  function formatGiBFromBytes(value) {
    const bytes = numberOrNull(value);
    if (bytes === null || bytes <= 0) return null;
    const gib = bytes / Math.pow(1024, 3);
    return (gib >= 10 ? gib.toFixed(0) : gib.toFixed(1)) + " GiB";
  }

  function formatInstalledMemory(platform) {
    const installedGiB = numberOrNull(platform && platform.system_memory && platform.system_memory.installed_gib);
    if (installedGiB === null || installedGiB <= 0) return null;
    const value = Number.isInteger(installedGiB) ? installedGiB : installedGiB.toFixed(2);
    return value + " GiB RAM";
  }

  function joinDetails(parts, fallback) {
    const joined = parts.filter(Boolean).join(" · ");
    return joined || fallback;
  }

  function cpuDetails(device, platform) {
    const cores = (device && device.details && device.details.cores) || {};
    const physical = numberOrNull(cores.physical);
    const logical = numberOrNull(cores.logical);
    const pCores = numberOrNull(cores.p_cores);
    const eCores = numberOrNull(cores.e_cores);
    let coreLabel = null;

    if (pCores !== null && eCores !== null) {
      coreLabel = pCores + " P + " + eCores + " E cores";
    } else if (physical !== null) {
      coreLabel = physical + " " + (physical === 1 ? "core" : "cores");
    }

    const threadLabel = logical !== null && logical !== physical
      ? logical + " " + (logical === 1 ? "thread" : "threads")
      : null;
    return joinDetails([coreLabel, threadLabel, formatInstalledMemory(platform)], "Compute device");
  }

  function gpuDetails(devices) {
    const discreteCount = devices.filter((d) => d.category === "dgpu").length;
    const integratedCount = devices.filter((d) => d.category === "igpu").length;
    const typeLabels = [];
    if (discreteCount) typeLabels.push(discreteCount + " dGPU");
    if (integratedCount) typeLabels.push(integratedCount + " iGPU");

    const memory = devices.length === 1
      ? formatGiBFromBytes(devices[0] && devices[0].details && devices[0].details.memory && devices[0].details.memory.total_bytes)
      : null;
    return joinDetails(typeLabels.concat([memory]), "Graphics accelerator");
  }

  function npuDetails(device) {
    return formatGiBFromBytes(device && device.details && device.details.memory && device.details.memory.total_bytes)
      || "AI accelerator";
  }

  function buildCardModels(capabilities) {
    const devices = Array.isArray(capabilities && capabilities.devices)
      ? capabilities.devices.filter((d) => d && d.present === true)
      : [];
    const cpu = devices.find((d) => d.category === "cpu");
    const gpus = devices.filter((d) => d.category === "igpu" || d.category === "dgpu");
    const npu = devices.find((d) => d.category === "npu");
    const cards = [];

    if (cpu) {
      cards.push({
        label: "CPU",
        name: deviceName(cpu, "CPU"),
        details: cpuDetails(cpu, capabilities.platform),
      });
    }

    if (gpus.length) {
      const names = gpus.map((d) => deviceName(d, "GPU"));
      cards.push({
        label: "GPU",
        name: gpus.length > 1 ? names[0] + " + " + (gpus.length - 1) + " more" : names[0],
        details: gpuDetails(gpus),
        tooltip: names.join(", "),
      });
    }

    if (npu) {
      cards.push({
        label: "NPU",
        name: deviceName(npu, "Intel NPU"),
        details: npuDetails(npu),
      });
    }

    return cards;
  }

  function textElement(tag, className, text) {
    const el = document.createElement(tag);
    el.className = className;
    el.textContent = text;
    return el;
  }

  function createCard(model) {
    const card = document.createElement("article");
    card.className = "system-device-card";
    card.setAttribute("role", "listitem");
    card.title = joinDetails([model.label, model.tooltip || model.name, model.details], model.label);

    const heading = document.createElement("div");
    heading.className = "system-device-card__heading";
    const status = textElement("span", "system-device-card__status", "");
    status.setAttribute("aria-hidden", "true");
    heading.append(status, textElement("span", "system-device-card__label", model.label));

    card.append(
      heading,
      textElement("strong", "system-device-card__name", model.name),
      textElement("span", "system-device-card__details", model.details)
    );
    return card;
  }

  function render(container, capabilities) {
    if (!container) return;
    const cards = buildCardModels(capabilities).map(createCard);
    container.replaceChildren(...cards);
    container.hidden = cards.length === 0;
  }

  async function fetchCapabilities() {
    try {
      const resp = await fetch(CAPABILITIES_URL, { method: "GET" });
      if (!resp.ok) throw new Error("HTTP " + resp.status);
      return await resp.json();
    } catch (err) {
      console.debug("System capabilities unavailable:", err);
      return null;
    }
  }

  async function init() {
    const container = document.getElementById("systemCapabilityCards");
    if (!container) return;
    const capabilities = await fetchCapabilities();
    render(container, capabilities);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

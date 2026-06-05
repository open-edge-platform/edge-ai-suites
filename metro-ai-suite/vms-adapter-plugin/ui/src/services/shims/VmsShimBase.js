// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

/**
 * VmsShimBase — abstract base class for vendor-specific VMS shims.
 *
 * Each shim encapsulates all vendor-specific display logic:
 *   - vendor identifier and display label
 *   - CSS badge class
 *   - write-back capability flags (mirrors IVmsCommandShim on backend)
 *
 * This mirrors the backend's ShimFactory + IVmsShim / IVmsCommandShim pattern
 * but lives entirely in the UI layer — no direct VMS network calls from the browser.
 */
export class VmsShimBase {
  /** @type {string} vendor key matching Camera.vendor from backend */
  vendor = '';

  /** @type {string} human-readable vendor label */
  label = '';

  /** @type {string} Tailwind CSS class string for the vendor badge */
  badgeCls = 'vms-badge vms-badge-gray';

  /**
   * Returns write-back capability flags matching IVmsCommandShim implementation.
   *
   * @returns {{ push_label: boolean, set_bookmark: boolean, acknowledge_event: boolean, trigger_recording: boolean }}
   */
  getCapabilities() {
    return {
      push_label: false,
      set_bookmark: false,
      acknowledge_event: false,
      trigger_recording: false,
    };
  }

  /**
   * Strips the vendor prefix from a raw camera_id, returning the bare device identifier.
   * e.g. "frigate:front_door" → "front_door"
   *      "nx:550e8400-e29b-41d4-a716-446655440000" → "550e8400-..."
   *
   * @param {string} cameraId
   * @returns {string}
   */
  formatDeviceId(cameraId) {
    return cameraId;
  }
}

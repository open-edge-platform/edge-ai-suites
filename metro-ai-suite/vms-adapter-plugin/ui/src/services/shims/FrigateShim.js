// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { VmsShimBase } from './VmsShimBase';

/**
 * FrigateShim — UI shim for Frigate VMS.
 *
 * Capabilities mirror FrigateCommandShim in the backend:
 *   push_label        ✅  POST /api/events/{id}/sub_label
 *   set_bookmark      ❌  not supported
 *   acknowledge_event ❌  Frigate has no acknowledge concept
 *   trigger_recording ✅  POST /api/events/create (manual recording)
 */
export class FrigateShim extends VmsShimBase {
  vendor   = 'frigate';
  label    = 'Frigate';
  badgeCls = 'vms-badge vms-badge-teal';

  getCapabilities() {
    return {
      push_label:        true,
      set_bookmark:      false,
      acknowledge_event: false,
      trigger_recording: true,
    };
  }

  formatDeviceId(cameraId) {
    return cameraId.replace(/^frigate:/, '');
  }
}

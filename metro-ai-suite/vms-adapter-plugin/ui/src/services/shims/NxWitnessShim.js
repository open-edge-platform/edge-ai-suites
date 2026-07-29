// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { VmsShimBase } from './VmsShimBase';

/**
 * NxWitnessShim — UI shim for Nx Witness VMS.
 *
 * Capabilities mirror NxCommandShim in the backend (all write-back supported):
 *   push_label        ✅  PUT /rest/v4/devices/{id}/tags
 *   set_bookmark      ✅  POST /rest/v4/bookmarks
 *   acknowledge_event ✅  POST /rest/v4/events/{id}/acknowledge
 *   trigger_recording ✅  POST /rest/v4/devices/{id}/recording/start
 */
export class NxWitnessShim extends VmsShimBase {
  vendor   = 'nx_witness';
  label    = 'Nx Witness';
  badgeCls = 'vms-badge vms-badge-blue';

  getCapabilities() {
    return {
      push_label:        true,
      set_bookmark:      true,
      acknowledge_event: true,
      trigger_recording: true,
    };
  }

  formatDeviceId(cameraId) {
    return cameraId.replace(/^nx:/, '');
  }
}

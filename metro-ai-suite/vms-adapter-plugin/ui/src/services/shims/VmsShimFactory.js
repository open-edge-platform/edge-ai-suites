// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { FrigateShim } from './FrigateShim';
import { NxWitnessShim } from './NxWitnessShim';
import { VmsShimBase } from './VmsShimBase';

/** Singleton instances — created once and reused. */
const _instances = {
  frigate:    new FrigateShim(),
  nx_witness: new NxWitnessShim(),
};

/**
 * VmsShimFactory — mirrors the backend ShimFactory pattern in the UI layer.
 *
 * Usage:
 *   const shim = VmsShimFactory.create('frigate');
 *   shim.getSnapshotUrl(camera);      // proxied snapshot URL
 *   shim.getCapabilities();           // write-back capability flags
 *   shim.label;                       // "Frigate"
 *   shim.badgeCls;                    // "vms-badge vms-badge-teal"
 */
export class VmsShimFactory {
  /**
   * Returns the singleton shim for the given vendor.
   * Falls back to a generic VmsShimBase for unknown vendors.
   *
   * @param {string} vendor  — 'frigate' | 'nx_witness'
   * @returns {VmsShimBase}
   */
  static create(vendor) {
    return _instances[vendor] ?? new VmsShimBase();
  }

  /**
   * Returns all registered shims (useful for VMS status overview panels).
   * @returns {VmsShimBase[]}
   */
  static getAll() {
    return Object.values(_instances);
  }
}

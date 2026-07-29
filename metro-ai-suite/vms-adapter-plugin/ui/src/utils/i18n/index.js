// Copyright (C) 2025 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { enTranslations } from './translations/en';

/**
 * Returns the translated string for the given key.
 * Supports simple template interpolation: t('toastDiscoverSuccess', { count: 3 })
 * will replace {{count}} with 3.
 *
 * Falls back to the raw key if no translation is found.
 *
 * @param {string} key
 * @param {Record<string, string|number>} [vars]
 * @returns {string}
 */
export function t(key, vars) {
  const raw = enTranslations[key] ?? key;
  if (!vars) return raw;
  return raw.replace(/\{\{(\w+)\}\}/g, (_, name) => String(vars[name] ?? `{{${name}}}`));
}

/** All raw translations (for external lookups or testing). */
export { enTranslations };

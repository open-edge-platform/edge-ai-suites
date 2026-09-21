// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

import { defaultUrlTransform } from 'react-markdown';

const env = (import.meta as any).env ?? {};
const API_BASE_URL: string = (env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

/**
 * Point the report's own links at the backend that serves them.
 *
 * Report markdown carries image URLs like `/report/{session}/mindmap-image`,
 * written root-relative because the generator does not know what host will
 * render them. Left alone they resolve against the *frontend* origin — the Vite
 * dev server, or the Electron bundle — and 404, which is why the mind-map
 * section of a report comes out as a broken image.
 *
 * Shared by the report panel and the history's file preview: both render the
 * same markdown, so both need the same rewriting.
 */
export const reportUrlTransform = ((url: string) => {
  if (url.startsWith('data:image/')) return url;
  if (url.startsWith('/report/')) {
    return `${API_BASE_URL}${url}`;
  }
  return defaultUrlTransform(url);
}) as any;

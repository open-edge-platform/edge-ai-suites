// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// Camera RTSP URLs, remembered on this machine.
//
// The backend has nowhere to keep them: POST /project is typed by
// dto/project_settings.py, which declares only name/location/microphone, so any
// camera field sent along is dropped on the way in and reads back empty. They
// are per-machine wiring rather than project settings anyway, which is what
// localStorage is for.

const KEY = 'smart-classroom.cameras';

export interface CameraUrls {
  front: string;
  back: string;
  board: string;
}

export const EMPTY_CAMERAS: CameraUrls = { front: '', back: '', board: '' };

const asText = (value: unknown): string => (typeof value === 'string' ? value : '');

/** Never throws: storage is a convenience here, not a precondition for recording. */
export function readCameras(): CameraUrls {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...EMPTY_CAMERAS };
    const stored = JSON.parse(raw) as Partial<CameraUrls>;
    return {
      front: asText(stored?.front),
      back: asText(stored?.back),
      board: asText(stored?.board),
    };
  } catch {
    // Malformed JSON, or storage disabled/full (private windows, some kiosk
    // policies). Start from empty rather than break the page.
    return { ...EMPTY_CAMERAS };
  }
}

export function writeCameras(cameras: CameraUrls): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(cameras));
  } catch {
    // Same as above — the session still runs, it just will not be remembered.
  }
}

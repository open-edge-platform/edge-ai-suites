// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0

// The rules behind StartRecordingModal.

import type { CameraUrls } from './cameraStorage';

/** Everything a live session is started with. */
export interface RecordingSettings extends CameraUrls {
  microphone: string;
}

// /devices reports "audio=<name>", and ffmpeg is handed "audio={mic_device}"
// again when recording starts (components/ffmpeg/audio_preprocessing.py), so
// what is stored must be the bare name.
export const deviceName = (device: string) => device.replace(/^audio=/, '');

/**
 * The device to preselect. A saved name that no longer exists is dropped rather
 * than offered back, since recording would fail on a device ffmpeg cannot open.
 * Both sides are normalised: the saved value may carry the "audio=" prefix from
 * an older release that wrote it that way.
 */
export function pickMicrophone(devices: string[], saved: string): string {
  const names = devices.map(deviceName);
  const wanted = deviceName(saved || '').trim();
  if (wanted && names.includes(wanted)) return wanted;
  return names[0] ?? '';
}

/**
 * Whether there is anything to record with: one usable input is enough.
 *
 * The record button used to demand a microphone *and* a camera whenever both
 * features were built in, which made a lecture with no cameras unrecordable on
 * a machine that happened to ship video analytics. The two pipelines are
 * independent — audio transcription and camera analytics each run on their own —
 * so either alone is a valid session.
 */
export function canStartRecording(input: {
  hasAudioFeatures: boolean;
  hasVideoAnalyticsFeature: boolean;
  microphone: string;
  cameras: CameraUrls;
}): boolean {
  return usesMicrophone(input) || usesCameras(input);
}

/** Whether this session will record audio: the feature is on and a device is chosen. */
export function usesMicrophone(input: {
  hasAudioFeatures: boolean;
  microphone: string;
}): boolean {
  return input.hasAudioFeatures && !!input.microphone.trim();
}

/** Whether this session will run camera pipelines: the feature is on and a URL is set. */
export function usesCameras(input: {
  hasVideoAnalyticsFeature: boolean;
  cameras: CameraUrls;
}): boolean {
  return (
    input.hasVideoAnalyticsFeature &&
    !!(input.cameras.front.trim() || input.cameras.back.trim() || input.cameras.board.trim())
  );
}

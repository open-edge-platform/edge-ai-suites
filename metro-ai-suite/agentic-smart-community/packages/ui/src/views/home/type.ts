// SPDX-FileCopyrightText: (C) 2026 Intel Corporation
// SPDX-License-Identifier: Apache-2.0
export interface CameraReport {
  id: number;
  source_id: string;
  report_date: string;
  report_text: string;
  event_count: number;
  motion_count: number;
  prompt_tokens: number;
  image_tokens: number;
  completion_tokens: number;
  status: string;
  created_at: string;
}

export interface ActivityRecord {
  id: string;
  time: string;
  minutes: number;
  sortValue: number;
  title: string;
  camera: string;
  description: string;
  videoSrc: string;
  poster: string;
  date: string;
  isoDate: string;
  mediaType: "video" | "image";
  recordKind: "static" | "motion";
  statusLabel: string;
  durationLabel: string;
  durationSecondsLabel: string;
  timestampLabel: string;
  alertType: string | null;
  alertLabel: string;
}

export interface CameraTaskRecord {
  id: number;
  source_id: string;
  clip_start_time: string;
  clip_duration: number;
  clip_file_path: string;
  summary_text: string;
  status: string;
  created_at: string;
  event_type?: string;
  actual_alert: boolean;
  alert?: string | null;
  [key: string]: unknown;
}
